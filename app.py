if sell_price_raw.strip():
    try:
        target_margin = 50.0
        sell_price_val = int(float(sell_price_raw))

        vat = 1.1
        fee_rate = float(config['FEE_RATE'])
        ad_rate = float(config['AD_RATE'])
        etc_rate = float(config['ETC_RATE'])
        inout_cost = round(float(config['INOUT_COST']) * vat)
        return_cost = round((float(config['PICKUP_COST']) + float(config['RESTOCK_COST'])) * float(config['RETURN_RATE']) * vat)
        supply_price = sell_price_val / vat

        left_b, right_b = 0, sell_price_val
        target_cost, yuan_cost, profit = 0, 0, 0

        while left_b <= right_b:
            mid = (left_b + right_b) // 2
            unit_cost = round(mid * vat)
            fee = round((sell_price_val * fee_rate / 100) * vat)
            ad_fee = round((sell_price_val * ad_rate / 100) * vat)
            etc_cost = round((sell_price_val * etc_rate / 100) * vat)

            total_cost = unit_cost + fee + ad_fee + inout_cost + return_cost + etc_cost
            margin_profit = sell_price_val - total_cost
            margin_mid = (margin_profit / supply_price) * 100

            # ✅ 디버그 출력 (범위 좁혀서 출력)
            if 48 <= margin_mid <= 52:
                st.write(f"🧪 mid={mid}, unit_cost={unit_cost}, fee={fee}, ad_fee={ad_fee}, etc={etc_cost}, total_cost={total_cost}, margin_profit={margin_profit}, margin_mid={margin_mid:.2f}%")

            if margin_mid < target_margin:
                right_b = mid - 1
            else:
                target_cost = mid
                left_b = mid + 1

        yuan_cost = math.ceil(target_cost / float(config["EXCHANGE_RATE"]))
        profit = sell_price_val - (
            round(target_cost * vat) + fee + ad_fee + inout_cost + return_cost + etc_cost
        )

        margin_display.markdown(f"""
<div style='height:10px; line-height:10px; color:#f63366; font-size:15px; margin-bottom:15px;'>
  마진율 {int(target_margin)}% 기준: {format_number(round(target_cost * vat))}원 ({yuan_cost}위안) / 마진: {format_number(profit)}원
</div>
""", unsafe_allow_html=True)
    except:
        margin_display.markdown("<div style='height:10px; line-height:10px; margin-bottom:15px;'>&nbsp;</div>", unsafe_allow_html=True)
else:
    margin_display.markdown("<div style='height:10px; line-height:10px; margin-bottom:15px;'>&nbsp;</div>", unsafe_allow_html=True)
