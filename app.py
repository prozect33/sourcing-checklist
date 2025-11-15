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

def format_number(val):
    if val is None:
        return ""
    return f"{int(val):,}" if float(val).is_integer() else f"{val:,.2f}"

def reset_inputs():
    # 탭1 리셋
    st.session_state["sell_price_raw"] = ""
    st.session_state["unit_yuan"] = ""
    st.session_state["unit_won"] = ""
    st.session_state["qty_raw"] = ""
    st.session_state["show_result"] = False
    
    # 탭2 일일 정산 리셋
    if "total_sales_qty" in st.session_state: st.session_state["total_sales_qty"] = 0
    if "total_revenue" in st.session_state: st.session_state["total_revenue"] = 0
    if "ad_cost" in st.session_state: st.session_state["ad_cost"] = 0

# --- Supabase 설정 로드 ---
try:
    # 환경 변수에서 Supabase 설정 로드
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Supabase 환경 변수를 로드하는 데 실패했습니다. `.env` 파일을 확인해 주세요.")
    st.stop()
# -----------------------------

# --- 설정값 로드 및 저장 (사이드바) ---
@st.cache_data(ttl=3600) # 1시간마다 캐시 갱신
def get_config_data():
    try:
        response = supabase.table("config").select("*").order("created_at", desc=True).limit(1).execute()
        if response.data:
            return response.data[0]
    except Exception:
        pass
    return {}

def save_config_data(new_config):
    try:
        # 기존 데이터를 덮어쓰거나 (upsert) 새로 저장
        supabase.table("config").upsert(new_config, on_conflict="id").execute()
        # 캐시 무효화
        get_config_data.clear() 
        st.success("설정이 저장되었습니다.")
        st.rerun() # 변경 사항 반영
    except Exception as e:
        st.error(f"설정 저장 중 오류가 발생했습니다: {e}")

# 설정값 초기화/로드
config = get_config_data()
default_config = {
    "id": 1,
    "FEE_RATE": 13.0,
    "VAT": 10.0,
    "EXCHANGE_RATE": 185.0,
    "INOUT_COST": 4500.0,
    "LOGISTICS_COST": 800.0,
    "CUSTOMS_COST": 3.0,
    "PACKAGING_COST": 400.0,
    "GIFT_COST": 300.0,
    "PICKUP_COST": 5000.0,
    "RESTOCK_COST": 3000.0,
    "RETURN_RATE": 5.0,
    "ETC_RATE": 2.0,
    "INVENTORY_LOSS": 1.0, # 재고 손실률 추가 (사용하지 않더라도 명시)
}

# 기본값 채우기
for key, default_val in default_config.items():
    if key not in config:
        config[key] = default_val


# --- 상품 데이터 로드 및 저장 ---
@st.cache_data(ttl=3600)
def get_product_data():
    try:
        response = supabase.table("products").select("*").execute()
        return {item['product_name']: item for item in response.data}
    except Exception:
        return {}

product_data_dict = get_product_data()
product_list = ["(상품을 선택해주세요)"] + list(product_data_dict.keys())


