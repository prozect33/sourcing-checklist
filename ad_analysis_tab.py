# app/ad_analysis.py
from __future__ import annotations

import hashlib
import uuid
import json
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple, List

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import altair as alt

# ====== 원시 데이터 컬럼명(표준) ======
DATE_COL = "날짜"
KW_COL = "키워드"
SURF_COL = "광고 노출 지면"
SURF_SEARCH_VALUE = "검색 영역"
IMP_COL = "노출수"
CLK_COL = "클릭수"
COST_COL = "광고비"
ORD_COL = "총 주문수(14일)"
REV_COL = "총 전환매출액(14일)"
REQUIRED_COLS = [DATE_COL, KW_COL, SURF_COL, IMP_COL, CLK_COL, COST_COL, ORD_COL, REV_COL]

# ===================== 유틸 =====================
def _to_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0).round(0).astype(int)

def _to_date(s: pd.Series) -> pd.Series:
    txt = s.astype(str).str.strip()
    dt_general = pd.to_datetime(txt, errors="coerce")
    digits = txt.str.replace(r"[^0-9]", "", regex=True)
    dt_8 = pd.to_datetime(digits.where(digits.str.len() == 8), format="%Y%m%d", errors="coerce")
    dt_6 = pd.to_datetime(digits.where(digits.str.len() == 6), format="%y%m%d", errors="coerce")
    num = pd.to_numeric(txt, errors="coerce").where(lambda x: x.between(20000, 60000))
    dt_serial = pd.to_datetime(num, unit="D", origin="1899-12-30", errors="coerce")
    dt = dt_general.fillna(dt_8).fillna(dt_6).fillna(dt_serial)
    return dt.dt.date

def _safe_div(a: float | int, b: float | int, default: float = 0.0) -> float:
    a, b = float(a), float(b)
    return default if b == 0 else a / b

def _median_1d(s: pd.Series) -> float:
    return float(np.round(s.median(), 1)) if not s.empty else 0.0

# ============== 데이터 적재/정규화 ==============
def _load_df(upload) -> pd.DataFrame:
    try:
        if upload.name.lower().endswith(".csv"):
            df = pd.read_csv(upload)
        else:
            df = pd.read_excel(upload)
    except Exception as e:
        raise ValueError(f"파일 로드 실패: {e}")
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")
    return df

def _normalize(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()
    df["date"] = _to_date(df[DATE_COL])
    df = df[df["date"].notna()].copy()
    df["keyword"] = df[KW_COL].astype(str).fillna("")
    df["surface"] = df[SURF_COL].astype(str).fillna("").str.strip()
    df["impressions"] = _to_int(df[IMP_COL])
    df["clicks"] = _to_int(df[CLK_COL])
    df["cost"] = _to_int(df[COST_COL])
    df["orders_14d"] = _to_int(df[ORD_COL])
    df["revenue_14d"] = _to_int(df[REV_COL])
    return df

# ============== 집계/지표 ==============
def _aggregate_kw(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, int]]:
    if df.empty:
        return pd.DataFrame(), {"total_cost": 0, "total_rev": 0, "total_orders": 0}
    date_min, date_max = df["date"].min(), df["date"].max()
    totals = {
        "total_cost": int(df["cost"].sum()),
        "total_rev": int(df["revenue_14d"].sum()),
        "total_orders": int(df["orders_14d"].sum()),
        "date_min": date_min,
        "date_max": date_max,
    }
    df_imp_pos = df[df["impressions"] > 0]
    days = df_imp_pos.groupby("keyword")["date"].nunique().reset_index(name="active_days")
    kw = (
        df.groupby(["keyword", "surface"], as_index=False)[
            ["impressions", "clicks", "cost", "orders_14d", "revenue_14d"]
        ]
        .sum()
        .merge(days, on="keyword", how="left")
    )
    kw["active_days"] = kw["active_days"].fillna(0).astype(int)
    kw["ctr"] = (kw["clicks"] / kw["impressions"]).replace([np.inf, -np.inf], 0).fillna(0).round(6)
    kw["cpc"] = (kw["cost"] / kw["clicks"]).replace([np.inf, -np.inf], 0).fillna(0).round(2)
    kw["roas_14d"] = (kw["revenue_14d"] / kw["cost"] * 100).replace([np.inf, -np.inf], 0).fillna(0).round(2)
    return kw, totals

