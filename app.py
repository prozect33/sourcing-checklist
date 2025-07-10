import streamlit as st

# 필수 함수 정의
def format_number(num):
    return f"{int(num):,}"

# 임시 테스트용 입력값
sell_price_raw = "10000"
qty_raw = "1"
unit_yuan = "20"
unit_won = ""

# config 설정값
config = {
    "EXCHANGE_RATE": 350,
    "FEE_RATE": 10,
    "AD_RATE": 5,
    "INOUT_COST": 300,
    "PICKUP_COST": 500,
    "RESTOCK_COST": 200,
    "RETURN_RATE": 0.1,
    "ETC_RATE": 1
}

cols = st.columns(2)
with cols[1]:
    if 'result' in locals() or True:  # 테스트용으로 항상 True 처리
        try:
            sell_price = int(float(sell_price_raw)) if sell_price_raw else None
            qty = int(float(qty_raw)) if qty_raw else None
        except:
            sell_price, qty = None, None

        if sell_price is None or qty is None:
            st.warning("판매가와 수량을 정확히 입력해주세요.")
        else:
            try:
                if unit_yuan:
                    unit_cost_val = round(float(unit_yuan) * float(config['EXCHANGE_RATE']))
                    cost_display = f"{format_number(unit_cost_val)}원 ({unit_yuan}위안)"
                elif unit_won:
                    unit_cost_val = round(float(unit_won))
                    cost_display = f"{format_number(unit_cost_val)}원"
                else:
                    unit_cost_val = 0
                    cost_display = "0원"
                unit_cost = unit_cost_val
            except:
                unit_cost = 0
                cost_display = "0원"

            fee = round((sell_price * float(config["FEE_RATE"]) * 1.1) / 100)
            ad = round((sell_price * float(config["AD_RATE"]) * 1.1) / 100)
            inout = round(float(config["INOUT_COST"]) * 1.1)
            pickup = round(float(config["PICKUP_COST"]) * 1.1)
            restock = round(float(config["RESTOCK_COST"]) * 1.1)
            return_rate = float(config["RETURN_RATE"])
            return_cost = round((pickup + restock) * return_rate)
            etc = round(sell_price * float(config["ETC_RATE"]) / 100 * 1.1)
            total_cost = round(unit_cost + fee + ad + inout + return_cost + etc)
            profit = sell_price - total_cost
            supply_price = sell_price / 1.1
            margin = round((profit / supply_price) * 100, 2) if supply_price != 0 else 0
            roi = round((profit / unit_cost) * 100, 2) if unit_cost != 0 else 0

            margin_profit = sell_price - (unit_cost + fee + inout)
            margin_ratio = round((margin_profit / supply_price) * 100, 2) if supply_price else 0

            # 세션 상태 저장
            st.session_state['calc_done'] = True
            st.session_state['sell_price'] = sell_price
            st.session_state['unit_cost'] = unit_cost
            st.session_state['cost_display'] = cost_display
            st.session_state['fee'] = fee
            st.session_state['ad'] = ad
            st.session_state['inout'] = inout
            st.session_state['pickup'] = pickup
            st.session_state['restock'] = restock
            st.session_state['return_cost'] = return_cost
            st.session_state['etc'] = etc
            st.session_state['total_cost'] = total_cost
            st.session_state['profit'] = profit
            st.session_state['supply_price'] = supply_price
            st.session_state['margin'] = margin
            st.session_state['roi'] = roi
            st.session_state['margin_profit'] = margin_profit
            st.session_state['margin_ratio'] = margin_ratio
            st.session_state['return_rate'] = return_rate
            st.session_state['unit_yuan'] = unit_yuan

    if st.session_state.get('calc_done'):
        sell_price = st.session_state['sell_price']
        unit_cost = st.session_state['unit_cost']
        cost_display = st.session_state['cost_display']
        fee = st.session_state['fee']
        ad = st.session_state['ad']
        inout = st.session_state['inout']
        pickup = st.session_state['pickup']
        restock = st.session_state['restock']
        return_cost = st.session_state['return_cost']
        etc = st.session_state['etc']
        total_cost = st.session_state['total_cost']
        profit = st.session_state['profit']
        supply_price = st.session_state['supply_price']
        margin = st.session_state['margin']
        roi = st.session_state['roi']
        margin_profit = st.session_state['margin_profit']
        margin_ratio = st.session_state['margin_ratio']
        return_rate = st.session_state['return_rate']
        unit_yuan = st.session_state['unit_yuan']

        st.markdown("### 📊 계산 결과")

        row = st.columns(7)
        row_labels = ["판매가", "원가", "최소 이익", "최소마진율", "투자수익률", "마진", "마진율"]
        row_values = [
            f"{format_number(sell_price)}원",
            cost_display,
            f"{format_number(profit)}원",
            f"{margin:.2f}%",
            f"{roi:.2f}%",
            f"{format_number(margin_profit)}원",
            f"{margin_ratio:.2f}%"
        ]
        for i in range(7):
            with row[i]:
                st.markdown(f"**{row_labels[i]}**")
                st.markdown(f"<div style='font-size: 16px;'>{row_values[i]}</div>", unsafe_allow_html=True)

        st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)

        show_details = st.checkbox("📦 상세 비용 항목 보기", value=False, key="show_details_checkbox")

        if show_details:
            st.markdown("### 상세 비용")
            st.markdown(f"**판매가:** {format_number(sell_price)}원")
            st.markdown(f"**원가:** {format_number(unit_cost)}원 ({unit_yuan}위안)" if unit_yuan else f"**원가:** {format_number(unit_cost)}원")
            st.markdown(f"**수수료:** {format_number(fee)}원 (판매가 × {config['FEE_RATE']}% × 1.1)")
            st.markdown(f"**광고비:** {format_number(ad)}원 (판매가 × {config['AD_RATE']}% × 1.1)")
            st.markdown(f"**입출고비용:** {format_number(inout)}원 ({format_number(config['INOUT_COST'])} × 1.1)")
            st.markdown(f"**회수비용:** {format_number(pickup)}원 ({format_number(config['PICKUP_COST'])} × 1.1)")
            st.markdown(f"**재입고비용:** {format_number(restock)}원 ({format_number(config['RESTOCK_COST'])} × 1.1)")
            st.markdown(f"**반품비용:** {format_number(return_cost)}원 ((({format_number(config['PICKUP_COST'])} × 1.1) + ({format_number(config['RESTOCK_COST'])} × 1.1)) × {return_rate * 100:.1f}%)")
            st.markdown(f"**기타비용:** {format_number(etc)}원 (판매가 × {config['ETC_RATE']}% × 1.1)")
            st.markdown(f"**총비용:** {format_number(total_cost)}원 (원가 + 위 항목 합산)")
            st.markdown(f"**공급가액:** {format_number(round(supply_price))}원 (판매가 ÷ 1.1)")
            st.markdown(f"**최소 이익:** {format_number(profit)}원 (판매가 - 총비용)")
            st.markdown(f"**최소마진율:** {margin:.2f}% ((최소 이익 ÷ 공급가액) × 100)")
            st.markdown(f"**투자수익률:** {roi:.2f}% ((최소 이익 ÷ 원가) × 100)")