# --- 사이드바 설정 영역 ---
with st.sidebar:
    st.title("⚙️ 마진 계산 설정")
    
    st.markdown("### 💰 비용 및 환율 설정")
    
    config["FEE_RATE"] = st.number_input("쇼핑몰 수수료율 (%)", value=config.get("FEE_RATE", 13.0), min_value=0.0, max_value=100.0, step=0.1, format="%.1f")
    config["VAT"] = st.number_input("VAT (%)", value=config.get("VAT", 10.0), min_value=0.0, max_value=100.0, step=0.1, format="%.1f")
    config["EXCHANGE_RATE"] = st.number_input("환율 (원/위안)", value=config.get("EXCHANGE_RATE", 185.0), min_value=1.0, step=0.1, format="%.2f")
    
    st.markdown("---")
    st.markdown("### 📦 고정/변동 비용 설정")
    
    config["INOUT_COST"] = st.number_input("기본 입출고/배송비 (원/건)", value=config.get("INOUT_COST", 4500.0), min_value=0.0, step=100.0, format="%.0f")
    config["LOGISTICS_COST"] = st.number_input("기본 물류비 (원/건)", value=config.get("LOGISTICS_COST", 800.0), min_value=0.0, step=100.0, format="%.0f")
    config["CUSTOMS_COST"] = st.number_input("기본 관세율 (%)", value=config.get("CUSTOMS_COST", 3.0), min_value=0.0, max_value=100.0, step=0.1, format="%.1f")
    config["ETC_RATE"] = st.number_input("기타 비용율 (% of 매출)", value=config.get("ETC_RATE", 2.0), min_value=0.0, max_value=100.0, step=0.1, format="%.1f")
    
    st.markdown("---")
    st.markdown("### 🎁 추가/반품 비용 설정")

    config["PACKAGING_COST"] = st.number_input("기본 포장비 (원/건)", value=config.get("PACKAGING_COST", 400.0), min_value=0.0, step=100.0, format="%.0f")
    config["GIFT_COST"] = st.number_input("기본 사은품 비용 (원/건)", value=config.get("GIFT_COST", 300.0), min_value=0.0, step=100.0, format="%.0f")
    
    config["RETURN_RATE"] = st.number_input("반품 예상 비율 (%)", value=config.get("RETURN_RATE", 5.0), min_value=0.0, max_value=100.0, step=0.1, format="%.1f")
    config["PICKUP_COST"] = st.number_input("반품 회수 비용 (원/건)", value=config.get("PICKUP_COST", 5000.0), min_value=0.0, step=100.0, format="%.0f")
    config["RESTOCK_COST"] = st.number_input("반품 재고 정리 비용 (원/건)", value=config.get("RESTOCK_COST", 3000.0), min_value=0.0, step=100.0, format="%.0f")

    st.markdown("---")
    if st.button("설정 저장하기", use_container_width=True):
        save_config_data(config)


# --- 메인 탭 영역 ---
tab1, tab2, tab3 = st.tabs(["📊 간단 마진 계산기", "📝 일일 정산", "📈 판매 현황"])

# 모든 계산에 사용될 상수
fee_rate = config["FEE_RATE"]
vat_rate = config["VAT"] / 100
exchange_rate = config["EXCHANGE_RATE"]
inout_cost = config["INOUT_COST"]
logistics_cost = config["LOGISTICS_COST"]
customs_rate = config["CUSTOMS_COST"] / 100
etc_rate = config["ETC_RATE"] / 100
packaging_cost = config["PACKAGING_COST"]
gift_cost = config["GIFT_COST"]
return_rate = config["RETURN_RATE"] / 100
pickup_cost = config["PICKUP_COST"]
restock_cost = config["RESTOCK_COST"]
vat = 1 + vat_rate # 1.1

