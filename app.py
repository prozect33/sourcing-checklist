import streamlit as st
import pandas as pd

st.set_page_config(page_title="세부 마진 계산기", layout="wide")
st.title("🧾 세부 마진 계산기")

st.markdown("아래 표에 모든 상품 정보를 가로로 입력하세요.")

# 전체 항목 정의
columns = [
    "상품명", "판매가(₩)", "위안화(¥)", "원화(₩)", "수량",
    "수수료율(%)", "광고비율(%)", "입출고비용(₩)", "회수비용(₩)", "재입고비용(₩)",
    "반품률(%)", "기타비용률(%)", "환율(₩/¥)", "포장비(₩)", "사은품비용(₩)"
]

# 기본값 설정
default_row = {
    "상품명": "",
    "판매가(₩)": "",
    "위안화(¥)": "",
    "원화(₩)": "",
    "수량": "1",
    "수수료율(%)": 10.8,
    "광고비율(%)": 20.0,
    "입출고비용(₩)": 3000,
    "회수비용(₩)": 1500,
    "재입고비용(₩)": 500,
    "반품률(%)": 0.1,
    "기타비용률(%)": 2.0,
    "환율(₩/¥)": 350,
    "포장비(₩)": 0,
    "사은품비용(₩)": 0
}

# 표 생성 (5행 기본)
data = pd.DataFrame([default_row.copy() for _ in range(5)])

# 입력 UI
edited_df = st.data_editor(
    data,
    num_rows="dynamic",
    use_container_width=True
)

# 제출 시 결과 출력
if st.button("📊 계산 시작"):
    st.success("입력값 확인:")
    st.dataframe(edited_df)
