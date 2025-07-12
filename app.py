import streamlit as st
import json
import os
import math

# 페이지 설정 및 여백 조정
st.set_page_config(page_title="간단 마진 계산기", layout="wide")
st.markdown(
    """
    <style>
      [data-testid="stSidebarHeader"] { display: none !important; }
      [data-testid="stSidebarContent"] { padding-top: 15px !important; }
      [data-testid="stHeading"] { margin-bottom: 15px !important; }
      [data-testid="stNumberInput"] button { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

DEFAULT_CONFIG_FILE = "default_config.json"

def default_config():
    return {
        "FEE_RATE": 10.8,
        "AD_RATE": 20.0,
        "INOUT_COST": 3000,
        "PICKUP_COST": 1500,
        "RESTOCK_COST": 500,
        "RETURN_RATE": 0.1,
        "ETC_RATE": 2.0,
        "EXCHANGE_RATE": 350,
        "PACKAGING_COST": 500,
        "GIFT_COST": 1000
    }

def load_config():
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, "r") as f:
                data = json.load(f)
                base = default_config()
                for k, v in data.items():
                    if k in base:
                        try:
                            base[k] = float(v)
                        except:
                            pass
                return base
        except:
            return default_config()
    else:
        return default_config()

def save_config(config):
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        json.dump(config, f)

def format_number(val):
    return f"{int(val):,}" if float(val).is_integer() else f"{val:,.2f}"

def reset_inputs():
    for key in ["sell_price_raw", "unit_yuan", "unit_won", "qty_raw"]:
        if key in st.session_state:
            st.session_state[key] = ""

config = load_config()

st.sidebar.header("🛠️ 설정값")
config["FEE_RATE"]     = st.sidebar.number_input("수수료율 (%)",    value=config["FEE_RATE"],     step=0.1,  format="%.2f")
config["AD_RATE"]      = st.sidebar.number_input("광고비율 (%)",    value=config["AD_RATE"],      step=0.1,  format="%.2f")
config["INOUT_COST"]   = st.sidebar.number_input("입출고비용 (원)", value=int(config["INOUT_COST"]), step=100)
config["PICKUP_COST"]  = st.sidebar.number_input("회수비용 (원)",   value=int(config["PICKUP_COST"]), step=100)
config["RESTOCK_COST"] = st.sidebar.number_input("재입고비용 (원)", value=int(config["RESTOCK_COST"]),step=100)
config["RETURN_RATE"]  = st.sidebar.number_input("반품률 (%)",      value=config["RETURN_RATE"],  step=0.1,  format="%.2f")
config["ETC_RATE"]     = st.sidebar.number_input("기타비용률 (%)",  value=config["ETC_RATE"],     step=0.1,  format="%.2f")
config["EXCHANGE_RATE"] = st.sidebar.number_input("위안화 환율",    value=int(config["EXCHANGE_RATE"]), step=1)
config["PACKAGING_COST"] = st.sidebar.number_input("포장비 (원)",     value=int(config["PACKAGING_COST"]), step=100)
config["GIFT_COST"]    = st.sidebar.number_input("사은품 비용 (원)",value=int(config["GIFT_COST"]),    step=100)

if st.sidebar.button("📂 기본값으로 저장"):
    save_config(config)
    st.sidebar.success("기본값이 저장되었습니다.")

def main():
    tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

    with tab1:
        left, right = st.columns(2)

        with left:
            st.subheader("판매정보 입력")
            sell_price_raw = st.text_input("판매가 (원)", value=st.session_state.get("sell_price_raw", ""))
            margin_display = st.empty()

            if sell_price_raw.strip():
                try:
                    target_margin = 50.0
                    sell_price_val = int(float(sell_price_raw))
                    vat = 1.1

                    fee = round((sell_price_val * config['FEE_RATE'] / 100) * vat)
                    ad_fee = round((sell_price_val * config['AD_RATE'] / 100) * vat)
                    inout_cost = round(config['INOUT_COST'] * vat)
                    return_cost = round((config['PICKUP_COST'] + config['RESTOCK_COST']) * (config['RETURN_RATE'] / 100) * vat)
                    etc_cost = round((sell_price_val * config['ETC_RATE'] / 100) * vat)
                    packaging_cost = round(config['PACKAGING_COST'] * vat)
                    gift_cost = round(config['GIFT_COST'] * vat)

                    supply_price = sell_price_val / vat

                    left_b, right_b = 0, sell_price_val
                    target_cost = 0
                    while left_b <= right_b:
                        mid = (left_b + right_b) // 2
                        partial = round(mid * vat) + fee + inout_cost + packaging_cost + gift_cost
                        margin_profit = sell_price_val - partial
                        margin_mid = margin_profit / supply_price * 100
                        if margin_mid < target_margin:
                            right_b = mid - 1
                        else:
                            target_cost = mid
                            left_b = mid + 1

                    yuan_cost = round(target_cost / config['EXCHANGE_RATE'], 2)

                    profit = sell_price_val - (
                        round(target_cost * vat) + fee + inout_cost + packaging_cost + gift_cost
                    )

                    margin_display.markdown(
                        f"""
<div style='height:10px; line-height:10px; color:#f63366; font-size:15px; margin-bottom:15px;'>
  마진율 {int(target_margin)}% 기준: {format_number(target_cost)}원 ({yuan_cost:.2f}위안) / 마진: {format_number(profit)}원
</div>
""", unsafe_allow_html=True)
                except:
                    margin_display.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            else:
                margin_display.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                unit_yuan = st.text_input("위안화 (¥)", value=st.session_state.get("unit_yuan", ""))
            with col2:
                unit_won = st.text_input("원화 (₩)", value=st.session_state.get("unit_won", ""))

            qty_raw = st.text_input("수량", value=st.session_state.get("qty_raw", "1"))
            calc_col, reset_col = st.columns(2)
            result = calc_col.button("계산하기")
            reset_col.button("리셋", on_click=reset_inputs)

        with right:
            if 'result' in locals() and result:
                try:
                    sell_price = int(float(sell_price_raw))
                    qty = int(float(qty_raw)) if qty_raw else 1
                except:
                    st.warning("판매가와 수량을 정확히 입력해주세요.")
                    st.stop()

                if unit_yuan:
                    unit_cost_val = round(float(unit_yuan) * config['EXCHANGE_RATE'])
                    cost_display  = f"{format_number(unit_cost_val)}원 ({unit_yuan}위안)"
                elif unit_won:
                    unit_cost_val = round(float(unit_won))
                    cost_display  = f"{format_number(unit_cost_val)}원"
                else:
                    unit_cost_val = 0
                    cost_display  = "0원"

                vat = 1.1
                unit_cost = round(unit_cost_val * qty * vat)

                fee = round((sell_price * config["FEE_RATE"] / 100) * vat)
                ad = round((sell_price * config["AD_RATE"] / 100) * vat)
                inout = round(config["INOUT_COST"] * vat)
                pickup = round(config["PICKUP_COST"] * vat)
                restock = round(config["RESTOCK_COST"] * vat)
                return_cost = round((pickup + restock) * (config["RETURN_RATE"] / 100))
                etc = round((sell_price * config["ETC_RATE"] / 100) * vat)
                packaging = round(config["PACKAGING_COST"] * vat)
                gift = round(config["GIFT_COST"] * vat)

                total_cost = unit_cost + fee + ad + inout + return_cost + etc + packaging + gift
                profit2 = sell_price - total_cost
                supply_price2 = sell_price / vat

                margin_profit = sell_price - (unit_cost + fee + inout + packaging + gift)
                margin_ratio = round((margin_profit / supply_price2) * 100, 2)
                roi = round((profit2 / unit_cost) * 100, 2) if unit_cost else 0
                roi_margin = round((margin_profit / unit_cost) * 100, 2) if unit_cost else 0

                st.markdown("### 📊 계산 결과")
                for bg, stats in [
                    ("#e8f5e9", [
                        ("💰 마진", f"{format_number(margin_profit)}원"),
                        ("📈 마진율", f"{margin_ratio:.2f}%"),
                        ("💹 투자수익률", f"{roi_margin:.2f}%")
                    ]),
                    ("#e3f2fd", [
                        ("🧮 최소 이익", f"{format_number(profit2)}원"),
                        ("📉 최소마진율", f"{(profit2/supply_price2*100):.2f}%"),
                        ("🧾 투자수익률", f"{roi:.2f}%")
                    ])
                ]:
                    st.markdown(
                        f"""
<div style='display: grid; grid-template-columns: 1fr 1fr 1fr; background: {bg};
             padding: 12px; border-radius: 10px; gap: 8px; margin-bottom: 12px;'>
  <div>
    <div style='font-weight:bold; font-size:15px;'>{stats[0][0]}</div>
    <div style='font-size:15px;'>{stats[0][1]}</div>
  </div>
  <div>
    <div style='font-weight:bold; font-size:15px;'>{stats[1][0]}</div>
    <div style='font-size:15px;'>{stats[1][1]}</div>
  </div>
  <div>
    <div style='font-weight:bold; font-size:15px;'>{stats[2][0]}</div>
    <div style='font-size:15px;'>{stats[2][1]}</div>
  </div>
</div>
""",
                        unsafe_allow_html=True,
                    )

                st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
                with st.expander("📦 상세 비용 항목 보기", expanded=False):
                    st.markdown(f"**판매가:** {format_number(sell_price)}원")
                    st.markdown(f"**원가:** {format_number(unit_cost)}원 ({cost_display})")
                    st.markdown(f"**수수료:** {format_number(fee)}원")
                    st.markdown(f"**광고비:** {format_number(ad)}원")
                    st.markdown(f"**입출고비용:** {format_number(inout)}원")
                    st.markdown(f"**회수비용 (참고):** {format_number(pickup)}원")
                    st.markdown(f"**재입고비용 (참고):** {format_number(restock)}원")
                    st.markdown(f"**반품비용:** {format_number(return_cost)}원")
                    st.markdown(f"**기타비용:** {format_number(etc)}원")
                    st.markdown(f"**포장비:** {format_number(packaging)}원")
                    st.markdown(f"**사은품 비용:** {format_number(gift)}원")
                    st.markdown(f"**총비용:** {format_number(total_cost)}원")
                    st.markdown(f"**공급가액:** {format_number(round(supply_price2))}원")
                    st.markdown(f"**최소 이익:** {format_number(profit2)}원")
                    st.markdown(f"**최소마진율:** {(profit2/supply_price2*100):.2f}%")
                    st.markdown(f"**투자수익률:** {roi:.2f}%")

    with tab2:
        st.subheader("세부 마진 계산기")
        st.info("준비 중입니다...")

if __name__ == "__main__":
    main()
