import streamlit as st
import math

def calculate_target_cost(selling_price, target_margin_rate, config):
    left, right = 0, selling_price
    result_cost = 0
    vat = 1.1
    while left <= right:
        mid = (left + right) // 2
        fee = round((selling_price * config["FEE_RATE"] * vat) / 100)
        ad_fee = round((selling_price * config["AD_RATE"] * vat) / 100)
        inout_cost = round(config["INOUT_COST"] * vat)
        return_cost = round((config["PICKUP_COST"] + config["RESTOCK_COST"]) * config["RETURN_RATE"] * vat)
        etc_cost = round(selling_price * (config["ETC_RATE"] / 100))
        total_cost = round(mid + fee + ad_fee + inout_cost + return_cost + etc_cost)
        profit = selling_price - total_cost
        supply_price = selling_price / vat
        margin_rate = round((profit / supply_price) * 100, 2)

        if margin_rate < target_margin_rate:
            right = mid - 1
        else:
            result_cost = mid
            left = mid + 1

    yuan_cost = math.ceil(result_cost / config["EXCHANGE_RATE"])
    return result_cost, yuan_cost, selling_price - result_cost

st.set_page_config(page_title="마진 테스트")

st.header("🔍 50% 마진 기준 원가 테스트")

config = {
    "FEE_RATE": 10.8,
    "AD_RATE": 20.0,
    "INOUT_COST": 3000,
    "PICKUP_COST": 1500,
    "RESTOCK_COST": 500,
    "RETURN_RATE": 0.1,
    "ETC_RATE": 2.0,
    "EXCHANGE_RATE": 350
}

sell_price_raw = st.text_input("판매가 입력", value="")

margin_50_placeholder = st.empty()

cleaned = sell_price_raw.strip().replace(",", "")
if cleaned:
    try:
        sell_price = int(float(cleaned))
        cost_won_50, cost_yuan_50, margin_50 = calculate_target_cost(sell_price, 50.0, config)
        margin_50_placeholder.markdown(
            f"<div style='margin-top: 12px; font-weight: 500;'>"
            f"마진율 50% 기준: {cost_won_50:,}원 ({cost_yuan_50}위안), 마진: {margin_50:,}원"
            f"</div>",
            unsafe_allow_html=True
        )
    except Exception as e:
        margin_50_placeholder.markdown(f"<span style='color:red;'>에러: {e}</span>", unsafe_allow_html=True)
else:
    margin_50_placeholder.markdown("<div style='height: 1em;'></div>", unsafe_allow_html=True)
