
import streamlit as st

st.set_page_config(layout="wide")

# 설정값 초기화
default_values = {
    "수수료율 (%)": 10.80,
    "광고비율 (%)": 20.00,
    "기타비용율 (%)": 2.00,
    "입출고비 (원)": 3000.0,
    "반품 회수비 (원)": 1500.0,
    "재입고비 (원)": 500.0,
    "반품률 (%)": 10.00,
    "환율 (1위안 = 원)": 350.0,
}

if "설정값" not in st.session_state:
    st.session_state["설정값"] = default_values.copy()

# 사이드바 - 설정값
with st.sidebar:
    st.header("⚙️ 설정값")
    for key in default_values:
        step_val = 0.01 if "율" in key else 100.0
        st.session_state["설정값"][key] = st.number_input(
            key, value=st.session_state["설정값"][key], step=step_val, format="%.2f" if "율" in key else "%.0f"
        )
    if st.button("💾 기본값으로 저장"):
        default_values.update(st.session_state["설정값"])

# 페이지 선택
page = st.radio("페이지 선택", ["간단 마진 계산기", "세부 마진 계산기"], horizontal=True)

# 본문
st.title(f"📦 {page}")

if page == "간단 마진 계산기":
    col_center = st.columns([1, 2, 1])[1]
    with col_center:
        st.markdown("### 판매가")
        price = st.text_input("판매가 입력", label_visibility="collapsed")

        st.markdown("### 단가")
        col1, col2 = st.columns(2)
        with col1:
            unit_yuan = st.text_input("위안화 입력", label_visibility="visible", placeholder="위안화 입력")
        with col2:
            unit_krw = st.text_input("원화 입력", label_visibility="visible", placeholder="원화 입력")

        st.markdown("### 수량")
        quantity = st.text_input("수량 입력 (기본 1)", value="1")

        st.button("계산하기")
