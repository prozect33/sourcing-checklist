# app/ad_analysis_tab.py
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# ===================== 설정/상수 =====================
SUPABASE_TABLE = "exclusion_keywords"

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

def _moving_average(y: np.ndarray, window: int) -> np.ndarray:
    window = max(7, int(window))
    if window % 2 == 0:
        window += 1
    pad = window // 2
    ypad = np.pad(y, (pad, pad), mode="edge")
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(ypad, kernel, mode="valid")

def _longest_true_run_by_x(mask: np.ndarray, x: np.ndarray) -> tuple[int, int]:
    best_span, best_s, cur_s = 0.0, -1, -1
    for i, v in enumerate(mask):
        if v and cur_s == -1:
            cur_s = i
        if (not v or i == len(mask) - 1) and cur_s != -1:
            e = i if not v else i
            span = float(x[e] - x[cur_s])
            if span > best_span:
                best_span, best_s = span, cur_s
            cur_s = -1
    if best_s == -1:
        return -1, -1
    e = best_s
    while e + 1 < len(mask) and mask[e + 1]:
        e += 1
    return best_s, e

def _quantile_x(x: np.ndarray, q: float) -> float:
    return float(np.quantile(x, float(np.clip(q, 0.0, 1.0))))

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
    # ASCII 콤마 제거(줄바꿈 분리와 충돌 방지)
    df["keyword"] = df[KW_COL].astype(str).str.replace(",", "", regex=False)
    df["surface"] = df[SURF_COL].astype(str).fillna("").str.strip()
    df["impressions"] = _to_int(df[IMP_COL])
    df["clicks"] = _to_int(df[CLK_COL])
    df["cost"] = _to_int(df[COST_COL])
    df["orders_14d"] = _to_int(df[ORD_COL])
    df["revenue_14d"] = _to_int(df[REV_COL])
    return df

# ===================== 집계/지표 =====================
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

# ===================== 컷 구조체 =====================
@dataclass(frozen=True)
class CpcCuts:
    bottom: float
    top: float

# ===================== 지표/표시 =====================
def _search_shares_for_cuts(kw: pd.DataFrame, cuts: CpcCuts) -> Dict[str, float]:
    total_cost_all = float(kw["cost"].sum())
    total_rev_all = float(kw["revenue_14d"].sum())

    kw_search_all = kw[kw["surface"] == SURF_SEARCH_VALUE]
    total_cost_search = float(kw_search_all["cost"].sum())
    total_rev_search = float(kw_search_all["revenue_14d"].sum())

    if (total_cost_all <= 0 and total_rev_all <= 0) or kw_search_all.empty:
        return {k: 0.0 for k in [
            "cost_share_bottom","rev_share_bottom","cost_share_top","rev_share_top",
            "cost_share_bottom_search","rev_share_bottom_search",
            "cost_share_top_search","rev_share_top_search"
        ]}

    base = kw[(kw["surface"] == SURF_SEARCH_VALUE) & (kw["clicks"] > 0)].copy()

    if "cpc" not in base.columns or base["cpc"].isna().any():
        base["cpc"] = base["cost"] / base["clicks"]

    # ===== bottom : 정방향 누적 =====
    base_asc = base.sort_values("cpc", ascending=True)
    m_bottom = base_asc["cpc"] <= float(cuts.bottom)

    cost_le_bottom = float(base_asc.loc[m_bottom, "cost"].sum())
    rev_le_bottom  = float(base_asc.loc[m_bottom, "revenue_14d"].sum())

    # ===== top : 역방향 누적 =====
    base_desc = base.sort_values("cpc", ascending=False)
    m_top = base_desc["cpc"] >= float(cuts.top)

    cost_ge_top = float(base_desc.loc[m_top, "cost"].sum())
    rev_ge_top  = float(base_desc.loc[m_top, "revenue_14d"].sum())


    def _pct(num: float, den: float) -> float:
        return round(_safe_div(num, den, 0.0) * 100, 2)

    return {
        "cost_share_bottom": _pct(cost_le_bottom, total_cost_all),
        "rev_share_bottom":  _pct(rev_le_bottom,  total_rev_all),
        "cost_share_top":    _pct(cost_ge_top,    total_cost_all),
        "rev_share_top":     _pct(rev_ge_top,     total_rev_all),
        "cost_share_bottom_search": _pct(cost_le_bottom, total_cost_search),
        "rev_share_bottom_search":  _pct(rev_le_bottom,  total_rev_search),
        "cost_share_top_search":    _pct(cost_ge_top,     total_cost_search),
        "rev_share_top_search":     _pct(rev_ge_top,      total_rev_search),
    }

