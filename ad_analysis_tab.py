import streamlit as st
import pandas as pd
import numpy as np
import uuid
import hashlib
import altair as alt

# ====== 고정 컬럼(대표님 확정: 총(14일)) ======
DATE_COL = "날짜"
KW_COL = "키워드"
IMP_COL = "노출수"
CLK_COL = "클릭수"
COST_COL = "광고비"
ORD_COL = "총 주문수(14일)"
REV_COL = "총 전환매출액(14일)"

# ====== 유틸 함수 ======
def _to_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0).round(0).astype(int)

def _to_date(s: pd.Series) -> pd.Series:
    ss = s.copy()
    txt = ss.astype(str).str.strip()
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
    if x is None: return False
    t = str(x).strip()
    if t == "" or t == "-" or t.lower() == "nan": return False
    if "비검색" in t: return False
    return True

def _safe_div(a, b, default=0.0):
    a, b = float(a), float(b)
    return default if b == 0 else a / b

def find_cpc_cut_kneedle_like(df_conv_sorted: pd.DataFrame) -> float:
    if df_conv_sorted.empty: return 0.0
    x = df_conv_sorted["cpc"].to_numpy(dtype=float)
    y = df_conv_sorted["cum_rev_share"].to_numpy(dtype=float)
    if len(x) < 3: return float(x[-1])
    x_n = (x - x.min()) / (x.max() - x.min() + 1e-12)
    y_n = (y - y.min()) / (y.max() - y.min() + 1e-12)
    diff = y_n - x_n
    idx = int(np.argmax(diff))
    return float(x[idx])

# ====== 분석용 내부 계산 함수 ======
def calc_min_order_threshold_from_first_conversion(df):
    rows = []
    for kwd, g in df.groupby("keyword"):
        g = g.sort_values("date").copy()
        hit = g[g["orders_14d"] > 0]
        if hit.empty: continue
        first = hit.iloc[0]
        rows.append({
            "active_days": (g.loc[:first.name, "impressions"] > 0).sum(),
            "impressions": g.loc[:first.name, "impressions"].sum(),
            "clicks": g.loc[:first.name, "clicks"].sum(),
        })
    if not rows:
        return {"active_days": 0, "impressions": 0, "clicks": 0}
    tdf = pd.DataFrame(rows)
    return {
        "active_days": int(tdf["active_days"].median()),
        "impressions": int(tdf["impressions"].median()),
        "clicks": int(tdf["clicks"].median()),
    }

def calc_first_conv_active_days_median(df):
    days = []
    for kwd, g in df.groupby("keyword"):
        g = g.sort_values("date").copy()
        hit = g[g["orders_14d"] > 0]
        if hit.empty: continue
        first = hit.iloc[0]
        active_days_until = (g.loc[:first.name, "impressions"] > 0).sum()
        days.append(active_days_until)
    if not days: return 0
    return int(pd.Series(days).median())

