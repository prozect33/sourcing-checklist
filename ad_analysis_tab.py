# app/ad_analysis_tab.py
from __future__ import annotations

import json
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

SMOOTH_DIVISOR = 70
SLOPE_Q = 0.64
LOWBACK_DELTA = 0.24
MIN_RUN_FRAC = 0.04

BOTTOM_Q_PRESETS: List[float] = [0.05, 0.10, 0.15, 0.20, 0.30]
TOP_Q_PRESETS:    List[float] = [0.05, 0.10, 0.15, 0.20, 0.30, 0.50]
DEFAULT_FLOOR_Q = BOTTOM_Q_PRESETS[0]
DEFAULT_CEIL_Q  = TOP_Q_PRESETS[0]

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
    df["keyword"] = df[KW_COL].astype(str).fillna("")
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

# ===================== 컷 계산 =====================
@dataclass(frozen=True)
class CpcCuts:
    bottom: float
    top: float

def _compute_auto_cpc_cuts(kw: pd.DataFrame) -> Tuple[CpcCuts, pd.DataFrame]:
    conv = kw[kw["orders_14d"] > 0].sort_values("cpc").copy()
    if conv.empty:
        return CpcCuts(0.0, 0.0), conv
    total_conv_rev = float(conv["revenue_14d"].sum())
    conv["cum_rev"] = conv["revenue_14d"].cumsum()
    conv["cum_rev_share"] = (conv["cum_rev"] / (total_conv_rev if total_conv_rev > 0 else 1.0)).clip(0, 1)
    x = conv["cpc"].to_numpy(float)
    y = conv["cum_rev_share"].to_numpy(float)
    n = len(x)
    if n < 5:
        return CpcCuts(bottom=float(x[0]), top=float(x[-1])), conv
    x_n = (x - x.min()) / (x.max() - x.min() + 1e-12)
    y_n = (y - y.min()) / (y.max() - y.min() + 1e-12)
    idx_top = int(np.argmax(y_n - x_n))
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
        s_high, _ = _longest_true_run_by_x(slope >= high_thr, x)
        if s_high == -1:
            high_thr = float(np.quantile(pos, 0.55))
            s_high, _ = _longest_true_run_by_x(slope >= high_thr, x)
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

def _build_candidate_lines(conv: pd.DataFrame, auto_cuts: CpcCuts) -> tuple[List[float], List[float]]:
    x = conv["cpc"].to_numpy(float)
    bottom_vals = []
    for q in BOTTOM_Q_PRESETS:
        floor_x = _quantile_x(x, q)
        bottom_vals.append(max(float(auto_cuts.bottom), float(floor_x)))
    top_vals = []
    for q in TOP_Q_PRESETS:
        ceil_x = _quantile_x(x, 1.0 - q)
        top_vals.append(min(float(auto_cuts.top), float(ceil_x)))
    def _dedup_sorted(vals: List[float]) -> List[float]:
        rounded = [round(v, 2) for v in vals]
        return sorted(dict.fromkeys(rounded))
    return _dedup_sorted(bottom_vals), _dedup_sorted(top_vals)

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
    if base.empty:
        return {k: 0.0 for k in [
            "cost_share_bottom","rev_share_bottom","cost_share_top","rev_share_top",
            "cost_share_bottom_search","rev_share_bottom_search",
            "cost_share_top_search","rev_share_top_search"
        ]}
    if "cpc" not in base.columns or base["cpc"].isna().any():
        base["cpc"] = base["cost"] / base["clicks"]
    m_le_bottom = base["cpc"] <= float(cuts.bottom)
    m_ge_top    = base["cpc"] >= float(cuts.top)
    cost_le_bottom = float(base.loc[m_le_bottom, "cost"].sum())
    rev_le_bottom  = float(base.loc[m_le_bottom, "revenue_14d"].sum())
    cost_ge_top    = float(base.loc[m_ge_top,    "cost"].sum())
    rev_ge_top     = float(base.loc[m_ge_top,    "revenue_14d"].sum())
    def _pct(num: float, den: float) -> float:
        return round(_safe_div(num, den, 0.0) * 100, 2)
    return {
        "cost_share_bottom": _pct(cost_le_bottom, total_cost_all),
        "rev_share_bottom":  _pct(rev_le_bottom,  total_rev_all),
        "cost_share_top":    _pct(cost_ge_top,    total_cost_all),
        "rev_share_top":     _pct(rev_ge_top,     total_rev_all),
        "cost_share_bottom_search": _pct(cost_le_bottom, total_cost_search),
        "rev_share_bottom_search":  _pct(rev_le_bottom,  total_rev_search),
        "cost_share_top_search":    _pct(cost_ge_top,    total_cost_search),
        "rev_share_top_search":     _pct(rev_ge_top,     total_rev_search),
    }

