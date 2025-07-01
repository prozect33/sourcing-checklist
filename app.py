
import streamlit as st

st.set_page_config(page_title="반품비용 테스트")

sell_price = st.number_input("판매가", value=22000)
pickup_base = 1500
restock_base = 500
return_rate = 0.1

pickup = round(pickup_base * 1.1)
restock = round(restock_base * 1.1)
return_cost = round((pickup + restock) * return_rate)

if st.button("계산하기"):
    st.write(f"**반품비용:** {return_cost:,}원 (({pickup} + {restock}) × {return_rate * 100:.1f}%)")
