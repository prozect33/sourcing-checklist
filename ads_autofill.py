
from __future__ import annotations

import io
import re
import unicodedata
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

def _normalize_label(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s)).strip().lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[()\[\]{}＜＞<>:·•‧∙\-\_]", "", s)
    return s

def _contains_all(label: str, keywords: List[str]) -> bool:
    return all(k in label for k in keywords)

def _guess_column(df: pd.DataFrame, *, must_all: Optional[List[str]] = None, any_of: Optional[List[str]] = None) -> Optional[str]:
    labels = {c: _normalize_label(c) for c in df.columns}
    if must_all:
        for c, n in labels.items():
            if _contains_all(n, must_all):
                return c
    if any_of:
        for kw in any_of:
            for c, n in labels.items():
                if kw in n:
                    return c
    return None

def _to_number(x) -> Optional[float]:
    if x is None: return None
    s = re.sub(r"[^\d\.\-]", "", str(x).strip())
    if s in ("", "-", ".", "-."): return None
    try: return float(s)
    except Exception: return None

def _yesterday() -> date:
    return date.today() - timedelta(days=1)

def _read_tables_from_html(raw: bytes) -> List[pd.DataFrame]:
    text = raw.decode("utf-8", errors="ignore")
    try:
        dfs = pd.read_html(text)
        if dfs: return dfs
    except Exception:
        pass
    soup = BeautifulSoup(text, "html.parser")
    dfs: List[pd.DataFrame] = []
    for t in soup.find_all("table"):
        try:
            dfs.extend(pd.read_html(str(t)))
        except Exception:
            continue
    return dfs

def _find_best_table(dfs: List[pd.DataFrame]) -> Optional[pd.DataFrame]:
    def score_df(df: pd.DataFrame) -> Tuple[int, int]:
        cols = [_normalize_label(c) for c in df.columns]
        req_all = [
            (["상태"], 2),
            (["캠페인", "이름"], 3),
        ]
        req_any = [
            (["집행", "광고비", "adcost", "cost"], 2),
            (["광고전환매출", "광고매출", "adgmv", "전환매출"], 1),
            (["광고전환판매수", "전환판매수", "전환수량", "conversionqty"], 1),
        ]
        strict, hits = 0, 0
        for keys, w in req_all:
            ok = any(_contains_all(c, keys) for c in cols)
            if ok: strict += 1; hits += w
        for keys, w in req_any:
            ok = any(all(k in c for k in keys) or any(k in c for k in keys) for c in cols)
            if ok: hits += w
        return strict, hits

    best, best_key = None, (-1, -1)
    for df in dfs:
        sc = score_df(df)
        if sc > best_key:
            best, best_key = df, sc
    return best

def _extract_campaign_rows(df: pd.DataFrame) -> pd.DataFrame:
    status_col = _guess_column(df, must_all=["상태"])
    campaign_col = _guess_column(df, must_all=["캠페인", "이름"])
    ad_cost_col = _guess_column(df, any_of=["집행", "광고비", "adcost", "cost"])
    ad_rev_col  = _guess_column(df, any_of=["광고전환매출", "광고매출", "adgmv", "전환매출"])
    ad_qty_col  = _guess_column(df, any_of=["광고전환판매수", "전환판매수", "전환수량", "conversionqty"])
    if not status_col or not campaign_col:
        raise ValueError("필수 열(상태, 캠페인 이름)을 찾지 못했습니다.")

    work_df = df[df[status_col].astype(str).str.contains("운영", na=False)].copy()
    out = pd.DataFrame({
        "status": work_df[status_col].astype(str),
        "campaign_name": work_df[campaign_col].astype(str),
        "ad_conv_qty": work_df[ad_qty_col] if ad_qty_col in work_df else None,
        "ad_conv_rev": work_df[ad_rev_col] if ad_rev_col in work_df else None,
        "ad_cost": work_df[ad_cost_col] if ad_cost_col in work_df else None,
    }).reset_index(drop=True)

    for c in ["ad_conv_qty", "ad_conv_rev", "ad_cost"]:
        if c in out.columns:
            out[c] = out[c].map(_to_number)
    out["row_id"] = out.index + 1
    return out

