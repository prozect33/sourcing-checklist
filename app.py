
import streamlit as st

# 상수 설정
FEE_RATE = 10.8  # 수수료율 (%)
AD_RATE = 20  # 광고비율 (%)
BASE_INOUT_COST = 3000  # 입출고비
BASE_PICKUP_COST = 1500  # 반품 회수비
BASE_RESTOCK_COST = 500  # 재입고비
RETURN_RATE = 0.1  # 반품율
EXCHANGE_RATE = 300  # 환율 (1위안 = 300원)

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

col1, col2 = st.columns([8, 2])
with col1:
    st.title("📦 간단 마진 계산기")
with col2:
    st.markdown("### ")
    st.button("간단 마진 계산기", disabled=True)

st.header("판매가 및 원가 입력")

# 입력: 판매가 (숫자 버튼 제거)
selling_price_input = st.text_input("판매가 (₩)", value="20000")

# 입력: 원화와 위안화 입력창 분리
col_krw, col_cny = st.columns(2)
with col_krw:
    cost_krw_input = st.text_input("원가 (₩ 원화)", value="")
with col_cny:
    cost_cny_input = st.text_input("원가 (¥ 위안화)", value="")

# 계산 버튼
if st.button("✅ 계산하기"):
    try:
        selling_price = int(selling_price_input.replace(",", "").strip())

        # 원가 우선순위: 원화 입력 > 위안화 입력
        if cost_krw_input.strip():
            cost = int(cost_krw_input.replace(",", "").strip())
        elif cost_cny_input.strip():
            cost = int(float(cost_cny_input.strip()) * EXCHANGE_RATE)
        else:
            st.error("원가를 입력하세요.")
            st.stop()

        # 계산식 적용
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

        # 결과 출력
        st.subheader("📊 결과")
        st.markdown(f"**수수료:** {fee:,} 원 (판매가 × {FEE_RATE}% × 1.1)")
        st.markdown(f"**광고비:** {ad_fee:,} 원 (판매가 × {AD_RATE}% × 1.1)")
        st.markdown(f"**입출고비용:** {inout_cost:,} 원 (기본 {BASE_INOUT_COST} × 1.1)")
        st.markdown(f"**반품비용:** {return_cost:,} 원 (({BASE_PICKUP_COST}+{BASE_RESTOCK_COST}) × {RETURN_RATE} × 1.1)")
        st.markdown(f"**기타비용:** {etc_cost:,} 원 (판매가 × 2%)")
        st.markdown(f"**총비용:** {total_cost:,} 원")
        st.markdown(f"**이익:** {profit:,} 원 (판매가 - 총비용)")
        st.markdown(f"**순마진율:** {margin_rate:.2f}% (이익 ÷ 공급가액 {supply_price:,.0f})")
        st.markdown(f"**ROI:** {roi:.2f}% (투자금 {cost:,}원 대비 수익금 {profit:,}원, {roi_ratio}배)")

    except ValueError:
        st.error("입력값에 숫자만 사용하세요.")
