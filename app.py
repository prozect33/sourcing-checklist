
import streamlit as st

def format_num(num):
    if int(num) == num:
        return f"{int(num):,}"
    else:
        return f"{num:,.2f}"

st.title("테스트: 기타비용 및 원가 계산식 출력")

sell_price_raw = st.text_input("판매가", "")
etc_rate_raw = st.text_input("기타비용률 (%)", "")
unit_yuan_raw = st.text_input("위안화 원가 (¥)", "")
unit_won_raw = st.text_input("원화 원가 (₩)", "")
exchange_rate = 350

try:
    sell_price = float(sell_price_raw)
    etc_rate = float(etc_rate_raw)
except:
    sell_price = None
    etc_rate = None

try:
    if unit_yuan_raw:
        unit_cost_val = round(float(unit_yuan_raw) * exchange_rate)
        cost_display = f"{unit_cost_val:,}원 (위안화 입력 환산: {unit_yuan_raw} × {exchange_rate})"
    elif unit_won_raw:
        unit_cost_val = round(float(unit_won_raw))
        cost_display = f"{unit_cost_val:,}원 (원화 입력)"
    else:
        unit_cost_val = 0
        cost_display = "0원"
except:
    unit_cost_val = 0
    cost_display = "0원"

if st.button("계산하기"):
    if sell_price is None or etc_rate is None:
        st.error("판매가와 기타비용률을 정확히 입력하세요.")
    else:
        sell_price_str = format_num(sell_price)
        etc_rate_str = format_num(etc_rate)
        etc_calc = f"({sell_price_str} × {etc_rate_str} ÷ 100) × 1.1"
        etc = round(sell_price * etc_rate / 100 * 1.1)
        st.write(f"기타비용 계산식: {etc_calc} = {etc:,}원")
        st.write(f"원가: {cost_display}")
