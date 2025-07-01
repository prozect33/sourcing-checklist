import streamlit as st

# Streamlit 저장용 세션 상태 초기화
if "custom_defaults" not in st.session_state:
    st.session_state.custom_defaults = {
        "fee_rate": 10.8,
        "ad_rate": 20.0,
        "etc_rate": 2.0,
        "inout_cost": 3000,
        "pickup_cost": 1500,
        "restock_cost": 500,
        "return_rate": 10.0,
        "exchange_rate": 350,
    }

# 기본 설정값 불러오기
defaults = st.session_state.custom_defaults

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

# 레이아웃 분할
left, center, right = st.columns([1, 1.5, 1])

# 왼쪽 설정 영역
with left:
    st.markdown("### ⚙️ 설정값")
    fee_rate = float(st.text_input("수수료율 (%)", value=str(defaults["fee_rate"]), key="fee_rate_input"))
    ad_rate = float(st.text_input("광고비율 (%)", value=str(defaults["ad_rate"]), key="ad_rate_input"))
    etc_rate = float(st.text_input("기타비용 (% 판매가 대비)", value=str(defaults["etc_rate"]), key="etc_rate_input"))
    inout_cost = int(st.text_input("입출고비 (원)", value=str(defaults["inout_cost"]), key="inout_cost_input"))
    pickup_cost = int(st.text_input("반품 회수비 (원)", value=str(defaults["pickup_cost"]), key="pickup_cost_input"))
    restock_cost = int(st.text_input("재입고비 (원)", value=str(defaults["restock_cost"]), key="restock_cost_input"))
    return_rate = float(st.text_input("반품율 (%)", value=str(defaults["return_rate"]), key="return_rate_input"))
    exchange_rate = int(st.text_input("환율 (1위안 = 원)", value=str(defaults["exchange_rate"]), key="exchange_rate_input"))

    if st.button("💾 기본값으로 저장"):
        st.session_state.custom_defaults = {
            "fee_rate": fee_rate,
            "ad_rate": ad_rate,
            "etc_rate": etc_rate,
            "inout_cost": inout_cost,
            "pickup_cost": pickup_cost,
            "restock_cost": restock_cost,
            "return_rate": return_rate,
            "exchange_rate": exchange_rate,
        }
        st.success("기본값이 저장되었습니다. 새로고침 후 반영됩니다.")

# 가운데 입력 및 출력 영역
with center:
    st.title("📦 간단 마진 계산기")
    st.markdown("#### **판매가**")
    selling_price_input = st.text_input("판매가", value="20000", label_visibility="collapsed", key="price_input")

    st.markdown("#### **원가**")
    col_yuan, col_won = st.columns([1, 1])
    with col_yuan:
        st.markdown("###### 위안화 (¥)")
        cost_cny_input = st.text_input("위안화 입력", value="", label_visibility="collapsed", key="cny_input")
    with col_won:
        st.markdown("###### 원화 (₩)")
        cost_krw_input = st.text_input("원화 입력", value="", label_visibility="collapsed", key="krw_input")

    calculate_button = st.button("계산하기")

    if calculate_button:
        try:
            selling_price = int(selling_price_input.replace(",", "").strip())

            if cost_krw_input.strip():
                cost = int(cost_krw_input.replace(",", "").strip())
            elif cost_cny_input.strip():
                cost = int(float(cost_cny_input.strip()) * exchange_rate)
            else:
                st.error("원가를 입력하세요.")
                st.stop()

            fee = round((selling_price * fee_rate * 1.1) / 100)
            ad_fee = round((selling_price * ad_rate * 1.1) / 100)
            inout = round(inout_cost * 1.1)
            return_cost = round((pickup_cost + restock_cost) * (return_rate / 100) * 1.1)
            etc_cost = round(selling_price * (etc_rate / 100))

            total_cost = cost + fee + ad_fee + inout + return_cost + etc_cost
            profit = selling_price - total_cost
            supply_price = selling_price / 1.1
            margin_rate = round((profit / supply_price) * 100, 2)
            roi = round((profit / cost) * 100, 2)
            roi_ratio = round((profit / cost) + 1, 1)

            st.markdown("---")
            st.markdown(f"**수수료:** {fee:,} 원")
            st.markdown(f"**광고비:** {ad_fee:,} 원")
            st.markdown(f"**입출고비용:** {inout:,} 원")
            st.markdown(f"**반품비용:** {return_cost:,} 원")
            st.markdown(f"**기타비용:** {etc_cost:,} 원")
            st.markdown(f"**총비용:** {total_cost:,} 원")
            st.markdown(f"**이익:** {profit:,} 원")
            st.markdown(f"**마진율:** {margin_rate:.2f}%")
            st.markdown(f"**ROI:** {roi:.2f}% ({roi_ratio}배 수익)")

        except ValueError:
            st.error("입력값에 숫자만 사용하세요.")