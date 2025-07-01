
import streamlit as st

# 기본 설정
st.set_page_config(page_title="마진 계산기", layout="wide")

# 세션 상태 초기화
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "간단 마진 계산기"

# 탭 선택 UI
col1, col2, col3 = st.columns([1, 1, 6])
with col1:
    if st.button("**간단 마진 계산기**" if st.session_state.active_tab == "간단 마진 계산기" else "간단 마진 계산기"):
        st.session_state.active_tab = "간단 마진 계산기"
with col2:
    if st.button("**세부 마진 계산기**" if st.session_state.active_tab == "세부 마진 계산기" else "세부 마진 계산기"):
        st.session_state.active_tab = "세부 마진 계산기"

# 간단 마진 계산기 페이지
if st.session_state.active_tab == "간단 마진 계산기":
    # 설정값 (왼쪽 정렬)
    with st.sidebar:
        st.markdown("### 설정값")
        fee_rate = st.number_input("수수료율 (%)", value=10.8, step=0.1)
        ad_rate = st.number_input("광고비율 (%)", value=20.0, step=0.1)
        base_inout_cost = st.number_input("입출고비 (₩)", value=3000, step=100)
        pickup_cost = st.number_input("회수비 (₩)", value=1500, step=100)
        restock_cost = st.number_input("재입고비 (₩)", value=500, step=100)
        return_rate = st.number_input("반품율 (%)", value=10.0, step=0.5)
        etc_rate = st.number_input("기타비용율 (%)", value=2.0, step=0.1)
        exchange_rate = st.number_input("환율 (1위안 = ?원)", value=350, step=10)

    col_main1, col_main2, col_main3 = st.columns([1, 2, 1])
    with col_main2:
        st.title("📦 간단 마진 계산기")
        selling_price_input = st.text_input("판매가", value="20000")

        st.markdown("#### 원가")
        col_cny, col_krw = st.columns(2)
        with col_cny:
            cost_cny_input = st.text_input("위안화 (¥)", value="")
        with col_krw:
            cost_krw_input = st.text_input("원화 (₩)", value="")

        if st.button("계산하기"):
            try:
                selling_price = int(selling_price_input.replace(",", "").strip())

                if cost_krw_input.strip():
                    cost = int(cost_krw_input.replace(",", "").strip())
                elif cost_cny_input.strip():
                    cost = int(float(cost_cny_input.strip()) * exchange_rate)
                else:
                    st.error("원가를 입력하세요.")
                    st.stop()

                fee = round((selling_price * fee_rate * 1.1) / 100)
                ad_fee = round((selling_price * ad_rate * 1.1) / 100)
                inout_cost = round(base_inout_cost * 1.1)
                return_cost = round((pickup_cost + restock_cost) * (return_rate / 100) * 1.1)
                etc_cost = round(selling_price * (etc_rate / 100))
                total_cost = round(cost + fee + ad_fee + inout_cost + return_cost + etc_cost)
                profit = selling_price - total_cost
                supply_price = selling_price / 1.1
                margin_rate = round((profit / supply_price) * 100, 2)
                roi = round((profit / cost) * 100, 2)
                roi_ratio = round((profit / cost) + 1, 1)

                st.markdown("---")
                st.markdown(f"**수수료:** {fee:,} 원")
                st.markdown(f"**광고비:** {ad_fee:,} 원")
                st.markdown(f"**입출고비용:** {inout_cost:,} 원")
                st.markdown(f"**반품비용:** {return_cost:,} 원")
                st.markdown(f"**기타비용:** {etc_cost:,} 원")
                st.markdown(f"**총비용:** {total_cost:,} 원")
                st.markdown(f"**이익:** {profit:,} 원")
                st.markdown(f"**마진율:** {margin_rate:.2f}%")
                st.markdown(f"**ROI:** {roi:.2f}% ({roi_ratio}배 수익)")

            except ValueError:
                st.error("입력값에 숫자만 사용하세요.")
else:
    st.title("📊 세부 마진 계산기")
    st.info("세부 마진 계산기 기능은 준비 중입니다.")
