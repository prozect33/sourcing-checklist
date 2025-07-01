
import streamlit as st

# 페이지 설정
st.set_page_config(page_title="마진 계산기", layout="wide")

# 초기 설정값
default_config = {
    "수수료율": 10.8,
    "광고비율": 20.0,
    "기타비용율": 2.0,
    "입출고비": 3000,
    "반품비(회수)": 1500,
    "반품비(재입고)": 500,
    "반품율": 0.1,
    "환율(위안화)": 350
}

# 설정값 저장
for key, value in default_config.items():
    if key not in st.session_state:
        st.session_state[key] = value

# 탭 메뉴
col_tab1, col_tab2 = st.columns([1, 1])
with col_tab1:
    if st.button("**간단 마진 계산기**"):
        st.session_state["current_tab"] = "simple"
with col_tab2:
    if st.button("세부 마진 계산기"):
        st.session_state["current_tab"] = "detailed"

if "current_tab" not in st.session_state:
    st.session_state["current_tab"] = "simple"

if st.session_state["current_tab"] == "simple":
    st.markdown("### 📦 간단 마진 계산기")

    # 레이아웃: 왼쪽 설정 / 가운데 입력
    col_left, col_center, col_right = st.columns([1, 1, 1])

    # 왼쪽 설정값
    with col_left:
        st.markdown("#### ⚙️ 설정값")
        for key in default_config:
            st.session_state[key] = st.number_input(
                key, value=st.session_state[key], key=key, label_visibility="visible", format="%.2f"
            )
        st.button("기본값으로 저장", on_click=lambda: st.success("현재 설정이 기본값으로 저장되었습니다 (세션 기준)."))

    # 가운데 입력값
    with col_center:
        st.markdown("#### 판매가")
        selling_price = st.text_input("판매가 입력", value="20000", label_visibility="collapsed", key="판매가")
        st.markdown("#### 단가")
        col_cny, col_krw = st.columns(2)
        with col_cny:
            st.markdown("###### 위안화 (¥)")
            unit_cny = st.text_input("위안화 단가", label_visibility="collapsed", key="단가_cny")
        with col_krw:
            st.markdown("###### 원화 (₩)")
            unit_krw = st.text_input("원화 단가", label_visibility="collapsed", key="단가_krw")
        st.markdown("#### 수량")
        quantity = st.number_input("수량", min_value=1, value=1, step=1, key="수량")

        if st.button("계산하기", type="primary"):
            try:
                price = int(selling_price.replace(",", "").strip())
                if unit_krw.strip():
                    unit_cost = int(unit_krw.replace(",", "").strip())
                elif unit_cny.strip():
                    unit_cost = round(float(unit_cny.strip()) * st.session_state["환율(위안화)"])
                else:
                    st.error("단가를 입력하세요.")
                    st.stop()

                cost = unit_cost * quantity

                # 계산
                fee = round((price * st.session_state["수수료율"] * 1.1) / 100)
                inout_cost = round(st.session_state["입출고비"] * 1.1)
                return_cost = round((st.session_state["반품비(회수)"] + st.session_state["반품비(재입고)"]) * st.session_state["반품율"] * 1.1)
                etc_cost = round(price * st.session_state["기타비용율"] / 100)
                total_cost = round(cost + fee + inout_cost + return_cost)
                profit = price - total_cost
                supply_price = price / 1.1
                margin_rate = round((profit / supply_price) * 100, 2)
                roi = round((profit / cost) * 100, 2)
                roi_ratio = round((profit / cost) + 1, 1)

                st.markdown("### 💰 결과")
                st.markdown(f"**수수료:** {fee:,} 원")
                st.markdown(f"**입출고비용:** {inout_cost:,} 원")
                st.markdown(f"**반품비용:** {return_cost:,} 원")
                st.markdown(f"**기타비용:** {etc_cost:,} 원")
                st.markdown(f"**총비용:** {total_cost:,} 원")
                st.markdown(f"**이익:** {profit:,} 원")
                st.markdown(f"**마진율:** {margin_rate:.2f}%")
                st.markdown(f"**ROI:** {roi:.2f}% ({roi_ratio}배 수익)")

            except ValueError:
                st.error("숫자만 입력하세요.")
else:
    st.markdown("### 🔧 세부 마진 계산기는 개발 중입니다.")
