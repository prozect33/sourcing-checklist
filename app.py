
# (전체 app.py 내용은 여기에 있어야 하지만 예시상 생략)
# 아래는 마진 계산 항목만 예시로 삽입한 부분입니다

# 마진 계산용 설정값 무시 계산
fee_base = round((sell_price * float(config["FEE_RATE"]) * 1.1) / 100)
inout_base = round(float(config["INOUT_COST"]) * 1.1)
margin_profit = sell_price - (unit_cost + fee_base + inout_base)
margin_ratio = round((margin_profit / (sell_price / 1.1)) * 100, 2) if sell_price else 0

st.markdown("### 💰 기본 마진 기준")
colm1, colm2 = st.columns(2)
with colm1:
    st.markdown("**마진**")
    st.markdown(f"<div style='font-size: 16px;'>{format_number(margin_profit)}원</div>", unsafe_allow_html=True)
with colm2:
    st.markdown("**마진율**")
    st.markdown(f"<div style='font-size: 16px;'>{margin_ratio:.2f}%</div>", unsafe_allow_html=True)
