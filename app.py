import streamlit as st
import json
import os

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
                return {k: float(v) if isinstance(v, str) and v.replace(".", "", 1).isdigit() else v for k, v in data.items()}
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

if st.sidebar.button("💾 기본값으로 저장"):
    save_config(config)
    st.sidebar.success("기본값이 저장되었습니다.")

tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

with tab1:
    left, right = st.columns(2)

    with left:
        st.subheader("판매정보 입력")
        sell_price_raw = st.text_input("판매가", value=st.session_state.get("sell_price_raw", ""), key="sell_price_raw")

        col1, col2 = st.columns([1, 1])
        with col1:
            unit_yuan = st.text_input("위안화 (¥)", value=st.session_state.get("unit_yuan", ""), key="unit_yuan")
        with col2:
            unit_won = st.text_input("원화 (₩)", value=st.session_state.get("unit_won", ""), key="unit_won")

        qty_raw = st.text_input("수량", value=st.session_state.get("qty_raw", "1"), key="qty_raw")

        col_calc, col_reset = st.columns([1, 1])
        with col_calc:
            result = st.button("계산하기")
        with col_reset:
            st.button("리셋", on_click=reset_inputs, key="reset_button")

    with right:
        st.markdown("🛠 **디버깅 체크포인트 1: with right 진입 성공**")

        if 'result' in locals() and result:
            st.markdown("🟢 **디버깅 체크포인트 2: 계산 버튼 눌림 감지**")

            try:
                sell_price = int(float(sell_price_raw)) if sell_price_raw else None
                qty = int(float(qty_raw)) if qty_raw else None
            except:
                sell_price, qty = None, None

            if sell_price is None or qty is None:
                st.warning("판매가와 수량을 정확히 입력해주세요.")
                st.markdown("🔴 **디버깅: 판매가 또는 수량 None**")
            else:
                st.markdown("🟢 **디버깅 체크포인트 3: 판매가/수량 파싱 성공**")
                try:
                    if unit_yuan:
                        unit_cost_val = round(float(unit_yuan) * float(config['EXCHANGE_RATE']))
                        cost_display = f"{format_number(unit_cost_val)}원 ({unit_yuan}위안)"
                    elif unit_won:
                        unit_cost_val = round(float(unit_won))
                        cost_display = f"{format_number(unit_cost_val)}원"
                    else:
                        unit_cost_val = 0
                        cost_display = "0원"
                    unit_cost = unit_cost_val
                except:
                    unit_cost = 0
                    cost_display = "0원"

                fee = round((sell_price * float(config["FEE_RATE"]) * 1.1) / 100)
                ad = round((sell_price * float(config["AD_RATE"]) * 1.1) / 100)
                inout = round(float(config["INOUT_COST"]) * 1.1)
                pickup = round(float(config["PICKUP_COST"]) * 1.1)
                restock = round(float(config["RESTOCK_COST"]) * 1.1)
                return_rate = float(config["RETURN_RATE"])
                return_cost = round((pickup + restock) * return_rate)
                etc = round(sell_price * float(config["ETC_RATE"]) / 100 * 1.1)
                total_cost = round(unit_cost + fee + ad + inout + return_cost + etc)
                profit = sell_price - total_cost
                supply_price = sell_price / 1.1
                margin = round((profit / supply_price) * 100, 2) if supply_price != 0 else 0
                roi = round((profit / unit_cost) * 100, 2) if unit_cost != 0 else 0

                margin_profit = sell_price - (unit_cost + fee + inout)
                margin_ratio = round((margin_profit / supply_price) * 100, 2) if supply_price else 0
                roi_margin = round((margin_profit / unit_cost) * 100, 2) if unit_cost else 0

                st.markdown("🟢 **디버깅 체크포인트 4: 계산 로직 완료**")
                st.markdown(f"🔍 margin_profit: {margin_profit}, roi_margin: {roi_margin}, roi: {roi}")

                st.markdown("### 📊 계산 결과")

                cols1 = st.columns([1, 1, 1, 1, 1, 1, 1])
                labels1 = ["마진", "마진율", "투자수익률(마진 기준)"]
                values1 = [
                    f"{format_number(margin_profit)}원",
                    f"{margin_ratio:.2f}%",
                    f"{roi_margin:.2f}%"
                ]
                for i in range(3):
                    with cols1[i + 2]:
                        st.markdown(f"**{labels1[i]}**")
                        st.markdown(f"<div style='font-size: 16px;'>{values1[i]}</div>", unsafe_allow_html=True)

                cols2 = st.columns([1, 1, 1, 1, 1, 1, 1])
                labels2 = ["최소 이익", "최소마진율", "투자수익률(전체 기준)"]
                values2 = [
                    f"{format_number(profit)}원",
                    f"{margin:.2f}%",
                    f"{roi:.2f}%"
                ]
                for i in range(3):
                    with cols2[i + 2]:
                        st.markdown(f"**{labels2[i]}**")
                        st.markdown(f"<div style='font-size: 16px;'>{values2[i]}</div>", unsafe_allow_html=True)

                st.markdown("<div style='height: 95px;'></div>", unsafe_allow_html=True)
