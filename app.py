
import streamlit as st
import json
import os

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# --- 기본 설정값 ---
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

# --- 설정 불러오기/저장 ---
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

# --- 본문: 탭 ---
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
        if result:
            # 원가 계산
            try:
                unit_cost = int(float(unit_yuan) * float(config["EXCHANGE_RATE"])) if unit_yuan else int(float(unit_won)) if unit_won else 0
            except:
                unit_cost = 0

            fee = sell_price * float(config["FEE_RATE"]) / 100 * 1.1
            ad = sell_price * float(config["AD_RATE"]) / 100 * 1.1
            inout = float(config["INOUT_COST"]) * 1.1
            pickup = float(config["PICKUP_COST"])
            restock = float(config["RESTOCK_COST"])
            return_rate = float(config["RETURN_RATE"])
            return_cost = (pickup + restock) * return_rate * 1.1
            etc = sell_price * float(config["ETC_RATE"]) / 100
            total_cost = unit_cost + fee + ad + inout + return_cost + etc
            profit = sell_price - total_cost
            supply_price = sell_price / 1.1
            margin = (profit / supply_price) * 100 if supply_price != 0 else 0
            roi = (profit / unit_cost) * 100 if unit_cost != 0 else 0

            # 결과 출력
            st.markdown("### 📊 계산 결과")
            st.write(f"**판매가:** {int(sell_price):,}원")
            st.write(f"**원가:** {int(unit_cost):,}원")
            st.write(f"**수수료:** {int(fee):,}원 (판매가 × {config['FEE_RATE']}% × 1.1)")
            st.write(f"**광고비:** {int(ad):,}원 (판매가 × {config['AD_RATE']}% × 1.1)")
            st.write(f"**입출고비용:** {int(inout):,}원 ({config['INOUT_COST']} × 1.1)")
            st.write(f"**회수비용:** {int(pickup):,}원")
            st.write(f"**재입고비용:** {int(restock):,}원")
            st.write(f"**반품률:** {float(return_rate) * 100:.1f}%")
            st.write(f"**기타비용:** {int(etc):,}원 (판매가 × {config['ETC_RATE']}%)")
            st.write(f"**총비용:** {int(total_cost):,}원 (원가 + 위 항목 합산)")
            st.write(f"**이익:** {int(profit):,}원 (판매가 - 총비용)")
            st.write(f"**공급가액:** {int(supply_price):,}원 (판매가 ÷ 1.1)")
            st.write(f"**순마진율:** {margin:.2f}% (이익 ÷ 공급가 × 100)")
            st.write(f"**ROI:** {roi:.2f}% (이익 ÷ 원가 × 100)")

with tab2:
    st.info("세부 마진 계산기는 아직 준비 중입니다.")