# 탭 1: 간단 마진 계산기
with tab1:
    st.header("🛒 상품 마진 계산기")
    st.markdown("---")
    
    left, right = st.columns(2)
    
    with left:
        st.subheader("💰 상품 정보 입력")
        
        # 입력 필드: 세션 상태를 사용하여 값 유지
        sell_price_raw = st.text_input("판매 가격 (원)", key="sell_price_raw", placeholder="부가세 포함 가격")
        unit_yuan = st.text_input("상품 원가 (위안)", key="unit_yuan")
        unit_won = st.text_input("추가 매입가 (원/개)", key="unit_won", placeholder="개별 포장비 등 (선택)")
        qty_raw = st.text_input("수량", key="qty_raw", placeholder="예상 판매 수량 (선택)")
        
        # 버튼 영역
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("계산하기", use_container_width=True):
                st.session_state["show_result"] = True
        with col_btn2:
            if st.button("입력 초기화", use_container_width=True):
                reset_inputs()
                st.session_state["show_result"] = False
                st.rerun()

    with right:
        st.subheader("📊 결과 분석 (개당)")
        
        if st.session_state["show_result"] and sell_price_raw:
            try:
                # 1. 입력값 정리 및 숫자 변환
                sell_price = float(sell_price_raw.replace(",", ""))
                unit_yuan_val = float(unit_yuan.replace(",", "")) if unit_yuan else 0
                unit_won_val = float(unit_won.replace(",", "")) if unit_won else 0
                qty = int(qty_raw.replace(",", "")) if qty_raw else 1
                
                # 2. 비용 계산 (개당)
                
                # A. 매출 관련 비용
                fee = round((sell_price / vat) * fee_rate / 100 * vat) # 수수료 (부가세 제외 금액 * 수수료율 * 부가세)
                vat_cost = round(sell_price * vat_rate / vat) # 매출 부가세 (판매가 / 1.1 * 0.1)
                
                # B. 매입 관련 비용 (원가)
                purchase_cost = round((unit_yuan_val * exchange_rate) + unit_won_val)
                customs_cost = round(purchase_cost * customs_rate * vat) # 관세 (원가 * 관세율 * 부가세)
                
                # C. 운영 관련 비용 (원가 기준)
                inout_shipping_cost = round(inout_cost / qty * vat) # 입출고/배송비 (총합을 수량으로 나눈 후 부가세 적용)
                logistics = round(logistics_cost / qty * vat) # 물류비 (총합을 수량으로 나눈 후 부가세 적용)

                # D. 기타 고정 비용 (개당)
                packaging = round(packaging_cost * vat) # 포장비
                gift = round(gift_cost * vat) # 사은품 비용
                etc = round((sell_price * etc_rate) * vat) # 기타 비용 (매출 * 기타율 * 부가세)
                
                # E. 반품 관련 비용 (개당)
                return_cost = round((pickup_cost + restock_cost) * return_rate * vat)
                
                # 3. 마진 계산
                total_cost = (fee + vat_cost + purchase_cost + customs_cost + 
                              inout_shipping_cost + logistics + packaging + 
                              gift + etc + return_cost)
                
                gross_profit = sell_price - total_cost
                
                gross_profit_percent = (gross_profit / sell_price) * 100 if sell_price else 0
                
                # 4. 결과 출력
                st.metric(label="✅ 총 순이익금 (개당)", value=f"{format_number(gross_profit)}원", delta=f"{gross_profit_percent:.1f}%")
                
                with st.expander("세부 비용 내역"):
                    cost_df = pd.DataFrame({
                        "구분": ["매출", "매출", "매입", "매입", "운영", "운영", "고정", "고정", "기타", "반품"],
                        "항목": ["판매가", "쇼핑몰 수수료", "상품 원가", "관세", "입출고/배송비", "물류비", "포장비", "사은품 비용", "기타 비용", "반품 처리 비용"],
                        "비용 (원)": [sell_price, fee, purchase_cost, customs_cost, 
                                   inout_shipping_cost, logistics, packaging, gift, 
                                   etc, return_cost]
                    })
                    cost_df["비용 (원)"] = cost_df["비용 (원)"].apply(format_number)
                    cost_df = cost_df.set_index("구분")
                    st.table(cost_df)
                    st.caption(f"총 비용: {format_number(total_cost)}원")
                
            except ValueError:
                st.error("입력값은 숫자여야 하며, 판매 가격은 필수입니다.")
        else:
            st.info("판매 가격 및 원가 등을 입력하고 '계산하기'를 눌러주세요.")

