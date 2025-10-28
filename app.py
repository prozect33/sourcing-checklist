import streamlit as st
import json
import os
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
        with open(DEFAULT_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return default_config()

def save_config(config):
    with open(DEFAULT_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def calculate_margins(config, sell_price, unit_yuan, qty):
    # 위에서 계산된 organic_sales_qty_calc, organic_revenue_calc, daily_profit 등의 변수가 
    # 이 함수 외부에서 사용되므로, 여기서는 기본 마진 계산만 수행합니다.
    
    # 1. 원가 계산 (원화)
    unit_won = unit_yuan * config["EXCHANGE_RATE"]
    
    # 2. 총 매출 (원화)
    total_revenue = sell_price * qty
    
    # 3. 비용 계산 (원화)
    # 3-1. 판매 수수료 (Fee Rate)
    fee_cost = total_revenue * (config["FEE_RATE"] / 100)
    
    # 3-2. 광고비
    # 광고 매출액이 입력되지 않았으므로, 총 매출액을 기준으로 광고비를 계산한다고 가정 (일반적인 방식)
    # daily_ad_cost는 일일 정산 저장 시 외부에서 입력되므로, 이 함수에서는 계산하지 않습니다.
    
    # 3-3. 기타 고정/변동 비용 (수수료 외)
    inout_cost = config["INOUT_COST"]
    pickup_cost = config["PICKUP_COST"]
    restock_cost = config["RESTOCK_COST"]
    packaging_cost = config["PACKAGING_COST"]
    gift_cost = config["GIFT_COST"]
    
    # 3-4. 상품 원가
    product_cost = unit_won * qty
    
    # 3-5. 총 비용 (원가 + 수수료 + 기타 고정 비용)
    total_fixed_cost = fee_cost + product_cost + inout_cost + pickup_cost + restock_cost + packaging_cost + gift_cost
    
    # 4. 잠정 이익금 (광고비 제외)
    provisional_profit = total_revenue - total_fixed_cost
    
    # 5. 마진율 (잠정)
    if total_revenue > 0:
        margin_rate = (provisional_profit / total_revenue) * 100
    else:
        margin_rate = 0
        
    return {
        "total_revenue": total_revenue,
        "total_fixed_cost": total_fixed_cost,
        "provisional_profit": provisional_profit,
        "margin_rate": margin_rate,
        "unit_won": unit_won
    }

# Supabase 초기화
# 환경 변수에서 URL과 KEY를 불러옵니다.
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Supabase 연결 실패: {e}")
        supabase = None
else:
    st.warning("SUPABASE_URL 또는 SUPABASE_KEY 환경 변수가 설정되지 않았습니다. 데이터 저장 기능이 비활성화됩니다.")
    supabase = None

def main():
    config = load_config()

    st.title("💰 마진 계산기 & 일일 정산")
    
    tab1, tab2, tab3 = st.tabs(["마진 계산기", "일일 정산 저장", "판매 현황"])

    # --- 탭 1: 마진 계산기 (변경 없음) ---
    with tab1:
        # (기존 탭 1 코드 유지)
        pass

    # --- 탭 2: 일일 정산 저장 (수정된 핵심 부분) ---
    with tab2:
        st.header("일일 정산 기록")

        # 1. 상품명 및 날짜 선택
        with st.container():
            col1, col2 = st.columns([1, 1])
            
            # 상품명 드롭다운 (가정: 제품 목록을 가져오는 로직은 유지됨)
            # 여기서는 샘플로 목록을 가정합니다. 실제 목록 가져오기 코드는 유지되어야 합니다.
            
            # 1-1. 상품명 선택 (DB에서 가져온 상품 목록을 가정)
            if 'product_list' in st.session_state and st.session_state.product_list:
                 product_options = ["상품을 선택해주세요"] + st.session_state.product_list
            else:
                 product_options = ["상품을 선택해주세요", "샘플 상품 A", "샘플 상품 B"] # 상품 목록 로딩 실패 시 임시
            
            selected_product_name = col1.selectbox("상품명", product_options, key="tab2_product_name")
            
            # 1-2. 날짜 선택
            report_date = col2.date_input("정산 날짜", datetime.date.today(), key="tab2_report_date")
            
            # 2. 상품 상세 정보 로드 (가정: 기존 로직 유지)
            product_data = {} 
            if selected_product_name != "상품을 선택해주세요":
                # 실제 코드에서는 이 부분에서 DB에서 해당 상품의 상세 정보를 로드해야 합니다.
                # 여기서는 마진 계산에 필요한 최소한의 데이터만 가정합니다.
                if selected_product_name == "샘플 상품 A":
                    product_data = {"unit_yuan": 100, "sell_price": 30000}
                elif selected_product_name == "샘플 상품 B":
                    product_data = {"unit_yuan": 50, "sell_price": 20000}
                # ... (DB에서 실제 데이터 로드 로직이 필요)
            
            if product_data:
                st.markdown(f"**선택된 상품의 기준 원가:** {product_data.get('unit_yuan', 0)} 위안 / **판매가:** {product_data.get('sell_price', 0)} 원")
            else:
                st.warning("선택된 상품의 정보가 없거나 로드할 수 없습니다.")


        with st.expander("일일 정산"):
            if not product_data:
                st.info("먼저 상품을 선택해주세요.")
                # 일일 순이익금 관련 변수 초기화
                daily_profit = 0
            else:
                # 3. 일일 판매 기록 입력
                col3, col4, col5 = st.columns([1, 1, 1])

                st.session_state.total_sales_qty = col3.number_input("전체 판매 수량 (개)", min_value=0, value=0, key="daily_qty")
                st.session_state.ad_sales_qty = col4.number_input("광고 판매 수량 (개)", min_value=0, value=0, key="daily_ad_qty")
                st.session_state.ad_cost = col5.number_input("일일 광고비 (원)", min_value=0, value=0, key="daily_ad_cost")
                
                # 4. 매출액 계산 및 순이익 계산
                
                # 총 매출액 및 광고 매출액 계산 (판매가 * 수량)
                sell_price = product_data.get("sell_price", 0)
                unit_yuan = product_data.get("unit_yuan", 0)
                
                st.session_state.total_revenue = sell_price * st.session_state.total_sales_qty
                st.session_state.ad_revenue = sell_price * st.session_state.ad_sales_qty
                
                # 마진 계산 로직 재사용
                margin_results = calculate_margins(config, sell_price, unit_yuan, st.session_state.total_sales_qty)
                
                # 자연 판매 수량/매출액 계산
                organic_sales_qty_calc = max(st.session_state.total_sales_qty - st.session_state.ad_sales_qty, 0)
                organic_revenue_calc = max(st.session_state.total_revenue - st.session_state.ad_revenue, 0)
                
                # 일일 순이익금 = (총 매출 - 총 고정 비용) - (광고비)
                # calculate_margins의 provisional_profit은 광고비가 제외된 이익
                daily_profit = margin_results["provisional_profit"] - st.session_state.ad_cost
                
                
                st.subheader("매출 및 순이익 결과 (자동 계산)")
                col6, col7, col8 = st.columns(3)
                col6.metric(label="전체 매출액", value=f"{st.session_state.total_revenue:,}원")
                col7.metric(label="광고 매출액", value=f"{st.session_state.ad_revenue:,}원")
                col8.metric(label="자연 매출액", value=f"{organic_revenue_calc:,}원")
                
                st.markdown("---")
                st.metric(label="일일 순이익금", value=f"{daily_profit:,}원")
                
                
                # --- [수정된 부분] UPSERT(덮어쓰기) 로직 시작 (라인 100~121 대체) ---
                if st.button("일일 정산 저장하기"):
                    # 저장 로직
                    if selected_product_name == "상품을 선택해주세요":
                        st.warning("상품을 먼저 선택해야 저장할 수 있습니다.")
                    elif not product_data:
                        st.warning("선택된 상품의 상세 정보가 없습니다.")
                    elif st.session_state.total_sales_qty == 0 and st.session_state.total_revenue == 0:
                        st.warning("판매 수량 또는 매출액을 입력해야 저장할 수 있습니다.")
                    else:
                        try:
                            # data_to_save 딕셔너리 생성
                            data_to_save = {
                                "date": report_date.isoformat(),
                                "product_name": selected_product_name,
                                "daily_sales_qty": st.session_state.total_sales_qty,
                                "daily_revenue": st.session_state.total_revenue,
                                "ad_sales_qty": st.session_state.ad_sales_qty,
                                "ad_revenue": st.session_state.ad_revenue,
                                "organic_sales_qty": organic_sales_qty_calc,
                                "organic_revenue": organic_revenue_calc,
                                "daily_ad_cost": st.session_state.ad_cost,
                                "daily_profit": daily_profit,
                                "created_at": datetime.datetime.now().isoformat()
                            }
                            
                            # --- INSERT 대신 UPSERT(덮어쓰기) 적용 ---
                            supabase.table("daily_sales").insert(data_to_save).on_conflict(
                                "date, product_name"  # 날짜와 상품명이 동일하면 덮어씁니다.
                            ).execute()
                            
                            st.success(f"'{selected_product_name}'의 {report_date} 판매 기록이 **성공적으로 저장/수정**되었습니다!")
                        
                        except Exception as e:
                            st.error(f"데이터 저장 중 오류가 발생했습니다: {e}")
                # --- [수정된 부분] UPSERT(덮어쓰기) 로직 끝 ---

    # --- 탭 3: 판매 현황 (변경 없음) ---
    with tab3:
        if supabase:
            try:
                # 1. 데이터 로드
                response = supabase.table("daily_sales").select("*").order("date", desc=True).execute()
                data = response.data
                
                if data:
                    df = pd.DataFrame(data)
                    df['date'] = pd.to_datetime(df['date'])
                    
                    # 2. 필터 선택 (상품명)
                    product_filters = ["(전체 상품)"] + sorted(df['product_name'].unique())
                    selected_product_filter = st.selectbox("상품 필터", product_filters, key="sales_filter")

                    if selected_product_filter != "(전체 상품)":
                        df_filtered = df[df['product_name'] == selected_product_filter]
                    else:
                        df_filtered = df.copy()

                    st.markdown("#### 일일 판매 기록")
                    
                    df_display = df_filtered.copy()
                    
                    # 컬럼명 변경
                    df_display = df_display.rename(columns={
                        "date": "날짜",
                        "product_name": "상품명",
                        "daily_sales_qty": "전체 수량",
                        "daily_revenue": "전체 매출액",
                        "ad_sales_qty": "광고 수량",
                        "ad_revenue": "광고 매출액",
                        "organic_sales_qty": "자연 수량",
                        "organic_revenue": "자연 매출액",
                        "daily_ad_cost": "일일 광고비",
                        "daily_profit": "일일 순이익금",
                    })
                    
                    # 데이터프레임 표시를 위한 포맷팅
                    df_display['날짜'] = df_display['날짜'].dt.strftime('%Y-%m-%d')
                    
                    # 좌측 정렬 및 포맷팅을 위해 숫자 컬럼을 문자열로 변환
                    format_cols = ['전체 매출액', '전체 수량', '광고 매출액', '자연 매출액', '일일 광고비', '일일 순이익금']
                    for col in format_cols:
                        if '수량' in col:
                            df_display[col] = df_display[col].fillna(0).astype(int).apply(lambda x: f"{x:,}")
                        else:
                            df_display[col] = df_display[col].fillna(0).astype(int).apply(lambda x: f"{x:,}원")

                    display_cols = ['날짜', '상품명', '전체 매출액', '전체 수량', '광고 매출액', '자연 매출액', '일일 광고비', '일일 순이익금']
                    st.dataframe(df_display[display_cols], use_container_width=True)

                    st.markdown("---")
                    st.markdown("#### 상품별 총 순이익금")
                    
                    # 총 순이익금 계산 및 표시
                    df_grouped = df.groupby("product_name").agg(total_profit=('daily_profit', 'sum')).reset_index()
                    df_grouped = df_grouped.rename(columns={"product_name": "상품명", "total_profit": "총 순이익금"})
                    
                    # 포맷팅
                    df_grouped['총 순이익금'] = df_grouped['총 순이익금'].fillna(0).astype(int).apply(lambda x: f"{x:,}원")
                    
                    st.dataframe(df_grouped, use_container_width=True)
                else:
                    st.info("아직 저장된 판매 기록이 없습니다.")
            except Exception as e:
                st.error(f"판매 현황을 불러오는 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    # 메인 실행 전에 탭 1의 세션 상태 키 초기화 보장
    if "sell_price_raw" not in st.session_state: st.session_state["sell_price_raw"] = ""
    if "unit_yuan" not in st.session_state: st.session_state["unit_yuan"] = ""
    if "unit_won" not in st.session_state: st.session_state["unit_won"] = ""
    if "qty_raw" not in st.session_state: st.session_state["qty_raw"] = ""
    if "show_result" not in st.session_state: st.session_state["show_result"] = False
    if "total_sales_qty" not in st.session_state: st.session_state["total_sales_qty"] = 0
    if "total_revenue" not in st.session_state: st.session_state["total_revenue"] = 0
    if "ad_sales_qty" not in st.session_state: st.session_state["ad_sales_qty"] = 0
    if "ad_revenue" not in st.session_state: st.session_state["ad_revenue"] = 0
    if "ad_cost" not in st.session_state: st.session_state["ad_cost"] = 0
    
    main()
