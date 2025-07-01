
import streamlit as st

# 초기 설정값
default_settings = {
    "수수료율 (%)": 10.8,
    "광고비율 (%)": 20.0,
    "기타비용율 (%)": 2.0,
    "입출고비 (원)": 3000,
    "반품 회수비 (원)": 1500,
    "재입고비 (원)": 500,
    "반품율 (%)": 10.0,
    "환율 (1위안 = 원)": 350,
}

# 세션 상태 초기화
for key, value in default_settings.items():
    if key not in st.session_state:
        st.session_state[key] = value

# 페이지 설정
st.set_page_config(page_title="마진 계산기", layout="wide")

# 페이지 선택
tab = st.radio("페이지 선택", ["간단 마진 계산기", "세부 마진 계산기"], horizontal=True)
st.markdown("---")

# 설정값 사이드바
with st.sidebar:
    st.header("⚙️ 설정값")
    for key in default_settings:
        st.session_state[key] = st.number_input(key, value=st.session_state[key], step=1.0 if "율" in key else 100, format="%.2f" if "율" in key else "%d")

    if st.button("💾 기본값으로 저장"):
        for key in default_settings:
            default_settings[key] = st.session_state[key]

if tab == "간단 마진 계산기":
    st.markdown("### 📦 **간단 마진 계산기**")

    with st.container():
        col_center = st.columns([1, 2, 1])[1]

        with col_center:
            st.markdown("**판매가**")
            selling_price_input = st.text_input("판매가 입력", label_visibility="collapsed")

            st.markdown("**단가**")
            col1, col2 = st.columns(2)
            with col1:
                cost_cny_input = st.text_input("위안화 입력", label_visibility="collapsed")
            with col2:
                cost_krw_input = st.text_input("원화 입력", label_visibility="collapsed")

            st.markdown("**수량**")
            quantity_input = st.text_input("수량 입력 (기본 1)", value="1", label_visibility="collapsed")

            if st.button("계산하기"):
                try:
                    selling_price = int(selling_price_input.replace(",", "").strip())
                    quantity = int(quantity_input.strip())

                    if cost_krw_input.strip():
                        unit_cost = int(cost_krw_input.replace(",", "").strip())
                    elif cost_cny_input.strip():
                        unit_cost = float(cost_cny_input.strip()) * st.session_state["환율 (1위안 = 원)"]
                    else:
                        st.error("단가를 입력하세요.")
                        st.stop()

                    cost = unit_cost * quantity
                    fee = round((selling_price * st.session_state["수수료율 (%)"] * 1.1) / 100)
                    ad_fee = round((selling_price * st.session_state["광고비율 (%)"] * 1.1) / 100)
                    inout_cost = round(st.session_state["입출고비 (원)"] * 1.1)
                    return_cost = round((st.session_state["반품 회수비 (원)"] + st.session_state["재입고비 (원)"]) * st.session_state["반품율 (%)"] / 100 * 1.1)
                    etc_cost = round(selling_price * st.session_state["기타비용율 (%)"] / 100)
                    total_cost = round(cost + fee + ad_fee + inout_cost + return_cost + etc_cost)
                    profit = selling_price - total_cost
                    supply_price = selling_price / 1.1
                    margin_rate = round((profit / supply_price) * 100, 2)
                    roi = round((profit / cost) * 100, 2)
                    roi_ratio = round((profit / cost) + 1, 1)

                    st.markdown("---")
                    st.subheader("📊 결과")
                    st.markdown(f"**총비용:** {total_cost:,.0f} 원")
                    st.markdown(f"**이익:** {profit:,.0f} 원")
                    st.markdown(f"**마진율:** {margin_rate:.2f}%")
                    st.markdown(f"**ROI:** {roi:.2f}% ({roi_ratio}배 수익)")

                except ValueError:
                    st.error("숫자만 입력 가능합니다.")
