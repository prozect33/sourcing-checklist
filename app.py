# app.py
import streamlit as st
import json
import os
import math

from config import DEFAULT_CONFIG_FILE, default_config, load_config, save_config
from utils import compute_50pct_cost, format_number

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# ── 원본 그대로: 설정 로드, 기본값 채우기 ──
file_mtime = os.path.getmtime(DEFAULT_CONFIG_FILE) if os.path.exists(DEFAULT_CONFIG_FILE) else 0
config = load_config(file_mtime)
for k, v in default_config.items():
    if k not in config:
        config[k] = v

def reset_inputs():
    for key in ["sell_price_raw", "unit_yuan", "unit_won", "qty_raw"]:
        if key in st.session_state:
            st.session_state[key] = ""

# ── 원본 사이드바 ──
st.sidebar.header("🛠️ 설정값")
for key, label in [
    ("FEE_RATE", "수수료율 (%)"),
    ("AD_RATE", "광고비율 (%)"),
    ("INOUT_COST", "입출고비용 (원)"),
    ("PICKUP_COST", "회수비용 (원)"),
    ("RESTOCK_COST", "재입고비용 (원)"),
    ("RETURN_RATE", "반품률 (%)"),
    ("ETC_RATE", "기타비용률 (%)"),
    ("EXCHANGE_RATE", "위안화 환율"),
    ("PACKAGING_COST", "포장비용 (원)"),
    ("GIFT_COST", "사은품 비용 (원)")
]:
    val_str = st.sidebar.text_input(
        label,
        value=str(int(config[key])) if float(config[key]).is_integer() else str(config[key]),
        key=key
    )
    try:
        config[key] = float(val_str)
    except:
        pass

if st.sidebar.button("📂 기본값으로 저장"):
    save_config(config)
    st.sidebar.success("기본값이 저장되었습니다.")

tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

with tab1:
    left, right = st.columns(2)

    with left:
        st.subheader("판매정보 입력")

        # ── 원본 텍스트→숫자만 바뀜 ──
        sell_price_raw = st.number_input("판매가", min_value=0, step=100, value=0, format="%d", key="sell_price_raw")
        unit_yuan      = st.number_input("위안화 (¥)", min_value=0.0, step=0.1, value=0.0, key="unit_yuan")
        unit_won       = st.number_input("원화 (₩)", min_value=0, step=100, value=0, format="%d", key="unit_won")
        qty_raw        = st.number_input("수량",      min_value=1, step=1, value=1, format="%d", key="qty_raw")

        margin_display = st.empty()
        if sell_price_raw:
            # ── 원본 이분 탐색 → 수식 함수만 호출로 대체 ──
            target_cost, target_profit = compute_50pct_cost(sell_price_raw, config, qty_raw)
            yuan_cost = math.ceil(target_cost / config["EXCHANGE_RATE"])
            margin_display.markdown(f"""
<div style='height:10px; line-height:10px; color:#f63366; font-size:15px; margin-bottom:15px;'>
  마진율 50% 기준: {format_number(target_cost)}원 ({yuan_cost}위안) / 마진: {format_number(target_profit)}원
</div>""", unsafe_allow_html=True)
        else:
            margin_display.markdown("<div style='height:10px; margin-bottom:15px;'>&nbsp;</div>", unsafe_allow_html=True)

        calc_col, reset_col = st.columns(2)
        with calc_col:
            result = st.button("계산하기")
        with reset_col:
            st.button("리셋", on_click=reset_inputs)

    with right:
        if 'result' in locals() and result:
            # ── 원본 그대로: unit_cost 계산부에 qty만 곱함 ──
            try:
                sell_price = int(sell_price_raw)
                qty        = int(qty_raw)
            except:
                st.warning("판매가와 수량을 정확히 입력해주세요.")
                st.stop()

            if unit_yuan:
                unit_cost_val = round(unit_yuan * config["EXCHANGE_RATE"])
                cost_disp     = f"{format_number(unit_cost_val)}원 ({unit_yuan}위안)"
            else:
                unit_cost_val = round(unit_won)
                cost_disp     = f"{format_number(unit_cost_val)}원"

            vat       = 1.1
            unit_cost = round(unit_cost_val * vat) * qty

            fee         = round((sell_price * config["FEE_RATE"] / 100) * vat)
            ad          = round((sell_price * config["AD_RATE"] / 100) * vat)
            inout       = round(config["INOUT_COST"] * vat) * qty
            pickup      = round(config["PICKUP_COST"] * vat) * qty
            restock     = round(config["RESTOCK_COST"] * vat) * qty
            return_cost = round((config["PICKUP_COST"] + config["RESTOCK_COST"]) * config["RETURN_RATE"] * vat) * qty
            etc         = round((sell_price * config["ETC_RATE"] / 100))
            packaging   = round(config["PACKAGING_COST"] * vat) * qty
            gift        = round(config["GIFT_COST"] * vat) * qty

            total_cost = unit_cost + fee + ad + inout + return_cost + etc + packaging + gift
            supply2    = sell_price / vat
            profit2    = sell_price - total_cost
            margin_pf  = sell_price - (unit_cost + fee + inout)
            margin_rt  = round(margin_pf / supply2 * 100, 2)
            roi_margin = round(margin_pf / unit_cost * 100, 2) if unit_cost else 0
            roi        = round(profit2 / unit_cost * 100, 2) if unit_cost else 0

            st.markdown("### 📊 계산 결과")
            for bg, items in [
                ("#e8f5e9", [
                    ("💰 마진", f"{format_number(margin_pf)}원"),
                    ("📈 마진율", f"{margin_rt:.2f}%"),
                    ("💹 투자수익률", f"{roi_margin:.2f}%")
                ]),
                ("#e3f2fd", [
                    ("🧮 최소 이익", f"{format_number(profit2)}원"),
                    ("📉 최소마진율", f"{(profit2/supply2*100):.2f}%"),
                    ("🧾 투자수익률", f"{roi:.2f}%")
                ])
            ]:
                st.markdown(f"""
<div style='display:grid;grid-template-columns:1fr 1fr 1fr;background:{bg};padding:12px;border-radius:10px;gap:8px;margin-bottom:12px;'>
  <div><div style='font-weight:bold;'>{items[0][0]}</div><div>{items[0][1]}</div></div>
  <div><div style='font-weight:bold;'>{items[1][0]}</div><div>{items[1][1]}</div></div>
  <div><div style='font-weight:bold;'>{items[2][0]}</div><div>{items[2][1]}</div></div>
</div>""", unsafe_allow_html=True)

            with st.expander("📦 상세 비용 항목 보기"):
                # (이하 원본 expander 내용 그대로)
                …
with tab2:
    st.subheader("세부 마진 계산기")
    st.info("준비 중입니다...")
