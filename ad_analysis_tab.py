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

# ====== 유틸 ======
def _to_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0).round(0).astype(int)

def _to_date(s: pd.Series) -> pd.Series:
    ss = s.copy()

    # 문자열화(혼합형 대비)
    txt = ss.astype(str).str.strip()

    # 1) 일반 파싱(YYYY-MM-DD, YYYY/MM/DD, datetime 등)
    dt_general = pd.to_datetime(txt, errors="coerce")

    # 2) 숫자만 추출해서 8자리/6자리 날짜 처리 (예: 20251216, 251216)
    digits = txt.str.replace(r"[^0-9]", "", regex=True)

    dt_8 = pd.to_datetime(
        digits.where(digits.str.len() == 8),
        format="%Y%m%d",
        errors="coerce"
    )
    dt_6 = pd.to_datetime(
        digits.where(digits.str.len() == 6),
        format="%y%m%d",
        errors="coerce"
    )

    # 3) 엑셀 시리얼 처리 (범위 제한: 너무 큰 숫자는 날짜가 아니라 코드값일 가능성 큼)
    num = pd.to_numeric(txt, errors="coerce")
    num = num.where(num.between(20000, 60000))  # 대략 1954~2064 범위
    dt_serial = pd.to_datetime(num, unit="D", origin="1899-12-30", errors="coerce")

    # 우선순위: 일반 → 8자리 → 6자리 → 시리얼
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
    a = float(a)
    b = float(b)
    return default if b == 0 else a / b

# Kneedle “유사” 방식(누적곡선에서 횡보 시작점): y-x 최대점
def find_cpc_cut_kneedle_like(df_conv_sorted: pd.DataFrame) -> float:
    # df_conv_sorted: CPC 오름차순, columns: cpc, cum_rev_share
    if df_conv_sorted.empty:
        return 0.0
    x = df_conv_sorted["cpc"].to_numpy(dtype=float)
    y = df_conv_sorted["cum_rev_share"].to_numpy(dtype=float)

    if len(x) < 3:
        return float(x[-1])

    # normalize to 0~1
    x_n = (x - x.min()) / (x.max() - x.min() + 1e-12)
    y_n = (y - y.min()) / (y.max() - y.min() + 1e-12)

    # knee index = argmax(y - x)
    diff = y_n - x_n
    idx = int(np.argmax(diff))
    return float(x[idx])

def choose_threshold_d(converted: pd.DataFrame, nonconv: pd.DataFrame):
    """
    d) 전환경향 임계치(운영일/노출/클릭) 조합 선택
    - 후보값: 전환키워드 분포의 분위수 기반(25/50/75) + 운영일수 7 포함
    - 목적함수: Youden's J = TPR - FPR 최대
      (동점이면 TPR 큰 것, FPR 작은 것 선호)
    """
    if converted.empty:
        return {"active_days": 0, "impressions": 0, "clicks": 0, "tpr": 0.0, "fpr": 0.0, "j": 0.0}

    def qvals(s):
        # 정수 후보 임계치 세트
        qs = s.quantile([0.25, 0.5, 0.75]).round(0).astype(int).tolist()
        qs = [int(x) for x in qs if int(x) >= 0]
        return sorted(list(set(qs)))

    cand_days = sorted(list(set(qvals(converted["active_days"]) + [7])))
    cand_imp = qvals(converted["impressions"])
    cand_clk = qvals(converted["clicks"])

    # 후보가 너무 빈약하면 최소 0 보강
    if not cand_imp: cand_imp = [0]
    if not cand_clk: cand_clk = [0]

    best = None
    for d in cand_days:
        for i in cand_imp:
            for c in cand_clk:
                tp = ((converted["active_days"] >= d) &
                      (converted["impressions"] >= i) &
                      (converted["clicks"] >= c)).mean()  # TPR
                fp = ((nonconv["active_days"] >= d) &
                      (nonconv["impressions"] >= i) &
                      (nonconv["clicks"] >= c)).mean() if not nonconv.empty else 0.0  # FPR
                j = tp - fp
                cand = {"active_days": int(d), "impressions": int(i), "clicks": int(c),
                        "tpr": float(tp), "fpr": float(fp), "j": float(j)}
                if best is None:
                    best = cand
                else:
                    # maximize J, tie-break: higher TPR, then lower FPR
                    if (cand["j"] > best["j"]) or \
                       (cand["j"] == best["j"] and cand["tpr"] > best["tpr"]) or \
                       (cand["j"] == best["j"] and cand["tpr"] == best["tpr"] and cand["fpr"] < best["fpr"]):
                        best = cand

    return best or {"active_days": 0, "impressions": 0, "clicks": 0, "tpr": 0.0, "fpr": 0.0, "j": 0.0}
    st.write("✅ TAB5 BUILD = 2025-12-17-01")
    st.write("✅ ad_analysis_tab.py =", __file__)