def _display_table(title: str, dff: pd.DataFrame, extra: Iterable[str] | None = None) -> None:
    cols = ["keyword","surface","active_days","impressions","clicks","cost","orders_14d","revenue_14d","ctr","cpc","roas_14d"]
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

def _format_keywords_line_exact(words: Iterable[str]) -> str:
    return ",\u200b".join([w for w in words])

# ===================== 클립보드/JS =====================
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

# ===================== Supabase I/O =====================
def _supabase_rows(res: Any) -> List[Dict]:
    data = getattr(res, "data", None)
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    js = getattr(res, "json", None)
    if isinstance(js, dict) and isinstance(js.get("data"), list):
        return [r for r in js["data"] if isinstance(r, dict)]
    if isinstance(res, dict):
        if isinstance(res.get("data"), list):
            return [r for r in res["data"] if isinstance(r, dict)]
        if isinstance(res, list):
            return [r for r in res if isinstance(r, dict)]
    if isinstance(res, list):
        return [r for r in res if isinstance(r, dict)]
    return []

def _save_exclusion_to_supabase(supabase: Any, product_name: str, keywords_line: str) -> tuple[bool, str]:
    if supabase is None:
        return False, "supabase 클라이언트가 없습니다."
    try:
        kst = timezone(timedelta(hours=9))
        saved_at = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S%z")
        payload = {
            "product_name": product_name.strip(),
            "saved_at": saved_at,
            "keywords": keywords_line,
            "count": len([w for w in keywords_line.split(",") if w.strip()]),
        }
        res = supabase.table(SUPABASE_TABLE).insert(payload).execute()
        if hasattr(res, "error") and res.error:
            return False, str(res.error)
        return True, "저장 완료"
    except Exception as e:
        return False, f"저장 실패: {e}"

def _fetch_saved_exclusions_page(supabase: Any, offset: int, limit: int) -> Tuple[bool, str, List[Dict]]:
    """목록형: 전체에서 최신순 페이지네이션. anon 키면 RLS select 필요."""
    if supabase is None:
        return False, "supabase 클라이언트가 없습니다.", []
    try:
        # PostgREST range: 0-indexed inclusive. v2 SDK는 .range 사용.
        q = (
            supabase.table(SUPABASE_TABLE)
            .select("id,product_name,saved_at,keywords,count")
            .order("saved_at", desc=True)
        )
        # SDK v2 호환: .range(start, end)
        start = max(0, int(offset))
        end = start + max(1, int(limit)) - 1
        if hasattr(q, "range"):
            res = q.range(start, end).execute()
        else:
            # v1 호환: limit/offset
            res = q.limit(int(limit)).offset(int(offset)).execute()
        if hasattr(res, "error") and res.error:
            return False, str(res.error), []
        rows = _supabase_rows(res)
        return True, "ok", rows
    except Exception as e:
        return False, f"조회 실패: {e}", []

# ===================== UI: 4) 저장/복사 =====================
def _render_exclusion_union(exclusions: Dict[str, pd.DataFrame], supabase: Any | None) -> None:
    st.markdown("### 4) 제외 키워드 (통합 · 한바구니 · 중복 제거)")
    all_words = _gather_exclusion_keywords(exclusions)
    if not all_words:
        return
    line = _format_keywords_line_exact(all_words)
    product_name = st.text_input("상품명(필수)", key="ex_prod_name", placeholder="예: ABC-123 블루 1팩")
    do_save_copy = st.button("저장 및 복사하기", key="ex_union_save_copy", disabled=(not product_name.strip()))
    if do_save_copy:
        ok, msg = _save_exclusion_to_supabase(supabase, product_name, line)
        if ok:
            st.success(f"[{product_name}] {msg}")
            components.html(
                f"""
                <script>
                  const txt = {json.dumps(line)};
                  (async () => {{ try {{ await navigator.clipboard.writeText(txt); }} catch (e) {{}} }})();
                </script>
                """,
                height=0,
            )
        else:
            st.error(msg)
    _copy_to_clipboard_button(f"[복사하기] 총{len(all_words)}개", line, key="ex_union_copy")