# 탭 2: 일일 정산
with tab2:
    st.header("📝 일일 정산 기록")
    st.markdown("---")
    
    # 1. 상품 선택 및 데이터 로드
    col_prod, col_date = st.columns(2)
    with col_prod:
        selected_product_name = st.selectbox("상품 선택", product_list, key="daily_sales_product")
    with col_date:
        today_date = st.date_input("정산 날짜", datetime.date.today(), key="daily_sales_date")

    product_data = product_data_dict.get(selected_product_name)
    
    if selected_product_name != "(상품을 선택해주세요)" and product_data:
        
        # 2. 상품별 원가/비용 표시 (참고용)
        st.markdown(f"##### 🏷️ **{selected_product_name}** 상품 기준 비용")
        col_c1, col_c2, col_c3, col_c4 = st.columns(4)
        
        # 상품 상세 정보 표시
        col_c1.metric("위안가", f"{format_number(product_data.get('unit_yuan', 0))} 위안")
        col_c2.metric("추가 매입가", f"{format_number(product_data.get('unit_won', 0))} 원")
        col_c3.metric("쇼핑몰 수수료", f"{product_data.get('fee', config['FEE_RATE']):.1f}%")
        col_c4.metric("배송/입출고비", f"{format_number(product_data.get('inout_shipping_cost', config['INOUT_COST']))} 원")

        st.markdown("---")

        # 3. 판매 및 비용 입력
        st.markdown("##### 🛒 일일 판매 및 광고비 입력")

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.subheader("판매 수량")
            current_total_sales_qty = st.number_input("총 판매 수량 (광고+오가닉)", value=st.session_state.get("total_sales_qty", 0), min_value=0, step=1, key="total_sales_qty")
        with col_s2:
            st.subheader("총 매출액")
            current_total_revenue = st.number_input("총 매출액 (부가세 포함)", value=st.session_state.get("total_revenue", 0), min_value=0, step=10000, key="total_revenue")
        
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.subheader("광고비")
            current_ad_cost = st.number_input("총 광고비 (부가세 포함)", value=st.session_state.get("ad_cost", 0), min_value=0, step=1000, key="ad_cost")
        
        # 4. 일일 순이익 계산
        
        if current_total_sales_qty > 0 and current_total_revenue > 0:
            
            # 4-1. 상품별 상세 원가 로드 (저장된 상품 데이터 사용)
            quantity_for_calc = product_data.get("quantity", 1) # 상품 수량 (예: 1+1 = 2)
            unit_purchase_cost = (product_data.get("unit_yuan", 0) * exchange_rate + product_data.get("unit_won", 0)) / quantity_for_calc
            unit_logistics = product_data.get("logistics_cost", config['LOGISTICS_COST']) / quantity_for_calc
            unit_customs = product_data.get("customs_rate", config['CUSTOMS_COST']) / 100
            unit_etc = product_data.get("etc_cost", 0) / quantity_for_calc
            fee_rate_db = product_data.get("fee", 0.0)

            vat = 1.1 
            
            # --- 누락된 고정 비용 계산 (이전에 누락 지적된 부분) ---
            daily_packaging_cost = config.get("PACKAGING_COST", 0) * vat * current_total_sales_qty
            daily_gift_cost = config.get("GIFT_COST", 0) * vat * current_total_sales_qty
            daily_return_cost = (
                (config.get("PICKUP_COST", 0) + config.get("RESTOCK_COST", 0)) * (config.get("RETURN_RATE", 0.0) / 100) * vat * current_total_sales_qty
            )

            # 4-2. 총 순이익 계산 (판매 수량 기준으로 모든 비용 차감)
            daily_profit = (
                current_total_revenue 
                - (current_total_revenue * fee_rate_db / 100 * 1.1)  # 쇼핑몰 수수료
                - (unit_purchase_cost * current_total_sales_qty) # 매입비 (원가)
                - (product_data.get("inout_shipping_cost", config['INOUT_COST']) * current_total_sales_qty * 1.1) # 입출고/배송비
                - (unit_logistics * current_total_sales_qty * 1.1) # 물류비
                - (unit_purchase_cost * current_total_sales_qty * unit_customs * 1.1) # 관세
                - (current_total_revenue * unit_etc * 1.1) # 기타 비용 (매출 기준)
                - (current_ad_cost * 1.1) # 광고비
                
                # 추가된 누락 비용
                - daily_packaging_cost # 포장비
                - daily_gift_cost # 사은품 비용
                - daily_return_cost # 반품/회수비용
            )
            daily_profit = round(daily_profit)
            
            st.metric(label=f"💰 {today_date.isoformat()} 총 순이익금 (세후)", value=f"{format_number(daily_profit)} 원")

            # 5. DB 저장
            if st.button("일일 정산 기록 저장/업데이트", use_container_width=True, key="save_daily_sales"):
                try:
                    # Supabase에 upsert (업데이트 또는 삽입)
                    data = {
                        "date": today_date.isoformat(),
                        "product_name": selected_product_name,
                        "daily_sales_qty": current_total_sales_qty,
                        "daily_revenue": current_total_revenue,
                        "daily_ad_cost": current_ad_cost,
                        "daily_profit": daily_profit,
                    }
                    supabase.table("daily_sales").upsert(data, on_conflict="date,product_name").execute()
                    st.success(f"{today_date.isoformat()} {selected_product_name}의 정산 기록이 저장/업데이트 되었습니다.")
                    
                    # 저장 후 입력값 리셋
                    st.session_state["total_sales_qty"] = 0
                    st.session_state["total_revenue"] = 0
                    st.session_state["ad_cost"] = 0
                    st.rerun() 

                except Exception as e:
                    st.error(f"DB 저장 중 오류가 발생했습니다: {e}")
        
        else:
            st.info("판매 수량과 매출액을 입력하면 순이익이 계산됩니다.")

    else:
        st.warning("정산할 상품을 선택해주세요.")

