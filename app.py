import streamlit as st
import json
import os
import math
import pandas as pd
import datetime
from supabase import create_client, Client

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
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        json.dump(config, f)

def format_number(val):
    if val is None:
        return ""
    return f"{int(val):,}" if float(val).is_integer() else f"{val:,.2f}"

def reset_inputs():
    st.session_state["sell_price_raw"] = ""
    st.session_state["unit_yuan"] = ""
    st.session_state["unit_won"] = ""
    st.session_state["qty_raw"] = ""
    st.session_state["show_result"] = False

def load_supabase_credentials():
    # 실제 Supabase 키는 보안을 위해 'credentials.json' 파일을 통해 불러옵니다.
    # 이 파일을 Streamlit 앱과 같은 폴더에 생성해야 합니다.
    # 파일 내용: {"SUPABASE_URL": "당신의 URL", "SUPABASE_KEY": "당신의 KEY"}
    try:
        with open("credentials.json", "r") as f:
            creds = json.load(f)
            return creds["SUPABASE_URL"], creds["SUPABASE_KEY"]
    except FileNotFoundError:
        st.error("오류: 'credentials.json' 파일을 찾을 수 없습니다. 파일을 생성하고 Supabase 키를 입력해주세요.")
        # 더미 데이터 반환 (실제 실행을 위해서는 키가 필요함)
        return "DUMMY_URL", "DUMMY_KEY" 
    except json.JSONDecodeError:
        st.error("오류: 'credentials.json' 파일의 형식이 잘못되었습니다. JSON 형식을 확인해주세요.")
        return "DUMMY_URL", "DUMMY_KEY" 
    except KeyError:
        st.error("오류: 'credentials.json' 파일에 'SUPABASE_URL' 또는 'SUPABASE_KEY'가 없습니다.")
        return "DUMMY_URL", "DUMMY_KEY"
        
# --- 실시간 자연 판매 계산 및 세션 상태 업데이트 함수 ---
def update_organic_sales():
    """전체 판매량/매출액과 광고 판매량/매출액을 기반으로 자연 판매량을 계산하고 세션 상태에 저장합니다."""
    
    # 1. 자연 판매 수량 계산
    total_qty = st.session_state.get('total_sales_qty', 0)
    ad_qty = st.session_state.get('ad_sales_qty', 0)
    # 계산 결과가 음수가 되지 않도록 max(0, ...) 처리
    organic_qty = max(0, total_qty - ad_qty)
    st.session_state["organic_sales_qty"] = organic_qty

    # 2. 자연 판매 매출액 계산
    total_rev = st.session_state.get('total_revenue', 0)
    ad_rev = st.session_state.get('ad_revenue', 0)
    # 계산 결과가 음수가 되지 않도록 max(0, ...) 처리
    organic_rev = max(0, total_rev - ad_rev)
    st.session_state["organic_revenue"] = organic_rev
# -----------------------------------------------------------

config = load_config()

# Supabase 클라이언트 초기화
SUPABASE_URL, SUPABASE_KEY = load_supabase_credentials()
try:
    if SUPABASE_URL != "DUMMY_URL":
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    else:
        # 키가 없으면 임시 클라이언트 생성 (실제 DB 접근은 안 됨)
        class DummySupabase:
            def table(self, table_name): return self
            def select(self, *args): return self
            def eq(self, *args): return self
            def order(self, *args, **kwargs): return self
            def execute(self): return type('Response', (object,), {'data': []})()
            def insert(self, *args): return self
            def update(self, *args): return self
            def delete(self, *args): return self
        supabase = DummySupabase()
except Exception as e:
    st.error(f"Supabase 클라이언트 초기화 중 오류가 발생했습니다: {e}")
    st.stop()


# --- 세션 상태 초기화 (필수) ---
if "product_name_input" not in st.session_state:
    st.session_state.product_name_input = ""
# (중략... 다른 입력 필드 초기화는 편의상 생략합니다)
if "is_edit_mode" not in st.session_state:
    st.session_state.is_edit_mode = False

# 일일 정산 필드 세션 상태 초기화
if "total_sales_qty" not in st.session_state:
    st.session_state.total_sales_qty = 0
if "ad_sales_qty" not in st.session_state:
    st.session_state.ad_sales_qty = 0
if "total_revenue" not in st.session_state:
    st.session_state.total_revenue = 0
if "ad_revenue" not in st.session_state:
    st.session_state.ad_revenue = 0

# !!! 자연 판매 계산 결과를 위한 세션 상태 초기화 !!!
if "organic_sales_qty" not in st.session_state:
    st.session_state.organic_sales_qty = 0
if "organic_revenue" not in st.session_state:
    st.session_state.organic_revenue = 0
# -----------------------------------------------------------


def load_product_data(selected_product_name):
    # 상품 데이터 로딩 로직 (생략)
    pass

def safe_int(value):
    try:
        return int(float(value)) if value else 0
    except (ValueError, TypeError):
        return 0

def safe_float(value):
    try:
        return float(value) if value else 0.0
    except (ValueError, TypeError):
        return 0.0

def validate_inputs():
    # 입력 값 검증 로직 (생략)
    return True # 임시로 항상 True 반환

