
import streamlit as st
import json
import os

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# --- 파일 기반 설정 저장 및 로드 ---
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
                return {k: int(float(v)) if isinstance(v, str) and v.replace(".", "", 1).isdigit() else v for k, v in data.items()}
        except:
            return default_config
    else:
        return default_config

def save_config(config):
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        json.dump(config, f)

config = load_config()

# --- 사이드바: 설정값 입력 ---
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
    config[key] = st.sidebar.text_input(label, value=str(config[key]), key=key)

if st.sidebar.button("💾 기본값으로 저장"):
    save_config(config)
    st.sidebar.success("기본값이 저장되었습니다.")

# --- 본문: 탭 + 양쪽 분할 ---
tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

with tab1:
    left, right = st.columns(2)

    with left:
        st.subheader("판매정보 입력")

        sell_price = st.number_input("판매가", value=20000)
        col1, col2 = st.columns(2)
        with col1:
            unit_yuan = st.text_input("위안화 (¥)", value="")
        with col2:
            unit_won = st.text_input("원화 (₩)", value="")

        qty = st.number_input("수량", value=1, min_value=1)

        
        result = st.button("계산하기")
        with right:
            st.subheader("📊 계산 결과")
            if result:
                # 원가 계산
                if unit_yuan:
                    try:
                        unit_cost = int(float(unit_yuan) * float(config["EXCHANGE_RATE"]))
                    except:
                        unit_cost = 0
                elif unit_won:
                    try:
                        unit_cost = int(float(unit_won))
                    except:
                        unit_cost = 0
                else:
                    unit_cost = 0

                fee = sell_price * float(config["FEE_RATE"]) / 100
                ad = sell_price * float(config["AD_RATE"]) / 100
                return_cost = float(config["RETURN_RATE"]) * (float(config["PICKUP_COST"]) + float(config["RESTOCK_COST"]))
                etc = sell_price * float(config["ETC_RATE"]) / 100
                supply_price = sell_price / 1.1
                total_cost = unit_cost + fee + ad + float(config["INOUT_COST"]) + return_cost + etc
                profit = sell_price - total_cost
                margin = (profit / supply_price) * 100 if supply_price != 0 else 0
                roi = (profit / unit_cost) * 100 if unit_cost != 0 else 0

                st.write(f"**공급가액:** {int(supply_price):,}원 (판매가 ÷ 1.1)")
                st.write(f"**총비용:** {int(total_cost):,}원 (원가 + 수수료 + 광고비 + 입출고비 + 반품비 + 기타)")
                st.write(f"**이익:** {int(profit):,}원 (판매가 - 총비용)")
                st.write(f"**순마진율:** {margin:.2f}% (이익 ÷ 공급가액 × 100)")
                st.write(f"**ROI:** {roi:.2f}% (이익 ÷ 원가 × 100)")
            else:
                st.markdown("💡 왼쪽에 값을 입력하고 **계산하기** 버튼을 누르면 결과가 여기에 표시됩니다.")
    
            # 원가 계산
            if unit_yuan:
                try:
                    unit_cost = int(float(unit_yuan) * float(config["EXCHANGE_RATE"]))
                except:
                    unit_cost = 0
            elif unit_won:
                try:
                    unit_cost = int(float(unit_won))
                except:
                    unit_cost = 0
            else:
                unit_cost = 0

            fee = sell_price * float(config["FEE_RATE"]) / 100
            ad = sell_price * float(config["AD_RATE"]) / 100
            return_cost = float(config["RETURN_RATE"]) * (float(config["PICKUP_COST"]) + float(config["RESTOCK_COST"]))
            etc = sell_price * float(config["ETC_RATE"]) / 100
            supply_price = sell_price / 1.1
            total_cost = unit_cost + fee + ad + float(config["INOUT_COST"]) + return_cost + etc
            profit = sell_price - total_cost
            margin = (profit / supply_price) * 100 if supply_price != 0 else 0
            roi = (profit / unit_cost) * 100 if unit_cost != 0 else 0

            with right:
                st.subheader("📊 계산 결과")
                st.write(f"**공급가액:** {int(supply_price):,}원 (판매가 ÷ 1.1)")
                st.write(f"**총비용:** {int(total_cost):,}원 (원가 + 수수료 + 광고비 + 입출고비 + 반품비 + 기타)")
                st.write(f"**이익:** {int(profit):,}원 (판매가 - 총비용)")
                st.write(f"**순마진율:** {margin:.2f}% (이익 ÷ 공급가액 × 100)")
                st.write(f"**ROI:** {roi:.2f}% (이익 ÷ 원가 × 100)")

with tab2:
    st.info("세부 마진 계산기는 아직 준비 중입니다.")
