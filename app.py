import streamlit as st
import json
import os
import math

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

DEFAULT_CONFIG_FILE = "default_config.json"
default_config = {
    "FEE_RATE": 10.8,
    "AD_RATE": 20.0,
    "INOUT_COST": 3000,
    "PICKUP_COST": 1500,
    "RESTOCK_COST": 500,
    "RETURN_RATE": 0.1,
    "ETC_RATE": 2.0,
    "EXCHANGE_RATE": 350
}

def load_config():
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, "r") as f:
                data = json.load(f)
                return {k: float(v) if isinstance(v, str) and v.replace('.', '', 1).isdigit() else v for k, v in data.items()}
        except:
            return default_config
    else:
        return default_config

def save_config(config):
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        json.dump(config, f)

def format_number(val):
    return f"{int(val):,}" if float(val).is_integer() else f"{val:,.2f}"

def format_input_value(val):
    return str(int(val)) if float(val).is_integer() else str(val)

def reset_inputs():
    for key in ["sell_price_raw", "unit_yuan", "unit_won", "qty_raw"]:
        if key in st.session_state:
            st.session_state[key] = ""

config = load_config()

st.sidebar.header("🛠️ 설정값")
for key, label in [
    ("FEE_RATE", "수수료율 (%)"),
    ("AD_RATE", "광고비율 (%)"),
    ("INOUT_COST", "입출고비용 (원)"),
    ("PICKUP_COST", "회수비용 (원)"),
    ("RESTOCK_COST", "재입고비용 (원)"),
    ("RETURN_RATE", "반품률 (%)"),
    ("ETC_RATE", "기타비용률 (%)"),
    ("EXCHANGE_RATE", "위안화 환율")
]:
    config[key] = st.sidebar.text_input(label, value=format_input_value(config[key]), key=key)

if st.sidebar.button("📂 기본값으로 저장"):
    save_config(config)
    st.sidebar.success("기본값이 저장되었습니다.")

tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

with tab1:
    left, right = st.columns(2)

    with left:
        st.subheader("판매정보 입력")
        sell_price_raw = st.text_input("판매가", value=st.session_state.get("sell_price_raw", ""), key="sell_price_raw")

        # 공간 확보 및 결과 출력 영역
        margin_display = st.empty()

        if sell_price_raw.strip():
            try:
                target_margin = 50.0
                sell_price_val = int(float(sell_price_raw))
                fee = round((sell_price_val * float(config['FEE_RATE']) * 1.1) / 100)
                ad_fee = round((sell_price_val * float(config['AD_RATE']) * 1.1) / 100)
                inout_cost = round(float(config['INOUT_COST']) * 1.1)
                return_cost = round((float(config['PICKUP_COST']) + float(config['RESTOCK_COST'])) * float(config['RETURN_RATE']) * 1.1)
                etc_cost = round(sell_price_val * float(config['ETC_RATE']) / 100)
                supply_price = sell_price_val / 1.1

                left_b, right_b = 0, sell_price_val
                target_cost = 0
                while left_b <= right_b:
                    mid = (left_b + right_b) // 2
                    total_cost = round(mid + fee + ad_fee + inout_cost + return_cost + etc_cost)
                    profit = sell_price_val - total_cost
                    margin = profit / supply_price * 100
                    if margin < target_margin:
                        right_b = mid - 1
                    else:
                        target_cost = mid
                        left_b = mid + 1
                yuan_cost = math.ceil(target_cost / float(config["EXCHANGE_RATE"]))
                profit = sell_price_val - (target_cost + fee + ad_fee + inout_cost + return_cost + etc_cost)

                margin_display.markdown(f"""
<div style='color:#f63366; font-size:15px; line-height:1.6;'>
  마진율 {int(target_margin)}% 기준: {format_number(target_cost)}원 ({yuan_cost}위안)<br>
  마진: {format_number(profit)}원
</div>
""", unsafe_allow_html=True)
            except:
                pass
        else:
            # 초기 공간 확보용 (48px)
            margin_display.markdown("<div style='height:48px;'></div>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            unit_yuan = st.text_input("위안화 (¥)", value=st.session_state.get("unit_yuan", ""), key="unit_yuan")
        with col2:
            unit_won = st.text_input("원화 (₩)", value=st.session_state.get("unit_won", ""), key="unit_won")
        qty_raw = st.text_input("수량", value=st.session_state.get("qty_raw", "1"), key="qty_raw")
        calc_col, reset_col = st.columns(2)
        with calc_col:
            result = st.button("계산하기")
        with reset_col:
            st.button("리셋", on_click=reset_inputs)

    with right:
        # 계산 결과 표시 영역 (변경 없음)
        pass  # 기존 결과 영역 그대로 유지

with tab2:
    st.subheader("세부 마진 계산기")
    st.info("준비 중입니다...")
