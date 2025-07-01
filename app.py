
import streamlit as st

# 상수 초기값
DEFAULTS = {
    "수수료율(%)": 10.8,
    "광고비율(%)": 20.0,
    "기타비용(%)": 2.0,
    "입출고비(원)": 3000,
    "반품 회수비(원)": 1500,
    "재입고비(원)": 500,
    "반품율(%)": 10.0,
    "환율(1위안 = 원)": 350,
}

# 세션 상태에 저장된 값 불러오기 또는 초기화
for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# 탭 선택
tab1, tab2 = st.columns([1, 8])
with tab1:
    tab_selection = st.radio("페이지 선택", ["간단 마진 계산기", "세부 마진 계산기"], horizontal=True, label_visibility="collapsed")
st.markdown("## ")

if tab_selection == "간단 마진 계산기":
    # 왼쪽 설정값 입력
    with st.sidebar:
        st.markdown("### ⚙️ 설정값")
        for key in DEFAULTS:
            st.session_state[key] = st.number_input(key, value=st.session_state[key], key=key)

        if st.button("📄 기본값으로 저장"):
            for key in DEFAULTS:
                DEFAULTS[key] = st.session_state[key]

    # 중앙 입력 폼
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("#### **📦 간단 마진 계산기**")
        st.markdown("#### 판매가")
        selling_price_input = st.text_input("판매가", value="", key="selling_price", label_visibility="collapsed")

        st.markdown("#### 단가")
        cny, krw = st.columns(2)
        with cny:
            st.markdown("###### 위안화 (¥)")
            cost_cny_input = st.text_input("위안화", value="", key="cny_input", label_visibility="collapsed")
        with krw:
            st.markdown("###### 원화 (₩)")
            cost_krw_input = st.text_input("원화", value="", key="krw_input", label_visibility="collapsed")

        st.markdown("#### 수량")
        quantity_input = st.text_input("수량", value="1", key="quantity", label_visibility="collapsed")

        if st.button("계산하기"):
            try:
                selling_price = int(selling_price_input.replace(",", "").strip())
                quantity = int(quantity_input.replace(",", "").strip())
                if cost_krw_input.strip():
                    unit_cost = int(cost_krw_input.replace(",", "").strip())
                elif cost_cny_input.strip():
                    unit_cost = float(cost_cny_input.replace(",", "").strip()) * st.session_state["환율(1위안 = 원)"]
                else:
                    st.error("단가를 입력하세요.")
                    st.stop()

                cost = round(unit_cost * quantity)
                fee = round((selling_price * st.session_state["수수료율(%)"] * 1.1) / 100)
                ad_fee = round((selling_price * st.session_state["광고비율(%)"] * 1.1) / 100)
                inout_cost = round(st.session_state["입출고비(원)"] * 1.1)
                return_cost = round((st.session_state["반품 회수비(원)"] + st.session_state["재입고비(원)"])
                                    * st.session_state["반품율(%)"] / 100 * 1.1)
                etc_cost = round(selling_price * st.session_state["기타비용(%)"] / 100)
                total_cost = round(cost + fee + ad_fee + inout_cost + return_cost + etc_cost)
                profit = selling_price - total_cost
                supply_price = selling_price / 1.1
                margin_rate = round((profit / supply_price) * 100, 2)
                roi = round((profit / cost) * 100, 2)
                roi_ratio = round((profit / cost) + 1, 1)

                st.markdown("---")
                st.markdown(f"**수수료:** {fee:,} 원")
                st.markdown(f"**광고비:** {ad_fee:,} 원")
                st.markdown(f"**입출고비용:** {inout_cost:,} 원")
                st.markdown(f"**반품비용:** {return_cost:,} 원")
                st.markdown(f"**기타비용:** {etc_cost:,} 원")
                st.markdown(f"**총비용:** {total_cost:,} 원")
                st.markdown(f"**이익:** {profit:,} 원")
                st.markdown(f"**마진율:** {margin_rate:.2f}%")
                st.markdown(f"**ROI:** {roi:.2f}% ({roi_ratio}배 수익)")
            except ValueError:
                st.error("입력값에 숫자만 사용하세요.")
