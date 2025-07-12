tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

with tab1:
    left, right = st.columns(2)

    with left:
        st.subheader("판매정보 입력")
        sell_price_raw = st.text_input("판매가 (원)", value=st.session_state.get("sell_price_raw", ""))
        margin_display = st.empty()

        if sell_price_raw.strip():
            try:
                target_margin = 50.0
                sell_price_val = int(float(sell_price_raw))
                vat = 1.1

                fee            = round((sell_price_val * config['FEE_RATE'] / 100) * vat)
                ad_fee         = round((sell_price_val * config['AD_RATE'] / 100) * vat)
                inout_cost     = round(config['INOUT_COST'] * vat)
                return_cost    = round((config['PICKUP_COST'] + config['RESTOCK_COST']) * (config['RETURN_RATE'] / 100) * vat)
                etc_cost       = round((sell_price_val * config['ETC_RATE'] / 100) * vat)
                packaging_cost = round(config['PACKAGING_COST'] * vat)
                gift_cost      = round(config['GIFT_COST'] * vat)

                supply_price = sell_price_val / vat

                left_b, right_b = 0, sell_price_val
                target_cost = 0
                while left_b <= right_b:
                    mid = (left_b + right_b) // 2
                    partial = (
                        round(mid * vat)
                        + fee
                        + inout_cost
                        + packaging_cost
                        + gift_cost
                    )
                    margin_profit = sell_price_val - partial
                    margin_mid = margin_profit / supply_price * 100
                    if margin_mid < target_margin:
                        right_b = mid - 1
                    else:
                        target_cost = mid
                        left_b = mid + 1

                yuan_cost = round(target_cost / config['EXCHANGE_RATE'], 2)

                profit = sell_price_val - (
                    round(target_cost * vat)
                    + fee
                    + inout_cost
                    + packaging_cost
                    + gift_cost
                )

                st.write("[디버그] 환율:", config['EXCHANGE_RATE'])
                st.write("[디버그] target_cost:", target_cost)

                margin_display.markdown(
                    f"""
<div style='height:10px; line-height:10px; color:#f63366; font-size:15px; margin-bottom:15px;'>
  마진율 {int(target_margin)}% 기준: {format_number(target_cost)}원 ({yuan_cost:.2f}위안) / 마진: {format_number(profit)}원
</div>
""", unsafe_allow_html=True)
            except:
                margin_display.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
        else:
            margin_display.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
