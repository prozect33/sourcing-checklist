
import streamlit as st

# 설정값 초기화
default_values = {
    "수수료율(%)": 10.8,
    "광고비율(%)": 20,
    "입출고비": 3000,
    "반품 회수비": 1500,
    "재입고비": 500,
    "반품율(%)": 10,
    "환율": 350,
    "기타비용 비율(%)": 2,
}

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# 설정값 사이드바
with st.sidebar:
    st.subheader("⚙️ 설정값")
    for key, default in default_values.items():
        step = 0.1 if isinstance(default, float) else 100
        st.number_input(key, value=st.session_state.get(key, default), step=step, key=key)
    if st.button("기본값으로 저장"):
        st.success("기본값 저장 기능은 추후 구현 예정입니다.")

# 탭 메뉴
tab1, tab2 = st.columns([1, 1])
with tab1:
    if st.button("**간단 마진 계산기**"):
        st.session_state["tab"] = "간단"
with tab2:
    if st.button("세부 마진 계산기"):
        st.session_state["tab"] = "세부"

current_tab = st.session_state.get("tab", "간단")

if current_tab == "간단":
    # 가운데 정렬
    _, center, _ = st.columns([1, 1, 1])
    with center:
        st.markdown("### 판매가")
        selling_price = st.text_input("판매가", key="판매가", label_visibility="collapsed")

        st.markdown("### 단가")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### 위안화 (¥)")
            cost_cny = st.text_input("위안화", key="위안화", label_visibility="collapsed")
        with col2:
            st.markdown("##### 원화 (₩)")
            cost_krw = st.text_input("원화", key="원화", label_visibility="collapsed")

        st.markdown("### 수량")
        quantity = st.text_input("수량", key="수량", label_visibility="collapsed")

        if st.button("계산하기"):
            try:
                sell = int(selling_price.replace(",", ""))
                qty = int(quantity)
                if cost_krw.strip():
                    cost = int(cost_krw.replace(",", ""))
                elif cost_cny.strip():
                    cost = int(float(cost_cny) * st.session_state["환율"])
                else:
                    st.error("단가를 입력하세요.")
                    st.stop()

                fee = round((sell * st.session_state["수수료율(%)"] * 1.1) / 100)
                inout = round(st.session_state["입출고비"] * 1.1)
                return_cost = round((st.session_state["반품 회수비"] + st.session_state["재입고비"]) * st.session_state["반품율(%)"] / 100 * 1.1)
                etc = round(sell * st.session_state["기타비용 비율(%)"] / 100)
                total_cost = round((cost * qty) + fee + inout + return_cost + etc)
                profit = sell - total_cost
                supply = sell / 1.1
                margin = round((profit / supply) * 100, 2)
                roi = round((profit / (cost * qty)) * 100, 2)
                ratio = round((profit / (cost * qty)) + 1, 1)

                st.markdown(f"**수수료:** {fee:,} 원")
                st.markdown(f"**입출고비용:** {inout:,} 원")
                st.markdown(f"**반품비용:** {return_cost:,} 원")
                st.markdown(f"**기타비용:** {etc:,} 원")
                st.markdown(f"**총비용:** {total_cost:,} 원")
                st.markdown(f"**이익:** {profit:,} 원")
                st.markdown(f"**마진율:** {margin}%")
                st.markdown(f"**ROI:** {roi}% ({ratio}배 수익)")

            except:
                st.error("입력값을 확인하세요.")
