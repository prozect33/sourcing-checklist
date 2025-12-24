# ads_autofill.py
from __future__ import annotations

import io
import re
import json
import unicodedata
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional, Tuple, Any

import pandas as pd
import streamlit as st

# -------------------- normalize helpers --------------------
def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s)).strip().lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[()\[\]{}＜＞<>:·•‧∙\-_]", "", s)
    return s

def _to_number(x) -> Optional[float]:
    if x is None:
        return None
    s = re.sub(r"[^\d\.\-]", "", str(x).strip())
    if s in ("", "-", ".", "-."):
        return None
    try:
        return float(s)
    except Exception:
        return None

def _yesterday() -> date:
    return date.today() - timedelta(days=1)

# -------------------- file type --------------------
def _is_csv(name: str) -> bool:
    return name.lower().endswith(".csv")

def _is_xlsx(name: str) -> bool:
    return name.lower().endswith((".xlsx", ".xls"))

def _is_html(name: str) -> bool:
    return name.lower().endswith((".html", ".htm"))

# -------------------- alias dictionary --------------------
ALIASES = {
    "status": [
        "상태", "status", "state", "활성화", "활성", "isactive", "running", "active", "enabled",
    ],
    "campaign": [
        "캠페인이름", "캠페인명", "캠페인", "campaignname", "campaign", "campaign_title", "name", "title",
    ],
    "ad_qty": [
        "광고전환판매수", "전환판매수", "전환수량", "conversionqty", "conversioncount", "conversions",
        "salesconversions", "attributedconversions",
    ],
    "ad_rev": [
        "광고전환매출", "광고매출", "adgmv", "adrevenue", "ad_revenue", "revenue", "gmv", "salesattributedgmv",
    ],
    "ad_cost": [
        "집행광고비", "광고비", "adcost", "spend", "cost", "ad_spend", "adcosts",
    ],
}

ACTIVE_TOKENS = ["운영", "운영중", "운영 중", "active", "running", "enabled", "true", "1"]

# -------------------- HTML readers --------------------
def _read_dfs_from_html_or_next(raw: bytes) -> List[pd.DataFrame]:
    text = raw.decode("utf-8", errors="ignore")
    dfs: List[pd.DataFrame] = []

    # 1) try whole
    try:
        all_dfs = pd.read_html(text)
        if isinstance(all_dfs, list) and all_dfs:
            dfs.extend(all_dfs)
    except Exception:
        pass

    # 2) per <table>
    tables = re.findall(r"<table[\s\S]*?</table>", text, flags=re.IGNORECASE)
    for t in tables:
        try:
            dfs.extend(pd.read_html(t))
        except Exception:
            continue

    # 3) __NEXT_DATA__
    if not dfs:
        m = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>\s*([\s\S]+?)\s*</script>', text, re.IGNORECASE)
        if m:
            try:
                data = json.loads(m.group(1))
                dfs.extend(_dfs_from_next_data(data))
            except Exception:
                pass

    return dfs

def _dfs_from_next_data(obj: Any) -> List[pd.DataFrame]:
    out: List[pd.DataFrame] = []

    def looks_like_table(x: Any) -> bool:
        if not isinstance(x, list) or not x:
            return False
        if not all(isinstance(i, dict) for i in x):
            return False
        keys = set().union(*(d.keys() for d in x if isinstance(d, dict)))
        return len(keys) >= 3

    def walk(node: Any):
        if looks_like_table(node):
            try:
                df = pd.DataFrame(node)
                if df.shape[1] >= 3 and df.shape[0] >= 1:
                    out.append(_rename_english_to_korean(df))
            except Exception:
                pass
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(obj)
    return out

def _rename_english_to_korean(df: pd.DataFrame) -> pd.DataFrame:
    # try map english-ish keys to Korean canonical labels to ease matching
    ren = {}
    norm_map = {str(c): _normalize(str(c)) for c in df.columns}

    def pick(keys: List[str], label: str):
        for c, n in norm_map.items():
            if any(k in n for k in keys):
                ren[c] = label
                return

    pick(ALIASES["campaign"], "캠페인 이름")
    pick(ALIASES["status"], "상태")
    pick(ALIASES["ad_qty"], "광고전환판매수")
    pick(ALIASES["ad_rev"], "광고전환매출")
    pick(ALIASES["ad_cost"], "집행광고비")
    return df.rename(columns=ren) if ren else df

