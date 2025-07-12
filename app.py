import streamlit as st
import pandas as pd

st.set_page_config(page_title="실무형 세부 마진 계산기", layout="wide")

DEFAULTS = {
    "FEE_RATE": 10.8,
    "AD_RATE": 20.0,
    "INOUT_COST": 3000,
    "PICKUP_COST": 1500,
    "RESTOCK_COST": 500,
    "RETURN_RATE": 0.1,
    "ETC_RATE": 2.0,
    "EXCHANGE_RATE": 350,
    "PACKAGING_COST": 0,
    "GIFT_COST": 0
}

if "ledger" not in st.session_state:
    st.session_state.ledger = []

st.title("📦 실무형 세부 마진 계산기")

with st.form("input_form"):
    st.subheader("1️⃣ 상품 정보 입력")
    col1, col2, col3 = st.columns([2, 1, 1])
    product_name = col1.text_input("상품명")
    sell_price = col2.number_input("판매가 (₩)", value=12000, step=100)
    qty = col3.number_input("수량", value=1, step=1)

    st.divider()
    st.subheader("2️⃣ 원가 및 비용 입력")
    cost_col1, cost_col2, cost_col3 = st.columns(3)
    unit_yuan = cost_col1.number_input("공급가 (위안)", value=12.0, step=0.1)
    packaging_cost = cost_col2.number_input("포장비 (₩)", value=DEFAULTS["PACKAGING_COST"], step=100)
    gift_cost = cost_col3.number_input("사은품비 (₩)", value=DEFAULTS["GIFT_COST"], step=100)

    submitted = st.form_submit_button("💡 계산하기")

if submitted:
    try:
        vat = 1.1
        unit_cost = round(unit_yuan * DEFAULTS["EXCHANGE_RATE"])
        total_unit_cost = round(unit_cost * qty * vat)
        fee = round((sell_price * DEFAULTS["FEE_RATE"] / 100) * vat)
        ad = round((sell_price * DEFAULTS["AD_RATE"] / 100) * vat)
        inout = round(DEFAULTS["INOUT_COST"] * vat)
        pickup = round(DEFAULTS["PICKUP_COST"] * vat)
        restock = round(DEFAULTS["RESTOCK_COST"] * vat)
        return_cost = round((pickup + restock) * (DEFAULTS["RETURN_RATE"] / 100))
        etc = round((sell_price * DEFAULTS["ETC_RATE"] / 100) * vat)
        packaging = round(packaging_cost * vat)
        gift = round(gift_cost * vat)

        total_cost = total_unit_cost + fee + ad + inout + return_cost + etc + packaging + gift
        profit = sell_price - total_cost
        supply_price = sell_price / vat
        margin = round((sell_price - (total_unit_cost + fee + inout + packaging + gift)) / supply_price * 100, 2)
        roi = round((profit / total_unit_cost) * 100, 2) if total_unit_cost else 0

        st.success("✅ 계산 완료")
        st.metric("마진율", f"{margin:.2f}%")
        st.metric("ROI", f"{roi:.2f}%")
        st.metric("예상 이익", f"{profit:,}원")

        st.session_state.ledger.append({
            "상품명": product_name,
            "판매가(₩)": sell_price,
            "공급가(¥)": unit_yuan,
            "수량": qty,
            "총비용(₩)": total_cost,
            "이익(₩)": profit,
            "마진율(%)": margin,
            "ROI(%)": roi
        })

    except Exception as e:
        st.error("❌ 계산 중 오류가 발생했습니다.")

if st.session_state.ledger:
    st.markdown("### 📋 계산 결과 장부")
    ledger_df = pd.DataFrame(st.session_state.ledger)
    st.dataframe(ledger_df, use_container_width=True)

    csv = ledger_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 CSV 다운로드", data=csv, file_name="margin_ledger.csv", mime="text/csv")
