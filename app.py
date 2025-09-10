import streamlit as st
import json
import os
import math
import pandas as pd
import datetime
from supabase import create_client, Client

# Streamlit 페이지 설정
st.set_page_config(page_title="간단 마진 계산기", layout="wide")

st.markdown("""
    <style>
      [data-testid="stSidebarHeader"] { display: none !important; }
      [data-testid="stSidebarContent"] { padding-top: 15px !important; }
      [data-testid="stHeading"] { margin-bottom: 15px !important; }
      [data-testid="stNumberInput"] button { display: none !important; }
    </style>
""", unsafe_allow_html=True)


DEFAULT_CONFIG_FILE = "default_config.json"

def default_config():
    """기본 설정값을 반환합니다."""
    return {
        "FEE_RATE": 10.8,
        "AD_RATE": 20.0,
        "INOUT_COST": 3000.0,
        "PICKUP_COST": 0.0,
        "RESTOCK_COST": 0.0,
        "RETURN_RATE": 0.0,
        "ETC_RATE": 2.0,
        "EXCHANGE_RATE": 300,
        "PACKAGING_COST": 0,
        "GIFT_COST": 0
    }

def load_config():
    """설정 파일을 불러옵니다. 파일이 없거나 오류 발생 시 기본값을 사용합니다."""
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, "r") as f:
                data = json.load(f)
                base = default_config()
                for k, v in data.items():
                    if k in base:
                        try:
                            base[k] = float(v)
                        except:
                            pass
                return base
        except:
            return default_config()
    else:
        return default_config()

def save_config(config):
    """현재 설정값을 파일에 저장합니다."""
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        json.dump(config, f)

def format_number(val):
    """숫자를 천 단위로 포맷팅합니다."""
    return f"{int(val):,}" if float(val).is_integer() else f"{val:,.2f}"

def reset_inputs():
    """입력 필드를 초기화합니다."""
    st.session_state["sell_price_raw"] = ""
    st.session_state["unit_yuan"] = ""
    st.session_state["unit_won"] = ""
    st.session_state["qty_raw"] = "1"
    st.session_state["show_result"] = False  # 결과도 초기화

def load_supabase_credentials():
    """credentials.json 파일에서 Supabase 인증 정보를 불러옵니다."""
    try:
        with open("credentials.json", "r") as f:
            creds = json.load(f)
            return creds["SUPABASE_URL"], creds["SUPABASE_KEY"]
    except FileNotFoundError:
        st.error("오류: 'credentials.json' 파일을 찾을 수 없습니다. 파일을 생성하고 Supabase 키를 입력해주세요.")
        st.stop()
    except json.JSONDecodeError:
        st.error("오류: 'credentials.json' 파일의 형식이 잘못되었습니다. JSON 형식을 확인해주세요.")
        st.stop()
    except KeyError:
        st.error("오류: 'credentials.json' 파일에 'SUPABASE_URL' 또는 'SUPABASE_KEY'가 없습니다.")
        st.stop()

# 사이드바에 설정값 입력 필드 생성
config = load_config()
st.sidebar.header("🛠️ 설정값")
config["FEE_RATE"] = st.sidebar.number_input("수수료율 (%)", value=config["FEE_RATE"], step=0.1, format="%.2f")
config["AD_RATE"] = st.sidebar.number_input("광고비율 (%)", value=config["AD_RATE"], step=0.1, format="%.2f")
config["INOUT_COST"] = st.sidebar.number_input("입출고비용 (원)", value=int(config["INOUT_COST"]), step=100)
config["PICKUP_COST"] = st.sidebar.number_input("회수비용 (원)", value=int(config["PICKUP_COST"]), step=100)
config["RESTOCK_COST"] = st.sidebar.number_input("재입고비용 (원)", value=int(config["RESTOCK_COST"]), step=100)
config["RETURN_RATE"] = st.sidebar.number_input("반품률 (%)", value=config["RETURN_RATE"], step=0.1, format="%.2f")
config["ETC_RATE"] = st.sidebar.number_input("기타비용률 (%)", value=config["ETC_RATE"], step=0.1, format="%.2f")
config["EXCHANGE_RATE"] = st.sidebar.number_input("위안화 환율", value=int(config["EXCHANGE_RATE"]), step=1)
config["PACKAGING_COST"] = st.sidebar.number_input("포장비 (원)", value=int(config["PACKAGING_COST"]), step=100)
config["GIFT_COST"] = st.sidebar.number_input("사은품 비용 (원)", value=int(config["GIFT_COST"]), step=100)

if st.sidebar.button("📂 기본값으로 저장"):
    save_config(config)
    st.sidebar.success("기본값이 저장되었습니다.")

