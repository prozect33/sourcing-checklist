
import streamlit as st

# 페이지 설정
st.set_page_config(layout="wide", page_title="간단 마진 계산기")

# 초기 기본값 설정
default_values = {
    "수수료율 (%)": 10.8,
    "광고비율 (%)": 20.0,
    "기타비용율 (%)": 2.0,
    "입출고비 (원)": 3000,
    "반품 최소비 (원)": 1500,
    "재입고비 (원)": 500,
    "반품율 (%)": 10.0,
    "환율 (1위안 = 원)": 350
}

if "기본값" not in st.session_state:
    st.session_state["기본값"] = default_values.copy()

def reset_to_default():
    for key, value in st.session_state["기본값"].items():
        st.session_state[key] = value

# 페이지 선택
col1, col2 = st.columns([1, 8])
with col1:
    with st.sidebar:
        st.markdown("### ⚙️ 설정값")
        for key in default_values:
            if "비율" in key:
                st.session_state[key] = st.number_input(key, value=st.session_state.get(key, default_values[key]), step=0.1, format="%.2f", key=key)
            else:
                st.session_state[key] = st.number_input(key, value=st.session_state.get(key, default_values[key]), step=100, key=key)
        if st.button("💾 기본값으로 저장"):
            st.session_state["기본값"] = {key: st.session_state[key] for key in default_values}

with col2:
    st.markdown("### 페이지 선택")
    mode = st.radio("", ["간단 마진 계산기", "세부 마진 계산기"], horizontal=True)

    if mode == "간단 마진 계산기":
        st.markdown("## 📦 **간단 마진 계산기**")

        판매가 = st.number_input("판매가 입력", value=0, step=100)

        st.markdown("### 단가")
        col_위안, col_원화 = st.columns(2)
        with col_위안:
            위안화 = st.number_input("위안화 입력", value=0.0, format="%.2f")
        with col_원화:
            원화 = st.number_input("원화 입력", value=0)

        수량 = st.number_input("수량 입력 (기본 1)", value=1, step=1)

        if st.button("계산하기"):
            # 단가 계산
            환율 = st.session_state["환율 (1위안 = 원)"]
            단가 = 0
            if 위안화 > 0:
                단가 = 위안화 * 환율
            elif 원화 > 0:
                단가 = 원화
            원가 = 단가 * 수량

            공급가액 = 판매가 / 1.1
            수수료 = round(공급가액 * (st.session_state["수수료율 (%)"] / 100))
            광고비 = round(판매가 * (st.session_state["광고비율 (%)"] / 100))
            기타비 = round(판매가 * (st.session_state["기타비용율 (%)"] / 100))
            반품비 = round((st.session_state["반품 최소비 (원)"] + st.session_state["재입고비 (원)"]) * (st.session_state["반품율 (%)"] / 100))
            총비용 = 원가 + 수수료 + 광고비 + 기타비 + 반품비 + st.session_state["입출고비 (원)"]
            이익 = 판매가 - 총비용
            공급가 = 판매가 / 1.1
            순마진율 = round((이익 / 공급가) * 100, 2)
            ROI = round((이익 / 원가) * 100, 2) if 원가 != 0 else 0

            st.markdown("### 💡 결과")
            st.write(f"- 단가: {int(단가)}원")
            st.write(f"- 원가: {int(원가)}원 (단가 × 수량 = {int(단가)} × {int(수량)})")
            st.write(f"- 수수료: {수수료}원 (공급가액 × 수수료율)")
            st.write(f"- 광고비: {광고비}원 (판매가 × 광고비율)")
            st.write(f"- 기타비: {기타비}원 (판매가 × 기타비율)")
            st.write(f"- 반품비: {반품비}원 (최소비+재입고비 × 반품율)")
            st.write(f"- 입출고비: {st.session_state['입출고비 (원)']}원")
            st.write(f"- 총비용: {총비용}원")
            st.write(f"- 이익: {이익}원")
            st.write(f"- 순마진율: {순마진율}%")
            st.write(f"- ROI: {ROI}% (투자금 {int(원가)}원 대비 수익금 {이익}원)")

    else:
        st.markdown("## ✏️ **세부 마진 계산기**")
        st.info("세부 마진 계산기는 현재 준비 중입니다.")
