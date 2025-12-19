# path: app/ad_analysis.py
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import altair as alt  # kept for compatibility (unused in Plotly chart)
import plotly.graph_objects as go

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

# ====== 자동(bottom/top) 계산 파라미터(고정) ======
SMOOTH_DIVISOR = 70  # 창 = round(N / 70), 홀수, 최소7
SLOPE_Q = 0.64  # high 임계 분위
LOWBACK_DELTA = 0.24  # low_back_q = SLOPE_Q - LOWBACK_DELTA
MIN_RUN_FRAC = 0.04  # 스파이크 방지

# ====== 수동 캡 프리셋(화살표 단계) ======
Q_PRESETS: List[float] = [0.05, 0.10, 0.15, 0.20, 0.30, 0.50]  # bottom용
TOP_PRESETS: List[float] = list(reversed(Q_PRESETS))           # top은 역배치
DEFAULT_FLOOR_Q = 0.05
DEFAULT_CEIL_Q = 0.05  # (중요) _init_cap_indices가 Q_PRESETS로 인덱싱하므로 그대로 두세요

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


def _nearest_preset_index(q: float) -> int:
    return int(np.argmin([abs(p - q) for p in Q_PRESETS]))


def _quantile_x(x: np.ndarray, q: float) -> float:
    return float(np.quantile(x, float(np.clip(q, 0.0, 1.0))))

def _init_cap_indices() -> tuple[int, int]:
    # bottom: 프리셋 기본값 유지(가까운 값)
    idx_floor = _nearest_preset_index(DEFAULT_FLOOR_Q)

    # top: 6/6에서 시작 → 'top 선택에 쓰는 리스트'의 마지막 인덱스
    # TOP_PRESETS를 쓰고 있다면:
    idx_ceil = len(TOP_PRESETS) - 1

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


# ============== 컷 계산(자동 + 캡) ==============
@dataclass(frozen=True)
class CpcCuts:
    bottom: float
    top: float


