
import streamlit as st

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# 세션 상태 초기화 함수
def reset_inputs():
    for key in st.session_state.keys():
        if key.startswith("input_") or key.startswith("result_"):
            st.session_state[key] = ""

# 설정값 입력
with st.sidebar:
    st.header("🛠️ 설정값")
    FEE_RATE = st.number_input("수수료율 (%)", value=10.8)
    AD_RATE = st.number_input("광고비율 (%)", value=20.0)
    LOGISTICS_COST = st.number_input("입출고비용 (원)", value=3000)
    RETURN_COST = st.number_input("회수비용 (원)", value=1500)
    RESTOCK_COST = st.number_input("재입고비용 (원)", value=500)
    RETURN_RATE = st.number_input("반품률 (%)", value=0.1)
    ETC_RATE = st.number_input("기타비용률 (%)", value=2.0)
    EXCHANGE_RATE = st.number_input("위안화 환율", value=350)

# 입력창
st.markdown("### 판매정보 입력")
col1, col2 = st.columns(2)
with col1:
    sell_price = st.text_input("판매가", key="input_sell_price")
with col2:
    quantity = st.text_input("수량", key="input_quantity")

col3, col4 = st.columns(2)
with col3:
    cny_price = st.text_input("위안화 (¥)", key="input_cny")
with col4:
    krw_price = st.text_input("원화 (₩)", key="input_krw")

# 버튼 영역
col_btn1, col_btn2 = st.columns([1, 1])
with col_btn1:
    calculate = st.button("계산하기")
with col_btn2:
    reset = st.button("리셋")

# 계산 로직
if calculate and sell_price and quantity and (cny_price or krw_price):
    sell_price = int(sell_price)
    quantity = int(quantity)
    unit_price = int(float(krw_price)) if krw_price else int(float(cny_price) * EXCHANGE_RATE)
    cost = unit_price * quantity

    fee = round((sell_price * FEE_RATE * 1.1) / 100)
    ad = round((sell_price * AD_RATE * 1.1) / 100)
    logistics = round(LOGISTICS_COST * 1.1)
    return_fee = round(RETURN_COST * 1.1)
    restock = round(RESTOCK_COST * 1.1)
    refund_rate = RETURN_RATE / 100
    refund_cost = round((return_fee + restock) * refund_rate)
    etc = round((sell_price * ETC_RATE / 100) * 1.1)

    total_cost = cost + fee + ad + logistics + refund_cost + etc
    profit = sell_price - total_cost
    supply_price = round(sell_price / 1.1)
    margin_rate = round((profit / supply_price) * 100, 2)
    roi = round((profit / cost) * 100, 2)

    st.markdown("---")
    st.subheader("📊 계산 결과")

    def line(label, value, formula=""):
        st.write(f"**{label}:** {value:,}원{'  (' + formula + ')' if formula else ''}")

    line("판매가", sell_price)
    line("원가", cost, f"{unit_price:,} × {quantity}")
    line("수수료", fee, f"{sell_price:,} × {FEE_RATE}% × 1.1")
    line("광고비", ad, f"{sell_price:,} × {AD_RATE}% × 1.1")
    line("입출고비용", logistics, f"{LOGISTICS_COST:,} × 1.1")
    line("회수비용", return_fee, f"{RETURN_COST:,} × 1.1")
    line("재입고비용", restock, f"{RESTOCK_COST:,} × 1.1")
    line("반품비용", refund_cost, f"({return_fee} + {restock}) × {RETURN_RATE}%")
    line("기타비용", etc, f"{sell_price:,} × {ETC_RATE}% × 1.1")
    line("총비용", total_cost, f"원가 + 위 항목 합산")
    line("이익", profit, f"{sell_price:,} - 총비용")
    line("공급가액", supply_price, f"{sell_price:,} ÷ 1.1")
    line("순마진율", f"{margin_rate}%", f"{profit:,} ÷ {supply_price:,} × 100")
    line("ROI", f"{roi}%", f"{profit:,} ÷ {cost:,} × 100")

elif reset:
    reset_inputs()
    st.experimental_rerun()
