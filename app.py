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
                return {k: float(v) if isinstance(v, str) and v.replace('.', '', 1).isdigit() else v
                        for k, v in data.items()}
        except:
            return default_config
    return default_config

def save_config(config):
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        json.dump(config, f)

def format_number(val):
    return f"{int(val):,}" if float(val).is_integer() else f"{val:,.2f}"

def format_input_value(val):
    return str(int(val)) if float(val).is_integer() else str(val)

def reset_inputs():
    for k in ["sell_price_raw", "unit_yuan", "unit_won", "qty_raw"]:
        if k in st.session_state:
            st.session_state[k] = ""

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
    config[key] = st.sidebar.text_input(label, format_input_value(config[key]), key=key)
if st.sidebar.button("📂 기본값으로 저장"):
    save_config(config)
    st.sidebar.success("저장되었습니다")

tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

with tab1:
    left, right = st.columns(2)
    with left:
        st.subheader("판매정보 입력")
        sell_price_raw = st.text_input("판매가", st.session_state.get("sell_price_raw", ""), key="sell_price_raw")

        # → 출력 자리 미리 확보 (빈 칸)
        result_placeholder = st.empty()

        if sell_price_raw:
            try:
                sell_price = int(float(sell_price_raw))
                vat = 1.1
                fee = round((sell_price * float(config["FEE_RATE"]) / 100) * vat)
                ad  = round((sell_price * float(config["AD_RATE"]) / 100) * vat)
                inc = round(float(config["INOUT_COST"]) * vat)
                pk  = round(float(config["PICKUP_COST"]) * vat)
                rs  = round(float(config["RESTOCK_COST"]) * vat)
                ret = round((pk + rs) * float(config["RETURN_RATE"]))
                etc = round((sell_price * float(config["ETC_RATE"]) / 100))

                def cost_for_margin(rate):
                    lo, hi = 0, sell_price
                    best_cost, best_profit = 0, 0
                    while lo <= hi:
                        mid = (lo + hi) // 2
                        total = mid + fee + ad + inc + ret + etc
                        prof  = sell_price - total
                        mrt   = round((prof / (sell_price / vat)) * 100, 2)
                        if mrt < rate:
                            hi = mid - 1
                        else:
                            best_cost, best_profit = mid, prof
                            lo = mid + 1
                    return best_cost, best_profit

                cost50, profit50 = cost_for_margin(50.0)
                yuan50 = math.ceil(cost50 / float(config["EXCHANGE_RATE"]))

                # 최종 한 줄 출력 (두 번째 줄 제거)
                result_placeholder.markdown(
                    f"📌 마진율 50% 기준: {format_number(cost50)}원 ({yuan50}위안), 마진: {format_number(profit50)}원"
                )
            except:
                result_placeholder.empty()
                st.warning("판매가를 숫자로 정확히 입력해주세요.")

        col1, col2 = st.columns(2)
        with col1:
            unit_yuan = st.text_input("단가 (위안)", st.session_state.get("unit_yuan", ""), key="unit_yuan")
        with col2:
            unit_won  = st.text_input("단가 (원)",  st.session_state.get("unit_won",  ""), key="unit_won")
        qty_raw = st.text_input("수량", st.session_state.get("qty_raw", "1"), key="qty_raw")

        calc_col, reset_col = st.columns(2)
        with calc_col:
            do_calc = st.button("계산하기")
        with reset_col:
            st.button("리셋", on_click=reset_inputs)

    with right:
        if 'do_calc' in locals() and do_calc:
            # (기존 계산 결과 표시 부분 그대로 유지)
            # …
            pass  # 생략
            

with tab2:
    st.subheader("세부 마진 계산기")
    st.info("준비 중입니다...")
