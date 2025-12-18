# path: app/tabs/ad_analysis_tab.py
from __future__ import annotations

import hashlib
import uuid
from typing import Dict

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt


# ====== 원시 데이터 컬럼명(표준) ======
DATE_COL = "날짜"
KW_COL = "키워드"
IMP_COL = "노출수"
CLK_COL = "클릭수"
COST_COL = "광고비"
ORD_COL = "총 주문수(14일)"
REV_COL = "총 전환매출액(14일)"


# ====== 유틸 ======
def _to_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0).round(0).astype(int)


def _to_date(s: pd.Series) -> pd.Series:
    """왜: 업로드 형식(문자/엑셀일/혼합)을 포괄 처리"""
    txt = s.astype(str).str.strip()
    dt_general = pd.to_datetime(txt, errors="coerce")

    digits = txt.str.replace(r"[^0-9]", "", regex=True)
    dt_8 = pd.to_datetime(digits.where(digits.str.len() == 8), format="%Y%m%d", errors="coerce")
    dt_6 = pd.to_datetime(digits.where(digits.str.len() == 6), format="%y%m%d", errors="coerce")

    num = pd.to_numeric(txt, errors="coerce")
    num = num.where(num.between(20000, 60000))
    dt_serial = pd.to_datetime(num, unit="D", origin="1899-12-30", errors="coerce")

    dt = dt_general.fillna(dt_8).fillna(dt_6).fillna(dt_serial)
    return dt.dt.date


def _is_search_keyword(x: str) -> bool:
    if x is None:
        return False
    t = str(x).strip()
    if t == "" or t == "-" or t.lower() == "nan":
        return False
    if "비검색" in t:
        return False
    return True


def _safe_div(a, b, default=0.0):
    a, b = float(a), float(b)
    return default if b == 0 else a / b


def _median_int(v) -> int:
    s = pd.Series(v)
    return int(s.median()) if not s.empty else 0


# ====== t(기본 임계치) ======
def calc_base_threshold_t(df: pd.DataFrame) -> Dict[str, int]:
    """
    t = 키워드별 '첫 주문 발생 시점까지' 누적 [활동일/노출/클릭]의 중앙값(P50).
    활동일: 노출>0인 날짜 수.
    """
    rows = []
    for kw, g in df.groupby("keyword"):
        g = g.sort_values("date")
        if not (g["orders_14d"] > 0).any():
            continue
        first_row = g[g["orders_14d"] > 0].iloc[0]
        rows.append(
            {
                "active_days": int((g.loc[:first_row.name, "impressions"] > 0).sum()),
                "impressions": int(g.loc[:first_row.name, "impressions"].sum()),
                "clicks": int(g.loc[:first_row.name, "clicks"].sum()),
            }
        )
    if not rows:
        return {"active_days": 0, "impressions": 0, "clicks": 0}
    tdf = pd.DataFrame(rows)
    return {
        "active_days": _median_int(tdf["active_days"]),
        "impressions": _median_int(tdf["impressions"]),
        "clicks": _median_int(tdf["clicks"]),
    }


# ====== hold_days(활동일만 교체: 누적 기대주문 >=1 최초시점) ======
def calc_hold_days_expected_ge1(df: pd.DataFrame, t: Dict[str, int]) -> int:
    """
    유보기간(활동일) = '전환 有 & 최종 누적이 t(활동일/노출/클릭) 충족' 키워드에서
    누적 기대주문(cum_expected = cum_clicks * final_cvr) >= 1 '최초 시점'까지의 활동일들의 중앙값(P50).
    final_cvr = total_orders / total_clicks  (total_clicks==0 제외)
    활동일: impressions>0인 날짜 수.
    """
    days = []
    for kw, g in df.groupby("keyword"):
        g = g.sort_values("date")

        total_orders = int(g["orders_14d"].sum())
        total_clicks = int(g["clicks"].sum())
        if total_orders <= 0 or total_clicks <= 0:
            continue

        total_impr = int(g["impressions"].sum())
        total_active_days = int(g.loc[g["impressions"] > 0, "date"].nunique())
        # 최종 누적이 t 충족
        if not (
            total_active_days >= int(t["active_days"])
            and total_impr >= int(t["impressions"])
            and total_clicks >= int(t["clicks"])
        ):
            continue

        final_cvr = total_orders / total_clicks  # 왜: 기대전환 계산의 안정 CVR
        cum_clicks = g["clicks"].cumsum()
        cum_expected = cum_clicks * final_cvr
        hit = g.loc[cum_expected >= 1]
        if hit.empty:
            continue

        first_idx = hit.index[0]
        active_until = int((g.loc[:first_idx, "impressions"] > 0).sum())
        days.append(active_until)

    return _median_int(days)