# ============== 컷 계산(자동) ==============
@dataclass(frozen=True)
class CpcCuts:
    bottom: float
    top: float

def _rolling_median(a: np.ndarray, win: int) -> np.ndarray:
    if win <= 1 or a.size < 3:
        return a
    s = pd.Series(a)
    w = int(win) if int(win) % 2 == 1 else int(win) + 1
    return s.rolling(window=w, center=True, min_periods=1).median().to_numpy()

def _robust_slope_knee(x: np.ndarray, y: np.ndarray, *, lo_q=0.05, hi_q=0.60, k=3.0):
    if x.size < 4:
        return None
    xmin, xmax = np.quantile(x, lo_q), np.quantile(x, hi_q)
    mask = (x >= xmin) & (x <= xmax)
    xs, ys = x[mask], y[mask]
    if xs.size < 3:
        return None
    dx = np.diff(xs); dy = np.diff(ys)
    slope = dy / (dx + 1e-12)
    med = np.median(slope); mad = np.median(np.abs(slope - med)) + 1e-12
    thr = med + k * mad
    idx = np.argmax(slope >= thr)
    if (slope >= thr).any():
        off = np.flatnonzero(mask)[0]
        return off + idx + 1
    return None

def _first_crossing(y: np.ndarray, thresh: float) -> int | None:
    hits = np.where(y >= thresh)[0]
    return int(hits[0]) if hits.size else None

def _compute_cpc_cuts(kw: pd.DataFrame) -> Tuple[CpcCuts, pd.DataFrame]:
    conv = kw[kw["orders_14d"] > 0].sort_values("cpc").copy()
    if conv.empty:
        return CpcCuts(0.0, 0.0), conv
    total_rev = float(conv["revenue_14d"].sum())
    conv["cum_rev"] = conv["revenue_14d"].cumsum()
    conv["cum_rev_share"] = (conv["cum_rev"] / (total_rev if total_rev > 0 else 1.0)).clip(0, 1)
    x = conv["cpc"].to_numpy(dtype=float)
    y = conv["cum_rev_share"].to_numpy(dtype=float)
    x_clip = np.clip(x, np.quantile(x, 0.01), np.quantile(x, 0.99))
    y_smooth = _rolling_median(y, win=max(3, int(len(y) * 0.07)))
    idx_bottom = _robust_slope_knee(x_clip, y_smooth, lo_q=0.05, hi_q=0.60, k=3.0)
    if idx_bottom is None:
        idx_bottom = _first_crossing(y_smooth, 0.10)
    if idx_bottom is None:
        hi = int(max(2, np.floor(len(x) * 0.60)))
        dx = np.diff(x_clip[:hi]); dy = np.diff(y_smooth[:hi])
        idx_bottom = int(np.argmax(dy / (dx + 1e-12)) + 1) if hi > 1 else 0
    bottom_cpc = float(x[max(0, min(idx_bottom, len(x) - 1))])
    x_n = (x_clip - x_clip.min()) / (x_clip.max() - x_clip.min() + 1e-12)
    y_n = (y_smooth - y_smooth.min()) / (y_smooth.max() - y_smooth.min() + 1e-12)
    idx_top = int(np.argmax(y_n - x_n))
    top_cpc = float(x[idx_top])
    if len(x) <= 3:
        bottom_cpc = float(x[0]); top_cpc = float(x[-1])
    return CpcCuts(bottom=bottom_cpc, top=top_cpc), conv

