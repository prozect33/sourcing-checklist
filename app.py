
import streamlit as st

# 상수 설정
FEE_RATE = 10.8
AD_RATE = 20
BASE_INOUT_COST = 3000
BASE_PICKUP_COST = 1500
BASE_RESTOCK_COST = 500
RETURN_RATE = 0.1
EXCHANGE_RATE = 350

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

tab_options = ["간단마진계산기", "세부마진계산기"]
selected_tab = st.sidebar.radio("", tab_options)

tab_titles = {tab: f"**{tab}**" if tab == selected_tab else tab for tab in tab_options}

left, center, right = st.columns([1, 1, 1])

# 왼쪽 설정값 – 강조 없이 동일 스타일로
with left:
    st.markdown("### ⚙️ 설정값")
    st.markdown("- 수수료율: 10.8%")
    st.markdown("- 광고비율: 20%")
    st.markdown("- 기타비용: 판매가의 2%")
    st.markdown("- 입출고비: 3,000원")
    st.markdown("- 반품비: 회수 1,500원 + 재입고 500원 (반품율 10%)")
    st.markdown("- 환율: 1위안 = 350원")

with center:
    st.title(tab_titles[selected_tab])

if selected_tab == "간단마진계산기":
    with center:
        st.markdown("#### 판매가")
        selling_price_input = st.text_input("판매가", value="20000", max_chars=10, label_visibility="collapsed", key="price_input")

        st.markdown("#### 원가")
        col_yuan, col_won = st.columns(2)
        with col_yuan:
            st.markdown("###### 위안화 (¥)")
            cost_cny_input = st.text_input("위안화 입력", value="", max_chars=10, label_visibility="collapsed", key="cny_input")
        with col_won:
            st.markdown("###### 원화 (₩)")
            cost_krw_input = st.text_input("원화 입력", value="", max_chars=10, label_visibility="collapsed", key="krw_input")

        calculate_button = st.button("계산하기")

    if calculate_button:
        try:
            selling_price = int(selling_price_input.replace(",", "").strip())

            if cost_krw_input.strip():
                cost = int(cost_krw_input.replace(",", "").strip())
            elif cost_cny_input.strip():
                cost = int(float(cost_cny_input.strip()) * EXCHANGE_RATE)
            else:
                st.error("원가를 입력하세요.")
                st.stop()

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

            st.markdown("## ")
            with center:
                st.markdown(f"수수료: {fee:,} 원")
                st.markdown(f"광고비: {ad_fee:,} 원")
                st.markdown(f"입출고비용: {inout_cost:,} 원")
                st.markdown(f"반품비용: {return_cost:,} 원")
                st.markdown(f"기타비용: {etc_cost:,} 원")
                st.markdown(f"총비용: {total_cost:,} 원")
                st.markdown(f"이익: {profit:,} 원")
                st.markdown(f"마진율: {margin_rate:.2f}%")
                st.markdown(f"ROI: {roi:.2f}% ({roi_ratio}배 수익)")

        except ValueError:
            st.error("입력값에 숫자만 사용하세요.")
