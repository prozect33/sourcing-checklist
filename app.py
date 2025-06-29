
import streamlit as st

st.set_page_config(page_title="소싱 체크리스트 데모", layout="centered")
st.title("📦 해외 사입 소싱 체크리스트 데모")

# 1. 마진 계산기
st.header("1. 마진 계산기")
sale_price = st.number_input("판매가 (원)", value=20000)
product_cost = st.number_input("상품 원가 (위안)", value=20.0)
exchange_rate = st.number_input("환율 (1위안 → 원)", value=190.0)
intl_shipping = st.number_input("국제 배송비 (원)", value=2000)
fee_percent = st.slider("플랫폼 수수료 (%)", 0, 30, 10)
ad_percent = st.slider("광고비 비율 (%)", 0, 50, 10)

product_cost_krw = product_cost * exchange_rate
total_cost = product_cost_krw + intl_shipping + (sale_price * (fee_percent + ad_percent) / 100)
profit = sale_price - total_cost
margin = profit / sale_price * 100 if sale_price > 0 else 0

st.markdown(f"**순이익:** {int(profit):,}원")
st.markdown(f"**마진율:** {margin:.1f}%")
if margin < 20:
    st.warning("❌ 마진율이 낮습니다. 상품 탈락 권장")
else:
    st.success("✅ 마진 기준 통과")

# 2. 시장성 판단
st.header("2. 시장성 판단")
review_count = st.number_input("경쟁 상품 평균 리뷰 수", value=120)
if review_count > 500:
    st.warning("❌ 경쟁 과열. 신규 진입 어려움")
elif review_count > 100:
    st.info("⚠️ 중간 수준 경쟁")
else:
    st.success("✅ 진입 가능성 양호")

# 3. 전략 적합성
st.header("3. 전략 적합성")
seasonal = st.selectbox("시즌 상품인가요?", ["예", "아니오"])
if seasonal == "예":
    st.warning("⚠️ 시즌성 상품. 재고 관리 유의 필요")
else:
    st.success("✅ 연중 판매 가능")

# 최종 결과
st.header("🧾 최종 판단")
if margin >= 20 and review_count <= 100:
    st.success("🔥 이 상품은 소싱 검토 가치가 충분합니다!")
else:
    st.info("⏳ 보완 필요 또는 상품 제외 고려")