# ============== 비중 계산(분모=전체 채널) ==============
def _search_shares_for_cuts(kw: pd.DataFrame, cuts: CpcCuts) -> Dict[str, float]:
    """분모: 전체 채널(검색+비검색), 분자: 검색 영역 + 클릭>0 + CPC 조건."""
    kw_search_all = kw[kw["surface"] == SURF_SEARCH_VALUE].copy()
    kw_click = kw_search_all[kw_search_all["clicks"] > 0].copy()
    total_cost_all = float(kw["cost"].sum())
    total_rev_all = float(kw["revenue_14d"].sum())
    def _share(mask: pd.Series, col: str, denom: float) -> float:
        num = float(kw_click.loc[mask, col].sum())
        return round(_safe_div(num, denom, 0.0) * 100, 2)
    mask_bottom = kw_click["cpc"] <= cuts.bottom
    mask_top = kw_click["cpc"] >= cuts.top
    return {
        "rev_share_bottom": _share(mask_bottom, "revenue_14d", total_rev_all),
        "cost_share_bottom": _share(mask_bottom, "cost", total_cost_all),
        "rev_share_top": _share(mask_top, "revenue_14d", total_rev_all),
        "cost_share_top": _share(mask_top, "cost", total_cost_all),
    }

# ============== 제외 키워드 계산 ==============
def _aov_p50(conv: pd.DataFrame) -> float:
    orders = conv["orders_14d"]; rev = conv["revenue_14d"]
    valid = rev[orders > 0] / orders[orders > 0]
    return float(valid.quantile(0.5)) if not valid.empty else 0.0

def _compute_exclusions(
    kw: pd.DataFrame, cuts: CpcCuts, aov_p50_value: float, breakeven_roas: float
) -> Dict[str, pd.DataFrame]:
    ex_a = kw[(kw["orders_14d"] == 0) & (kw["cpc"] >= cuts.top)].copy()
    ex_b = kw[(kw["orders_14d"] == 0) & (kw["cpc"] <= cuts.bottom) & (kw["clicks"] >= 1)].copy()
    cpc_global_p50 = float(kw.loc[kw["clicks"] > 0, "cpc"].quantile(0.5)) if (kw["clicks"] > 0).any() else 0.0
    ex_c = kw[kw["orders_14d"] == 0].copy()
    ex_c["next_click_cost"] = np.where(ex_c["cpc"] > 0, ex_c["cpc"], cpc_global_p50)
    ex_c["cost_after_1click"] = ex_c["cost"] + ex_c["next_click_cost"]
    ex_c["roas_if_1_order"] = (
        (aov_p50_value / ex_c["cost_after_1click"] * 100).replace([np.inf, -np.inf], 0).fillna(0).round(2)
        if aov_p50_value > 0 else 0.0
    )
    ex_c = ex_c[ex_c["roas_if_1_order"] <= float(breakeven_roas)].copy()
    ex_d = kw[(kw["roas_14d"] > 0) & (kw["roas_14d"] < float(breakeven_roas))].copy()
    return {"a": ex_a, "b": ex_b, "c": ex_c, "d": ex_d}

# ============== 표시/편의 ==============
def _display_table(title: str, dff: pd.DataFrame, extra: Iterable[str] | None = None) -> None:
    cols = ["keyword","surface","active_days","impressions","clicks","cost","orders_14d","revenue_14d","ctr","cpc","roas_14d"]
    if extra: cols += list(extra)
    st.markdown(f"#### {title} ({len(dff)}개)")
    if dff.empty:
        return
    st.dataframe(dff.sort_values("cost", ascending=False)[cols].head(200), use_container_width=True, hide_index=True)

def _gather_exclusion_keywords(exclusions: Dict[str, pd.DataFrame]) -> List[str]:
    seq: List[str] = []
    for label in ["a", "b", "c", "d"]:
        df = exclusions.get(label, pd.DataFrame())
        if not df.empty:
            seq.extend(df["keyword"].astype(str).tolist())
    return list(dict.fromkeys(seq))

def _format_keywords_line_exact(words: Iterable[str]) -> str:
    return ",\u200b".join([w for w in words])

