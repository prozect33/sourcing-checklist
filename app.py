import streamlit as st
from supabase import create_client

# Supabase 연결
url = "https://eqwogoktpuvlilnlveva.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
supabase = create_client(url, key)
TABLE_NAME = "product_margins"

st.set_page_config(page_title="세부 마진 계산기", layout="wide")
st.title("🧾 세부 마진 계산기")

with st.form("margin_form"):
    st.markdown("### 📦 상품 입력")

    col1, col2 = st.columns(2)
    with col1:
        product_name = st.text_input("상품명")
        yuan_price = st.text_input("위안화 (¥)")
        quantity = st.number_input("수량", value=1, step=1)
        ad_rate = st.number_input("광고비율 (%)", value=20.0, step=0.1)
        pickup_cost = st.number_input("회수비용 (원)", value=1500, step=100)
        etc_rate = st.number_input("기타비용률 (%)", value=2.0, step=0.1)
        packaging_cost = st.number_input("포장비 (원)", value=0, step=100)
    with col2:
        sell_price = st.number_input("판매가 (원)", step=1000)
        won_price = st.text_input("원화 (₩)")
        fee_rate = st.number_input("수수료율 (%)", value=10.8, step=0.1)
        inout_cost = st.number_input("입출고비용 (원)", value=3000, step=100)
        restock_cost = st.number_input("재입고비용 (원)", value=500, step=100)
        return_rate = st.number_input("반품률 (%)", value=0.1, step=0.1)
        exchange_rate = st.number_input("위안화 환율", value=350, step=1)
        gift_cost = st.number_input("사은품 비용 (원)", value=0, step=100)

    submitted = st.form_submit_button("📥 Supabase에 저장하기")

    if submitted:
        if not product_name:
            st.warning("상품명을 입력해주세요.")
        else:
            row = {
                "product_name": product_name,
                "sell_price": sell_price,
                "yuan_price": yuan_price,
                "won_price": won_price,
                "quantity": quantity,
                "fee_rate": fee_rate,
                "ad_rate": ad_rate,
                "inout_cost": inout_cost,
                "pickup_cost": pickup_cost,
                "restock_cost": restock_cost,
                "return_rate": return_rate,
                "etc_rate": etc_rate,
                "exchange_rate": exchange_rate,
                "packaging_cost": packaging_cost,
                "gift_cost": gift_cost,
            }

            clean = {k: v for k, v in row.items() if v != "" and v is not None}

            supabase.table(TABLE_NAME).delete().eq("product_name", product_name).execute()
            supabase.table(TABLE_NAME).insert(clean).execute()
            st.success(f"✅ '{product_name}' 저장 완료되었습니다.")
