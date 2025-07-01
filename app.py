
import streamlit as st

# 기본 설정값
default_values = {
    "수수료율(%)": 10.8,
    "광고비율(%)": 20.0,
    "기타비용율(%)": 2.0,
    "입출고비용": 3000,
    "반품 회수비": 1500,
    "재입고비": 500,
    "반품율(%)": 10.0,
    "환율(1위안=원)": 350
}

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# 설정값 입력
with st.sidebar:
    st.markdown("### ⚙️ 설정값")
    for key in default_values:
        default = default_values[key]
        step = 0.1 if isinstance(default, float) else 100
        st.session_state[key] = st.number_input(
            key,
            value=st.session_state.get(key, default),
            step=step,
            key=key
        )

    if st.button("💾 기본값으로 저장"):
        for key in default_values:
            default_values[key] = st.session_state[key]

# 본문 제목과 입력 필드
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("### 간단 마진 계산기")

    st.markdown("#### 판매가")
    selling_price = st.text_input("판매가", value="20000", label_visibility="collapsed", key="판매가")

    st.markdown("#### 단가")
    unit_price_col1, unit_price_col2 = st.columns(2)
    with unit_price_col1:
        st.markdown("##### 위안화 (¥)")
        cny_cost = st.text_input("위안화", value="", label_visibility="collapsed", key="위안화")
    with unit_price_col2:
        st.markdown("##### 원화 (₩)")
        krw_cost = st.text_input("원화", value="", label_visibility="collapsed", key="원화")

    st.markdown("#### 수량")
    quantity = st.number_input("수량", value=1, min_value=1, step=1, key="수량")

    if st.button("계산하기"):
        try:
            selling_price = int(selling_price.replace(",", ""))
            if krw_cost:
                unit_cost = int(krw_cost.replace(",", ""))
            elif cny_cost:
                unit_cost = int(float(cny_cost) * st.session_state["환율(1위안=원)"])
            else:
                st.error("단가를 입력하세요.")
                st.stop()

            cost = unit_cost * quantity
            수수료 = round((selling_price * st.session_state["수수료율(%)"] * 1.1) / 100)
            광고비 = round((selling_price * st.session_state["광고비율(%)"] * 1.1) / 100)
            입출고비 = round(st.session_state["입출고비용"] * 1.1)
            반품비 = round((st.session_state["반품 회수비"] + st.session_state["재입고비"]) * st.session_state["반품율(%)"] / 100 * 1.1)
            기타비 = round(selling_price * st.session_state["기타비용율(%)"] / 100)
            총비용 = cost + 수수료 + 광고비 + 입출고비 + 반품비 + 기타비
            이익 = selling_price - 총비용
            공급가 = selling_price / 1.1
            마진율 = round((이익 / 공급가) * 100, 2)
            ROI = round((이익 / cost) * 100, 2)
            ROI배 = round((이익 / cost) + 1, 1)

            st.markdown("### 결과")
            st.write(f"**수수료:** {수수료:,} 원")
            st.write(f"**광고비:** {광고비:,} 원")
            st.write(f"**입출고비용:** {입출고비:,} 원")
            st.write(f"**반품비용:** {반품비:,} 원")
            st.write(f"**기타비용:** {기타비:,} 원")
            st.write(f"**총비용:** {총비용:,} 원")
            st.write(f"**이익:** {이익:,} 원")
            st.write(f"**마진율:** {마진율:.2f}%")
            st.write(f"**ROI:** {ROI:.2f}% ({ROI배}배 수익)")

        except ValueError:
            st.error("입력값이 잘못되었습니다.")