# --- 사이드바 설정 (코드가 길어져 main 함수 밖으로 뺌) ---
st.sidebar.header("🛠️ 설정값")
config["FEE_RATE"] = st.sidebar.number_input("수수료율 (%)", value=config["FEE_RATE"], step=0.1, format="%.2f", key="config_fee")
config["AD_RATE"] = st.sidebar.number_input("광고비율 (%)", value=config["AD_RATE"], step=0.1, format="%.2f", key="config_ad")
config["INOUT_COST"] = st.sidebar.number_input("입출고비용 (원)", value=int(config["INOUT_COST"]), step=100, key="config_inout")
config["PICKUP_COST"] = st.sidebar.number_input("회수비용 (원)", value=int(config["PICKUP_COST"]), step=100, key="config_pickup")
config["RESTOCK_COST"] = st.sidebar.number_input("재입고비용 (원)", value=int(config["RESTOCK_COST"]), step=100, key="config_restock")
config["RETURN_RATE"] = st.sidebar.number_input("반품률 (%)", value=config["RETURN_RATE"], step=0.1, format="%.2f", key="config_return")
config["ETC_RATE"] = st.sidebar.number_input("기타비용률 (%)", value=config["ETC_RATE"], step=0.1, format="%.2f", key="config_etc")
config["EXCHANGE_RATE"] = st.sidebar.number_input("위안화 환율", value=int(config["EXCHANGE_RATE"]), step=1, key="config_exchange")
config["PACKAGING_COST"] = st.sidebar.number_input("포장비 (원)", value=int(config["PACKAGING_COST"]), step=100, key="config_package")
config["GIFT_COST"] = st.sidebar.number_input("사은품 비용 (원)", value=int(config["GIFT_COST"]), step=100, key="config_gift")

if st.sidebar.button("📂 기본값으로 저장"):
    save_config(config)
    st.sidebar.success("기본값이 저장되었습니다.")
# -----------------------------------------------------------


def main():
    if 'show_product_info' not in st.session_state:
        st.session_state.show_product_info = False

    tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

    with tab1:
        # 간편 계산기 로직 (생략)
        st.subheader("판매정보 입력")
        st.text_input("판매가 (원)", key="sell_price_raw_tab1")
        st.info("여기는 간단 마진 계산기 탭입니다.")
        
    # -----------------------------------------------------------
    #              ✨ 세부 마진 계산기 (일일 정산) 탭 ✨
    # -----------------------------------------------------------
    with tab2:
        st.subheader("세부 마진 계산기")

        with st.expander("상품 정보 입력"):
            # 상품 로딩 및 저장 로직 (생략)
            st.info("이 부분은 상품 등록/수정/삭제 기능이 있는 곳입니다.")

        
        # --- 핵심: 일일 정산 필드 ---
        with st.expander("일일 정산", expanded=True):
            
            # 상품 선택 (임시 더미)
            product_list = ["상품을 선택해주세요", "상품 A", "상품 B"]
            selected_product_name = st.selectbox("상품 선택", product_list, key="product_select_daily")
            
            # 상품 상세 정보 (생략)
            
            report_date = st.date_input("날짜 선택", datetime.date.today())

            st.markdown("---")
            st.markdown("#### 전체 판매")
            
            # 1. 전체 판매 수량 입력 (변경 시 자연 판매 계산 함수 실행)
            st.number_input(
                "전체 판매 수량", 
                step=1, 
                key="total_sales_qty", 
                on_change=update_organic_sales
            )
            
            # 2. 전체 매출액 입력 (변경 시 자연 판매 계산 함수 실행)
            st.number_input(
                "전체 매출액", 
                step=1000, 
                key="total_revenue", 
                on_change=update_organic_sales
            )

            st.markdown("---")
            st.markdown("#### 광고 판매")
            
            # 3. 광고 전환 판매 수량 입력 (변경 시 자연 판매 계산 함수 실행)
            st.number_input(
                "광고 전환 판매 수량", 
                step=1, 
                key="ad_sales_qty", 
                on_change=update_organic_sales
            )
            
            # 4. 광고 전환 매출액 입력 (변경 시 자연 판매 계산 함수 실행)
            st.number_input(
                "광고 전환 매출액", 
                step=1000, 
                key="ad_revenue", 
                on_change=update_organic_sales
            )
            
            ad_cost = st.number_input("광고비", step=1000, key="ad_cost")

            st.markdown("---")
            st.markdown("#### 자연 판매 (자동 계산)")

            # !!! 핵심 수정 부분: 세션 상태의 값을 직접 value로 사용 !!!
            # 이렇게 해야 update_organic_sales 함수가 세션 상태를 변경했을 때, 
            # Streamlit이 이 위젯을 다시 그릴 때 변경된 값을 반영합니다.

            st.number_input(
                "자연 판매 수량",
                value=st.session_state.organic_sales_qty, # <- 실시간 계산된 세션 상태 값 사용
                disabled=True,
                key="organic_sales_qty_display" 
            )

            st.number_input(
                "자연 판매 매출액",
                value=st.session_state.organic_revenue, # <- 실시간 계산된 세션 상태 값 사용
                disabled=True,
                key="organic_revenue_display" 
            )
            # -----------------------------------------------------------

            st.metric(label="일일 순이익금", value="0")

            if st.button("일일 정산 저장하기"):
                st.warning("계산 로직이 비활성화되어 있습니다. 순이익 계산 로직을 추가한 후 저장할 수 있습니다.")

            with st.expander("판매 현황"):
                # 판매 현황 테이블 로직 (생략)
                st.info("여기는 일일 판매 현황 및 기록 테이블이 표시되는 곳입니다.")

if __name__ == "__main__":
    main()