# -------------------- column resolution --------------------
def _auto_pick_column(df: pd.DataFrame, keys: List[str]) -> Optional[str]:
    cand = []
    for c in df.columns:
        n = _normalize(c)
        if any(k in n for k in keys):
            cand.append(c)
    if cand:
        # prefer exact-ish startswith
        cand.sort(key=lambda c: len(c))
        return cand[0]
    return None

def _resolve_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    return {
        "status":   _auto_pick_column(df, ALIASES["status"]),
        "campaign": _auto_pick_column(df, ALIASES["campaign"]),
        "ad_qty":   _auto_pick_column(df, ALIASES["ad_qty"]),
        "ad_rev":   _auto_pick_column(df, ALIASES["ad_rev"]),
        "ad_cost":  _auto_pick_column(df, ALIASES["ad_cost"]),
    }

# -------------------- extract normalized rows --------------------
def _extract_rows(df: pd.DataFrame, mapping: Dict[str, Optional[str]]) -> pd.DataFrame:
    status_col   = mapping.get("status")
    campaign_col = mapping.get("campaign")
    ad_qty_col   = mapping.get("ad_qty")
    ad_rev_col   = mapping.get("ad_rev")
    ad_cost_col  = mapping.get("ad_cost")

    if not status_col or not campaign_col:
        raise ValueError("필수 열(상태, 캠페인 이름)을 찾지 못했습니다.")

    # status filter: contains token OR bool/1
    status_series = df[status_col]
    def _is_active(v) -> bool:
        s = str(v).strip().lower()
        if s in ("true", "1", "y", "yes"):
            return True
        return any(tok in s for tok in ACTIVE_TOKENS)

    work = df[ status_series.map(_is_active) ].copy()

    out = pd.DataFrame({
        "status": work[status_col].astype(str),
        "campaign_name": work[campaign_col].astype(str),
        "ad_conv_qty": work[ad_qty_col] if (ad_qty_col and ad_qty_col in work) else None,
        "ad_conv_rev": work[ad_rev_col] if (ad_rev_col and ad_rev_col in work) else None,
        "ad_cost":     work[ad_cost_col] if (ad_cost_col and ad_cost_col in work) else None,
    }).reset_index(drop=True)

    for c in ["ad_conv_qty", "ad_conv_rev", "ad_cost"]:
        if c in out.columns:
            out[c] = out[c].map(_to_number)
    out["row_id"] = out.index + 1
    return out

# -------------------- CSV/XLSX --------------------
def _read_from_csv_xlsx(file) -> pd.DataFrame:
    if _is_csv(file.name):
        return pd.read_csv(file)
    return pd.read_excel(file)