def _compute_auto_cpc_cuts(kw: pd.DataFrame) -> Tuple[CpcCuts, pd.DataFrame]:
    """
    자동 컷(원본 로직 유지):
      - bottom: high-임계 최장구간을 low-임계로 backtrack한 시작점
      - top   : argmax(y_n - x_n)
    주의: 여기서는 FLOOR 캡을 적용하지 않음(수동 캡이 별도로 들어감).
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
    if n < 5:
        return CpcCuts(bottom=float(x[0]), top=float(x[-1])), conv

    # ----- top (기존 유지) -----
    x_n = (x - x.min()) / (x.max() - x.min() + 1e-12)
    y_n = (y - y.min()) / (y.max() - y.min() + 1e-12)
    idx_top = int(np.argmax(y_n - x_n))

    # ----- bottom (심플 히스테리시스, floor 적용 없음) -----
    smooth_win = max(7, int(round(n / SMOOTH_DIVISOR)))
    if smooth_win % 2 == 0:
        smooth_win += 1

    y_s = _moving_average(y, smooth_win)
    slope = np.gradient(y_s, x)

    pos = slope[slope > 0]
    if pos.size == 0 or not np.any(np.isfinite(pos)):
        idx_bottom = 0
    else:
        high_thr = float(np.quantile(pos, float(np.clip(SLOPE_Q, 0.55, 0.9))))
        s_high, e_high = _longest_true_run_by_x(slope >= high_thr, x)

        if s_high == -1:
            high_thr = float(np.quantile(pos, 0.55))
            s_high, e_high = _longest_true_run_by_x(slope >= high_thr, x)

        if s_high == -1:
            idx_bottom = 0
        else:
            low_back_q = float(np.clip(SLOPE_Q - LOWBACK_DELTA, 0.15, 0.45))
            low_thr = float(np.quantile(pos, low_back_q))
            mask_low = slope >= low_thr

            s = s_high
            while s - 1 >= 0 and mask_low[s - 1]:
                s -= 1

            e = s
            while e + 1 < len(mask_low) and mask_low[e + 1]:
                e += 1

            min_run = max(2, int(np.ceil(n * MIN_RUN_FRAC)))
            if (e - s + 1) < min_run:
                e = min(n - 1, s + min_run - 1)

            idx_bottom = int(s)

    return CpcCuts(bottom=float(x[idx_bottom]), top=float(x[idx_top])), conv


def _apply_caps(auto_cuts: CpcCuts, conv: pd.DataFrame, floor_q: float, ceil_q: float) -> CpcCuts:
    """
    수동 캡:
      - bottom = max(auto_bottom, quantile(cpc, floor_q))
      - top    = min(auto_top,    quantile(cpc, 1 - ceil_q))
    """
    x = conv["cpc"].to_numpy(float)

    floor_x = _quantile_x(x, floor_q)
    ceil_x = _quantile_x(x, 1.0 - ceil_q)

    bottom = max(float(auto_cuts.bottom), float(floor_x))
    top = min(float(auto_cuts.top), float(ceil_x))

    if top <= bottom:
        top = float(x[-1])
        st.warning("top ≤ bottom 이 되어 top을 최댓값으로 완화했습니다. (CEIL 단계를 오른쪽으로 옮겨보세요)")

    return CpcCuts(bottom=bottom, top=top)


# ============== 지표/표시 ==============
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
    orders = conv["orders_14d"]
    rev = conv["revenue_14d"]
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


def _display_table(title: str, dff: pd.DataFrame, extra: Iterable[str] | None = None) -> None:
    cols = [
        "keyword",
        "surface",
        "active_days",
        "impressions",
        "clicks",
        "cost",
        "orders_14d",
        "revenue_14d",
        "ctr",
        "cpc",
        "roas_14d",
    ]
    if extra:
        cols += list(extra)
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


# ============== Plotly 차트 ==============
def _plot_cpc_curve_plotly(conv: pd.DataFrame, cuts: CpcCuts) -> None:
    x = conv["cpc"].to_numpy(float)
    y = conv["cum_rev_share"].to_numpy(float)

    idx_b = int(np.argmin(np.abs(x - cuts.bottom)))
    idx_t = int(np.argmin(np.abs(x - cuts.top)))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name="cum_rev_share", hovertemplate="CPC=%{x:.0f}<br>Share=%{y:.2%}<extra></extra>"))
    fig.add_vline(x=cuts.bottom, line_dash="dot")
    fig.add_vline(x=cuts.top, line_dash="dash")

    fig.add_trace(
        go.Scatter(
            x=[x[idx_b], x[idx_t]],
            y=[y[idx_b], y[idx_t]],
            mode="markers",
            name="cuts",
            marker=dict(symbol="triangle-up", size=12),
            hovertemplate="CPC=%{x:.0f}<br>Share=%{y:.2%}<extra></extra>",
        )
    )
    fig.update_layout(
        height=380,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title="CPC",
        yaxis_title="누적매출비중",
        yaxis=dict(tickformat=".0%"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


# ============== Streamlit 탭 ==============
def render_ad_analysis_tab(supabase):
    st.subheader("광고분석 (총 14일 기준)")

    # --- 입력 위젯 ---
    up = st.file_uploader("로우데이터 업로드 (xlsx/csv)", type=["xlsx", "csv"], key="ad_up")
    breakeven_roas = st.number_input("손익분기 ROAS", min_value=0.0, value=0.0, step=10.0, key="ad_be")

    # --- [핵심 수정①] 분석 세션 상태 (버튼의 일회성 회피) ---
    if "ad_run_started" not in st.session_state:
        st.session_state["ad_run_started"] = False

    run_clicked = st.button("🔍 분석하기", key="ad_run", use_container_width=True)
    if run_clicked:
        # why: rerun 때 버튼값은 False로 떨어짐 → 세션 플래그로만 판정
        st.session_state["ad_run_started"] = True

    # --- [핵심 수정②] 조기 종료 게이트를 세션 플래그로 ---
    if not st.session_state["ad_run_started"]:
        return

    # --- 검증 ---
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

    # --- 집계 ---
    kw, totals = _aggregate_kw(df)

    st.markdown("### 1) 기본 성과 지표")
    st.caption(f"기간: {totals['date_min']} ~ {totals['date_max']}")
    total_cost = totals["total_cost"]
    total_rev = totals["total_rev"]
    total_orders = totals["total_orders"]

    def _row(name: str, sub: pd.DataFrame) -> Dict[str, float | int | str]:
        c = int(sub["cost"].sum())
        r = int(sub["revenue_14d"].sum())
        o = int(sub["orders_14d"].sum())
        return {
            "영역": name,
            "광고비": c,
            "광고비비율(%)": round(_safe_div(c, total_cost) * 100, 2),
            "매출": r,
            "매출비율(%)": round(_safe_div(r, total_rev) * 100, 2),
            "주문": o,
            "주문비율(%)": round(_safe_div(o, total_orders) * 100, 2),
            "ROAS": round(_safe_div(r, c) * 100, 2),
        }

    rows = [
        _row("전체", df),
        _row("검색", df[df["surface"] == SURF_SEARCH_VALUE]),
        _row("비검색", df[df["surface"] != SURF_SEARCH_VALUE]),
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # --- 컷 & 캡 ---
    st.markdown("### 2) CPC-누적매출 비중 & 컷 (수동 캡: 화살표)")
    auto_cuts, conv = _compute_auto_cpc_cuts(kw)
    if conv.empty:
        st.caption("전환 발생 키워드가 없어 컷은 0으로 처리됩니다.")
        return

    # --- [핵심 수정③] q 단계 인덱스 최초 1회만 초기화 ---
    if "q_idx_floor_bottom" not in st.session_state or "q_idx_ceil_top" not in st.session_state:
        idx_floor, idx_ceil = _init_cap_indices()
        st.session_state["q_idx_floor_bottom"] = idx_floor
        st.session_state["q_idx_ceil_top"] = idx_ceil

    # 소프트 리셋: q 단계만
    c1, c2, c3 = st.columns([3, 3, 2])
    with c3:
        if st.button("↻ 리셋", key="cap_reset"):
            idx_floor, idx_ceil = _init_cap_indices()
            st.session_state["q_idx_floor_bottom"] = idx_floor
            st.session_state["q_idx_ceil_top"] = idx_ceil

    # --- 화살표 컨트롤 (세션 인덱스 증감만 수행) ---
    left, right = st.columns(2)
    with left:
        st.caption(f"**Bottom floor** • 단계 {st.session_state['q_idx_floor_bottom'] + 1}/{len(Q_PRESETS)}")
        bl, _, br = st.columns([1, 2, 1])
        if bl.button("◀", key="floor_left"):
            st.session_state["q_idx_floor_bottom"] = max(0, st.session_state["q_idx_floor_bottom"] - 1)
        if br.button("▶", key="floor_right"):
            st.session_state["q_idx_floor_bottom"] = min(len(Q_PRESETS) - 1, st.session_state["q_idx_floor_bottom"] + 1)

    with right:
        st.caption(f"**Top ceiling** • 단계 {st.session_state['q_idx_ceil_top'] + 1}/{len(Q_PRESETS)}")
        tl, _, tr = st.columns([1, 2, 1])
        if tl.button("◀", key="ceil_left"):
            st.session_state["q_idx_ceil_top"] = max(0, st.session_state["q_idx_ceil_top"] - 1)
        if tr.button("▶", key="ceil_right"):
            st.session_state["q_idx_ceil_top"] = min(len(TOP_PRESETS) - 1, st.session_state["q_idx_ceil_top"] + 1)

    floor_q = Q_PRESETS[st.session_state["q_idx_floor_bottom"]]
    ceil_q = TOP_PRESETS[st.session_state["q_idx_ceil_top"]]
    cuts = _apply_caps(auto_cuts, conv, floor_q=floor_q, ceil_q=ceil_q)

    # --- 차트 & 지표 ---
    _plot_cpc_curve_plotly(conv, cuts)

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

    # --- 제외 키워드 ---
    st.markdown("### 3) 제외 키워드")
    exclusions = _compute_exclusions(kw, cuts, aov50, float(breakeven_roas))
    _display_table("a) CPC_cut top 이상 전환 0", exclusions["a"])
    _display_table("b) CPC_cut bottom 이하 전환 0", exclusions["b"])
    _display_table("c) 전환 시 손익 ROAS 미달", exclusions["c"], extra=["roas_if_1_order"])
    _display_table("d) 손익 ROAS 미달", exclusions["d"])

    _render_exclusion_union(exclusions)

    # --- 저장 (선택) ---
    with st.expander("💾 저장 (선택)", expanded=False):
        c1, c2 = st.columns([2, 3])
        with c1:
            product_name = st.text_input("상품명", value="", key="ad_product")
        with c2:
            note = st.text_input("메모", value="", key="ad_note")
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
