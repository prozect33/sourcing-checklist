# app/ad_cpc_cuts_app.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Dict

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt


# =========================
# 파라미터 & 결과 구조체
# =========================
@dataclass(frozen=True)
class CutParams:
    min_clicks: int = 3
    min_keywords: int = 3
    bottom_share_ceiling: float = 0.50          # bottom 탐색 상한(≤50%)
    top_share_window: Tuple[float, float] = (0.80, 0.98)  # top 탐색 윈도우
    q_high_jump: float = 0.80                   # '큰 점프' 분위수
    q_low_flat: float = 0.30                    # '평탄' 분위수
    L_post: int = 3                             # 점프 직후 평탄 최소 길이
    min_gap: float = 50.0                       # bottom-top 최소 간격(원)


@dataclass(frozen=True)
class CutsResult:
    bottom: float
    top: float
    debug: Dict[str, dict]


# =========================
# 데이터 정규화/집계
# =========================
REQUIRED = {
    "cpc": ["cpc", "CPC", "단가", "클릭당비용"],
    "clicks": ["clicks", "클릭", "클릭수"],
    "revenue": ["revenue", "매출", "총 전환매출액(14일)", "revenue_14d"],
    "keyword": ["keyword", "키워드"],
}

def _find_col(df: pd.DataFrame, cands: list[str]) -> Optional[str]:
    cols = {c.lower(): c for c in df.columns}
    for k in cands:
        if k.lower() in cols:
            return cols[k.lower()]
    return None