def render_ads_autofill_section(
    key_prefix: str = "ads_autofill",
    on_save: Optional[Callable[[Dict], None]] = None,
) -> None:
    st.subheader("광고 자동기입(HTML)")
    up = st.file_uploader("광고 리포트 HTML 업로드", type=["html", "htm"], key=f"{key_prefix}_uploader")

    if "ads_autofill_rows" not in st.session_state:
        st.session_state["ads_autofill_rows"] = None
    if "ads_saved_rows" not in st.session_state:
        st.session_state["ads_saved_rows"] = []

    if up is not None:
        raw = up.read()
        dfs = _read_tables_from_html(raw)
        if not dfs:
            st.warning("테이블을 찾지 못했습니다.")
            return
        best = _find_best_table(dfs)
        if best is None:
            st.warning("필수 열을 가진 테이블을 찾지 못했습니다.")
            return
        try:
            rows = _extract_campaign_rows(best)
        except Exception as e:
            st.error(f"파싱 실패: {e}")
            return
        if rows.empty:
            st.info("상태에 '운영'이 포함된 캠페인이 없습니다.")
            st.session_state["ads_autofill_rows"] = None
            return
        st.session_state["ads_autofill_rows"] = rows

    rows_df: Optional[pd.DataFrame] = st.session_state.get("ads_autofill_rows")
    if rows_df is None or (isinstance(rows_df, pd.DataFrame) and rows_df.empty):
        st.caption("파일 업로드 후 결과가 표시됩니다.")
        return

    st.success(f"대상 캠페인 {len(rows_df)}건 감지됨(상태에 '운영' 포함).")
    st.divider()

    selected_all = st.checkbox("전체 선택", value=True)
    selection: Dict[int, bool] = {}

    def _fmt(v):
        if v is None or (isinstance(v, float) and pd.isna(v)): return ""
        try:
            f = float(v)
            return str(int(f)) if f.is_integer() else str(f)
        except Exception:
            return str(v)

    for _, r in rows_df.iterrows():
        rid = int(r["row_id"])
        with st.container(border=True):
            st.markdown(f"**캠페인 #{rid}**")
            selection[rid] = st.checkbox("저장 대상", value=selected_all, key=f"sel_{rid}")

            dt = st.date_input("날짜", value=_yesterday(), key=f"date_{rid}")

            base_name = r.get("campaign_name", "") or ""
            st.text_input("상품명(캠페인 이름, 읽기전용)", value=base_name, disabled=True, key=f"base_{rid}")
            alias = st.text_input("기입 상품명(미기입시 캠페인 이름 사용)", value=base_name, key=f"alias_{rid}")

            total_qty   = st.text_input("전체 판매 수량", value="", key=f"tqty_{rid}")
            total_rev   = st.text_input("전체 매출액", value="", key=f"trev_{rid}")
            coupon_unit = st.text_input("개당 쿠폰가", value="", key=f"cpn_{rid}")

            ad_qty  = st.text_input("광고 전환 판매 수량", value=_fmt(r.get("ad_conv_qty")), key=f"aqty_{rid}")
            ad_rev  = st.text_input("광고 매출액(광고 전환 매출)", value=_fmt(r.get("ad_conv_rev")), key=f"arev_{rid}")
            ad_cost = st.text_input("광고 비용(집행 광고비)", value=_fmt(r.get("ad_cost")), key=f"acost_{rid}")

            if st.button("이 행 저장", key=f"save_{rid}"):
                row = {
                    "date": str(dt),
                    "product_name": (alias or "").strip() or base_name,
                    "campaign_name": base_name,
                    "total_sales_qty": _to_number(total_qty) or 0,
                    "total_revenue": _to_number(total_rev) or 0.0,
                    "coupon_unit": _to_number(coupon_unit) or 0.0,
                    "ad_sales_qty": _to_number(ad_qty) or 0,
                    "ad_revenue": _to_number(ad_rev) or 0.0,
                    "ad_cost": _to_number(ad_cost) or 0.0,
                }
                if on_save:
                    on_save(row)
                st.session_state["ads_saved_rows"].append(row)
                st.success(f"#{rid} 저장됨: {row['product_name']}")

    st.divider()
    if st.button("선택한 항목 모두 저장"):
        count = 0
        for _, r in rows_df.iterrows():
            rid = int(r["row_id"])
            if not selection.get(rid): 
                continue
            base_name = st.session_state.get(f"base_{rid}", "")
            alias     = st.session_state.get(f"alias_{rid}", "") or base_name
            dt        = st.session_state.get(f"date_{rid}", _yesterday())
            row = {
                "date": str(dt),
                "product_name": alias,
                "campaign_name": base_name,
                "total_sales_qty": _to_number(st.session_state.get(f"tqty_{rid}", "")) or 0,
                "total_revenue": _to_number(st.session_state.get(f"trev_{rid}", "")) or 0.0,
                "coupon_unit": _to_number(st.session_state.get(f"cpn_{rid}", "")) or 0.0,
                "ad_sales_qty": _to_number(st.session_state.get(f"aqty_{rid}", "")) or 0,
                "ad_revenue": _to_number(st.session_state.get(f"arev_{rid}", "")) or 0.0,
                "ad_cost": _to_number(st.session_state.get(f"acost_{rid}", "")) or 0.0,
            }
            if on_save:
                on_save(row)
            st.session_state["ads_saved_rows"].append(row)
            count += 1
        st.success(f"일괄 저장 완료: {count}건")

    saved_rows = st.session_state.get("ads_saved_rows", [])
    if saved_rows:
        st.write("저장 데이터(미연동 환경 미리보기):")
        out_df = pd.DataFrame(saved_rows)
        st.dataframe(out_df, use_container_width=True)

        csv = io.StringIO()
        out_df.to_csv(csv, index=False, encoding="utf-8-sig")
        st.download_button(
            "CSV 다운로드",
            data=csv.getvalue().encode("utf-8-sig"),
            file_name=f"daily_settlement_ad_autofill_{date.today().isoformat()}.csv",
            mime="text/csv",
        )
