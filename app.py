import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="세부 마진 계산기", layout="wide")

# 설정값 (간단 마진 계산기 기준)
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

# 타이틀 및 판매가 입력
st.title("📊 세부 마진 계산기")
sell_price = st.number_input("판매가 (₩)", value=12000, step=100)

# 기본 옵션 3행 입력 템플릿
initial_data = pd.DataFrame([
    {
        "공급가(¥)": 12.0,
        "수량": 1,
        "수수료율(%)": DEFAULTS["FEE_RATE"],
        "광고비율(%)": DEFAULTS["AD_RATE"],
        "입출고비(₩)": DEFAULTS["INOUT_COST"],
        "회수비(₩)": DEFAULTS["PICKUP_COST"],
        "재입고비(₩)": DEFAULTS["RESTOCK_COST"],
        "반품률(%)": DEFAULTS["RETURN_RATE"],
        "기타비용률(%)": DEFAULTS["ETC_RATE"],
        "포장비(₩)": DEFAULTS["PACKAGING_COST"],
        "사은품비(₩)": DEFAULTS["GIFT_COST"]
    } for _ in range(3)
])

st.markdown("#### 옵션별 입력 (가로 비교형)")
edited_df = st.data_editor(
    initial_data,
    num_rows="dynamic",
    use_container_width=True
)

# 계산 실행
if st.button("💡 계산하기"):
    results = []
    for _, row in edited_df.iterrows():
        try:
            vat = 1.1
            unit_cost = round(float(row["공급가(¥)"]) * DEFAULTS["EXCHANGE_RATE"])
            qty = int(row["수량"])
            total_unit_cost = round(unit_cost * qty * vat)

            fee = round((sell_price * row["수수료율(%)"] / 100) * vat)
            ad = round((sell_price * row["광고비율(%)"] / 100) * vat)
            inout = round(row["입출고비(₩)"] * vat)
            pickup = round(row["회수비(₩)"] * vat)
            restock = round(row["재입고비(₩)"] * vat)
            return_cost = round((pickup + restock) * (row["반품률(%)"] / 100))
            etc = round((sell_price * row["기타비용률(%)"] / 100) * vat)
            packaging = round(row["포장비(₩)"] * vat)
            gift = round(row["사은품비(₩)"] * vat)

            total_cost = total_unit_cost + fee + ad + inout + return_cost + etc + packaging + gift
            profit = sell_price - total_cost
            supply_price = sell_price / vat
            margin = round((sell_price - (total_unit_cost + fee + inout + packaging + gift)) / supply_price * 100, 2)
            roi = round((profit / total_unit_cost) * 100, 2) if total_unit_cost else 0

            results.append({
                "총비용(₩)": total_cost,
                "이익(₩)": profit,
                "마진율(%)": margin,
                "ROI(%)": roi
            })
        except:
            results.append({
                "총비용(₩)": "에러",
                "이익(₩)": "에러",
                "마진율(%)": "에러",
                "ROI(%)": "에러"
            })

    result_df = pd.concat([edited_df, pd.DataFrame(results)], axis=1)
    st.markdown("#### 💎 계산 결과")
    st.dataframe(result_df, use_container_width=True)
