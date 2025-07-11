import streamlit as st
import json
import os
import math

# Streamlit 간단 마진 계산기 (원본 기반, 풀버전)
st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# 설정 파일 및 기본값
default_config = {
    "FEE_RATE": 10.8,       # 수수료율 (%)
    "AD_RATE": 20.0,        # 광고비율 (%)
    "INOUT_COST": 3000,     # 입출고비용 (원)
    "PICKUP_COST": 1500,    # 회수비용 (원)
    "RESTOCK_COST": 500,    # 재입고비용 (원)
    "RETURN_RATE": 0.1,     # 반품률 (%)
    "ETC_RATE": 2.0,        # 기타비용률 (%)
    "EXCHANGE_RATE": 350    # 환율 (1위안 = 원)
}
CONFIG_FILE = "default_config.json"

# 설정 로드/저장 함수
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                # 문자열 숫자 처리
                return {k: float(v) if isinstance(v, str) and v.replace('.', '', 1).isdigit() else v for k, v in data.items()}
        except:
            return default_config
    return default_config


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f)

# 숫자 포매팅 함수
def format_number(val):
    return f"{int(val):,}" if float(val).is_integer() else f"{val:,.2f}"

def format_input(val):
    return str(int(val)) if float(val).is_integer() else str(val)

# 설정 불러오기
config = load_config()

# 사이드바 설정 UI
st.sidebar.header("🛠️ 설정값")
for key, label in [
    ("FEE_RATE", "수수료율 (%)"),
    ("AD_RATE", "광고비율 (%)"),
    ("INOUT_COST", "입출고비용 (원)"),
    ("PICKUP_COST", "회수비용 (원)"),
    ("RESTOCK_COST", "재입고비용 (원)"),
    ("RETURN_RATE", "반품률 (%)"),
    ("ETC_RATE", "기타비용률 (%)"),
    ("EXCHANGE_RATE", "환율 (1¥ → 원)")
]:
    config[key] = st.sidebar.text_input(label, value=format_input(config[key]), key=key)

if st.sidebar.button("📂 기본값 저장"):
    save_config(config)
    st.sidebar.success("저장 완료")

# 탭 생성
tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

with tab1:
    # 입력 칼럼
    left, right = st.columns(2)
    with left:
        st.subheader("판매정보 입력")
        sell_price_raw = st.text_input("판매가 (원)", key="sell_price_raw")

        # 여유 공간(플레이스홀더) 생성
        placeholder = st.empty()

    with right:
        # 계산 버튼 및 리셋
        if st.button("계산하기"):
            # nothing here
            pass
        if st.button("리셋", on_click=lambda: st.session_state.clear()):
            pass

    # 입력 후 동적 표시
    if sell_price_raw:
        try:
            selling_price = float(sell_price_raw)
            # 50% 마진 기준 원가
            target_rate = 50.0 / 100
            cost_won = round(selling_price * (1 - target_rate))
            cost_yuan = round(cost_won / float(config['EXCHANGE_RATE']), 2)
            margin_val = round(selling_price - cost_won)
            text = f"마진율 50% 기준: {format_number(cost_won)}원 ({cost_yuan}위안), 마진: {format_number(margin_val)}원"
        except:
            text = "숫자를 올바르게 입력해주세요."
        placeholder.markdown(f"**{text}**")

with tab2:
    st.subheader("세부 마진 계산기")
    st.info("준비 중입니다...")
