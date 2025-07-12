import streamlit as st
import pandas as pd
from supabase import create_client

# Supabase 연결 정보
url = "https://eqwogoktpuvlilnlveva.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVxd29nb2t0cHV2bGlsbmx2ZXZhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIzMDk3NjEsImV4cCI6MjA2Nzg4NTc2MX0.2MmOaxur_gDaVsGK6UloWls8GMG4aH_q7EBuzHAXpLw"
supabase = create_client(url, key)
TABLE_NAME = "product_margins"

st.set_page_config(page_title="세부 마진 계산기", layout="wide")
st.title("🧾 세부 마진 계산기")

# 검색
search_name = st.text_input("🔍 상품명으로 검색해서 불러오기")
load_btn = st.button("불러오기")

# 항목 정의
columns = [
    "product_name", "sell_price", "yuan_price", "won_price", "quantity",
    "fee_rate", "ad_rate", "inout_cost", "pickup_cost", "restock_cost",
    "return_rate", "etc_rate", "exchange_rate", "packaging_cost", "gift_cost"
]

default_row = {
    "product_name": "",
    "sell_price": "",
    "yuan_price": "",
    "won_price": "",
    "quantity": "1",
    "fee_rate": 10.8,
    "ad_rate": 20.0,
    "inout_cost": 3000,
    "pickup_cost": 1500,
    "restock_cost": 500,
    "return_rate": 0.1,
    "etc_rate": 2.0,
    "exchange_rate": 350,
    "packaging_cost": 0,
    "gift_cost": 0
}

data = pd.DataFrame([default_row.copy() for _ in range(5)])

if load_btn and search_name.strip():
    result = supabase.table(TABLE_NAME).select("*").eq("product_name", search_name.strip()).execute()
    records = result.data
    if records:
        data = pd.DataFrame(records)[columns]
        st.success(f"✅ '{search_name}'에 해당하는 데이터 불러왔습니다.")
    else:
        st.warning(f"'{search_name}'에 해당하는 데이터가 없습니다.")

# 표 입력
edited = st.data_editor(data, num_rows="dynamic", use_container_width=True)

# 저장: 기존 상품 삭제 후 insert
if st.button("📥 저장하기"):
    for _, row in edited.iterrows():
        name = row["product_name"]
        if not name:
            continue
        # 기존 항목 삭제
        supabase.table(TABLE_NAME).delete().eq("product_name", name).execute()
        # 새로 삽입
        supabase.table(TABLE_NAME).insert(row.to_dict()).execute()
    st.success("✅ Supabase에 저장 완료되었습니다.")