# ===================== UI: 5) 저장된 제외 키워드 (목록형) =====================
def _render_saved_exclusions_list(supabase: Any | None) -> None:
    st.markdown("### 5) 저장된 제외 키워드 (목록)")
    # 상태 초기화
    if "ex_list_page" not in st.session_state:
        st.session_state["ex_list_page"] = 0
    if "ex_list_page_size" not in st.session_state:
        st.session_state["ex_list_page_size"] = 20

    c1, c2, c3 = st.columns([1,1,6])
    with c1:
        page_size = st.selectbox("페이지 크기", options=[10, 20, 50], index=[10,20,50].index(st.session_state["ex_list_page_size"]), key="ex_list_size_sel")
        st.session_state["ex_list_page_size"] = int(page_size)
    with c2:
        # 새로고침(페이지 유지)
        refresh = st.button("새로고침", key="ex_list_refresh", use_container_width=True)
    with c3:
        st.caption("최신 저장 순으로 표시됩니다.")

    # 페이지 오프셋 계산
    page = int(st.session_state["ex_list_page"])
    limit = int(st.session_state["ex_list_page_size"])
    offset = page * limit

    ok, msg, rows = _fetch_saved_exclusions_page(supabase, offset=offset, limit=limit)
    if not ok:
        st.error(msg)
        return

    if not rows:
        if page == 0:
            st.info("저장된 항목이 없습니다.")
        else:
            st.info("더 이상 항목이 없습니다.")
        # 이전 페이지 버튼만 노출
        prev_dis = page <= 0
        cprev, cnext = st.columns(2)
        with cprev:
            if st.button("이전", disabled=prev_dis, key=f"ex_list_prev_empty", use_container_width=True):
                st.session_state["ex_list_page"] = max(0, page - 1)
        with cnext:
            st.button("다음", disabled=True, key=f"ex_list_next_empty", use_container_width=True)
        return

    # 목록 렌더(행형 카드)
    for i, row in enumerate(rows):
        product = row.get("product_name", "") or ""
        saved_at = row.get("saved_at", "") or ""
        count = row.get("count", 0) or 0
        kws = row.get("keywords", "") or ""
        cc1, cc2 = st.columns([6,2])
        with cc1:
            st.markdown(f"**{product}** · {saved_at} · {count}개")
            st.code(kws, language="text")
        with cc2:
            _copy_to_clipboard_button("복사", kws, key=f"ex_list_copy_{page}_{i}")

    # 페이지 네비게이션
    cprev, cnext = st.columns(2)
    with cprev:
        prev_dis = page <= 0
        if st.button("이전", disabled=prev_dis, key=f"ex_list_prev_{page}", use_container_width=True):
            st.session_state["ex_list_page"] = max(0, page - 1)
            st.experimental_rerun()
    with cnext:
        # next 가능성 판단: 현재 rows 수가 limit와 같으면 다음 페이지 시도 가능
        next_dis = len(rows) < limit
        if st.button("다음", disabled=next_dis, key=f"ex_list_next_{page}", use_container_width=True):
            st.session_state["ex_list_page"] = page + 1
            st.experimental_rerun()