def render_ad_analysis_tab(supabase):
    st.subheader("광고분석 (총 14일 기준)")

    # (1) 업로드 + 입력
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

    # (2) 로드
    try:
        if up.name.lower().endswith(".csv"):
            df_raw = pd.read_csv(up)
        else:
            df_raw = pd.read_excel(up)
    except Exception as e:
        st.error(f"파일 로드 실패: {e}")
        return

    # (3) 필수 컬럼 확인
    required = [DATE_COL, KW_COL, IMP_COL, CLK_COL, COST_COL, ORD_COL, REV_COL]
    missing = [c for c in required if c not in df_raw.columns]
    if missing:
        st.error(f"필수 컬럼 누락: {missing}")
        st.dataframe(pd.DataFrame({"현재 컬럼": df_raw.columns}))
        return

    # (4) 정제
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

    date_min = df["date"].min()
    date_max = df["date"].max()

    # ====== (A) 전체 성과 + 검색/비검색 ======
    total_cost = int(df["cost"].sum())
    total_rev = int(df["revenue_14d"].sum())
    total_orders = int(df["orders_14d"].sum())
    total_roas = round(_safe_div(total_rev, total_cost, 0) * 100, 2)

    st.markdown("### 1) 기본 성과 지표")
    st.caption(f"기간: {date_min} ~ {date_max}")

    # 검색/비검색 분리
    df_search = df[df["is_search"] == True]
    df_non = df[df["is_search"] == False]

    def agg(sub):
        c = int(sub["cost"].sum())
        r = int(sub["revenue_14d"].sum())
        o = int(sub["orders_14d"].sum())
        ro = round(_safe_div(r, c, 0) * 100, 2)
        return c, r, o, ro

    s_cost, s_rev, s_orders, s_roas = agg(df_search)
    n_cost, n_rev, n_orders, n_roas = agg(df_non)

    # 비율 계산
    def pct(part, whole):
        return round(_safe_div(part, whole, 0) * 100, 2)

    rows = [
        {
            "영역": "전체",
            "광고비": total_cost,
            "광고비비율(%)": 100.00,
            "매출": total_rev,
            "매출비율(%)": 100.00,
            "주문": total_orders,
            "주문비율(%)": 100.00,
            "ROAS": total_roas,
        },
        {
            "영역": "검색",
            "광고비": s_cost,
            "광고비비율(%)": pct(s_cost, total_cost),
            "매출": s_rev,
            "매출비율(%)": pct(s_rev, total_rev),
            "주문": s_orders,
            "주문비율(%)": pct(s_orders, total_orders),
            "ROAS": s_roas,
        },
        {
            "영역": "비검색",
            "광고비": n_cost,
            "광고비비율(%)": pct(n_cost, total_cost),
            "매출": n_rev,
            "매출비율(%)": pct(n_rev, total_rev),
            "주문": n_orders,
            "주문비율(%)": pct(n_orders, total_orders),
            "ROAS": n_roas,
        },
    ]

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    perf_rate = 0.0 if target_roas == 0 else round(total_roas / float(target_roas), 4)
    st.write({
        "목표 ROAS": float(target_roas),
        "목표 대비 성과율(ROAS/목표ROAS)": perf_rate,
        "손익분기 ROAS": float(breakeven_roas),
    })

    # ====== (B) 키워드 집계 ======
    kw = (
        df.groupby(["keyword", "is_search"], as_index=False)[
            ["impressions", "clicks", "cost", "orders_14d", "revenue_14d"]
        ].sum()
    )

    # active_days: 노출수>0인 날짜 수
    df_imp_pos = df[df["impressions"] > 0]
    days = df_imp_pos.groupby("keyword")["date"].nunique().reset_index(name="active_days")
    kw = kw.merge(days, on="keyword", how="left").fillna({"active_days": 0})
    kw["active_days"] = kw["active_days"].astype(int)

    kw["ctr"] = (kw["clicks"] / kw["impressions"]).replace([np.inf, -np.inf], 0).fillna(0).round(6)
    kw["cpc"] = (kw["cost"] / kw["clicks"]).replace([np.inf, -np.inf], 0).fillna(0).round(2)
    kw["cvr"] = (kw["orders_14d"] / kw["clicks"]).replace([np.inf, -np.inf], 0).fillna(0).round(6)
    kw["roas_14d"] = (kw["revenue_14d"] / kw["cost"] * 100).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    st.markdown("### 2) 키워드 요약 TOP 50 (비용 기준)")
    st.dataframe(
        kw.sort_values(["cost", "revenue_14d"], ascending=[False, False]).head(50),
        use_container_width=True,
        hide_index=True
    )

    # ====== (C) CPC 누적매출 비중 + CPC_cut ======
    conv = kw[kw["orders_14d"] > 0].copy()
    conv = conv.sort_values("cpc", ascending=True)

    if conv.empty:
        cpc_cut = 0.0
        st.warning("전환 발생 키워드가 없습니다. CPC_cut을 0으로 처리합니다.")
        curve_payload = []
    else:
        total_conv_rev = conv["revenue_14d"].sum()
        conv["cum_rev"] = conv["revenue_14d"].cumsum()
        conv["cum_rev_share"] = (conv["cum_rev"] / (total_conv_rev if total_conv_rev > 0 else 1)).clip(0, 1)
        cpc_cut = round(find_cpc_cut_kneedle_like(conv[["cpc", "cum_rev_share"]]), 2)

        # 그래프 (matplotlib: 세로선 표시)
        st.markdown("### 3) CPC-누적매출 비중 곡선 + 횡보 시작점(CPC_cut)")

        chart_df = conv[["cpc", "cum_rev_share"]].copy()

        line = alt.Chart(chart_df).mark_line().encode(
            x=alt.X("cpc:Q", title="CPC"),
            y=alt.Y("cum_rev_share:Q", title="누적 매출 비중")
        )

        vline = alt.Chart(
            pd.DataFrame({"cpc_cut": [cpc_cut]})
        ).mark_rule(strokeDash=[6, 4]).encode(
            x="cpc_cut:Q"
        )

        st.altair_chart(line + vline, use_container_width=True)

    st.write({"CPC_cut": cpc_cut})

    # ====== (D) 제외 키워드 4종 ======
    st.markdown("### 4) 제외 키워드")

    # a) CPC_cut 이상 & 전환 0
    ex_a = kw[(kw["orders_14d"] == 0) & (kw["cpc"] >= cpc_cut)].copy()

    # b) 운영≥7일 & 전환 있음 & ROAS < 손익분기
    ex_b = kw[(kw["active_days"] >= 7) & (kw["orders_14d"] > 0) & (kw["roas_14d"] < float(breakeven_roas))].copy()

    # c) 전환0인데 1건 전환 가정 시 ROAS ≤ 손익분기
    # - 1건 매출은 "전환된 키워드의 주문당 매출(rev/orders) P50"로 가정
    if not conv.empty:
        aov = (conv["revenue_14d"] / conv["orders_14d"]).replace([np.inf, -np.inf], 0).fillna(0)
        aov_p50 = float(aov.quantile(0.5))
    else:
        aov_p50 = 0.0

    ex_c = kw[kw["orders_14d"] == 0].copy()
    ex_c["roas_if_1_order"] = (aov_p50 / ex_c["cost"] * 100).replace([np.inf, -np.inf], 0).fillna(0).round(2)
    ex_c = ex_c[ex_c["roas_if_1_order"] <= float(breakeven_roas)].copy()

    # d) 전환경향 임계치 충족 & 전환0
    converted = kw[kw["orders_14d"] > 0][["keyword", "active_days", "impressions", "clicks"]].copy()
    nonconv = kw[kw["orders_14d"] == 0][["keyword", "active_days", "impressions", "clicks"]].copy()

    best_th = choose_threshold_d(converted, nonconv)
    ex_d = kw[
        (kw["orders_14d"] == 0) &
        (kw["active_days"] >= best_th["active_days"]) &
        (kw["impressions"] >= best_th["impressions"]) &
        (kw["clicks"] >= best_th["clicks"])
    ].copy()

    st.write({
        "d 임계치 선택결과": best_th,
        "c 1건가정 주문당매출(P50)": round(aov_p50, 2)
    })

    # 출력 표(각 그룹)
    def show_df(title, dff, extra_cols=None):
        st.markdown(f"#### {title} ({len(dff)}개)")
        cols = ["keyword", "active_days", "impressions", "clicks", "cost", "orders_14d", "revenue_14d", "cpc", "roas_14d"]
        if extra_cols:
            cols += extra_cols
        exist = [c for c in cols if c in dff.columns]
        st.dataframe(dff.sort_values("cost", ascending=False)[exist].head(200), use_container_width=True, hide_index=True)

    show_df("a) CPC_cut 이상 & 전환0", ex_a)
    show_df("b) 운영≥7 & 전환있음 & ROAS<손익분기", ex_b)
    show_df("c) 전환0 & 1건가정 ROAS≤손익분기", ex_c, extra_cols=["roas_if_1_order"])
    show_df("d) 전환경향 임계치 충족 & 전환0", ex_d)

    # ====== (E) 저장 ======
    st.markdown("### 5) Supabase 저장")
    if st.button("✅ 분석 결과 저장", key="ad_save"):
        try:
            run_id = str(uuid.uuid4())
            file_sha1 = hashlib.sha1(up.getvalue()).hexdigest()  # 추적용(로우 저장은 안함)

            # runs
            supabase.table("ad_analysis_runs").insert({
                "run_id": run_id,
                "product_name": product_name.strip(),
                "source_filename": up.name,
                "source_rows": int(len(df_raw)),
                "date_min": str(date_min),
                "date_max": str(date_max),
                "note": note.strip() if note else None,
                "target_roas": float(target_roas),
                "breakeven_roas": float(breakeven_roas),
                "cpc_cut": float(cpc_cut),
            }).execute()

            # keyword_total
            payload_kw = kw.copy()
            payload_kw["run_id"] = run_id
            payload_kw = payload_kw.rename(columns={"keyword": "keyword"})
            rows_kw = payload_kw[[
                "run_id","keyword","is_search","active_days","impressions","clicks","cost","orders_14d","revenue_14d",
                "ctr","cpc","cvr","roas_14d"
            ]].to_dict(orient="records")

            def chunk(lst, n=1000):
                for i in range(0, len(lst), n):
                    yield lst[i:i+n]

            for part in chunk(rows_kw, 1000):
                supabase.table("ad_analysis_keyword_total").upsert(part).execute()

            # artifacts (그래프/임계치/제외리스트/권고슬롯)
            artifacts = [
                {"run_id": run_id, "artifact_key": "settings", "payload": {
                    "target_roas": float(target_roas),
                    "breakeven_roas": float(breakeven_roas),
                    "cpc_cut": float(cpc_cut),
                    "aov_p50": float(aov_p50),
                    "best_threshold_d": best_th,
                    "date_min": str(date_min),
                    "date_max": str(date_max),
                    "file_sha1": file_sha1
                }},
                {"run_id": run_id, "artifact_key": "chart_cpc_cumrev", "payload": curve_payload},
                {"run_id": run_id, "artifact_key": "exclusions", "payload": {
                    "a": ex_a["keyword"].tolist(),
                    "b": ex_b["keyword"].tolist(),
                    "c": ex_c["keyword"].tolist(),
                    "d": ex_d["keyword"].tolist(),
                }},
                {"run_id": run_id, "artifact_key": "recommendations_placeholder", "payload": {"items": []}},
            ]
            supabase.table("ad_analysis_artifacts").upsert(artifacts).execute()

            st.success(f"저장 완료: {product_name} / run_id={run_id}")

        except Exception as e:
            st.error(f"저장 실패: {e}")
