import streamlit as st

# 페이지 구성
st.set_page_config(page_title="세부 마진 계산기", layout="wide")

# 설정값 초기화 (간단 마진 계산기 기준)
config = {
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

st.title("📊 세부 마진 계산기")

# 공통 판매가 입력
sell_price_input = st.text_input("판매가 (₩)", value="12000")

# 초기 3줄 입력 지원
num_rows = 3

# 입력 컬럼 정의
columns = [
    "공급 단가(¥)", "수량", "수수료율(%)", "광고비율(%)",
    "입출고비용(₩)", "회수비용(₩)", "재입고비용(₩)", "반품률(%)",
    "기타비용률(%)", "포장비(₩)", "사은품(₩)"
]

# 결과 컬럼 정의
result_columns = ["총비용", "이익", "마진율(%)", "ROI(%)"]

# 테이블 형태 입력
inputs = []
for i in range(num_rows):
    with st.expander(f"옵션 {i+1}", expanded=True):
        row = {}
        cols = st.columns(len(columns))
        for idx, col in enumerate(columns):
            default_val = {
                "공급 단가(¥)": 12.0,
                "수량": 1,
                "수수료율(%)": config["FEE_RATE"],
                "광고비율(%)": config["AD_RATE"],
                "입출고비용(₩)": config["INOUT_COST"],
                "회수비용(₩)": config["PICKUP_COST"],
                "재입고비용(₩)": config["RESTOCK_COST"],
                "반품률(%)": config["RETURN_RATE"],
                "기타비용률(%)": config["ETC_RATE"],
                "포장비(₩)": config["PACKAGING_COST"],
                "사은품(₩)": config["GIFT_COST"]
            }.get(col, 0)
            row[col] = cols[idx].number_input(col, value=default_val, step=1.0 if "비율" in col or "률" in col else 100)
        inputs.append(row)

# 계산 버튼
if st.button("💡 계산하기"):
    try:
        sell_price = int(float(sell_price_input))
    except:
        st.error("판매가를 정확히 입력해주세요.")
        st.stop()

    vat = 1.1
    for idx, row in enumerate(inputs):
        # 계산 로직
        unit_cost_won = round(float(row["공급 단가(¥)"]) * config["EXCHANGE_RATE"])
        qty = int(row["수량"])
        fee = round((sell_price * row["수수료율(%)"] / 100) * vat)
        ad = round((sell_price * row["광고비율(%)"] / 100) * vat)
        inout = round(row["입출고비용(₩)"] * vat)
        pickup = round(row["회수비용(₩)"] * vat)
        restock = round(row["재입고비용(₩)"] * vat)
        return_cost = round((pickup + restock) * (row["반품률(%)"] / 100))
        etc = round((sell_price * row["기타비용률(%)"] / 100) * vat)
        packaging = round(row["포장비(₩)"] * vat)
        gift = round(row["사은품(₩)"] * vat)

        total_unit_cost = round(unit_cost_won * qty * vat)
        total_cost = total_unit_cost + fee + ad + inout + return_cost + etc + packaging + gift
        profit = sell_price - total_cost
        supply_price = sell_price / vat
        margin = round((sell_price - (total_unit_cost + fee + inout + packaging + gift)) / supply_price * 100, 2)
        roi = round((profit / total_unit_cost) * 100, 2) if total_unit_cost else 0

        # 결과 출력
        st.markdown(f"### ✅ 옵션 {idx+1} 결과")
        st.markdown(f"- **총비용:** {total_cost:,}원")
        st.markdown(f"- **이익:** {profit:,}원")
        st.markdown(f"- **마진율:** {margin:.2f}%")
        st.markdown(f"- **ROI:** {roi:.2f}%")
        st.markdown("---")