# Supabase 클라이언트 초기화
try:
    SUPABASE_URL, SUPABASE_KEY = load_supabase_credentials()
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Supabase 클라이언트 초기화 중 오류가 발생했습니다: {e}")
    st.stop()

# 세션 상태 초기화
if "product_name_edit" not in st.session_state:
    st.session_state.product_name_edit = ""
if "sell_price_edit" not in st.session_state:
    st.session_state.sell_price_edit = 0
if "fee_rate_edit" not in st.session_state:
    st.session_state.fee_rate_edit = 0.0
if "inout_shipping_cost_edit" not in st.session_state:
    st.session_state.inout_shipping_cost_edit = 0
if "purchase_cost_edit" not in st.session_state:
    st.session_state.purchase_cost_edit = 0
if "quantity_edit" not in st.session_state:
    st.session_state.quantity_edit = 1
if "logistics_cost_edit" not in st.session_state:
    st.session_state.logistics_cost_edit = 0
if "customs_duty_edit" not in st.session_state:
    st.session_state.customs_duty_edit = 0
if "etc_cost_edit" not in st.session_state:
    st.session_state.etc_cost_edit = 0
if "is_edit_mode" not in st.session_state:
    st.session_state.is_edit_mode = False

# 상품 정보 불러오기/리셋 함수
def load_product_data(selected_product_name):
    """선택된 상품의 정보를 불러와 세션 상태를 업데이트합니다."""
    if selected_product_name == "새로운 상품 입력":
        st.session_state.is_edit_mode = False
        st.session_state.product_name_edit = ""
        st.session_state.sell_price_edit = 0
        st.session_state.fee_rate_edit = config["FEE_RATE"]
        st.session_state.inout_shipping_cost_edit = config["INOUT_COST"]
        st.session_state.purchase_cost_edit = 0
        st.session_state.quantity_edit = 1
        st.session_state.logistics_cost_edit = 0
        st.session_state.customs_duty_edit = 0
        st.session_state.etc_cost_edit = 0
    else:
        try:
            response = supabase.table("products").select("*").eq("product_name", selected_product_name).execute()
            if response.data:
                product_data = response.data[0]
                st.session_state.is_edit_mode = True
                st.session_state.product_name_edit = product_data.get("product_name", "")
                st.session_state.sell_price_edit = int(product_data.get("sell_price", 0))
                st.session_state.fee_rate_edit = float(product_data.get("fee", 0.0))
                st.session_state.inout_shipping_cost_edit = int(product_data.get("inout_shipping_cost", 0))
                st.session_state.purchase_cost_edit = int(product_data.get("purchase_cost", 0))
                st.session_state.quantity_edit = int(product_data.get("quantity", 1))
                st.session_state.logistics_cost_edit = int(product_data.get("logistics_cost", 0))
                st.session_state.customs_duty_edit = int(product_data.get("customs_duty", 0))
                st.session_state.etc_cost_edit = int(product_data.get("etc_cost", 0))
        except Exception as e:
            st.error(f"상품 정보를 불러오는 중 오류가 발생했습니다: {e}")

# 마진 계산 함수
def calculate_profit(sell_price, unit_cost, fee_rate, ad_rate, return_rate, etc_rate,
                     inout_cost, packaging_cost, gift_cost, pickup_cost, restock_cost, exchange_rate, unit_yuan, qty):
    
    # 비용 계산
    unit_won = unit_yuan * exchange_rate # 위안화 상품의 원화 환산
    
    total_cost = (unit_cost * qty) + (unit_won * qty) + inout_cost + packaging_cost + gift_cost
    total_revenue = sell_price * qty
    
    fee = (total_revenue * fee_rate / 100) * 1.1 # 수수료 (부가세 포함)
    ad = total_revenue * ad_rate / 100
    
    # 반품 및 기타 비용
    return_cost = total_revenue * return_rate / 100 + pickup_cost + restock_cost
    etc = total_revenue * etc_rate / 100
    
    # 이익 계산
    gross_profit = total_revenue - (unit_cost * qty + fee + inout_cost + packaging_cost + gift_cost + etc) # 마진 계산
    gross_profit_rate = (gross_profit / total_revenue) * 100 if total_revenue > 0 else 0
    
    net_profit = gross_revenue - ad - return_cost # 최소 이익 계산
    net_profit_rate = (net_profit / total_revenue) * 100 if total_revenue > 0 else 0
    
    return gross_profit, gross_profit_rate, net_profit, net_profit_rate

