
import streamlit as st

# 기본 설정값
DEFAULTS = {
    "FEE_RATE": 10.8,
    "AD_RATE": 20.0,
    "BASE_INOUT_COST": 3000,
    "BASE_PICKUP_COST": 1500,
    "BASE_RESTOCK_COST": 500,
    "RETURN_RATE": 10.0,
    "ETC_COST_RATE": 2.0,
    "EXCHANGE_RATE": 350
}

# 세션 상태 초기화
if "settings" not in st.session_state:
    st.session_state["settings"] = DEFAULTS.copy()

# 저장 함수
def save_defaults():
    for key in DEFAULTS:
        st.session_state["settings"][key] = st.session_state.get(key, DEFAULTS[key])
    st.success("✅ 설정값이 저장되었습니다.")

# 탭 전환
tab = st.radio("페이지 선택", ["간단 마진 계산기", "세부 마진 계산기"], horizontal=True,
               label_visibility="collapsed")

# 설정값 사이드바
with st.sidebar:
    st.subheader("⚙️ 설정값")
    st.number_input("수수료율 (%)", key="FEE_RATE", value=st.session_state["settings"]["FEE_RATE"])
    st.number_input("광고비율 (%)", key="AD_RATE", value=st.session_state["settings"]["AD_RATE"])
    st.number_input("기타비용 (% 판매가 대비)", key="ETC_COST_RATE", value=st.session_state["settings"]["ETC_COST_RATE"])
    st.number_input("입출고비 (원)", key="BASE_INOUT_COST", value=st.session_state["settings"]["BASE_INOUT_COST"])
    st.number_input("반품 회수비 (원)", key="BASE_PICKUP_COST", value=st.session_state["settings"]["BASE_PICKUP_COST"])
    st.number_input("재입고비 (원)", key="BASE_RESTOCK_COST", value=st.session_state["settings"]["BASE_RESTOCK_COST"])
    st.number_input("반품율 (%)", key="RETURN_RATE", value=st.session_state["settings"]["RETURN_RATE"])
    st.number_input("환율 (1위안 = 원)", key="EXCHANGE_RATE", value=st.session_state["settings"]["EXCHANGE_RATE"])
    st.button("💾 기본값으로 저장", on_click=save_defaults)

if tab == "간단 마진 계산기":
    st.markdown("<h2 style='text-align: center;'>📦 간단 마진 계산기</h2>", unsafe_allow_html=True)

    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown("#### 판매가")
        price_input = st.text_input("판매가", key="price", label_visibility="collapsed")

        st.markdown("#### 단가")
        col_yuan, col_won = st.columns(2)
        with col_yuan:
            yuan_price = st.text_input("위안화 (¥)", key="cny_price")
        with col_won:
            won_price = st.text_input("원화 (₩)", key="krw_price")

        st.markdown("#### 수량")
        quantity = st.text_input("수량", key="qty", value="1")

        calculate_button = st.button("계산하기")

    if calculate_button:
        try:
            selling_price = int(price_input.replace(",", "").strip())
            quantity = int(quantity.strip())

            if won_price.strip():
                cost = int(won_price.replace(",", "").strip()) * quantity
            elif yuan_price.strip():
                cost = int(float(yuan_price.strip()) * st.session_state["settings"]["EXCHANGE_RATE"]) * quantity
            else:
                st.error("단가를 입력하세요.")
                st.stop()

            fee = round((selling_price * st.session_state["settings"]["FEE_RATE"] * 1.1) / 100)
            ad_fee = round((selling_price * st.session_state["settings"]["AD_RATE"] * 1.1) / 100)
            inout_cost = round(st.session_state["settings"]["BASE_INOUT_COST"] * 1.1)
            return_cost = round((st.session_state["settings"]["BASE_PICKUP_COST"] +
                                 st.session_state["settings"]["BASE_RESTOCK_COST"]) *
                                 (st.session_state["settings"]["RETURN_RATE"] / 100) * 1.1)
            etc_cost = round(selling_price * st.session_state["settings"]["ETC_COST_RATE"] / 100)

            total_cost = round(cost + fee + ad_fee + inout_cost + return_cost + etc_cost)
            profit = selling_price - total_cost
            supply_price = selling_price / 1.1
            margin_rate = round((profit / supply_price) * 100, 2)
            roi = round((profit / cost) * 100, 2)
            roi_ratio = round((profit / cost) + 1, 1)

            with center:
                st.markdown(f"**수수료:** {fee:,} 원")
                st.markdown(f"**광고비:** {ad_fee:,} 원")
                st.markdown(f"**입출고비용:** {inout_cost:,} 원")
                st.markdown(f"**반품비용:** {return_cost:,} 원")
                st.markdown(f"**기타비용:** {etc_cost:,} 원")
                st.markdown(f"**총비용:** {total_cost:,} 원")
                st.markdown(f"**이익:** {profit:,} 원")
                st.markdown(f"**마진율:** {margin_rate:.2f}%")
                st.markdown(f"**ROI:** {roi:.2f}% ({roi_ratio}배 수익)")

        except Exception as e:
            st.error("입력값 오류 또는 계산 중 문제 발생")