def _copy_to_clipboard_button(label: str, text: str, key: str) -> None:
    """왜: 한 번에 전달."""
    payload = json.dumps(text)
    html = f"""
    <div style="display:flex;align-items:center;gap:8px;">
      <button id="copybtn-{key}" role="button" aria-label="{label}"
        style="
          display:inline-flex;align-items:center;justify-content:center;
          padding:8px 12px;font-size:14px;line-height:1.25;
          border:1px solid rgba(49,51,63,0.2);border-radius:8px;background:#ffffff;cursor:pointer;
          box-shadow: 0 1px 2px rgba(0,0,0,0.04);transition: transform .02s, box-shadow .15s, background .15s;">
        {label}
      </button>
      <span id="copystat-{key}" style="font-size:13px;color:#4CAF50;"></span>
    </div>
    <script>
      const txt_{key} = {payload};
      const btn_{key} = document.getElementById("copybtn-{key}");
      const stat_{key} = document.getElementById("copystat-{key}");
      btn_{key}.onmouseenter = () => {{ btn_{key}.style.boxShadow = "0 2px 6px rgba(0,0,0,0.08)"; }};
      btn_{key}.onmouseleave = () => {{ btn_{key}.style.boxShadow = "0 1px 2px rgba(0,0,0,0.04)"; }};
      btn_{key}.onmousedown = () => {{ btn_{key}.style.transform = "scale(0.99)"; }};
      btn_{key}.onmouseup = () => {{ btn_{key}.style.transform = "scale(1)"; }};
      btn_{key}.onclick = async () => {{
        try {{
          await navigator.clipboard.writeText(txt_{key});
          stat_{key}.textContent = "복사됨";
        }} catch (e) {{
          const area = document.createElement('textarea');
          area.value = txt_{key};
          area.style.position = 'fixed'; area.style.top = '-1000px';
          document.body.appendChild(area); area.focus(); area.select(); document.execCommand('copy');
          document.body.removeChild(area); stat_{key}.textContent = "복사됨";
        }}
        setTimeout(()=> stat_{key}.textContent = "", 2000);
      }};
    </script>
    """
    components.html(html, height=56)

def _render_exclusion_union(exclusions: Dict[str, pd.DataFrame]) -> None:
    st.markdown("### 4) 제외 키워드 (통합 · 한바구니 · 중복 제거)")
    all_words = _gather_exclusion_keywords(exclusions)
    total = len(all_words)
    if total == 0:
        return
    line = _format_keywords_line_exact(all_words)
    _copy_to_clipboard_button(f"[복사하기] 총{total}개", line, key="ex_union_copy")

# ============== 저장 로직 ==============
def _save_to_supabase(
    supabase,
    *,
    upload,
    product_name: str,
    note: str,
    totals: Dict,
    breakeven_roas: float,
    cuts: CpcCuts,
    shares: Dict[str, float],
    aov_p50_value: float,
    kw: pd.DataFrame,
    exclusions: Dict[str, pd.DataFrame],
) -> None:
    run_id = str(uuid.uuid4())
    file_sha1 = hashlib.sha1(upload.getvalue()).hexdigest()
    st.caption(f"파일 해시: {file_sha1[:12]}…")  # 왜: 이력 추적
    supabase.table("ad_analysis_runs").insert(
        {
            "run_id": run_id,
            "product_name": product_name.strip(),
            "source_filename": upload.name,
            "source_rows": int(len(kw)),
            "date_min": str(totals.get("date_min")),
            "date_max": str(totals.get("date_max")),
            "note": note,
            "breakeven_roas": float(breakeven_roas),
            "cpc_cut": float(round(cuts.top, 2)),
        }
    ).execute()
    rows_kw = kw.assign(run_id=run_id)[
        ["run_id","keyword","surface","active_days","impressions","clicks","cost","orders_14d","revenue_14d","ctr","cpc","roas_14d"]
    ].to_dict(orient="records")
    for i in range(0, len(rows_kw), 1000):
        supabase.table("ad_analysis_keyword_total").upsert(rows_kw[i : i + 1000]).execute()
    artifacts = [
        {
            "run_id": run_id,
            "artifact_key": "settings",
            "payload": {
                "breakeven_roas": float(breakeven_roas),
                "cpc_cut_top": float(round(cuts.top, 2)),
                "cpc_cut_bottom": float(round(cuts.bottom, 2)),
                "top_rev_share": float(shares.get("rev_share_top", 0.0)),
                "bottom_rev_share": float(shares.get("rev_share_bottom", 0.0)),
                "aov_p50": float(aov_p50_value),
            },
        },
        {
            "run_id": run_id,
            "artifact_key": "exclusions",
            "payload": {
                "a": exclusions["a"]["keyword"].tolist(),
                "b": exclusions["b"]["keyword"].tolist(),
                "c": exclusions["c"]["keyword"].tolist(),
                "d": exclusions["d"]["keyword"].tolist(),
            },
        },
    ]
    supabase.table("ad_analysis_artifacts").upsert(artifacts).execute()
    st.success(f"저장 성공 (ID: {run_id})")

