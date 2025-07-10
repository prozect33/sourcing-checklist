import streamlit as st
import json
import os
import math

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

DEFAULT_CONFIG_FILE = "default_config.json"
default_config = {
    "FEE_RATE": 10.8, "AD_RATE": 20.0,
    "INOUT_COST": 3000, "PICKUP_COST": 1500, "RESTOCK_COST": 500,
    "RETURN_RATE": 0.1, "ETC_RATE": 2.0,
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
        st.session_state.pop(k, None)

config = load_config()

# ── 사이드바 설정 ──
st.sidebar.header("🛠️ 설정값")
for key, label in [
    ("FEE_RATE","수수료율 (%)"),("AD_RATE","광고비율 (%)"),
    ("INOUT_COST","입출고비용 (원)"),("PICKUP_COST","회수비용 (원)"),
    ("RESTOCK_COST","재입고비용 (원)"),("RETURN_RATE","반품률 (%)"),
    ("ETC_RATE","기타비용률 (%)"),("EXCHANGE_RATE","위안화 환율")
]:
    config[key] = st.sidebar.text_input(label, format_input_value(config[key]), key=key)
if st.sidebar.button("📂 기본값으로 저장"):
    save_config(config)
    st.sidebar.success("저장되었습니다")

tab1, tab2 = st.tabs(["간단 마진 계산기","세부 마진 계산기"])
with tab1:
    left, right = st.columns(2)
    with left:
        st.subheader("판매정보 입력")
        sell_price_raw = st.text_input("판매가", st.session_state.get("sell_price_raw",""), key="sell_price_raw")

        # 1) 결과 컨테이너 확보 (고정 높이 div 만 렌더)
        result_container = st.empty()
        result_container.markdown(
            "<div style='position:relative; height:1.5em;'></div>",
            unsafe_allow_html=True
        )

        # 2) 실제 계산 후, div 위에 절대 위치로 텍스트 오버레이
        if sell_price_raw:
            try:
                sell_price = int(float(sell_price_raw))
                vat = 1.1
                fee  = round((sell_price * config["FEE_RATE"]/100)*vat)
                ad   = round((sell_price * config["AD_RATE"]/100)*vat)
                inc  = round(config["INOUT_COST"]*vat)
                pk   = round(config["PICKUP_COST"]*vat)
                rs   = round(config["RESTOCK_COST"]*vat)
                ret  = round((pk+rs)*config["RETURN_RATE"])
                etc  = round(sell_price*config["ETC_RATE"]/100)

                def cost_for_margin(rate):
                    lo, hi = 0, sell_price
                    bc, bp = 0, 0
                    while lo<=hi:
                        mid = (lo+hi)//2
                        total = mid+fee+ad+inc+ret+etc
                        prof  = sell_price-total
                        mrt   = round((prof/(sell_price/vat))*100,2)
                        if mrt<rate:
                            hi = mid-1
                        else:
                            bc, bp = mid, prof
                            lo = mid+1
                    return bc, bp

                cost50, prof50 = cost_for_margin(50.0)
                y50 = math.ceil(cost50/config["EXCHANGE_RATE"])

                # 오버레이 텍스트
                result_container.markdown(
                    f"<div style='position:absolute; top:0; left:0;'>"
                    f"📌 마진율 50% 기준: {format_number(cost50)}원 ({y50}위안), 마진: {format_number(prof50)}원"
                    f"</div>",
                    unsafe_allow_html=True
                )
            except:
                # 오류시 빈 컨테이너 유지
                pass

        # 이하 단가/수량/버튼 (위치 고정)
        col1, col2 = st.columns(2)
        with col1:
            unit_yuan = st.text_input("단가 (위안)", st.session_state.get("unit_yuan",""), key="unit_yuan")
        with col2:
            unit_won  = st.text_input("단가 (원)",  st.session_state.get("unit_won",""), key="unit_won")
        qty_raw = st.text_input("수량", st.session_state.get("qty_raw","1"), key="qty_raw")
        calc_col, reset_col = st.columns(2)
        with calc_col:
            do_calc = st.button("계산하기")
        with reset_col:
            st.button("리셋", on_click=reset_inputs)

    with right:
        # 기존 계산 결과 (생략)
        pass

with tab2:
    st.subheader("세부 마진 계산기")
    st.info("준비 중입니다...")
