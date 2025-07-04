
import streamlit as st

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

left, right = st.columns(2)

with left:
    st.subheader("판매정보 입력")
    sell_price = st.text_input("판매가", key="판매가")
    col1, col2 = st.columns(2)
    with col1:
        unit_yuan = st.text_input("위안화", key="위안화")
    with col2:
        unit_won = st.text_input("원화", key="원화")
    qty = st.text_input("수량", key="수량")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        calculate = st.button("계산하기")
    with col_b:
        if st.button("리셋하기"):
            st.session_state["판매가"] = ""
            st.session_state["위안화"] = ""
            st.session_state["원화"] = ""
            st.session_state["수량"] = ""

with right:
    if calculate:
        st.markdown("### 📊 계산 결과")
        st.write(f"**판매가:** {sell_price}")
        st.write(f"**위안화:** {unit_yuan}")
        st.write(f"**원화:** {unit_won}")
        st.write(f"**수량:** {qty}")