def _display_table(title: str, dff: pd.DataFrame, extra: Iterable[str] | None = None) -> None:
    cols = [
        "keyword","surface","active_days","impressions","clicks","cost",
        "orders_14d","revenue_14d","ctr","cpc","roas_14d",
    ]
    if dff.empty:
        st.markdown(f"#### {title} (0개)")
        return
    if extra:
        cols += list(extra)
    st.markdown(f"#### {title} ({len(dff)}개)")
    st.dataframe(dff.sort_values("cost", ascending=False)[cols].head(200),
                 use_container_width=True, hide_index=True)

def _gather_exclusion_keywords(exclusions: Dict[str, pd.DataFrame]) -> List[str]:
    seq: List[str] = []
    for label in ["a", "b", "c", "d"]:
        df = exclusions.get(label, pd.DataFrame())
        if not df.empty:
            seq.extend(df["keyword"].astype(str).tolist())
    return list(dict.fromkeys(seq))

# ===== 키워드 분리/병합 =====
def _split_keywords(text: str) -> list[str]:
    if not text:
        return []
    parts = [p.strip() for p in str(text).split("\n")]
    return [p for p in parts if p != ""]

def _merge_keywords(current: list[str], previous: list[str]) -> list[str]:
    seen, merged = set(), []
    for w in current + previous:
        if w not in seen:
            seen.add(w); merged.append(w)
    return merged

def _format_keywords_line_storage(words: list[str]) -> str:
    cleaned = [w.strip() for w in words]
    return "\n".join([w for w in cleaned if w != ""])

# ===================== 복사 UI(내용 숨김, 제스처 기반) =====================
def _copy_button_hidden(text: str, key: str) -> None:
    """사용자 제스처 후 복사. 브라우저 보안 대비."""
    safe = html.escape(text or "")
    safe_js = safe.replace("\r", "").replace("\n", "\\n")
    components.html(
        f"""
        <div style="margin:6px 0;">
          <button id="btn-{key}" style="padding:6px 10px;border:1px solid #ccc;border-radius:8px;cursor:pointer;">
            복사
          </button>
          <span id="msg-{key}" style="font-size:13px;color:#4CAF50;margin-left:8px;"></span>
        </div>
        <script>
          const hidden_{key} = "{safe_js}"
            .replaceAll("&amp;","&").replaceAll("&lt;","<")
            .replaceAll("&gt;",">").replaceAll("&quot;","\\\"");
          const btn = document.getElementById("btn-{key}");
          const msg = document.getElementById("msg-{key}");
          btn.onclick = async () => {{
            try {{
              await navigator.clipboard.writeText(hidden_{key});
              msg.textContent = "복사됨";
            }} catch (e) {{
              try {{
                const ta = document.createElement('textarea');
                ta.value = hidden_{key};
                ta.style.position='fixed'; ta.style.top='-9999px';
                document.body.appendChild(ta); ta.focus(); ta.select(); document.execCommand('copy');
                document.body.removeChild(ta);
                msg.textContent = "복사됨";
              }} catch (e2) {{
                msg.textContent = "복사 실패";
              }}
            }}
            setTimeout(()=> msg.textContent = "", 2000);
          }};
        </script>
        """,
        height=40,
    )