# ===================== 차트 =====================
def _plot_cpc_curve_plotly_multi(kw: pd.DataFrame, selected: CpcCuts, bottoms: List[float], tops: List[float]) -> None:
    conv = kw[(kw["orders_14d"] > 0) & (kw["cpc"].notna())].copy()
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
    fig.add_vline(x=selected.bottom, line_dash="solid", opacity=1.0, line_color="blue", line_width=3)
    fig.add_vline(x=selected.top,    line_dash="solid", opacity=1.0, line_color="red",  line_width=3)
    for b in bottoms:
        fig.add_vline(x=b, line_dash="dot",  opacity=0.35, line_color="blue", line_width=1)
    for t in tops:
        fig.add_vline(x=t, line_dash="dash", opacity=0.35, line_color="red",  line_width=1)
    fig.update_layout(height=380, margin=dict(l=20, r=20, t=30, b=20),
                      xaxis_title="CPC", yaxis_title="누적매출비중(conv)",
                      yaxis=dict(tickformat=".0%"), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# ===================== 제외 로직/엔트리 =====================
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
        (aov_p50_value / ex_c["cost_after_1click"] * 100).replace([np.inf, -np.inf], 0).fillna(0).round(2)
        if aov_p50_value > 0 else 0.0
    )
    ex_c = ex_c[ex_c["roas_if_1_order"] <= float(breakeven_roas)].copy()
    ex_d = kw[(kw["roas_14d"] > 0) & (kw["roas_14d"] < float(breakeven_roas))].copy()
    return {"a": ex_a, "b": ex_b, "c": ex_c, "d": ex_d}

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
        c = int(sub["cost"].sum()); r = int(sub["revenue_14d"].sum()); o = int(sub["orders_14d"].sum())
        return {"영역": name, "광고비": c, "광고비비율(%)": round(_safe_div(c, total_cost) * 100, 2),
                "매출": r, "매출비율(%)": round(_safe_div(r, total_rev) * 100, 2),
                "주문": o, "주문비율(%)": round(_safe_div(o, total_orders) * 100, 2),
                "ROAS": round(_safe_div(r, c) * 100, 2)}

    rows = [_row("전체", df), _row("검색", df[df["surface"] == SURF_SEARCH_VALUE]), _row("비검색", df[df["surface"] != SURF_SEARCH_VALUE])]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("### 2) CPC-누적매출 비중")
    auto_cuts, conv = _compute_auto_cpc_cuts(kw)
    if conv.empty:
        st.caption("전환 발생 키워드가 없어 컷은 0으로 처리됩니다.")
        return

    bottom_lines, top_lines = _build_candidate_lines(conv, auto_cuts)
    if not bottom_lines or not top_lines:
        st.warning("후보 선이 없습니다. 데이터 분포를 확인하세요.")
        return

    if "sel_bottom_idx" not in st.session_state or "sel_top_idx" not in st.session_state:
        x = conv["cpc"].to_numpy(float)
        default_bottom = max(float(auto_cuts.bottom), _quantile_x(x, DEFAULT_FLOOR_Q))
        default_top = min(float(auto_cuts.top), _quantile_x(x, 1.0 - DEFAULT_CEIL_Q))
        st.session_state["sel_bottom_idx"] = int(np.argmin([abs(v - round(default_bottom, 2)) for v in bottom_lines]))
        st.session_state["sel_top_idx"] = int(np.argmin([abs(v - round(default_top, 2)) for v in top_lines]))

    def _clamp(i: int, n: int) -> int: return 0 if n <= 0 else int(max(0, min(i, n - 1)))
    st.session_state["sel_bottom_idx"] = _clamp(st.session_state["sel_bottom_idx"], len(bottom_lines))
    st.session_state["sel_top_idx"] = _clamp(st.session_state["sel_top_idx"], len(top_lines))

    c1, c2 = st.columns(2)
    with c1:
        ncols = min(10, len(bottom_lines)); idx = 0
        rows_btn = (len(bottom_lines) + ncols - 1) // ncols
        for _ in range(rows_btn):
            cols = st.columns(ncols)
            for c in range(ncols):
                if idx >= len(bottom_lines): break
                if cols[c].button(f"B{idx + 1}", key=f"btn_b_{idx}"): st.session_state["sel_bottom_idx"] = idx
                idx += 1
        b_idx = st.session_state["sel_bottom_idx"]
    with c2:
        ncols = min(10, len(top_lines)); idx = 0
        rows_btn = (len(top_lines) + ncols - 1) // ncols
        for _ in range(rows_btn):
            cols = st.columns(ncols)
            for c in range(ncols):
                if idx >= len(top_lines): break
                if cols[c].button(f"T{idx + 1}", key=f"btn_t_{idx}"): st.session_state["sel_top_idx"] = idx
                idx += 1
        t_idx = st.session_state["sel_top_idx"]

    sel_cuts = CpcCuts(bottom=float(bottom_lines[b_idx]), top=float(top_lines[t_idx]))
    _plot_cpc_curve_plotly_multi(kw, sel_cuts, bottom_lines, top_lines)

    shares = _search_shares_for_cuts(kw, sel_cuts)
    aov50 = _aov_p50(conv)
    st.markdown(
        f"""
- **CPC_cut bottom:** {sel_cuts.bottom:.2f}원  
  · 전체 매출 비중 {shares['rev_share_bottom']:.2f}% / 검색 매출 비중 {shares['rev_share_bottom_search']:.2f}%
  · 전체 광고비 비중 {shares['cost_share_bottom']:.2f}% / 검색 광고비 비중 {shares['cost_share_bottom_search']:.2f}%

- **CPC_cut top:** {sel_cuts.top:.2f}원  
  · 전체 매출 비중 {shares['rev_share_top']:.2f}% / 검색 매출 비중 {shares['rev_share_top_search']:.2f}%
  · 전체 광고비 비중 {shares['cost_share_top']:.2f}% / 검색 광고비 비중 {shares['cost_share_top_search']:.2f}%
""")

    st.markdown("### 3) 제외 키워드")
    exclusions = _compute_exclusions(kw, sel_cuts, aov50, float(breakeven_roas))
    _display_table("a) CPC_cut top 이상 전환 0", exclusions["a"])
    _display_table("b) CPC_cut bottom 이하 전환 0", exclusions["b"])
    _display_table("c) 전환 시 손익 ROAS 미달", exclusions["c"], extra=["roas_if_1_order"])
    _display_table("d) 손익 ROAS 미달", exclusions["d"])

    _render_exclusion_union(exclusions, supabase)         # 4)
    _render_saved_exclusions_list(supabase)               # 5) 목록형

# if __name__ == "__main__":
#     render_ad_analysis_tab(None)
