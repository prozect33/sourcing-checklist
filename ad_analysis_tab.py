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

# ====== 표준 컬럼명 ======
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

# ====== 탐지 파라미터(팀 고정) ======
SMOOTH_DIVISOR = 70        # 창 = round(N / 50), 최소 7, 홀수  (완만 구간 보존 위해 60→50으로 다소 강하게)
LOW_Q = 0.65               # 양의 기울기 하위 25% 이상을 오르막으로 간주(완만 포함)
LOW_Q_FALLBACK = 0.55      # 데이터 약할 때 완화
GAP_TOL_DIVISOR = 180      # 빈틈 메움 허용 폭 = ceil(N / 100) 포인트
MIN_RUN_FRAC = 0.04        # 최소 지속 길이 비율(스파이크 방지)
FLOOR_Q = 0.22          # ← 새로 추가
BACK_CAP_FRAC = 0.35    # ← 새로 추가

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

def _moving_average(y: np.ndarray, window: int) -> np.ndarray:
    """왜: 장기 흐름 추출(초반 완만 구간 보존 목적)."""
    window = max(7, int(window))
    if window % 2 == 0:
        window += 1
    pad = window // 2
    ypad = np.pad(y, (pad, pad), mode="edge")
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(ypad, kernel, mode="valid")

def _fill_small_gaps(mask: np.ndarray, max_gap: int) -> np.ndarray:
    """왜: 노이즈가 만든 짧은 0 구간을 메워 '긴 오르막' 유지."""
    if max_gap <= 0:
        return mask
    out = mask.copy()
    i = 0
    n = len(mask)
    while i < n:
        if not out[i]:
            j = i
            while j < n and not out[j]:
                j += 1
            gap_len = j - i
            if 0 < gap_len <= max_gap:
                out[i:j] = True
            i = j
        else:
            i += 1
    return out

def _longest_true_run_by_x(mask: np.ndarray, x: np.ndarray) -> tuple[int, int]:
    """True 구간 중 x-길이(end_x - start_x)가 최대인 [s,e] 반환. 없으면 (-1,-1)."""
    best_span, best_s, cur_s = 0.0, -1, -1
    for i, v in enumerate(mask):
        if v and cur_s == -1:
            cur_s = i
        if (not v or i == len(mask) - 1) and cur_s != -1:
            e = i if not v else i  # v==False면 i-1이 끝이지만 span 계산엔 무관
            span = float(x[e] - x[cur_s])
            if span > best_span:
                best_span, best_s = span, cur_s
            cur_s = -1
    if best_s == -1:
        return -1, -1
    # 끝 인덱스 재탐색
    e = best_s
    while e + 1 < len(mask) and mask[e + 1]:
        e += 1
    return best_s, e

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

@dataclass(frozen=True)
class CpcCuts:
    bottom: float
    top: float

def _compute_cpc_cuts(kw: pd.DataFrame) -> Tuple[CpcCuts, pd.DataFrame]:
    """
    bottom: **가장 긴 오르막(x-길이 최대)의 시작점**(저임계+틈 메움)
    top   : 정규화 후 y_n - x_n 최대 지점(기존)
    """
    conv = kw[kw["orders_14d"] > 0].sort_values("cpc").copy()
    if conv.empty:
        return CpcCuts(0.0, 0.0), conv

    total_conv_rev = float(conv["revenue_14d"].sum())
    conv["cum_rev"] = conv["revenue_14d"].cumsum()
    conv["cum_rev_share"] = (conv["cum_rev"] / (total_conv_rev if total_conv_rev > 0 else 1.0)).clip(0, 1)

    x = conv["cpc"].to_numpy(dtype=float)
    y = conv["cum_rev_share"].to_numpy(dtype=float)
    n = len(x)
    if n < 4:
        return CpcCuts(bottom=float(x[0]), top=float(x[-1])), conv

    # ----- top (기존 방식 유지) -----
    x_n = (x - x.min()) / (x.max() - x.min() + 1e-12)
    y_n = (y - y.min()) / (y.max() - y.min() + 1e-12)
    idx_top = int(np.argmax(y_n - x_n))

    # ----- bottom (Hysteresis: high-threshold run -> extend left by low-threshold) -----
    n = len(x)
    smooth_win = max(7, int(round(n / SMOOTH_DIVISOR)))
    if smooth_win % 2 == 0:
        smooth_win += 1
    y_s = _moving_average(y, smooth_win)
    slope = np.gradient(y_s, x)

    pos = slope[slope > 0]
    if pos.size == 0 or not np.any(np.isfinite(pos)):
        idx_bottom = 0
    else:
        # 1) 높은 임계(high)로 "가파른 구간"을 먼저 찾는다
        high_thr = float(np.quantile(pos, LOW_Q))               # e.g. 0.60~0.70
        mask_high = slope >= high_thr
        gap_tol = max(1, int(np.ceil(n / GAP_TOL_DIVISOR)))
        mask_high = _fill_small_gaps(mask_high, gap_tol)
        s_high, e_high = _longest_true_run_by_x(mask_high, x)

        if s_high == -1:
            # 가파른 구간 자체가 없으면 완화
            high_thr = float(np.quantile(pos, LOW_Q_FALLBACK))
            mask_high = slope >= high_thr
            mask_high = _fill_small_gaps(mask_high, gap_tol)
            s_high, e_high = _longest_true_run_by_x(mask_high, x)

        if s_high == -1:
            idx_bottom = 0
        else:
            # 2) 낮은 임계(low_back)로 같은 "덩어리"를 왼쪽으로 확장(언덕 '발' 포착)
            #    high보다 0.20~0.30 분위수 낮게 두는 게 안정적
            low_back_q = max(0.15, min(float(LOW_Q) - 0.25, 0.45))  # 예: LOW_Q=0.65 -> 0.40
            low_thr = float(np.quantile(pos, low_back_q))
            mask_low = slope >= low_thr
            mask_low = _fill_small_gaps(mask_low, gap_tol)

            # high 구간(s_high~e_high)을 포함하는 low 구간의 '시작'으로 backtrack
            s = s_high
            while s - 1 >= 0 and mask_low[s - 1]:
                s -= 1
            # ---- Guardrails: floor & back-cap ----
            # 1) 바닥 잠금: x-quantile(FLOOR_Q)보다 왼쪽 금지
            floor_x = float(np.quantile(x, FLOOR_Q))
            floor_idx = int(np.searchsorted(x, floor_x, side="left"))

            # 2) 확장 상한: high구간 시작점에서 전체 span의 BACK_CAP_FRAC만큼만 왼쪽 허용
            x_span = float(x[-1] - x[0])
            cap_x = float(x[s_high]) - BACK_CAP_FRAC * x_span
            cap_idx = int(np.searchsorted(x, max(cap_x, x[0]), side="left"))

            # 오른쪽으로 최소 보정
            s = max(s, floor_idx, cap_idx)    

            # 최소 지속 길이 보정(너무 짧은 스파이크 방지)
            min_run = max(2, int(np.ceil(n * MIN_RUN_FRAC)))
            e = s
            while e + 1 < len(mask_low) and mask_low[e + 1]:
                e += 1
            if (e - s + 1) < min_run:
                e = min(n - 1, s + min_run - 1)

            idx_bottom = int(s)

    cuts = CpcCuts(bottom=float(x[idx_bottom]), top=float(x[idx_top]))
    return cuts, conv