def _normalize_columns(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()
    col_map: Dict[str, str] = {}
    for std, cands in REQUIRED.items():
        c = _find_col(df, cands)
        if c is None and std != "keyword":
            raise ValueError(f"필수 컬럼 없음: {std} (후보: {cands})")
        if c is not None:
            col_map[std] = c

    out = pd.DataFrame()
    out["cpc"] = pd.to_numeric(df[col_map["cpc"]], errors="coerce")
    out["clicks"] = pd.to_numeric(df[col_map["clicks"]], errors="coerce").fillna(0).astype(int)
    out["revenue"] = pd.to_numeric(df[col_map["revenue"]], errors="coerce").fillna(0.0)
    if "keyword" in col_map:
        out["keyword"] = df[col_map["keyword"]].astype(str)
    else:
        out["keyword"] = ""
    out = out.dropna(subset=["cpc"]).sort_values("cpc").reset_index(drop=True)
    return out

def _aggregate_by_cpc(df_std: pd.DataFrame, p: CutParams) -> pd.DataFrame:
    tmp = df_std.copy()
    tmp["kw_cnt"] = 1
    agg = (
        tmp.groupby("cpc", as_index=False)[["clicks", "revenue", "kw_cnt"]]
        .sum()
        .sort_values("cpc")
        .reset_index(drop=True)
    )
    # 표본가드(왜: 우연 스파이크 방지)
    agg = agg[(agg["clicks"] >= p.min_clicks) & (agg["kw_cnt"] >= p.min_keywords)].reset_index(drop=True)
    if agg.empty:
        raise ValueError("표본가드 이후 데이터가 비었습니다. min_clicks/min_keywords를 낮추세요.")

    total_rev = float(agg["revenue"].sum())
    if total_rev <= 0:
        raise ValueError("총 매출이 0입니다.")
    agg["cum_rev"] = agg["revenue"].cumsum()
    agg["cum_share"] = (agg["cum_rev"] / total_rev).clip(0.0, 1.0)

    share = agg["cum_share"].to_numpy(dtype=float)
    delta = np.empty_like(share)
    delta[0] = share[0]
    if len(share) > 1:
        delta[1:] = np.diff(share)
    agg["delta_s"] = delta
    return agg[["cpc", "clicks", "revenue", "kw_cnt", "cum_share", "delta_s"]]


# =========================
# bottom / top 산정
# =========================
def _find_bottom(agg: pd.DataFrame, p: CutParams) -> tuple[float, dict]:
    """큰 점프 직후 긴 평탄이 바로 이어지는 구간의 시작점을 bottom으로."""
    w = agg.loc[agg["cum_share"] <= p.bottom_share_ceiling].copy()
    if len(w) < 2:
        return float(agg["cpc"].iloc[0]), {"mode": "fallback_low_data"}

    deltas = w["delta_s"].to_numpy(dtype=float)
    q_high = float(np.quantile(deltas, p.q_high_jump))
    q_low = float(np.quantile(deltas, p.q_low_flat))

    def post_run_len(start_i: int) -> int:
        run = 0
        for k in range(start_i + 1, len(deltas)):
            if deltas[k] <= q_low:
                run += 1
            else:
                break
        return run

    cands: list[tuple[int, float, int]] = []
    for i in range(len(deltas) - 1):  # i: jump index, bottom은 i+1의 cpc
        if deltas[i] >= q_high:
            run = post_run_len(i)
            if run >= p.L_post:
                cands.append((i, deltas[i], run))

    if cands:
        # 우선순위: 평탄 run 길이 ↓, 점프 delta ↓, 실제 bottom cpc ↑
        cands.sort(key=lambda t: (-t[2], -t[1], w["cpc"].iloc[t[0] + 1]))
        i_best, jump_delta, flat_len = cands[0]
        bottom = float(w["cpc"].iloc[i_best + 1])
        dbg = {
            "mode": "pattern",
            "jump_cpc": float(w["cpc"].iloc[i_best]),
            "jump_delta": float(jump_delta),
            "post_flat_len": int(flat_len),
            "q_high": q_high,
            "q_low": q_low,
        }
        return bottom, dbg

    # 폴백: 윈도우 내 최대 delta 지점의 다음 포인트
    i_best = int(np.argmax(deltas))
    i_pick = min(i_best + 1, len(deltas) - 1)
    bottom = float(w["cpc"].iloc[i_pick])
    dbg = {
        "mode": "fallback_max_delta",
        "jump_cpc": float(w["cpc"].iloc[i_best]),
        "jump_delta": float(deltas[i_best]),
        "q_high": q_high,
        "q_low": q_low,
    }
    return bottom, dbg


def _find_top_knee_window(agg: pd.DataFrame, p: CutParams) -> tuple[float, dict]:
    """80–98% 윈도우에서만 knee(elbow) 계산."""
    lo, hi = p.top_share_window
    w = agg.loc[(agg["cum_share"] >= lo) & (agg["cum_share"] <= hi)].copy()
    if len(w) >= 2:
        x = w["cpc"].to_numpy(dtype=float)
        y = w["cum_share"].to_numpy(dtype=float)
        x_n = (x - x.min()) / (x.max() - x.min() + 1e-12)
        y_n = (y - y.min()) / (y.max() - y.min() + 1e-12)
        idx = int(np.argmax(y_n - x_n))
        return float(w["cpc"].iloc[idx]), {"mode": "knee_in_window", "idx": idx, "win_lo": lo, "win_hi": hi}

    # 폴백: 전구간에서 lo 이상 최초
    arr = agg["cum_share"].to_numpy(dtype=float)
    idx = int(np.searchsorted(arr, lo, side="left"))
    idx = min(idx, len(agg) - 1)
    return float(agg["cpc"].iloc[idx]), {"mode": "fallback_first_ge_lo", "win_lo": lo}


def compute_cuts(
    df_raw: pd.DataFrame,
    *,
    params: Optional[CutParams] = None,
    cpc_col: str = "cpc",
    clicks_col: str = "clicks",
    revenue_col: str = "revenue",
    keyword_col: Optional[str] = "keyword",
) -> CutsResult:
    """핵심 API: 원시 행 데이터 → bottom/top 계산"""
    p = params or CutParams()
    df_std = pd.DataFrame(
        {
            "cpc": pd.to_numeric(df_raw[cpc_col], errors="coerce"),
            "clicks": pd.to_numeric(df_raw[clicks_col], errors="coerce").fillna(0).astype(int),
            "revenue": pd.to_numeric(df_raw[revenue_col], errors="coerce").fillna(0.0),
            "keyword": df_raw[keyword_col] if (keyword_col and keyword_col in df_raw.columns) else "",
        }
    ).dropna(subset=["cpc"]).sort_values("cpc").reset_index(drop=True)

    agg = _aggregate_by_cpc(df_std, p)
    bottom, dbg_b = _find_bottom(agg, p)
    top, dbg_t = _find_top_knee_window(agg, p)

    # 정합성
    if top < bottom:
        top = bottom
    if (top - bottom) < p.min_gap:
        top = bottom + p.min_gap

    return CutsResult(bottom=bottom, top=top, debug={"bottom": dbg_b, "top": dbg_t})


# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="CPC 누적매출 컷 산정", layout="wide")
st.title("CPC 누적매출 비중 & 컷 (Bottom/Top)")

with st.sidebar:
    st.header("업로드")
    up = st.file_uploader("CSV 또는 Excel 업로드", type=["csv", "xlsx", "xls"])
    st.caption("필수 컬럼: cpc, clicks, revenue (keyword 선택) — 한국어 컬럼명도 자동 인식")

    st.header("설정")
    min_clicks = st.number_input("최소 클릭(표본가드)", 0, 50, 3, 1)
    min_keywords = st.number_input("최소 키워드수(표본가드)", 0, 50, 3, 1)
    bottom_ceiling = st.slider("bottom 탐색 상한(누적비중)", 0.10, 0.90, 0.50, 0.01)
    top_win = st.slider("top 윈도우(80–98%)", 0.70, 0.999, (0.80, 0.98), 0.01)
    q_high = st.slider("점프 분위수 q_high", 0.5, 0.99, 0.80, 0.01)
    q_low = st.slider("평탄 분위수 q_low", 0.01, 0.49, 0.30, 0.01)
    l_post = st.number_input("점프 이후 평탄 최소 길이", 1, 20, 3, 1)
    min_gap = st.number_input("bottom-top 최소 간격(원)", 0, 1000, 50, 10)

    params = CutParams(
        min_clicks=int(min_clicks),
        min_keywords=int(min_keywords),
        bottom_share_ceiling=float(bottom_ceiling),
        top_share_window=(float(top_win[0]), float(top_win[1])),
        q_high_jump=float(q_high),
        q_low_flat=float(q_low),
        L_post=int(l_post),
        min_gap=float(min_gap),
    )

tab_chart, tab_table, tab_debug = st.tabs(["차트", "표", "디버그"])

if up is None:
    st.info("샘플이 필요하면 CSV/XLSX를 업로드하세요. 컬럼명은 cpc/clicks/revenue/keyword(선택) 입니다.")
else:
    # 파일 로드
    if up.name.lower().endswith(".csv"):
        df0 = pd.read_csv(up)
    else:
        df0 = pd.read_excel(up)

    try:
        df_norm = _normalize_columns(df0)
        res = compute_cuts(df_norm, params=params)
        agg = _aggregate_by_cpc(df_norm, params)

        with tab_chart:
            # 라인 차트 + 컷 라인
            base = alt.Chart(agg).encode(x=alt.X("cpc:Q", title="cpc (원)"))
            line = base.mark_line().encode(y=alt.Y("cum_share:Q", title="cum_rev_share"))
            bottom_rule = alt.Chart(pd.DataFrame({"cpc": [res.bottom]})).mark_rule(strokeDash=[4, 4]).encode(x="cpc:Q")
            top_rule = alt.Chart(pd.DataFrame({"cpc": [res.top]})).mark_rule(strokeDash=[4, 4]).encode(x="cpc:Q")
            st.altair_chart((line + bottom_rule + top_rule).properties(height=360), use_container_width=True)

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("CPC_cut bottom", f"{res.bottom:,.0f}원")
            with c2:
                st.metric("CPC_cut top", f"{res.top:,.0f}원")
            with c3:
                st.write("범례: 파선 = 컷 지점")

        with tab_table:
            st.subheader("CPC별 집계표")
            st.dataframe(agg, use_container_width=True, height=420)

        with tab_debug:
            st.subheader("디버그 정보")
            st.json(res.debug)

    except Exception as e:
        st.error(f"처리 실패: {e}")