# 메인 앱 로직
def main():
    st.title("간단 마진 계산기")
    
    tab1, tab2 = st.tabs(["단건 계산기", "일일 정산"])
    
    with tab1:
        st.subheader("🛒 개별 상품 마진 계산")
        
        col1, col2 = st.columns(2)
        with col1:
            sell_price = st.number_input("판매가 (원)", min_value=0, value=0, key="sell_price_raw")
        with col2:
            qty = st.number_input("수량 (개)", min_value=1, value=1, key="qty_raw")
            
        st.write("---")
        
        st.subheader("🏷️ 원가 및 부가 비용")
        col_cost1, col_cost2, col_cost3 = st.columns(3)
        with col_cost1:
            unit_won = st.number_input("원가 (원)", min_value=0, value=0, key="unit_won")
        with col_cost2:
            unit_yuan = st.number_input("위안화 상품 원가 (위안)", min_value=0, value=0, key="unit_yuan")
        
        st.write("---")
        
        if st.button("📈 결과 보기", use_container_width=True):
            st.session_state["show_result"] = True
            
        if st.session_state.get("show_result"):
            with st.spinner("계산 중..."):
                gross_profit, gross_profit_rate, net_profit, net_profit_rate = calculate_profit(
                    sell_price, unit_won, config["FEE_RATE"], config["AD_RATE"], config["RETURN_RATE"],
                    config["ETC_RATE"], config["INOUT_COST"], config["PACKAGING_COST"], config["GIFT_COST"],
                    config["PICKUP_COST"], config["RESTOCK_COST"], config["EXCHANGE_RATE"], unit_yuan, qty
                )
            
            st.markdown("### 📊 마진 계산 결과")
            st.markdown(f"**총 매출액:** {format_number(sell_price * qty)} 원")
            st.markdown(f"**총 비용:** {format_number((sell_price * qty) - gross_profit)} 원")
            
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                st.metric("마진", f"{format_number(gross_profit)} 원", f"{gross_profit_rate:,.2f}%")
            with col_res2:
                st.metric("최소 이익", f"{format_number(net_profit)} 원", f"{net_profit_rate:,.2f}%")
                
    with tab2:
        st.subheader("📅 일일 정산")
        
        col_daily1, col_daily2 = st.columns(2)
        with col_daily1:
            total_revenue = st.number_input("전체 매출액 (원)", min_value=0, value=0)
        with col_daily2:
            sales_quantity = st.number_input("판매 개수 (총합)", min_value=0, value=0)

        # Supabase에서 모든 상품 정보 불러오기
        try:
            response = supabase.table("products").select("*").execute()
            products_data = response.data
        except Exception as e:
            products_data = []
            st.error(f"상품 정보를 불러오는 중 오류가 발생했습니다: {e}")

        if st.button("📈 일일 정산 계산", use_container_width=True):
            if total_revenue > 0 and sales_quantity > 0 and products_data:
                
                # 모든 상품의 총 비용을 계산
                total_product_cost = 0
                for product in products_data:
                    # 상품 정보를 기반으로 개당 비용 계산
                    unit_purchase_cost = int(product.get("purchase_cost", 0))
                    unit_logistics_cost = int(product.get("logistics_cost", 0)) / int(product.get("quantity", 1)) if int(product.get("quantity", 1)) > 0 else 0
                    unit_customs_cost = int(product.get("customs_duty", 0)) / int(product.get("quantity", 1)) if int(product.get("quantity", 1)) > 0 else 0
                    unit_etc_cost = int(product.get("etc_cost", 0)) / int(product.get("quantity", 1)) if int(product.get("quantity", 1)) > 0 else 0
                    
                    # 모든 비용 합산
                    total_product_cost += (unit_purchase_cost + unit_logistics_cost + unit_customs_cost + unit_etc_cost + config["INOUT_COST"]) * sales_quantity

                # 총 수수료 계산 (VAT 포함)
                total_fee = (total_revenue * config["FEE_RATE"] / 100) * 1.1

                # 총 광고비 계산
                total_ad_cost = total_revenue * config["AD_RATE"] / 100

                # 총 일일 비용 계산
                total_daily_cost = total_product_cost + total_fee + total_ad_cost

                # 최종 일일 순이익금 계산
                daily_profit = total_revenue - total_daily_cost
                daily_profit_rate = (daily_profit / total_revenue) * 100 if total_revenue > 0 else 0
                
                st.markdown("### 📊 일일 정산 결과")
                col_daily_res1, col_daily_res2 = st.columns(2)
                with col_daily_res1:
                    st.metric("총 비용", f"{format_number(total_daily_cost)} 원")
                with col_daily_res2:
                    st.metric("일일 순이익금", f"{format_number(daily_profit)} 원", f"{daily_profit_rate:,.2f}%")
            else:
                st.warning("매출액과 판매 개수, 그리고 Supabase에 등록된 상품이 있어야 계산이 가능합니다.")
                
if __name__ == "__main__":
    main()
