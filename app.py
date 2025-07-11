import streamlit as st
import os
import math

from config import DEFAULT_CONFIG_FILE, default_config, load_config, save_config
from utils  import compute_50pct_cost, format_number

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# ─── 설정 로드 (mtime 기반 캐시) ───
file_mtime = os.path.getmtime(DEFAULT_CONFIG_FILE) if os.path.exists(DEFAULT_CONFIG_FILE) else 0
config     = load_config(file_mtime)

# ─── 사이드바 ───
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
    val = st.sidebar.number_input(
        label,
        min_value=0.0,
        value=float(config.get(key, default_config[key])),
        step=1.0 if "RATE" not in key else 0.1
    )
    config[key] = val

if st.sidebar.button("📂 기본값으로 저장"):
    save_config(config)
    st.sidebar.success("기본값이 저장되었습니다.")

# ─── 탭 정의 ───
tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

with tab1:
    left, right = st.columns(2)

    with left:
        st.subheader("판매정보 입력")
        sell_price = st.number_input("판매가 (₩)", min_value=0, step=100, value=0, format="%d")
        qty        = st.number_input("수량",     min_value=1, step=1,   value=1, format="%d")

        unit_yuan = st.number_input("위안화 단가 (¥)", min_value=0.0, step=0.1, value=0.0)
        unit_won  = st.number_input("원화 단가 (₩)",   min_value=0,   step=100, value=0,   format="%d")

        # ─ 50% 목표 마진 계산 (수식 버전) ─
        if sell_price > 0:
            c50, p50 = compute_50pct_cost(sell_price, config, qty)
            y50 = math.ceil(c50 / config["EXCHANGE_RATE"])
            st.markdown(f"**마진율 50% 기준:** {format_number(c50)}원 ({y50}위안) / 마진: {format_number(p50)}원")

        if st.button("계산하기"):
            # ─ 단가×수량 계산 ─
            if unit_yuan > 0:
                unit_cost_val = unit_yuan * config["EXCHANGE_RATE"]
                cost_disp = f"{format_number(unit_cost_val)}원 ({unit_yuan}¥) × {qty}"
            else:
                unit_cost_val = unit_won
                cost_disp = f"{format_number(unit_cost_val)}원 × {qty}"

            vat = 1.1
            unit_cost = round(unit_cost_val * qty * vat)

            # ─ 기타 비용 계산 ─
            fee         = round((sell_price * config["FEE_RATE"] / 100) * vat)
            ad          = round((sell_price * config["AD_RATE"] / 100) * vat)
            inout       = round(config["INOUT_COST"] * vat) * qty
            pickup      = round(config["PICKUP_COST"] * vat) * qty
            restock     = round(config["RESTOCK_COST"] * vat) * qty
            return_cost = round((config["PICKUP_COST"] + config["RESTOCK_COST"]) * config["RETURN_RATE"] * vat) * qty
            etc         = round((sell_price * config["ETC_RATE"] / 100) * vat)
            packaging   = round(config["PACKAGING_COST"] * vat) * qty
            gift        = round(config["GIFT_COST"] * vat) * qty

            total_cost = unit_cost + fee + ad + inout + return_cost + etc + packaging + gift
            supply     = sell_price / vat
            profit     = sell_price - total_cost
            margin_rt  = profit / supply * 100 if supply else 0
            roi        = profit / unit_cost * 100 if unit_cost else 0

            st.markdown("### 📊 계산 결과")
            st.markdown(f"- 💰 마진: {format_number(profit)}원")
            st.markdown(f"- 📈 마진율: {margin_rt:.2f}%")
            st.markdown(f"- 💹 투자수익률: {roi:.2f}%")

            with st.expander("📦 상세 비용 보기"):
                st.markdown(f"**판매가:** {format_number(sell_price)}원")
                st.markdown(f"**원가:** {format_number(unit_cost)}원 ({cost_disp})")
                st.markdown(f"**수수료:** {format_number(fee)}원")
                st.markdown(f"**광고비:** {format_number(ad)}원")
                st.markdown(f"**입출고비용:** {format_number(inout)}원")
                st.markdown(f"**반품비용:** {format_number(return_cost)}원")
                st.markdown(f"**기타비용:** {format_number(etc)}원")
                st.markdown(f"**포장비용:** {format_number(packaging)}원")
                st.markdown(f"**사은품비용:** {format_number(gift)}원")
                st.markdown(f"**총비용:** {format_number(total_cost)}원")
                st.markdown(f"**공급가액:** {format_number(round(supply))}원")
                st.markdown(f"**최소 이익:** {format_number(profit)}원")
                st.markdown(f"**최소 마진율:** {margin_rt:.2f}%")
                st.markdown(f"**투자수익률:** {roi:.2f}%")

with tab2:
    st.subheader("세부 마진 계산기")
    st.info("준비 중입니다...")
