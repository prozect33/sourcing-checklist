
import streamlit as st

# 초기 설정값 (세션 상태에 저장)
default_settings = {
    "수수료율(%)": 10.8,
    "광고비율(%)": 20.0,
    "기타비용 (% 판매가 대비)": 2.0,
    "입출고비 (원)": 3000,
    "반품 회수비 (원)": 1500,
    "재입고비 (원)": 500,
    "반품율 (%)": 10.0,
    "환율 (1위안 = 원)": 350
}

# 세션 상태에 초기값 설정
for key, value in default_settings.items():
    if key not in st.session_state:
        st.session_state[key] = value

# 페이지 설정
st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# 탭 선택
tabs = ["간단 마진 계산기", "세부 마진 계산기"]
selected_tab = st.radio("", tabs, horizontal=True)
st.markdown("---")

# 왼쪽에 설정값 입력
with st.sidebar:
    st.header("⚙️ 설정값")
    for key in default_settings.keys():
        st.number_input(key, value=st.session_state[key], key=key)
    if st.button("💾 기본값으로 저장"):
        for key in default_settings.keys():
            st.session_state[key] = st.session_state[key]

# 간단 마진 계산기 탭
if selected_tab == "간단 마진 계산기":
    st.title("📦 간단 마진 계산기")

    st.markdown("#### 판매가")
    selling_price_input = st.text_input("판매가", value="", max_chars=10, label_visibility="collapsed", key="price_input")

    st.markdown("#### 단가")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("###### 위안화 (¥)")
        cost_cny_input = st.text_input("위안화 입력", value="", max_chars=10, label_visibility="collapsed", key="cny_input")
    with col2:
        st.markdown("###### 원화 (₩)")
        cost_krw_input = st.text_input("원화 입력", value="", max_chars=10, label_visibility="collapsed", key="krw_input")

    st.markdown("#### 수량")
    quantity_input = st.text_input("수량 입력", value="1", max_chars=5, label_visibility="collapsed", key="qty_input")

    if st.button("계산하기"):
        try:
            selling_price = int(selling_price_input.replace(",", "").strip())
            quantity = int(quantity_input.strip())

            if cost_krw_input.strip():
                cost = int(cost_krw_input.replace(",", "").strip()) * quantity
            elif cost_cny_input.strip():
                rate = st.session_state["환율 (1위안 = 원)"]
                cost = int(float(cost_cny_input.strip()) * rate * quantity)
            else:
                st.error("원가를 입력하세요.")
                st.stop()

            # 설정값
            fee_rate = st.session_state["수수료율(%)"]
            ad_rate = st.session_state["광고비율(%)"]
            etc_rate = st.session_state["기타비용 (% 판매가 대비)"]
            inout_cost = st.session_state["입출고비 (원)"]
            pickup_cost = st.session_state["반품 회수비 (원)"]
            restock_cost = st.session_state["재입고비 (원)"]
            return_rate = st.session_state["반품율 (%)"] / 100

            fee = round((selling_price * fee_rate * 1.1) / 100)
            ad_fee = round((selling_price * ad_rate * 1.1) / 100)
            etc_cost = round(selling_price * (etc_rate / 100))
            return_cost = round((pickup_cost + restock_cost) * return_rate * 1.1)
            inout = round(inout_cost * 1.1)

            total_cost = cost + fee + ad_fee + inout + return_cost + etc_cost
            profit = selling_price - total_cost
            supply_price = selling_price / 1.1
            margin_rate = round((profit / supply_price) * 100, 2)
            roi = round((profit / cost) * 100, 2)
            roi_ratio = round((profit / cost) + 1, 1)

            st.markdown("## 결과")
            st.markdown(f"**수수료:** {fee:,} 원")
            st.markdown(f"**광고비:** {ad_fee:,} 원")
            st.markdown(f"**입출고비용:** {inout:,} 원")
            st.markdown(f"**반품비용:** {return_cost:,} 원")
            st.markdown(f"**기타비용:** {etc_cost:,} 원")
            st.markdown(f"**총비용:** {total_cost:,} 원")
            st.markdown(f"**이익:** {profit:,} 원")
            st.markdown(f"**마진율:** {margin_rate:.2f}%")
            st.markdown(f"**ROI:** {roi:.2f}% ({roi_ratio}배 수익)")

        except ValueError:
            st.error("숫자만 입력하세요.")