# ===================== Supabase I/O =====================
def _supabase_rows(res: Any) -> List[Dict]:
    data = getattr(res, "data", None)
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    js = getattr(res, "json", None)
    if isinstance(js, dict) and isinstance(js.get("data"), list):
        return [r for r in js["data"] if isinstance(r, dict)]
    if isinstance(res, dict) and isinstance(res.get("data"), list):
        return [r for r in res["data"] if isinstance(r, dict)]
    if isinstance(res, list):
        return [r for r in res if isinstance(r, dict)]
    return []

def _save_or_update_merged(supabase: Any, product_name: str, current_words: List[str]) -> tuple[bool, str, str, int]:
    if supabase is None:
        return False, "supabase 클라이언트가 없습니다.", "", 0
    try:
        sel = (
            supabase.table(SUPABASE_TABLE)
            .select("id,product_name,keywords")
            .eq("product_name", product_name)
            .limit(1)
            .execute()
        )
        rows = _supabase_rows(sel)
        prev_words: List[str] = _split_keywords((rows[0].get("keywords", "") if rows else ""))

        merged_words = _merge_keywords(current_words, prev_words)
        merged_line = _format_keywords_line_storage(merged_words)
        merged_count = len(merged_words)

        kst = timezone(timedelta(hours=9))
        saved_at = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S%z")
        payload = {"product_name": product_name, "saved_at": saved_at, "keywords": merged_line, "count": merged_count}

        if rows:
            upd = supabase.table(SUPABASE_TABLE).update(payload).eq("product_name", product_name).execute()
            if hasattr(upd, "error") and upd.error:
                return False, str(upd.error), "", 0
        else:
            ins = supabase.table(SUPABASE_TABLE).insert(payload).execute()
            if hasattr(ins, "error") and ins.error:
                return False, str(ins.error), "", 0

        return True, "저장 및 병합 완료", merged_line, merged_count
    except Exception as e:
        return False, f"저장/병합 실패: {e}", "", 0

# ===================== 4) 저장/병합/복사 =====================
def _render_exclusion_union(exclusions: Dict[str, pd.DataFrame], supabase: Any | None) -> None:
    all_words = _gather_exclusion_keywords(exclusions)
    if not all_words:
        return

    current_words = [w for w in all_words if w]
    product_name = st.text_input("상품명(필수)", key="ex_prod_name", placeholder="")

    do_merge_copy = st.button("저장 및 병합 복사", key="ex_union_merge_copy", disabled=(not product_name.strip()))
    if do_merge_copy:
        ok, msg, merged_line, merged_count = _save_or_update_merged(supabase, product_name.strip(), current_words)
        if ok:
            st.success(f"[{product_name}] {msg}({merged_count})")
            _copy_button_hidden(merged_line, key="merged_clip_hidden")
            pairs = st.session_state.get("ex_name_pairs", [])
            names = [n for n, _ in pairs]
            if product_name in names:
                idx = names.index(product_name)
                pairs[idx] = (product_name, merged_count)
            else:
                pairs = [(product_name, merged_count)] + pairs
            st.session_state["ex_name_pairs"] = pairs
        else:
            st.error(msg)

# ===================== 5) 저장된 제외 키워드 (상품명(개수) 목록) =====================
def _fetch_latest_name_counts(supabase: Any, max_rows: int = 500) -> list[tuple[str, int]]:
    if supabase is None:
        return []
    try:
        q = (
            supabase.table(SUPABASE_TABLE)
            .select("product_name,keywords,saved_at")
            .order("saved_at", desc=True)
        )
        res = q.range(0, max(1, int(max_rows)) - 1).execute() if hasattr(q, "range") else q.limit(int(max_rows)).execute()
        data = getattr(res, "data", None)
        if not isinstance(data, list):
            js = getattr(res, "json", None)
            if isinstance(js, dict) and isinstance(js.get("data"), list):
                data = js["data"]
        if not isinstance(data, list):
            return []
        seen, pairs = set(), []
        for r in data:
            if not isinstance(r, dict):
                continue
            name = str(r.get("product_name", "")).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            cnt = len(_split_keywords(str(r.get("keywords", "") or "")))
            pairs.append((name, cnt))
        return pairs
    except Exception:
        return []

