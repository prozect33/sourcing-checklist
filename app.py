...
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

        st.write("[디버그] 환율:", config['EXCHANGE_RATE'], "target_cost:", target_cost)  # 디버깅용 출력

        margin_display.markdown(
            f"""
<div style='height:10px; line-height:10px; color:#f63366; font-size:15px; margin-bottom:15px;'>
  마진율 {int(target_margin)}% 기준: {format_number(target_cost)}원 ({yuan_cost:.2f}위안) / 마진: {format_number(profit)}원
</div>
""", unsafe_allow_html=True)
...
