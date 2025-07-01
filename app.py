
import streamlit as st

# 기본 설정값
default_values = {
    "FEE_RATE": 10.8,
    "AD_RATE": 20.0,
    "INOUT_COST": 3000,
    "PICKUP_COST": 1500,
    "RESTOCK_COST": 500,
    "RETURN_RATE": 0.1,
    "ETC_RATE": 2.0,
    "EXCHANGE_RATE": 350
}

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# 설정값 슬라이드 패널
with st.sidebar:
    st.header("⚙️ 설정값")
    for key in default_values:
        st.session_state[key] = st.number_input(
            key,
            value=st.session_state.get(key, default_values[key]),
            step=1.0 if isinstance(default_values[key], float) else 100,
            format="%.2f" if isinstance(default_values[key], float) else "%d"
        )

# 탭 선택
tab1, tab2 = st.columns(2)
with tab1:
    if st.button("**간단 마진 계산기**"):
        st.session_state["tab"] = "simple"
with tab2:
    if st.button("세부 마진 계산기"):
        st.session_state["tab"] = "detailed"

if st.session_state.get("tab", "simple") == "simple":
    st.markdown("### 간단 마진 계산기")

    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown("#### 판매가")
        selling_price = st.number_input("판매가", value=20000, step=100, label_visibility="collapsed")

        st.markdown("#### 단가")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("###### 위안화 (¥)")
            cny_price = st.text_input("위안화", label_visibility="collapsed")
        with col2:
            st.markdown("###### 원화 (₩)")
            krw_price = st.text_input("원화", label_visibility="collapsed")

        st.markdown("#### 수량")
        quantity = st.number_input("수량", min_value=1, value=1, step=1)

        if st.button("계산하기"):
            if krw_price:
                unit_cost = int(krw_price.replace(",", "").strip())
            elif cny_price:
                unit_cost = int(float(cny_price.strip()) * st.session_state["EXCHANGE_RATE"])
            else:
                st.error("단가를 입력해주세요.")
                st.stop()

            total_cost_price = unit_cost * quantity
            fee = round(selling_price * st.session_state["FEE_RATE"] / 100)
            ad_fee = round(selling_price * st.session_state["AD_RATE"] / 100)
            inout_cost = round(st.session_state["INOUT_COST"])
            return_cost = round((st.session_state["PICKUP_COST"] + st.session_state["RESTOCK_COST"]) * st.session_state["RETURN_RATE"])
            etc_cost = round(selling_price * st.session_state["ETC_RATE"] / 100)

            total_expense = total_cost_price + fee + ad_fee + inout_cost + return_cost + etc_cost
            profit = selling_price - total_expense
            supply_price = selling_price / 1.1
            margin_rate = round((profit / supply_price) * 100, 2)
            roi = round((profit / total_cost_price) * 100, 2)
            roi_ratio = round((profit / total_cost_price) + 1, 1)

            st.markdown(f"**수수료:** {fee:,} 원")
            st.markdown(f"**광고비:** {ad_fee:,} 원")
            st.markdown(f"**입출고비용:** {inout_cost:,} 원")
            st.markdown(f"**반품비용:** {return_cost:,} 원")
            st.markdown(f"**기타비용:** {etc_cost:,} 원")
            st.markdown(f"**총비용:** {total_expense:,} 원")
            st.markdown(f"**이익:** {profit:,} 원")
            st.markdown(f"**마진율:** {margin_rate:.2f}%")
            st.markdown(f"**ROI:** {roi:.2f}% ({roi_ratio}배 수익)")