def _render_saved_exclusions_names(supabase: Any | None) -> None:
    st.markdown("### 5) 저장된 제외 키워드 (목록)")
    if "ex_name_pairs" not in st.session_state:
        st.session_state["ex_name_pairs"] = _fetch_latest_name_counts(supabase, max_rows=500)
    if "ex_names_page" not in st.session_state:
        st.session_state["ex_names_page"] = 0

    pairs: list[tuple[str, int]] = st.session_state["ex_name_pairs"]
    PAGE_SIZE = 20

    max_page = 0 if not pairs else (len(pairs) - 1) // PAGE_SIZE
    page = max(0, min(int(st.session_state["ex_names_page"]), max_page))
    st.session_state["ex_names_page"] = page

    start, end = page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE
    slice_pairs = pairs[start:end]

    if not slice_pairs:
        st.info("저장된 항목이 없습니다.")
    else:
        for name, cnt in slice_pairs:
            st.markdown(f"- {name}({cnt})")

    show_prev, show_next = page > 0, page < max_page
    if show_prev or show_next:
        cprev, cnext = st.columns(2)
        with cprev:
            if show_prev and st.button("이전", key=f"ex_names_prev_{page}", use_container_width=True):
                st.session_state["ex_names_page"] = page - 1
                st.experimental_rerun()
        with cnext:
            if show_next and st.button("다음", key=f"ex_names_next_{page}", use_container_width=True):
                st.session_state["ex_names_page"] = page + 1
                st.experimental_rerun()

# ===================== 차트(수동 컷만) =====================
def _plot_cpc_curve_plotly_manual(kw: pd.DataFrame, selected: CpcCuts) -> None:
    # 검색 영역만 누적에 포함
    conv = kw[(kw["orders_14d"] > 0) & (kw["cpc"].notna()) & (kw["surface"] == SURF_SEARCH_VALUE)].copy()
    if conv.empty:
        st.warning("전환 발생 키워드가 없어 그래프를 표시할 수 없습니다.")
        return

    conv = conv.sort_values("cpc").reset_index(drop=True)
    total_conv_rev = float(conv["revenue_14d"].sum())
    if total_conv_rev <= 0:
        st.warning("conv 총매출이 0입니다.")
        return

    x_vals = conv["cpc"].to_numpy(float)
    y_share_conv = (conv["revenue_14d"].cumsum().to_numpy(float) / total_conv_rev).clip(0, 1)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_vals, y=y_share_conv, mode="lines", line=dict(width=2),
        name="누적비중(≤CPC)", hovertemplate="CPC=%{x:.0f}<br>Share=%{y:.2%}<extra></extra>",
    ))
    # 사용자가 입력한 두 개의 기준선만 표시
    fig.add_vline(x=float(selected.bottom), line_dash="dash", opacity=1.0, line_color="blue", line_width=3)
    fig.add_vline(x=float(selected.top),    line_dash="dash", opacity=1.0, line_color="red",  line_width=3)

    fig.update_layout(
        height=380,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title="CPC",
        yaxis_title="누적매출비중(conv)",
        yaxis=dict(tickformat=".0%"),
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)

# ===================== AOV, 제외 계산 =====================
def _aov_p50(df: pd.DataFrame) -> float:
    if df is None or df.empty:
        return 0.0
    rev_col = "revenue_14d"; ord_col = "orders_14d"
    if rev_col not in df.columns or ord_col not in df.columns:
        return 0.0
    s_orders = pd.to_numeric(df[ord_col], errors="coerce")
    s_rev = pd.to_numeric(df[rev_col], errors="coerce")
    mask = (s_orders > 0) & s_rev.notna()
    if not mask.any():
        return 0.0
    aov = (s_rev[mask] / s_orders[mask]).replace([np.inf, -np.inf], np.nan).dropna()
    if aov.empty:
        return 0.0
    return float(np.median(aov))

