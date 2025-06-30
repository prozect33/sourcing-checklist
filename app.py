
import streamlit as st

# 상수 설정
FEE_RATE = 10.8  # 수수료율 (%)
AD_RATE = 20  # 광고비율 (%)
BASE_INOUT_COST = 3000  # 입출고비
BASE_PICKUP_COST = 1500  # 반품 회수비
BASE_RESTOCK_COST = 500  # 재입고비
RETURN_RATE = 0.1  # 반품율
EXCHANGE_RATE = 300  # 환율 (1위안 = 300원)

st.set_page_config(page_title="간단 마진 계산기", layout="centered")
st.title("📦 간단 마진 계산기")

# 탭 구분
tab = st.selectbox("🔍 기능 선택", ["간단 마진 계산기"])

if tab == "간단 마진 계산기":
    st.header("판매가 및 원가 입력")

    selling_price = st.number_input("판매가 (₩)", min_value=0, step=100, value=20000)
    cost_unit = st.radio("원가 단위 선택", ["₩ 원화", "¥ 위안화"])
    cost_input = st.number_input("원가", min_value=0.0, step=1.0, value=20.0)

    if cost_unit == "¥ 위안화":
        cost = round(cost_input * EXCHANGE_RATE)
    else:
        cost = int(round(cost_input))

    if st.button("✅ 계산하기"):
        fee = round((selling_price * FEE_RATE * 1.1) / 100)
        ad_fee = round((selling_price * AD_RATE * 1.1) / 100)
        inout_cost = round(BASE_INOUT_COST * 1.1)
        return_cost = round((BASE_PICKUP_COST + BASE_RESTOCK_COST) * RETURN_RATE * 1.1)
        etc_cost = round(selling_price * 0.02)
        total_cost = round(cost + fee + ad_fee + inout_cost + return_cost + etc_cost)
        profit = selling_price - total_cost
        supply_price = selling_price / 1.1
        margin_rate = round((profit / supply_price) * 100, 2)
        roi = round((profit / cost) * 100, 2)
        roi_ratio = round((profit / cost) + 1, 1)

        st.subheader("📊 결과")
        st.markdown(f"**수수료:** {fee:,} 원")
        st.markdown(f"**광고비:** {ad_fee:,} 원")
        st.markdown(f"**입출고비용:** {inout_cost:,} 원")
        st.markdown(f"**반품비용:** {return_cost:,} 원")
        st.markdown(f"**기타비용:** {etc_cost:,} 원")
        st.markdown(f"**총비용:** {total_cost:,} 원")
        st.markdown(f"**이익:** {profit:,} 원")
        st.markdown(f"**순마진율:** {margin_rate:.2f}%")
        st.markdown(f"**ROI:** {roi:.2f}% (투자금 {cost:,}원 대비 수익금 {profit:,}원, {roi_ratio}배)")
