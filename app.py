import streamlit as st
import math

st.set_page_config(page_title="세부 마진 계산기", layout="wide")
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

def format_number(val):
    return f"{int(val):,}" if float(val).is_integer() else f"{val:,.2f}"

st.title("🧾 세부 마진 계산기")

left, right = st.columns(2)

with left:
    st.subheader("판매정보 및 비용 입력")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        sell_price = st.number_input("판매가 (원)", step=1000)
        pickup_cost = st.number_input("회수비용 (원)", value=1500, step=100)
        return_rate = st.number_input("반품률 (%)", value=0.1, step=0.1)
        gift_cost = st.number_input("사은품 비용 (원)", value=0, step=100)

    with col2:
        fee_rate = st.number_input("수수료율 (%)", value=10.8, step=0.1)
        restock_cost = st.number_input("재입고비용 (원)", value=500, step=100)
        etc_rate = st.number_input("기타비용률 (%)", value=2.0, step=0.1)
        packaging_cost = st.number_input("포장비 (원)", value=0, step=100)

    with col3:
        unit_yuan = st.text_input("위안화 (¥)")
        quantity = st.number_input("수량", value=1, step=1)
        exchange_rate = st.number_input("위안화 환율", value=350, step=1)
        inout_cost = st.number_input("입출고비용 (원)", value=3000, step=100)

    with col4:
        unit_won = st.text_input("원화 (₩)")
        ad_rate = st.number_input("광고비율 (%)", value=20.0, step=0.1)

    result = st.button("계산하기")

with right:
    if result:
        try:
            qty = int(quantity)
            unit_cost_val = 0
            cost_display = "0원"

            if unit_yuan:
                unit_cost_val = round(float(unit_yuan) * exchange_rate)
                cost_display = f"{format_number(unit_cost_val)}원 ({unit_yuan}위안)"
            elif unit_won:
                unit_cost_val = round(float(unit_won))
                cost_display = f"{format_number(unit_cost_val)}원"

            vat = 1.1
            unit_cost = round(unit_cost_val * qty * vat)

            fee = round((sell_price * fee_rate / 100) * vat)
            ad = round((sell_price * ad_rate / 100) * vat)
            inout = round(inout_cost * vat)
            pickup = round(pickup_cost * vat)
            restock = round(restock_cost * vat)
            return_cost = round((pickup + restock) * (return_rate / 100))
            etc = round((sell_price * etc_rate / 100) * vat)
            packaging = round(packaging_cost * vat)
            gift = round(gift_cost * vat)

            total_cost = unit_cost + fee + ad + inout + return_cost + etc + packaging + gift
            profit = sell_price - total_cost
            supply_price = sell_price / vat

            margin_profit = sell_price - (unit_cost + fee + inout + packaging + gift)
            margin_ratio = round((margin_profit / supply_price) * 100, 2)
            roi = round((profit / unit_cost) * 100, 2) if unit_cost else 0
            roi_margin = round((margin_profit / unit_cost) * 100, 2) if unit_cost else 0

            st.markdown("### 📊 계산 결과")
            for bg, stats in [
                ("#e8f5e9", [
                    ("💰 마진", f"{format_number(margin_profit)}원"),
                    ("📈 마진율", f"{margin_ratio:.2f}%"),
                    ("💹 투자수익률", f"{roi_margin:.2f}%")
                ]),
                ("#e3f2fd", [
                    ("🧮 최소 이익", f"{format_number(profit)}원"),
                    ("📉 최소마진율", f"{(profit/supply_price*100):.2f}%"),
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
        except:
            st.warning("입력값을 정확히 입력해주세요.")