def _compute_exclusions(kw: pd.DataFrame, cuts: CpcCuts, aov_p50_value: float, breakeven_roas: float) -> Dict[str, pd.DataFrame]:
    ex_a = kw[(kw["orders_14d"] == 0) & (kw["cpc"] >= cuts.top)].copy()
    ex_b = kw[(kw["orders_14d"] == 0) & (kw["cpc"] <= cuts.bottom) & (kw["clicks"] >= 1)].copy()
    cpc_global_p50 = float(kw.loc[kw["clicks"] > 0, "cpc"].quantile(0.5)) if (kw["clicks"] > 0).any() else 0.0
    ex_c = kw[kw["orders_14d"] == 0].copy()
    ex_c["next_click_cost"] = np.where(ex_c["cpc"] > 0, ex_c["cpc"], cpc_global_p50)
    ex_c["cost_after_1click"] = ex_c["cost"] + ex_c["next_click_cost"]
    ex_c["roas_if_1_order"] = (
        (aov_p50_value / ex_c["cost_after_1click"] * 100)
        .replace([np.inf, -np.inf], 0)
        .fillna(0)
        .round(2)
        if aov_p50_value > 0
        else 0.0
    )
    ex_c = ex_c[ex_c["roas_if_1_order"] <= float(breakeven_roas)].copy()
    ex_d = kw[(kw["roas_14d"] > 0) & (kw["roas_14d"] < float(breakeven_roas))].copy()
    return {"a": ex_a, "b": ex_b, "c": ex_c, "d": ex_d}

