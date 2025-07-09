import streamlit as st
import json
import os

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

DEFAULT_CONFIG_FILE = "default_config.json"
default_config = {
    "FEE_RATE": 10.8,
    "AD_RATE": 20.0,
st.markdown("""
<style>
div[data-testid="metric-container"] > div {
    font-size: 18px !important;
}
div[data-testid="metric-container"] > label {
    font-size: 14px !important;
}
</style>
""", unsafe_allow_html=True)
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

config = load_config()
st.markdown("""
<style>
div[data-testid="metric-container"] > div {
    font-size: 18px !important;
}
div[data-testid="metric-container"] > label {
    font-size: 14px !important;
}
</style>
""", unsafe_allow_html=True)

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

def reset_inputs():
    for key in ["sell_price_raw", "unit_yuan", "unit_won", "qty_raw"]:
        if key in st.session_state:
            st.session_state[key] = ""

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
        if 'result' in locals() and result:
            try:
                sell_price = int(float(sell_price_raw)) if sell_price_raw else None
                qty = int(float(qty_raw)) if qty_raw else None
            except:
                sell_price, qty = None, None

            if sell_price is None or qty is None:
                st.warning("판매가와 수량을 정확히 입력해주세요.")
            else:
                try:
                    if unit_yuan:
                        unit_cost_val = round(float(unit_yuan) * float(config["EXCHANGE_RATE"]))
                        cost_display = f"{format_number(unit_cost_val)}원 (위안화 입력 환산: {unit_yuan} × {config['EXCHANGE_RATE']})"
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
            st.markdown("### 📊 계산 결과")
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("판매가", f"{format_number(sell_price)}원")
            col2.metric("원가", cost_display)
            col3.metric("ROI", f"{roi:.2f}%")
            col4.metric("최소 이익", f"{format_number(profit)}원")
            col5.metric("최소마진율", f"{margin:.2f}%")
            with st.expander("📦 상세 비용 항목 보기"):
                st.write(f"**수수료:** {format_number(fee)}원 (판매가 × {config['FEE_RATE']}% × 1.1)")
                st.write(f"**광고비:** {format_number(ad)}원 (판매가 × {config['AD_RATE']}% × 1.1)")
                st.write(f"**입출고비용:** {format_number(inout)}원 ({format_number(config['INOUT_COST'])} × 1.1)")
                st.write(f"**회수비용:** {format_number(pickup)}원 ({format_number(config['PICKUP_COST'])} × 1.1)")
                st.write(f"**재입고비용:** {format_number(restock)}원 ({format_number(config['RESTOCK_COST'])} × 1.1)")
                st.write(f"**반품비용:** {format_number(return_cost)}원 ((({format_number(config['PICKUP_COST'])} × 1.1) + ({format_number(config['RESTOCK_COST'])} × 1.1)) × {return_rate * 100:.1f}%)")
                st.write(f"**기타비용:** {format_number(etc)}원 (판매가 × {config['ETC_RATE']}% × 1.1)")
                st.write(f"**총비용:** {format_number(total_cost)}원 (원가 + 위 항목 합산)")
                st.write(f"**공급가액:** {format_number(round(supply_price))}원 (판매가 ÷ 1.1)")
            pass  # placeholder to avoid IndentationError