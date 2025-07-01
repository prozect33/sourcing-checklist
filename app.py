import streamlit as st
import json
import os

SETTINGS_FILE = "settings.json"

# 기본값
default_values = {
    "수수료율 (%)": 10.8,
    "광고비율 (%)": 20.0,
    "입출고비용 (원)": 3000,
    "회수비용 (원)": 1500,
    "재입고비용 (원)": 500,
    "반품률 (%)": 0.1,
    "기타비용률 (%)": 2.0,
    "위안화 환율": 350
}

# 정수 항목 정의
int_keys = ["입출고비용 (원)", "회수비용 (원)", "재입고비용 (원)", "위안화 환율"]
float_keys = [k for k in default_values if k not in int_keys]

# 설정 파일 불러오기
if os.path.exists(SETTINGS_FILE):
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            loaded_values = json.load(f)
            for k, v in loaded_values.items():
                if k in int_keys:
                    default_values[k] = int(v)
                else:
                    default_values[k] = float(v)
    except Exception as e:
        st.error(f"설정값 불러오기 실패: {e}")

# 세션 상태 초기화
for key, value in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# 설정값 탭
with st.sidebar:
    st.header("⚙️ 설정값")
    with st.form("settings_form"):
        new_values = {}
        for key in default_values:
            new_values[key] = st.text_input(key, value=str(int(st.session_state[key]) if key in int_keys else st.session_state[key]))
        submitted = st.form_submit_button("기본값으로 저장")
        if submitted:
            try:
                for key in default_values:
                    if key in int_keys:
                        st.session_state[key] = int(float(new_values[key]))
                    else:
                        st.session_state[key] = float(new_values[key])
                with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                    json.dump({k: int(st.session_state[k]) if k in int_keys else st.session_state[k] for k in default_values}, f, ensure_ascii=False, indent=2)
                st.success("기본값이 저장되었습니다.")
            except Exception as e:
                st.error(f"저장 중 오류 발생: {e}")

# 탭 구성
tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

with tab1:
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
                unit_cost = int(float(cny_price.strip()) * st.session_state["위안화 환율"])
            else:
                st.error("단가를 입력해주세요.")
                st.stop()

            total_cost_price = unit_cost * quantity
            fee = round(selling_price * st.session_state["수수료율 (%)"] / 100)
            ad_fee = round(selling_price * st.session_state["광고비율 (%)"] / 100)
            inout_cost = round(st.session_state["입출고비용 (원)"])
            return_cost = round((st.session_state["회수비용 (원)"] + st.session_state["재입고비용 (원)"]) * st.session_state["반품률 (%)"])
            etc_cost = round(selling_price * st.session_state["기타비용률 (%)"] / 100)

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

with tab2:
    st.info("세부 마진 계산기는 아직 구현되지 않았습니다.")