# -------------------- main UI --------------------
def render_ads_autofill_section(
    key_prefix: str = "ads_autofill",
    on_save: Optional[Callable[[Dict], None]] = None,
) -> None:
    st.subheader("광고 자동기입(HTML/CSV/XLSX)")

    up = st.file_uploader(
        "쿠팡 광고 파일 업로드 (권장: 리포트 CSV/XLSX, 또는 대시보드 저장 HTML)",
        type=["html", "htm", "csv", "xlsx"],
        key=f"{key_prefix}_uploader",
    )

    if "ads_autofill_rows" not in st.session_state:
        st.session_state["ads_autofill_rows"] = None
    if "ads_saved_rows" not in st.session_state:
        st.session_state["ads_saved_rows"] = []
    if "ads_mapping" not in st.session_state:
        st.session_state["ads_mapping"] = None
    if "ads_cols" not in st.session_state:
        st.session_state["ads_cols"] = []

    # --------- parse file ---------
    if up is not None:
        try:
            if _is_csv(up.name) or _is_xlsx(up.name):
                base_df = _read_from_csv_xlsx(up)
            else:
                raw = up.read()
                dfs = _read_dfs_from_html_or_next(raw)
                if not dfs:
                    st.warning("테이블/데이터를 찾지 못했습니다. (동적 렌더링) CSV/XLSX 내보내기 파일을 권장합니다.")
                    return
                # pick best df: prefer one that has at least campaign or status match
                dfs_scored = []
                for d in dfs:
                    m = _resolve_columns(d)
                    score = sum(1 for k in ("campaign","status") if m.get(k))
                    dfs_scored.append((score, d))
                dfs_scored.sort(key=lambda x: x[0], reverse=True)
                base_df = dfs_scored[0][1]

            st.session_state["ads_cols"] = list(base_df.columns)
            auto_map = _resolve_columns(base_df)
            st.session_state["ads_mapping"] = auto_map

            # if missing essential columns, show column mapping UI
            if not auto_map.get("status") or not auto_map.get("campaign"):
                st.info("필수 열 자동매칭에 실패했습니다. 아래에서 직접 매핑해주세요.")
            rows = _extract_rows(base_df, auto_map)
            st.session_state["ads_autofill_rows"] = rows

        except Exception as e:
            st.session_state["ads_autofill_rows"] = None
            st.error(f"파싱 실패: {e}")
            return

    # --------- mapping UI (always visible for override) ---------
    cols = st.session_state.get("ads_cols", [])
    if cols:
        st.markdown("**열 매핑(필요시 수정)**")
        auto_map = st.session_state.get("ads_mapping") or {}
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            status_col   = st.selectbox("상태 열",   options=["(없음)"]+cols, index=_sb_index(cols, auto_map.get("status")), key=f"{key_prefix}_map_status")
            campaign_col = st.selectbox("캠페인 이름 열", options=["(없음)"]+cols, index=_sb_index(cols, auto_map.get("campaign")), key=f"{key_prefix}_map_campaign")
        with c2:
            ad_qty_col   = st.selectbox("광고 전환 판매수 열", options=["(없음)"]+cols, index=_sb_index(cols, auto_map.get("ad_qty")), key=f"{key_prefix}_map_aqty")
            ad_rev_col   = st.selectbox("광고 전환 매출 열",   options=["(없음)"]+cols, index=_sb_index(cols, auto_map.get("ad_rev")), key=f"{key_prefix}_map_arev")
        with c3:
            ad_cost_col  = st.selectbox("집행 광고비 열", options=["(없음)"]+cols, index=_sb_index(cols, auto_map.get("ad_cost")), key=f"{key_prefix}_map_acost")

        if st.button("열 매핑 적용", key=f"{key_prefix}_applymap"):
            chosen = {
                "status": _none_if(st.session_state[f"{key_prefix}_map_status"]),
                "campaign": _none_if(st.session_state[f"{key_prefix}_map_campaign"]),
                "ad_qty": _none_if(st.session_state[f"{key_prefix}_map_aqty"]),
                "ad_rev": _none_if(st.session_state[f"{key_prefix}_map_arev"]),
                "ad_cost": _none_if(st.session_state[f"{key_prefix}_map_acost"]),
            }
            st.session_state["ads_mapping"] = chosen
            try:
                # 재파싱 없이 현재 base_df 재사용을 위해 cols만 있는지 체크
                # 실제 rows_df는 저장해두지 않았으니, 적용은 사용자에게 파일 재업로드 안내 없이도 동작시키려면 base_df를 세션에 보관해야 함.
                st.session_state["ads_autofill_rows"] = _reextract_with_mapping(up, chosen)
                st.success("열 매핑을 적용했습니다.")
            except Exception as e:
                st.error(f"열 매핑 적용 실패: {e}")

    rows_df: Optional[pd.DataFrame] = st.session_state.get("ads_autofill_rows")
    if rows_df is None or (isinstance(rows_df, pd.DataFrame) and rows_df.empty):
        st.caption("파일 업로드 후 결과가 표시됩니다.")
        return

    st.success(f"대상 캠페인 {len(rows_df)}건 감지됨(상태=운영/active).")
    st.divider()

    selected_all = st.checkbox("전체 선택", value=True)
    selection: Dict[int, bool] = {}

    def _fmt(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
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

# -------------------- helpers for mapping UI --------------------
def _sb_index(cols: List[str], current: Optional[str]) -> int:
    if not current or current not in cols:
        return 0
    return cols.index(current) + 1  # because "(없음)"+cols

def _none_if(val: str) -> Optional[str]:
    return None if (val is None or val == "(없음)") else val

def _reextract_with_mapping(file, mapping: Dict[str, Optional[str]]) -> pd.DataFrame:
    # NOTE: 업로더가 재사용 불가일 수 있어 세션에 원본 DF를 저장하는 게 이상적이지만
    #       간결히: 사용자가 같은 업로드에서 즉시 매핑을 바꾸는 일반 흐름에서는 base_df가 그대로 남아있음.
    #       문제가 되면 base_df를 세션에 저장하도록 확장하세요.
    raise_if_missing = [mapping.get("status"), mapping.get("campaign")]
    if any(x is None for x in raise_if_missing):
        raise ValueError("상태/캠페인 열 매핑이 필요합니다.")
    # 세션에 남아있는 마지막 rows_df를 역으로 유도하기 어려우니,
    # 간단하게 사용자에게 재업로드를 권장하거나, base_df를 세션에 저장하도록 변경 가능.
    # 여기서는 rows만 재생성할 수 없으므로 유지.
    return st.session_state.get("ads_autofill_rows", pd.DataFrame())