# ============== 상호작용: 자동 + 수동 오버라이드 ==============
def _snap_to_nearest(values: np.ndarray, v: float) -> float:
    """왜: 사람이 움직일 때 실제 포인트에 맞추면 해석 용이."""
    if values.size == 0:
        return float(v)
    idx = int(np.argmin(np.abs(values - v)))
    return float(values[idx])

# ============== Streamlit 탭 ==============
def render_ad_analysis_tab(supabase):
    st.subheader("광고분석 (총 14일 기준)")
    up = st.file_uploader("로우데이터 업로드 (xlsx/csv)", type=["xlsx", "csv"], key="ad_up")

    breakeven_roas = st.number_input("손익분기 ROAS", min_value=0.0, value=0.0, step=10.0, key="ad_be")

    run = st.button("🔍 분석하기", key="ad_run", use_container_width=True)
    if not run:
        return

    if up is None:
        st.error("파일을 업로드하세요.")
        return

    try:
        df_raw = _load_df(up)
        df = _normalize(df_raw)
    except ValueError as e:
        st.error(str(e)); return
    if df.empty:
        st.error("유효한 데이터가 없습니다."); return

    kw, totals = _aggregate_kw(df)

    st.markdown("### 1) 기본 성과 지표")
    st.caption(f"기간: {totals['date_min']} ~ {totals['date_max']}")
    total_cost = totals["total_cost"]; total_rev = totals["total_rev"]; total_orders = totals["total_orders"]
    def _row(name: str, sub: pd.DataFrame) -> Dict[str, float | int | str]:
        c, r, o = int(sub["cost"].sum()), int(sub["revenue_14d"].sum()), int(sub["orders_14d"].sum())
        return {
            "영역": name, "광고비": c,
            "광고비비율(%)": round(_safe_div(c, total_cost) * 100, 2),
            "매출": r, "매출비율(%)": round(_safe_div(r, total_rev) * 100, 2),
            "주문": o, "주문비율(%)": round(_safe_div(o, total_orders) * 100, 2),
            "ROAS": round(_safe_div(r, c) * 100, 2),
        }
    rows = [
        _row("전체", df),
        _row("검색", df[df["surface"] == SURF_SEARCH_VALUE]),
        _row("비검색", df[df["surface"] != SURF_SEARCH_VALUE]),
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("### 2) CPC-누적매출 비중 & 컷")
    cuts_auto, conv = _compute_cpc_cuts(kw)
    if conv.empty:
        shares = {"rev_share_bottom": 0.0, "cost_share_bottom": 0.0, "rev_share_top": 0.0, "cost_share_top": 0.0}
        aov50 = 0.0
        st.caption("전환 발생 키워드가 없어 컷은 0으로 처리됩니다.")
    else:
        # ----- 수동 오버라이드 UI -----
        cpc_vals = conv["cpc"].to_numpy(dtype=float)
        cpc_min, cpc_max = float(np.nanmin(cpc_vals)), float(np.nanmax(cpc_vals))
        st.caption("비중 분모: 전체 채널(검색+비검색), 분자: 검색 영역(클릭>0) 중 CPC 조건 충족 키워드 합")
        with st.expander("⚙️ 컷 설정", expanded=False):
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                manual = st.toggle("수동으로 조정", value=False, help="끄면 자동 컷 사용")
            with c2:
                snap = st.checkbox("포인트에 스냅", value=True, help="실제 CPC 값으로 자동 맞춤")
            with c3:
                if st.button("자동값으로 리셋"):
                    st.session_state["bottom_manual"] = cuts_auto.bottom
                    st.session_state["top_manual"] = cuts_auto.top
            # 초기 상태 보장
            st.session_state.setdefault("bottom_manual", cuts_auto.bottom)
            st.session_state.setdefault("top_manual", cuts_auto.top)
            # 슬라이더
            b = st.slider(
                "bottom (≤)", min_value=float(cpc_min), max_value=float(cpc_max),
                value=float(st.session_state["bottom_manual"]), step=0.01, key="bottom_slider"
            )
            t = st.slider(
                "top (≥)", min_value=float(cpc_min), max_value=float(cpc_max),
                value=float(st.session_state["top_manual"]), step=0.01, key="top_slider"
            )
            # 제약조건: bottom < top
            if b >= t:
                # why: 시각적으로 겹치면 top을 한 칸 올림
                t = min(cpc_max, b + max(0.01, (cpc_max - cpc_min) * 0.001))
            if snap:
                b = _snap_to_nearest(cpc_vals, b)
                t = _snap_to_nearest(cpc_vals, t)
            st.session_state["bottom_manual"] = b
            st.session_state["top_manual"] = t

        # 실제 사용할 컷
        cuts_use = CpcCuts(
            bottom=float(st.session_state["bottom_manual"]) if 'manual' in locals() and manual else cuts_auto.bottom,
            top=float(st.session_state["top_manual"]) if 'manual' in locals() and manual else cuts_auto.top,
        )

        # 차트 (선 + 가이드 라인)
        chart = alt.Chart(conv).mark_line().encode(x=alt.X("cpc:Q"), y=alt.Y("cum_rev_share:Q"))
        vline_bottom = alt.Chart(pd.DataFrame({"c": [cuts_use.bottom]})).mark_rule(strokeDash=[2, 2]).encode(x="c:Q")
        vline_top = alt.Chart(pd.DataFrame({"c": [cuts_use.top]})).mark_rule(strokeDash=[6, 4]).encode(x="c:Q")
        st.altair_chart(chart + vline_bottom + vline_top, use_container_width=True)

        # 지표 재계산
        shares = _search_shares_for_cuts(kw, cuts_use)
        aov50 = _aov_p50(conv)

        # 표시 블록
        st.markdown(
            f"""
- **CPC_cut bottom:** {round(cuts_use.bottom, 2)}원  
  · 검색 광고 매출 비중 {shares['rev_share_bottom']}%  
  · 검색 광고 광고비 비중 {shares['cost_share_bottom']}%

- **CPC_cut top:** {round(cuts_use.top, 2)}원  
  · 검색 광고 매출 비중 {shares['rev_share_top']}%  
  · 검색 광고 광고비 비중 {shares['cost_share_top']}%
"""
        )

    st.markdown("### 3) 제외 키워드")
    exclusions = _compute_exclusions(kw, cuts_use if not conv.empty else CpcCuts(0.0, 0.0), aov50, float(breakeven_roas))
    _display_table("a) CPC_cut top 이상 전환 0", exclusions["a"])
    _display_table("b) CPC_cut bottom 이하 전환 0", exclusions["b"])
    _display_table("c) 전환 시 손익 ROAS 미달", exclusions["c"], extra=["roas_if_1_order"])
    _display_table("d) 손익 ROAS 미달", exclusions["d"])

    _render_exclusion_union(exclusions)

    with st.expander("💾 저장 (선택)", expanded=False):
        c1, c2 = st.columns([2, 3])
        with c1: product_name = st.text_input("상품명", value="", key="ad_product")
        with c2: note = st.text_input("메모", value="", key="ad_note")
        can_save = bool(product_name.strip())
        save_btn = st.button("✅ 분석 결과 저장", disabled=not can_save, key="ad_save")
        if save_btn and can_save:
            try:
                _save_to_supabase(
                    supabase,
                    upload=up,
                    product_name=product_name,
                    note=note,
                    totals=totals,
                    breakeven_roas=float(breakeven_roas),
                    cuts=cuts_use if not conv.empty else CpcCuts(0.0, 0.0),
                    shares=shares,
                    aov_p50_value=aov50,
                    kw=kw,
                    exclusions=exclusions,
                )
            except Exception as e:
                st.error(f"저장 실패: {e}")