# 탭 3: 판매 현황
with tab3:
    st.header("📈 기간별 판매 현황")
    
    # 1. 기간별 전체 순이익 조회 (조회 버튼 포함)
    st.markdown("---")
    st.markdown("#### 📅 기간별 전체 순이익 조회")

    # 세션 상태를 사용하여 선택한 날짜 유지
    today = datetime.date.today()
    default_start_date = today - datetime.timedelta(days=6) # 최근 7일

    if "profit_start_date_val" not in st.session_state:
        st.session_state.profit_start_date_val = default_start_date
    if "profit_end_date_val" not in st.session_state:
        st.session_state.profit_end_date_val = today
    if "run_profit_query" not in st.session_state:
        st.session_state.run_profit_query = False

    col_date1, col_date2 = st.columns([1, 1])
    with col_date1:
        start_date = st.date_input(
            "시작 날짜", 
            value=st.session_state.profit_start_date_val, 
            key="profit_start_date_input",
            on_change=lambda: st.session_state.__setitem__("profit_start_date_val", st.session_state.profit_start_date_input)
        )
    with col_date2:
        end_date = st.date_input(
            "종료 날짜", 
            value=st.session_state.profit_end_date_val, 
            key="profit_end_date_input",
            on_change=lambda: st.session_state.__setitem__("profit_end_date_val", st.session_state.profit_end_date_input)
        )

    # 조회하기 버튼 추가 및 로직 실행
    col_btn, col_space = st.columns([1, 2])
    with col_btn:
        if st.button("순이익 조회하기", use_container_width=True, key="profit_query_btn"):
            st.session_state.run_profit_query = True
            st.rerun() # 버튼 클릭 시 즉시 실행

    # 순이익 계산 및 표시 로직 (버튼 클릭 시에만 실행)
    if st.session_state.run_profit_query:
        if start_date and end_date and start_date <= end_date:
            st.markdown(f"##### 🔎 **{start_date.isoformat()} ~ {end_date.isoformat()}** 순이익 집계 결과")
            try:
                # DB에서 daily_profit만 로드하고 날짜 범위 필터링
                response_all = supabase.table("daily_sales").select("daily_profit").gte("date", start_date.isoformat()).lte("date", end_date.isoformat()).execute()
                df_all = pd.DataFrame(response_all.data)
                
                if not df_all.empty and "daily_profit" in df_all.columns:
                    # 합산 전, 데이터 타입 안정성을 확보
                    df_all["daily_profit"] = pd.to_numeric(df_all["daily_profit"], errors='coerce').fillna(0)
                    total_period_profit = df_all["daily_profit"].sum()
                    
                    st.metric(label="전체 상품 총 순이익금", value=f"{format_number(total_period_profit)}원")
                else:
                    st.info("선택 기간에 저장된 판매 기록이 없습니다.")
                    
            except Exception as e:
                st.error(f"기간별 순이익 계산 중 오류가 발생했습니다: {e}")
        elif start_date and end_date:
            st.warning("시작 날짜가 종료 날짜보다 늦을 수 없습니다.")

    st.markdown("---")
    st.markdown("#### 📊 상품별 판매 현황") 
    
    # 2. 상품별 상세 현황 (필터 및 데이터 표시)
    
    selected_product_filter = st.selectbox("상품 필터", product_list, key="product_filter")
    
    # --- 데이터 로드 ---
    # 쿼리 빌드
    query = supabase.table("daily_sales").select("*")
    
    # 날짜 필터 적용
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        # 세션 상태에 값이 없으면 초기값 설정
        if "sales_status_start_date" not in st.session_state:
            st.session_state.sales_status_start_date = default_start_date
        
        filter_start_date = st.date_input(
            "조회 시작 날짜", 
            value=st.session_state.sales_status_start_date, 
            key="sales_status_start_date_input",
            on_change=lambda: st.session_state.__setitem__("sales_status_start_date", st.session_state.sales_status_start_date_input)
        )

    with col_d2:
        # 세션 상태에 값이 없으면 초기값 설정
        if "sales_status_end_date" not in st.session_state:
            st.session_state.sales_status_end_date = today
            
        filter_end_date = st.date_input(
            "조회 종료 날짜", 
            value=st.session_state.sales_status_end_date, 
            key="sales_status_end_date_input",
            on_change=lambda: st.session_state.__setitem__("sales_status_end_date", st.session_state.sales_status_end_date_input)
        )

    # 쿼리에 날짜 조건 추가
    if filter_start_date and filter_end_date:
        query = query.gte("date", filter_start_date.isoformat()).lte("date", filter_end_date.isoformat())

    # 상품 필터 조건 추가
    if selected_product_filter != "(상품을 선택해주세요)":
        query = query.eq("product_name", selected_product_filter)

    # 쿼리 실행
    try:
        response = query.order("date", desc=True).execute()
        df = pd.DataFrame(response.data)

        if not df.empty:
            
            # 페이지네이션 설정
            page_size = 10
            total_rows = len(df)
            total_pages = (total_rows + page_size - 1) // page_size

            if "daily_sales_page" not in st.session_state:
                st.session_state.daily_sales_page = 1
            
            # 페이지 범위 계산
            start_index = (st.session_state.daily_sales_page - 1) * page_size
            end_index = min(start_index + page_size, total_rows)
            
            df_display = df.iloc[start_index:end_index].copy()

            # 데이터 정제 및 표시 형식 설정
            df_display["daily_revenue"] = df_display["daily_revenue"].apply(format_number)
            df_display["daily_ad_cost"] = df_display["daily_ad_cost"].apply(format_number)
            df_display["daily_profit"] = df_display["daily_profit"].apply(format_number)
            
            # 컬럼명 변경
            df_display.rename(columns={
                "date": "날짜",
                "product_name": "상품명",
                "daily_sales_qty": "판매 수량",
                "daily_revenue": "총 매출액 (원)",
                "daily_ad_cost": "총 광고비 (원)",
                "daily_profit": "순이익금 (원)"
            }, inplace=True)
            
            # 표시할 컬럼 선택
            columns_to_display = ["날짜", "상품명", "판매 수량", "총 매출액 (원)", "총 광고비 (원)", "순이익금 (원)"]
            
            # 데이터프레임 출력
            st.dataframe(df_display[columns_to_display], use_container_width=True, hide_index=True)
            
            # 요약 통계
            if selected_product_filter != "(상품을 선택해주세요)":
                # 순이익 컬럼을 숫자형으로 변환하여 합계 계산
                total_profit_filtered = pd.to_numeric(df["daily_profit"], errors='coerce').fillna(0).sum()
                st.markdown(f"**선택 상품 ({selected_product_filter}) 총 순이익**: **{format_number(total_profit_filtered)}** 원")

            # 페이지네이션 버튼
            if total_pages > 1:
                page_cols = st.columns([1, 1, 1])
                
                if page_cols[0].button("이전", disabled=(st.session_state.daily_sales_page <= 1), key="prev_page_btn"):
                    st.session_state.daily_sales_page -= 1
                    st.rerun() 

                page_cols[1].markdown(
                    f"<div style='text-align:center; font-size:16px; margin-top:5px;'>페이지 {st.session_state.daily_sales_page} / {total_pages}</div>", 
                    unsafe_allow_html=True
                )

                if page_cols[2].button("다음", disabled=(st.session_state.daily_sales_page >= total_pages), key="next_page_btn"):
                    st.session_state.daily_sales_page += 1
                    st.rerun() 

                st.markdown("---")

            else: # selected_product_filter == "(상품을 선택해주세요)" 일 때
                # 아무 것도 표시하지 않음
                pass


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