# ===================== 메인 탭 =====================
def render_ad_analysis_tab(supabase: Any | None = None) -> None:
    st.subheader("광고분석 (총 14일 기준)")

    up = st.file_uploader("로우데이터 업로드 (xlsx/csv)", type=["xlsx", "csv"], key="ad_up")
    breakeven_roas = st.number_input("손익분기 ROAS", min_value=0.0, value=0.0, step=10.0, key="ad_be")

    if "ad_run_started" not in st.session_state:
        st.session_state["ad_run_started"] = False
    if st.button("🔍 분석하기", key="ad_run", use_container_width=True):
        st.session_state["ad_run_started"] = True
    if not st.session_state["ad_run_started"]:
        return

    if up is None:
        st.error("파일을 업로드하세요.")
        return
    try:
        df_raw = _load_df(up)
        df = _normalize(df_raw)
    except ValueError as e:
        st.error(str(e))
        return
    if df.empty:
        st.error("유효한 데이터가 없습니다.")
        return

    kw, totals = _aggregate_kw(df)

    st.markdown("### 1) 기본 성과 지표")
    st.caption(f"기간: {totals['date_min']} ~ {totals['date_max']}")
    total_cost = totals["total_cost"]; total_rev = totals["total_rev"]; total_orders = totals["total_orders"]

    def _row(name: str, sub: pd.DataFrame) -> Dict[str, float | int | str]:
        c = int(sub["cost"].sum()); 
        r = int(sub["revenue_14d"].sum()); 
        o = int(sub["orders_14d"].sum()); 
        clicks = int(sub[CLK_COL].sum())
        return {
            "영역": name,
            "주문": o,
            "매출": r, "매출비율(%)": round(_safe_div(r, total_rev) * 100, 2),
            "광고비": c, "광고비비율(%)": round(_safe_div(c, total_cost) * 100, 2),
            "ROAS": round(_safe_div(r, c) * 100, 2),
            "평균 CPC": round(_safe_div(c, clicks), 2),
        }

    rows = [
        _row("전체", df),
        _row("검색", df[df["surface"] == SURF_SEARCH_VALUE]),
        _row("비검색", df[df["surface"] != SURF_SEARCH_VALUE]),
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("### 2) CPC-누적매출 비중")
    conv = kw[(kw["orders_14d"] > 0) & (kw["cpc"].notna())].copy()
    if conv.empty:
        st.caption("전환 발생 키워드가 없어 컷은 0으로 처리됩니다.")
        return

    # ---- 수동 입력 전용: 데이터 범위로 가이드 ----
    x = conv["cpc"].to_numpy(float)
    cpc_min, cpc_max = float(np.nanmin(x)), float(np.nanmax(x))

    # (추가) 기존 세션값을 min/max로 클램프하여 number_input에 전달할 안전 기본값 생성
    val_bottom = float(st.session_state.get("manual_bottom", cpc_min))
    val_top    = float(st.session_state.get("manual_top", cpc_max))
    val_bottom = max(cpc_min, min(val_bottom, cpc_max))
    val_top    = max(cpc_min, min(val_top,    cpc_max))

    # 초기값 기억
    if "manual_bottom" not in st.session_state:
        st.session_state["manual_bottom"] = float(cpc_min)
    if "manual_top" not in st.session_state:
        st.session_state["manual_top"] = float(cpc_max)

    c1, c2 = st.columns(2)
    with c1:
        manual_bottom = st.number_input(
            "CPC cut bottom",
            min_value=float(cpc_min),
            max_value=float(cpc_max),
            value=float(val_bottom),
            step=10.0,
            help="그래프 툴팁(CPC) 보고 수동 입력"
        )
    with c2:
        manual_top = st.number_input(
            "CPC cut top",
            min_value=float(cpc_min),
            max_value=float(cpc_max),
            value=float(val_top),
            step=10.0,
            help="그래프 툴팁(CPC) 보고 수동 입력"
        )

    # 사용성: bottom>top 입력 시 자동 스왑
    if manual_bottom > manual_top:
        manual_bottom, manual_top = manual_top, manual_bottom

    # 상태 저장
    st.session_state["manual_bottom"] = float(manual_bottom)
    st.session_state["manual_top"] = float(manual_top)

    sel_cuts = CpcCuts(bottom=float(manual_bottom), top=float(manual_top))
    _plot_cpc_curve_plotly_manual(kw, sel_cuts)

    shares = _search_shares_for_cuts(kw, sel_cuts)
    aov50 = _aov_p50(conv)

    st.markdown(
        f"""
- **CPC_cut bottom:** {sel_cuts.bottom:.2f}원  
  · 전체 매출비중 {shares['rev_share_bottom']:.2f}% / 검색 매출비중 {shares['rev_share_bottom_search']:.2f}%  
  · 전체 광고비비중 {shares['cost_share_bottom']:.2f}% / 검색 광고비비중 {shares['cost_share_bottom_search']:.2f}%

- **CPC_cut top:** {sel_cuts.top:.2f}원  
  · 전체 매출비중 {shares['rev_share_top']:.2f}% / 검색 매출비중 {shares['rev_share_top_search']:.2f}%  
  · 전체 광고비비중 {shares['cost_share_top']:.2f}% / 검색 광고비비중 {shares['cost_share_top_search']:.2f}%
"""
    )

    st.markdown("### 3) 제외 키워드")
    exclusions = _compute_exclusions(kw, sel_cuts, aov50, float(breakeven_roas))
    _display_table("a) CPC_cut top 이상 전환 0", exclusions["a"])
    _display_table("b) CPC_cut bottom 이하 전환 0", exclusions["b"])
    _display_table("c) 전환 시 손익 ROAS 미달", exclusions["c"], extra=["roas_if_1_order"])
    _display_table("d) 손익 ROAS 미달", exclusions["d"])

    # 4) 저장 및 병합 복사
    _render_exclusion_union(exclusions, supabase)

    # 5) 저장명 목록(상품명(개수))
    _render_saved_exclusions_names(supabase)

# if __name__ == "__main__":
#     render_ad_analysis_tab(None)