def build_min_conversion_condition(df: pd.DataFrame) -> Dict[str, int]:
    """
    '최소 전환 조건' 구성:
    - 활동일: hold_days_expected_ge1
    - 노출: t.impressions
    - 클릭: t.clicks
    """
    t = calc_base_threshold_t(df)
    hold_days = calc_hold_days_expected_ge1(df, t)
    return {"active_days": int(hold_days), "impressions": int(t["impressions"]), "clicks": int(t["clicks"])}


def format_min_condition_label(min_cond: Dict[str, int]) -> str:
    return f"최소 전환 조건 (운영{min_cond['active_days']}일 / 노출{min_cond['impressions']} / 클릭{min_cond['clicks']})"


# ====== 제외 d) 필터 ======
def filter_min_conversion_condition(kw_total: pd.DataFrame, min_cond: Dict[str, int]) -> pd.DataFrame:
    """
    제외 d) = 주문=0 & 활동일≥min_cond.active_days & 노출≥min_cond.impressions & 클릭≥min_cond.clicks
    """
    return kw_total[
        (kw_total["orders_14d"] == 0)
        & (kw_total["active_days"] >= int(min_cond["active_days"]))
        & (kw_total["impressions"] >= int(min_cond["impressions"]))
        & (kw_total["clicks"] >= int(min_cond["clicks"]))
    ].copy()