# ====== 메인 렌더링 함수 ======
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

    date_min, date_max = df["date"].min(), df["date"].max()

    # 1) 기본 성과 지표
    st.markdown("### 1) 기본 성과 지표")
    st.caption(f"기간: {date_min} ~ {date_max}")

    total_cost, total_rev, total_orders = int(df["cost"].sum()), int(df["revenue_14d"].sum()), int(df["orders_14d"].sum())
    total_roas = round(_safe_div(total_rev, total_cost, 0) * 100, 2)

    df_search, df_non = df[df["is_search"]], df[~df["is_search"]]
    
    def get_row(name, sub, t_cost, t_rev, t_ord):
        c, r, o = int(sub["cost"].sum()), int(sub["revenue_14d"].sum()), int(sub["orders_14d"].sum())
        return {
            "영역": name, "광고비": c, "광고비비율(%)": round(_safe_div(c, t_cost)*100, 2),
            "매출": r, "매출비율(%)": round(_safe_div(r, t_rev)*100, 2),
            "주문": o, "주문비율(%)": round(_safe_div(o, t_ord)*100, 2),
            "ROAS": round(_safe_div(r, c)*100, 2)
        }

    rows = [
        {"영역": "전체", "광고비": total_cost, "광고비비율(%)": 100.0, "매출": total_rev, "매출비율(%)": 100.0, "주문": total_orders, "주문비율(%)": 100.0, "ROAS": total_roas},
        get_row("검색", df_search, total_cost, total_rev, total_orders),
        get_row("비검색", df_non, total_cost, total_rev, total_orders)
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # 2) 키워드 집계
    kw = df.groupby(["keyword", "is_search"], as_index=False)[["impressions", "clicks", "cost", "orders_14d", "revenue_14d"]].sum()
    df_imp_pos = df[df["impressions"] > 0]
    days = df_imp_pos.groupby("keyword")["date"].nunique().reset_index(name="active_days")
    kw = kw.merge(days, on="keyword", how="left").fillna({"active_days": 0})
    kw["active_days"] = kw["active_days"].astype(int)
    kw["ctr"] = (kw["clicks"] / kw["impressions"]).fillna(0).round(6)
    kw["cpc"] = (kw["cost"] / kw["clicks"]).replace([np.inf, -np.inf], 0).fillna(0).round(2)
    kw["roas_14d"] = (kw["revenue_14d"] / kw["cost"] * 100).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    # 3) CPC 누적매출 비중 + CPC_cut
    cpc_cut, cut_rev_share, aov_p50 = 0.0, 0.0, 0.0
    conv = kw[kw["orders_14d"] > 0].sort_values("cpc")

    if conv.empty:
        st.warning("전환 발생 키워드가 없습니다. CPC_cut을 0으로 처리합니다.")
    else:
        total_conv_rev = conv["revenue_14d"].sum()
        conv["cum_rev"] = conv["revenue_14d"].cumsum()
        conv["cum_rev_share"] = (conv["cum_rev"] / total_conv_rev).clip(0, 1)
        cpc_cut = round(find_cpc_cut_kneedle_like(conv[["cpc", "cum_rev_share"]]), 2)
        rev_above_cut = conv.loc[conv["cpc"] >= cpc_cut, "revenue_14d"].sum()
        cut_rev_share = round(_safe_div(rev_above_cut, total_conv_rev) * 100, 2)
        
        st.markdown("### 3) CPC-누적매출 비중 곡선 + 횡보 시작점(CPC_cut)")
        chart = alt.Chart(conv).mark_line().encode(x="cpc:Q", y="cum_rev_share:Q")
        vline = alt.Chart(pd.DataFrame({"c": [cpc_cut]})).mark_rule(strokeDash=[6, 4]).encode(x="c:Q")
        st.altair_chart(chart + vline, use_container_width=True)
        st.caption(f"CPC_cut: {cpc_cut}원 ({cut_rev_share}%)")
        
        aov = (conv["revenue_14d"] / conv["orders_14d"]).dropna()
        aov_p50 = float(aov.quantile(0.5)) if not aov.empty else 0.0

    # 4) 제외 키워드 로직
    st.markdown("### 4) 제외 키워드")
    ex_a = kw[(kw["orders_14d"] == 0) & (kw["cpc"] >= cpc_cut)].copy()
    ex_b = kw[(kw["active_days"] >= 7) & (kw["orders_14d"] > 0) & (kw["roas_14d"] < float(breakeven_roas))].copy()

    cpc_global_p50 = float(kw.loc[kw["clicks"] > 0, "cpc"].quantile(0.5)) if (kw["clicks"] > 0).any() else 0.0
    ex_c = kw[kw["orders_14d"] == 0].copy()
    ex_c["next_click_cost"] = np.where(ex_c["cpc"] > 0, ex_c["cpc"], cpc_global_p50)
    ex_c["cost_after_1click"] = ex_c["cost"] + ex_c["next_click_cost"]
    ex_c["roas_if_1_order"] = (aov_p50 / ex_c["cost_after_1click"] * 100).fillna(0).round(2)
    ex_c = ex_c[ex_c["roas_if_1_order"] <= float(breakeven_roas)].copy()

    t = calc_min_order_threshold_from_first_conversion(df)
    first_conv_days = calc_first_conv_active_days_median(df)
    ex_d = kw[(kw["orders_14d"] == 0) & (kw["active_days"] >= first_conv_days) & 
              (kw["impressions"] >= t["impressions"]) & (kw["clicks"] >= t["clicks"])]

    def show_df(title, dff, extra=None):
        st.markdown(f"#### {title} ({len(dff)}개)")
        cols = ["keyword", "active_days", "impressions", "clicks", "cost", "orders_14d", "revenue_14d", "cpc", "roas_14d"]
        if extra: cols += extra
        st.dataframe(dff.sort_values("cost", ascending=False)[cols].head(200), use_container_width=True, hide_index=True)

    show_df("a) CPC_cut 이상 전환 0", ex_a)
    show_df("b) 운영 7일 이상 손익분기 미달", ex_b)
    show_df("c) 전환 시 예상 ROAS 미달", ex_c, ["roas_if_1_order"])
    show_df(f"d) 임계치 초과 전환 0 (운영{first_conv_days}일/노출{t['impressions']}/클릭{t['clicks']})", ex_d)

    # 5) 저장
    st.markdown("### 5) Supabase 저장")
    if st.button("✅ 분석 결과 저장", key="ad_save"):
        try:
            run_id = str(uuid.uuid4())
            file_sha1 = hashlib.sha1(up.getvalue()).hexdigest()
            supabase.table("ad_analysis_runs").insert({
                "run_id": run_id, "product_name": product_name.strip(), "source_filename": up.name,
                "source_rows": len(df_raw), "date_min": str(date_min), "date_max": str(date_max),
                "note": note, "target_roas": float(target_roas), "breakeven_roas": float(breakeven_roas), "cpc_cut": float(cpc_cut)
            }).execute()
            
            # 키워드 데이터 업로드 (청크 단위)
            rows_kw = kw.assign(run_id=run_id)[["run_id","keyword","is_search","active_days","impressions","clicks","cost","orders_14d","revenue_14d","ctr","cpc","roas_14d"]].to_dict(orient="records")
            for i in range(0, len(rows_kw), 1000):
                supabase.table("ad_analysis_keyword_total").upsert(rows_kw[i:i+1000]).execute()

            artifacts = [
                {"run_id": run_id, "artifact_key": "settings", "payload": {"target_roas": target_roas, "breakeven_roas": breakeven_roas, "cpc_cut": cpc_cut, "aov_p50": aov_p50}},
                {"run_id": run_id, "artifact_key": "exclusions", "payload": {"a": ex_a["keyword"].tolist(), "b": ex_b["keyword"].tolist(), "c": ex_c["keyword"].tolist(), "d": ex_d["keyword"].tolist()}}
            ]
            supabase.table("ad_analysis_artifacts").upsert(artifacts).execute()
            st.success(f"저장 성공 (ID: {run_id})")
        except Exception as e:
            st.error(f"저장 실패: {e}")
