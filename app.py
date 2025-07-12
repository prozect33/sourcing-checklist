import streamlit as st
import pandas as pd

st.set_page_config(page_title="세부 마진 계산기", layout="wide")
st.title("🧾 세부 마진 계산기")

st.markdown("상품별로 정보를 가로 표 형식으로 입력하세요.")

# 기본 입력 표 데이터 생성
default_data = pd.DataFrame([
    {"상품명": "", "판매가(₩)": "", "위안화(¥)": "", "원화(₩)": "", "수량": "1"}
    for _ in range(5)
])

# 표 형식 입력 UI
edited_df = st.data_editor(
    default_data,
    num_rows="dynamic",  # 행 수 추가 가능
    use_container_width=True
)

# 제출 버튼
if st.button("📊 계산 시작"):
    st.success("입력값 확인:")
    st.dataframe(edited_df)