# ====== Streamlit 탭 렌더링 ======
def render_ad_analysis_tab(supabase):
    st.subheader("광고분석 (총 14일 기준)")

    up = st.file_uploader("로우데이터 업로드 (xlsx/csv)", type=["xlsx", "csv"], key="ad_up")
    if up is None:
        st.info("파일 업로드 후 분석 폼이 생성됩니다.")
        return

    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        product_name = st.text_input("상품명", value="", key="ad_product")
    with c2:
        target_roas = st.number_input("목표 ROAS", min_value=0.0, value=0.0, step=10.0, key="ad_target")
    with c3:
        breakeven_roas = st.number_input("손익분기 ROAS", min_value=0.0, value=0.0, step=10.0, key="ad_be")

    note = st.text_input("메모(선택)", value="", key="ad_note")

    if not product_name.strip():
        st.warning("상품명을 입력하세요.")
        return

    # 데이터 로드
    try:
        df_raw = pd.read_csv(up) if up.name.lower().endswith(".csv") else pd.read_excel(up)
    except Exception as e:
        st.error(f"파일 로드 실패: {e}")
        return

    required = [DATE_COL, KW_COL, IMP_COL, CLK_COL, COST_COL, ORD_COL, REV_COL]
    missing = [c for c in required if c not in df_raw.columns]
    if missing:
        st.error(f"필수 컬럼 누락: {missing}")
        return

    # 정규화
    df = df_raw.copy()
    df["date"] = _to_date(df[DATE_COL])
    df = df[df["date"].notna()].copy()
    df["keyword"] = df[KW_COL].astype(str).fillna("").str.strip()
    df["is_search"] = df["keyword"].map(_is_search_keyword)
    df["impressions"] = _to_int(df[IMP_COL])
    df["clicks"] = _to_int(df[CLK_COL])
    df["cost"] = _to_int(df[COST_COL])
    df["orders_14d"] = _to_int(df[ORD_COL])
    df["revenue_14d"] = _to_int(df[REV_COL])

    if df.empty:
        st.warning("유효한 데이터가 없습니다.")
        return

    date_min, date_max = df["date"].min(), df["date"].max()

    # 1) 기본 성과 지표
    st.markdown("### 1) 기본 성과 지표")
    st.caption(f"기간: {date_min} ~ {date_max}")

    total_cost = int(df["cost"].sum())
    total_rev = int(df["revenue_14d"].sum())
    total_orders = int(df["orders_14d"].sum())
    total_roas = round(_safe_div(total_rev, total_cost, 0) * 100, 2)

    df_search, df_non = df[df["is_search"]], df[~df["is_search"]]

    def _row(name, sub):
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
        {"영역": "전체", "광고비": total_cost, "광고비비율(%)": 100.0, "매출": total_rev, "매출비율(%)": 100.0, "주문": total_orders, "주문비율(%)": 100.0, "ROAS": total_roas},
        _row("검색", df_search),
        _row("비검색", df_non),
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # 2) 키워드 집계
    kw = (
        df.groupby(["keyword", "is_search"], as_index=False)[["impressions", "clicks", "cost", "orders_14d", "revenue_14d"]]
        .sum()
    )
    df_imp_pos = df[df["impressions"] > 0]
    days = df_imp_pos.groupby("keyword")["date"].nunique().reset_index(name="active_days")
    kw = kw.merge(days, on="keyword", how="left").fillna({"active_days": 0})
    kw["active_days"] = kw["active_days"].astype(int)
    kw["ctr"] = (kw["clicks"] / kw["impressions"]).fillna(0).round(6)
    kw["cpc"] = (kw["cost"] / kw["clicks"]).replace([np.inf, -np.inf], 0).fillna(0).round(2)
    kw["roas_14d"] = (kw["revenue_14d"] / kw["cost"] * 100).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    # 3) CPC-누적매출 비중 & 컷
    st.markdown("### 3) CPC-누적매출 비중 & 컷")
    conv = kw[kw["orders_14d"] > 0].sort_values("cpc")
    cpc_cut, cut_rev_share, aov_p50 = 0.0, 0.0, 0.0
    if conv.empty:
        st.warning("전환 발생 키워드가 없습니다. CPC_cut을 0으로 처리합니다.")
    else:
        total_conv_rev = conv["revenue_14d"].sum()
        conv["cum_rev"] = conv["revenue_14d"].cumsum()
        conv["cum_rev_share"] = (conv["cum_rev"] / total_conv_rev).clip(0, 1)
        # 간단한 Kneedle 유사 포인트
        x = conv["cpc"].to_numpy(dtype=float)
        y = conv["cum_rev_share"].to_numpy(dtype=float)
        if len(x) >= 3:
            x_n = (x - x.min()) / (x.max() - x.min() + 1e-12)
            y_n = (y - y.min()) / (y.max() - y.min() + 1e-12)
            idx = int(np.argmax(y_n - x_n))
            cpc_cut = float(x[idx])
        else:
            cpc_cut = float(x[-1])
        rev_above_cut = conv.loc[conv["cpc"] >= cpc_cut, "revenue_14d"].sum()
        cut_rev_share = round(_safe_div(rev_above_cut, total_conv_rev) * 100, 2)

        chart = alt.Chart(conv).mark_line().encode(x="cpc:Q", y="cum_rev_share:Q")
        vline = alt.Chart(pd.DataFrame({"c": [cpc_cut]})).mark_rule(strokeDash=[6, 4]).encode(x="c:Q")
        st.altair_chart(chart + vline, use_container_width=True)
        st.caption(f"CPC_cut: {round(cpc_cut, 2)}원 (누적매출 비중 {cut_rev_share}%)")

        aov = (conv["revenue_14d"] / conv["orders_14d"]).dropna()
        aov_p50 = float(aov.quantile(0.5)) if not aov.empty else 0.0

    # 4) 제외 키워드
    st.markdown("### 4) 제외 키워드")

    # a) CPC_cut 이상 전환 0
    ex_a = kw[(kw["orders_14d"] == 0) & (kw["cpc"] >= cpc_cut)].copy()

    # b) 운영 7일 이상 손익분기 미달
    ex_b = kw[(kw["active_days"] >= 7) & (kw["orders_14d"] > 0) & (kw["roas_14d"] < float(breakeven_roas))].copy()

    # c) 1클릭 추가해도 BE 미달(보수적)
    cpc_global_p50 = float(kw.loc[kw["clicks"] > 0, "cpc"].quantile(0.5)) if (kw["clicks"] > 0).any() else 0.0
    ex_c = kw[kw["orders_14d"] == 0].copy()
    ex_c["next_click_cost"] = np.where(ex_c["cpc"] > 0, ex_c["cpc"], cpc_global_p50)
    ex_c["cost_after_1click"] = ex_c["cost"] + ex_c["next_click_cost"]
    ex_c["roas_if_1_order"] = (aov_p50 / ex_c["cost_after_1click"] * 100).replace([np.inf, -np.inf], 0).fillna(0).round(2)
    ex_c = ex_c[ex_c["roas_if_1_order"] <= float(breakeven_roas)].copy()

    # d) 임계치 초과 전환 0  (== 최소 전환 조건)
    min_cond = build_min_conversion_condition(df)
    ex_d = filter_min_conversion_condition(kw, min_cond)

    def _show_df(title, dff, extra=None):
        st.markdown(f"#### {title} ({len(dff)}개)")
        cols = ["keyword", "active_days", "impressions", "clicks", "cost", "orders_14d", "revenue_14d", "ctr", "cpc", "roas_14d"]
        if extra:
            cols += extra
        st.dataframe(dff.sort_values("cost", ascending=False)[cols].head(200), use_container_width=True, hide_index=True)

    _show_df("a) CPC_cut 이상 전환 0", ex_a)
    _show_df("b) 운영 7일 이상 손익분기 미달", ex_b)
    _show_df("c) 전환 시 예상 ROAS 미달", ex_c, ["roas_if_1_order"])
    _show_df(f"d) {format_min_condition_label(min_cond)}", ex_d)

    # 5) 저장
    st.markdown("### 5) Supabase 저장")
    if st.button("✅ 분석 결과 저장", key="ad_save"):
        try:
            run_id = str(uuid.uuid4())
            file_sha1 = hashlib.sha1(up.getvalue()).hexdigest()
            st.caption(f"파일 해시: {file_sha1[:12]}…")

            supabase.table("ad_analysis_runs").insert(
                {
                    "run_id": run_id,
                    "product_name": product_name.strip(),
                    "source_filename": up.name,
                    "source_rows": len(df_raw),
                    "date_min": str(date_min),
                    "date_max": str(date_max),
                    "note": note,
                    "target_roas": float(target_roas),
                    "breakeven_roas": float(breakeven_roas),
                    "cpc_cut": float(round(cpc_cut, 2)),
                }
            ).execute()

            rows_kw = kw.assign(run_id=run_id)[
                ["run_id", "keyword", "is_search", "active_days", "impressions", "clicks", "cost", "orders_14d", "revenue_14d", "ctr", "cpc", "roas_14d"]
            ].to_dict(orient="records")
            for i in range(0, len(rows_kw), 1000):
                supabase.table("ad_analysis_keyword_total").upsert(rows_kw[i : i + 1000]).execute()

            artifacts = [
                {
                    "run_id": run_id,
                    "artifact_key": "settings",
                    "payload": {
                        "target_roas": target_roas,
                        "breakeven_roas": breakeven_roas,
                        "cpc_cut": float(round(cpc_cut, 2)),
                        "aov_p50": aov_p50,
                        "min_condition": min_cond,
                    },
                },
                {
                    "run_id": run_id,
                    "artifact_key": "exclusions",
                    "payload": {"a": ex_a["keyword"].tolist(), "b": ex_b["keyword"].tolist(), "c": ex_c["keyword"].tolist(), "d": ex_d["keyword"].tolist()},
                },
            ]
            supabase.table("ad_analysis_artifacts").upsert(artifacts).execute()
            st.success(f"저장 성공 (ID: {run_id})")
        except Exception as e:
            st.error(f"저장 실패: {e}")