def _search_shares_for_cuts(kw: pd.DataFrame, cuts: CpcCuts) -> Dict[str, float]:
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
        style="display:inline-flex;align-items:center;justify-content:center;padding:8px 12px;font-size:14px;line-height:1.25;border:1px solid rgba(49,51,63,0.2);border-radius:8px;background:#ffffff;cursor:pointer;box-shadow: 0 1px 2px rgba(0,0,0,0.04);transition: transform .02s, box-shadow .15s, background .15s;">
        {label}
      </button>
      <span id="copystat-{key}" style="font-size:13px;color:#4CAF50;"></span>
    </div>
    <script>
      const txt_{key} = {payload};
      const btn_{key} = document.getElementById("copybtn-{key}");
      const stat_{key} = document.getElementById("copystat-{key}");
      btn_{key}.onclick = async () => {{
        try {{ await navigator.clipboard.writeText(txt_{key}); stat_{key}.textContent = "복사됨"; }}
        catch (e) {{
          const area = document.createElement('textarea');
          area.value = txt_{key}; area.style.position = 'fixed'; area.style.top = '-1000px';
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
    st.caption(f"파일 해시: {file_sha1[:12]}…")
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

# ============== Streamlit 탭 ==============
def render_ad_analysis_tab(supabase):
    st.subheader("광고분석 (총 14일 기준)")
    up = st.file_uploader("로우데이터 업로드 (xlsx/csv)", type=["xlsx", "csv"], key="ad_up")
    breakeven_roas = st.number_input("손익분기 ROAS", min_value=0.0, value=0.0, step=10.0, key="ad_be")

    run = st.button("🔍 분석하기", key="ad_run", use_container_width=True)
    if not run:
        return
    if up is None:
        st.error("파일을 업로드하세요."); return

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
    cuts, conv = _compute_cpc_cuts(kw)
    if conv.empty:
        shares = {"rev_share_bottom": 0.0, "cost_share_bottom": 0.0, "rev_share_top": 0.0, "cost_share_top": 0.0}
        aov50 = 0.0
        st.caption("전환 발생 키워드가 없어 컷은 0으로 처리됩니다.")
    else:
        chart = alt.Chart(conv).mark_line().encode(x="cpc:Q", y="cum_rev_share:Q")
        vline_bottom = alt.Chart(pd.DataFrame({"c": [cuts.bottom]})).mark_rule(strokeDash=[2, 2]).encode(x="c:Q")
        vline_top = alt.Chart(pd.DataFrame({"c": [cuts.top]})).mark_rule(strokeDash=[6, 4]).encode(x="c:Q")
        st.altair_chart(chart + vline_bottom + vline_top, use_container_width=True)
        shares = _search_shares_for_cuts(kw, cuts)
        aov50 = _aov_p50(conv)

        st.caption("비중 분모: 전체 채널(검색+비검색), 분자: 검색 영역(클릭>0) 중 CPC 조건 충족 키워드 합")

        st.markdown(
            f"""
- **CPC_cut bottom:** {round(cuts.bottom, 2)}원  
  · 검색 광고 매출 비중 {shares['rev_share_bottom']}%  
  · 검색 광고 광고비 비중 {shares['cost_share_bottom']}%

- **CPC_cut top:** {round(cuts.top, 2)}원  
  · 검색 광고 매출 비중 {shares['rev_share_top']}%  
  · 검색 광고 광고비 비중 {shares['cost_share_top']}%
"""
        )

    st.markdown("### 3) 제외 키워드")
    exclusions = _compute_exclusions(kw, cuts, aov50, float(breakeven_roas))
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
                    cuts=cuts,
                    shares=shares,
                    aov_p50_value=aov50,
                    kw=kw,
                    exclusions=exclusions,
                )
            except Exception as e:
                st.error(f"저장 실패: {e}")
