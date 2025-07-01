
import streamlit as st

# 기본 설정값
DEFAULTS = {
    "수수료율 (%)": 10.8,
    "광고비율 (%)": 20.0,
    "기타비용 (% 판매가 대비)": 2.0,
    "입출고비 (원)": 3000,
    "반품 회수비 (원)": 1500,
    "재입고비 (원)": 500,
    "반품율 (%)": 10.0,
    "환율 (1위안 = 원)": 350
}

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# 설정값 초기화
if "settings" not in st.session_state:
    st.session_state.settings = DEFAULTS.copy()

# 왼쪽 설정값 영역
with st.sidebar:
    st.markdown("### ⚙️ 설정값")
    for key in DEFAULTS.keys():
        st.session_state.settings[key] = st.number_input(
            label=key,
            value=st.session_state.settings[key],
            key=key,
            label_visibility="visible",
            step=1.0 if isinstance(DEFAULTS[key], float) else 100,
            format="%.2f" if isinstance(DEFAULTS[key], float) else "%d"
        )
    if st.button("📌 기본값으로 저장"):
        DEFAULTS.update(st.session_state.settings)

# 가운데 입력 영역
_, center, _ = st.columns([1, 1, 1])

with center:
    st.title("📦 간단 마진 계산기")
    st.markdown("#### **판매가**")
    selling_price_input = st.text_input("판매가", value="20000", label_visibility="collapsed")

    st.markdown("#### **원가**")
    col_yuan, col_won = st.columns(2)
    with col_yuan:
        st.markdown("###### 위안화 (¥)")
        cost_cny_input = st.text_input("위안화", value="", label_visibility="collapsed")
    with col_won:
        st.markdown("###### 원화 (₩)")
        cost_krw_input = st.text_input("원화", value="", label_visibility="collapsed")

    calculate_button = st.button("계산하기")

# 계산 로직
if calculate_button:
    try:
        selling_price = int(selling_price_input.replace(",", "").strip())

        if cost_krw_input.strip():
            cost = int(cost_krw_input.replace(",", "").strip())
        elif cost_cny_input.strip():
            rate = st.session_state.settings["환율 (1위안 = 원)"]
            cost = int(float(cost_cny_input.strip()) * rate)
        else:
            st.error("원가를 입력하세요.")
            st.stop()

        # 설정값 불러오기
        FEE_RATE = st.session_state.settings["수수료율 (%)"]
        AD_RATE = st.session_state.settings["광고비율 (%)"]
        ETC_RATE = st.session_state.settings["기타비용 (% 판매가 대비)"]
        BASE_INOUT_COST = st.session_state.settings["입출고비 (원)"]
        PICKUP_COST = st.session_state.settings["반품 회수비 (원)"]
        RESTOCK_COST = st.session_state.settings["재입고비 (원)"]
        RETURN_RATE = st.session_state.settings["반품율 (%)"] / 100

        # 비용 계산
        fee = round((selling_price * FEE_RATE * 1.1) / 100)
        ad_fee = round((selling_price * AD_RATE * 1.1) / 100)
        inout_cost = round(BASE_INOUT_COST * 1.1)
        return_cost = round((PICKUP_COST + RESTOCK_COST) * RETURN_RATE * 1.1)
        etc_cost = round(selling_price * (ETC_RATE / 100))
        total_cost = round(cost + fee + ad_fee + inout_cost + return_cost + etc_cost)
        profit = selling_price - total_cost
        supply_price = selling_price / 1.1
        margin_rate = round((profit / supply_price) * 100, 2)
        roi = round((profit / cost) * 100, 2)
        roi_ratio = round((profit / cost) + 1, 1)

        st.markdown("## ")
        with center:
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
