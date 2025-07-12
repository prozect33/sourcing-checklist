import streamlit as st

st.set_page_config(page_title="세부 마진 계산기", layout="wide")
st.title("🧾 세부 마진 계산기")

st.markdown("상품별로 판매가, 원가, 수량을 입력하세요. (계산 기능은 아직 없습니다)")

# 초기 표 행 수
row_count = 5

# 테이블 구조 (입력용)
columns = ["상품명", "판매가(₩)", "위안화(¥)", "원화(₩)", "수량"]
table_data = []

with st.form("margin_input_form"):
    for i in range(row_count):
        cols = st.columns(len(columns))
        row = []
        for j, col_name in enumerate(columns):
            key = f"{col_name}_{i}"
            placeholder = "" if col_name != "수량" else "1"
            value = st.text_input(label=col_name if i == 0 else "", value=placeholder, key=key)
            row.append(value)
        table_data.append(row)
    
    submitted = st.form_submit_button("계산 시작")

if submitted:
    st.success("입력 완료 (계산 기능은 아직 미구현)")
    st.write("입력된 데이터:")
    st.write(table_data)
