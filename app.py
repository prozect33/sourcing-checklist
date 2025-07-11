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

        # 마진 텍스트 공간 고정 (22px) / 텍스트 없을 때도 동일하게
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
                target_cost, yuan_cost, profit = 0, 0, 0

                while left_b <= right_b:
                    mid = (left_b + right_b) // 2
                    total_cost = round(mid + fee + ad_fee + inout_cost + return_cost + etc_cost)
                    profit_mid = sell_price_val - total_cost
                    margin_mid = profit_mid / supply_price * 100
                    if margin_mid < target_margin:
                        right_b = mid - 1
                    else:
                        target_cost = mid
                        left_b = mid + 1

                yuan_cost = math.ceil(target_cost / float(config["EXCHANGE_RATE"]))
                profit = sell_price_val - (target_cost + fee + ad_fee + inout_cost + return_cost + etc_cost)

                margin_display.markdown(f"""
<div style='height:10px; line-height:10px; color:#f63366; font-size:15px; margin-bottom:15px;'>
  &nbsp;마진율 {int(target_margin)}% 기준: {format_number(target_cost)}원 ({yuan_cost}위안) / 마진: {format_number(profit)}원
</div>
""", unsafe_allow_html=True)
            except:
                margin_display.markdown("<div style='height:10px; line-height:10px; margin-bottom:15px;'>&nbsp;</div>", unsafe_allow_html=True)
        else:
            margin_display.markdown("<div style='height:10px; line-height:10px; margin-bottom:15px;'>&nbsp;</div>", unsafe_allow_html=True)

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
        if 'result' in locals() and result:
            try:
                sell_price = int(float(sell_price_raw))
                qty = int(float(qty_raw))
            except:
                st.warning("판매가와 수량을 정확히 입력해주세요.")
                st.stop()

            if unit_yuan:
                unit_cost_val = round(float(unit_yuan) * float(config['EXCHANGE_RATE']))
                cost_display = f"{format_number(unit_cost_val)}원 ({unit_yuan}위안)"
            elif unit_won:
                unit_cost_val = round(float(unit_won))
                cost_display = f"{format_number(unit_cost_val)}원"
            else:
                unit_cost_val = 0
                cost_display = "0원"

            vat = 1.1
            unit_cost = round(unit_cost_val * vat)

            fee = round((sell_price * float(config["FEE_RATE"]) / 100) * vat)
            ad = round((sell_price * float(config["AD_RATE"]) / 100) * vat)
            inout = round(float(config["INOUT_COST"]) * vat)
            pickup = round(float(config["PICKUP_COST"]) * vat)
            restock = round(float(config["RESTOCK_COST"]) * vat)
            return_cost = round((pickup + restock) * float(config["RETURN_RATE"]))
            etc = round((sell_price * float(config["ETC_RATE"]) / 100) * vat)

            total_cost = unit_cost + fee + ad + inout + return_cost + etc
            profit2 = sell_price - total_cost
            supply_price2 = sell_price / vat

            margin_profit = sell_price - (unit_cost + fee + inout)
            margin_ratio = round((margin_profit / supply_price2) * 100, 2)
            roi = round((profit2 / unit_cost) * 100, 2) if unit_cost else 0
            roi_margin = round((margin_profit / unit_cost) * 100, 2) if unit_cost else 0

            st.markdown("### 📊 계산 결과")
            for bg, stats in [
                ("#e8f5e9", [("💰 마진", f"{format_number(margin_profit)}원"),
                              ("📈 마진율", f"{margin_ratio:.2f}%"),
                              ("💹 투자수익률", f"{roi_margin:.2f}%")]),
                ("#e3f2fd", [("🧮 최소 이익", f"{format_number(profit2)}원"),
                              ("📉 최소마진율", f"{(profit2/supply_price2*100):.2f}%"),
                              ("🧾 투자수익률", f"{roi:.2f}%")])
            ]:
                st.markdown(f"""
<div style='display: grid; grid-template-columns: 1fr 1fr 1fr; background: {bg}; padding: 12px; border-radius: 10px; gap: 8px; margin-bottom: 12px;'>
  <div><div style='font-weight:bold; font-size:15px;'>{stats[0][0]}</div><div style='font-size:15px;'>{stats[0][1]}</div></div>
  <div><div style='font-weight:bold; font-size:15px;'>{stats[1][0]}</div><div style='font-size:15px;'>{stats[1][1]}</div></div>
  <div><div style='font-weight:bold; font-size:15px;'>{stats[2][0]}</div><div style='font-size:15px;'>{stats[2][1]}</div></div>
</div>
""", unsafe_allow_html=True)

            st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
            with st.expander("📦 상세 비용 항목 보기", expanded=False):
                st.markdown(f"**판매가:** {format_number(sell_price)}원")
                st.markdown(f"**원가:** {format_number(unit_cost)}원 ({cost_display})")
                st.markdown(f"**수수료:** {format_number(fee)}원 (판매가 × {config['FEE_RATE']}% × 1.1)")
                st.markdown(f"**광고비:** {format_number(ad)}원 (판매가 × {config['AD_RATE']}% × 1.1)")
                st.markdown(f"**입출고비용:** {format_number(inout)}원 ({config['INOUT_COST']} × 1.1)")
                st.markdown(f"**회수비용:** {format_number(pickup)}원 ({config['PICKUP_COST']} × 1.1)")
                st.markdown(f"**재입고비용:** {format_number(restock)}원 ({config['RESTOCK_COST']} × 1.1)")
                st.markdown(f"**반품비용:** {format_number(return_cost)}원 ((회수비용+재입고비용) × {float(config['RETURN_RATE'])*100:.1f}% )")
                st.markdown(f"**기타비용:** {format_number(etc)}원 (판매가 × {config['ETC_RATE']}% × 1.1)")
                st.markdown(f"**총비용:** {format_number(total_cost)}원")
                st.markdown(f"**공급가액:** {format_number(round(supply_price2))}원 (판매가 ÷ 1.1)")
                st.markdown(f"**최소 이익:** {format_number(profit2)}원 (판매가 - 총비용)")
                st.markdown(f"**최소마진율:** {(profit2/supply_price2*100):.2f}%")
                st.markdown(f"**투자수익률:** {roi:.2f}%")

with tab2:
    st.subheader("세부 마진 계산기")
    st.info("준비 중입니다...")
