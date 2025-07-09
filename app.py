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
                    st.markdown("**판매가**")
                    st.markdown(f"<div style='font-size: 16px;'>{format_number(sell_price)}원</div>", unsafe_allow_html=True)
                with col2:
                    st.markdown("**원가**")
                    st.markdown(cost_display, unsafe_allow_html=True)
                with col3:
                    st.markdown("**최소 이익**")
                    st.markdown(f"<div style='font-size: 16px;'>{format_number(profit)}원</div>", unsafe_allow_html=True)
                with col4:
                    st.markdown("**최소마진율**")
                    st.markdown(f"<div style='font-size: 16px;'>{margin:.2f}%</div>", unsafe_allow_html=True)
                with col5:
                    st.markdown("**투자수익률**")
                    st.markdown(f"<div style='font-size: 16px;'>{roi:.2f}%</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size: 16px;'>{margin:.2f}%</div>", unsafe_allow_html=True)

                st.markdown("<div style='margin-top: 18px;'></div>", unsafe_allow_html=True)

                with st.expander("📦 상세 비용 항목 보기", expanded=False):
                    st.markdown(f"**수수료:** {format_number(fee)}원 (판매가 × {config['FEE_RATE']}% × 1.1)")
                    st.markdown(f"**광고비:** {format_number(ad)}원 (판매가 × {config['AD_RATE']}% × 1.1)")
                    st.markdown(f"**입출고비용:** {format_number(inout)}원 ({format_number(config['INOUT_COST'])} × 1.1)")
                    st.markdown(f"**회수비용:** {format_number(pickup)}원 ({format_number(config['PICKUP_COST'])} × 1.1)")
                    st.markdown(f"**재입고비용:** {format_number(restock)}원 ({format_number(config['RESTOCK_COST'])} × 1.1)")
                    st.markdown(f"**반품비용:** {format_number(return_cost)}원 ((({format_number(config['PICKUP_COST'])} × 1.1) + ({format_number(config['RESTOCK_COST'])} × 1.1)) × {return_rate * 100:.1f}%)")
                    st.markdown(f"**기타비용:** {format_number(etc)}원 (판매가 × {config['ETC_RATE']}% × 1.1)")
                    st.markdown(f"**총비용:** {format_number(total_cost)}원 (원가 + 위 항목 합산)")
                    st.markdown(f"**공급가액:** {format_number(round(supply_price))}원 (판매가 ÷ 1.1)")