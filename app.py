
import streamlit as st

# 페이지 설정
st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# 세션 상태 초기화
if "selected_page" not in st.session_state:
    st.session_state.selected_page = "간단 마진 계산기"

# 탭 스타일 선택
col1, col2 = st.columns([1, 1])
with col1:
    if st.button("간단 마진 계산기"):
        st.session_state.selected_page = "간단 마진 계산기"
with col2:
    if st.button("세부 마진 계산기"):
        st.session_state.selected_page = "세부 마진 계산기"

# 현재 페이지 이름 표시 (선택된 탭은 굵게)
st.markdown(f"### 📦 **{st.session_state.selected_page}**")

# 가운데 정렬된 좁은 입력 섹션
_, center, _ = st.columns([1, 2, 1])

with center:
    st.markdown("#### 판매가")
    selling_price = st.text_input("", key="price", label_visibility="collapsed", placeholder="판매가 입력")

    st.markdown("#### 단가")
    col_cny, col_krw = st.columns(2)
    with col_cny:
        st.markdown("###### 위안화 (¥)")
        cny_input = st.text_input("", key="cny", label_visibility="collapsed", placeholder="위안화 입력")
    with col_krw:
        st.markdown("###### 원화 (₩)")
        krw_input = st.text_input("", key="krw", label_visibility="collapsed", placeholder="원화 입력")

    st.markdown("#### 수량")
    qty_input = st.text_input("", key="qty", label_visibility="collapsed", placeholder="수량 입력 (기본 1)")

    st.button("계산하기")
