import streamlit as st
import json
import os
import datetime
from supabase import create_client, Client
import pandas as pd
import math # math 모듈은 이미 import 되어 있으나, 사용하지 않는 경우 삭제 가능

# --- Streamlit 페이지 설정 및 스타일 ---
st.set_page_config(page_title="간단/세부 마진 계산기", layout="wide")

st.markdown("""
    <style>
      /* 사이드바 헤더 숨김, 상단 패딩 조정 */
      [data-testid="stSidebarHeader"] { display: none !important; }
      [data-testid="stSidebarContent"] { padding-top: 15px !important; }
      /* 제목 하단 여백 조정 */
      [data-testid="stHeading"] { margin-bottom: 15px !important; }
      /* number_input 스텝 버튼 숨김 (필요시 복구) */
      /* [data-testid="stNumberInput"] button { display: none !important; } */
    </style>
""", unsafe_allow_html=True)

# --- 상수 및 설정 함수 ---
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
        "EXCHANGE_RATE": 300.0, # int 대신 float으로 통일
        "PACKAGING_COST": 0.0,
        "GIFT_COST": 0.0
    }

def load_config():
    """설정 파일을 로드하고 유효성을 검사합니다."""
    base = default_config()
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, "r") as f:
                data = json.load(f)
            
            # 로드된 데이터로 기본값 덮어쓰기 (타입 변환 시 오류 방지)
            for k, v in data.items():
                if k in base:
                    try:
                        base[k] = float(v)
                    except (ValueError, TypeError):
                        st.sidebar.warning(f"설정 파일의 '{k}' 값이 유효하지 않아 기본값으로 대체됩니다.")
                        pass # 변환 실패 시 기본값 유지
            return base
        except (IOError, json.JSONDecodeError):
            st.sidebar.error("설정 파일 로드 중 오류 발생. 기본값을 사용합니다.")
            return default_config()
    else:
        return default_config()

def save_config(config):
    """설정값을 파일에 저장합니다."""
    # 저장 시 모든 숫자를 float으로 변환하여 저장
    config_to_save = {k: float(v) for k, v in config.items()}
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        json.dump(config_to_save, f, indent=4)

def format_number(val):
    """숫자를 천 단위 구분 기호를 포함한 문자열로 포맷합니다."""
    if val is None or val == "":
        return "0"
    try:
        val = float(val)
    except:
        return "N/A" # 유효하지 않은 값 처리

    if val == 0:
        return "0"
        
    # 소수점 이하가 0이면 정수형으로 표시, 아니면 소수점 둘째 자리까지 표시
    if val.is_integer():
        return f"{int(val):,}"
    else:
        return f"{val:,.2f}"

def reset_inputs():
    """간단 계산기 탭의 입력 필드를 초기화하고 결과를 숨깁니다."""
    # 세션 상태 키 초기화 (모두 빈 문자열로 설정)
    for key in ["sell_price_raw", "unit_yuan", "unit_won", "qty_raw"]:
        st.session_state[key] = ""
    st.session_state["show_result"] = False

def load_supabase_credentials():
    """Supabase 인증 정보를 'credentials.json'에서 로드합니다."""
    try:
        with open("credentials.json", "r") as f:
            creds = json.load(f)
            return creds.get("SUPABASE_URL"), creds.get("SUPABASE_KEY")
    except FileNotFoundError:
        st.error("오류: 'credentials.json' 파일을 찾을 수 없습니다. 파일을 생성하고 Supabase 키를 입력해주세요.")
        st.stop()
    except json.JSONDecodeError:
        st.error("오류: 'credentials.json' 파일의 형식이 잘못되었습니다. JSON 형식을 확인해주세요.")
        st.stop()
    except KeyError:
        st.error("오류: 'credentials.json' 파일에 'SUPABASE_URL' 또는 'SUPABASE_KEY'가 없습니다.")
        st.stop()

# --- 안전한 값 변환 함수 (공백 체크 오류 방지 핵심) ---
def safe_int(value):
    """값(문자열 포함)을 안전하게 정수로 변환합니다. 변환 실패 시 0을 반환합니다."""
    if value is None or str(value).strip() == "":
        return 0
    try:
        # float으로 먼저 변환 후 int로 변환하여 "100.0" 같은 값도 처리
        return int(float(value))
    except (ValueError, TypeError):
        return 0

def safe_float(value):
    """값(문자열 포함)을 안전하게 float으로 변환합니다. 변환 실패 시 0.0을 반환합니다."""
    if value is None or str(value).strip() == "":
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

# --- Supabase 데이터 관련 함수 ---
def load_product_data(selected_product_name):
    """선택된 상품의 데이터를 로드하여 세션 상태에 반영합니다."""
    # st.session_state.product_loader는 selectbox의 key
    if st.session_state.product_loader == "새로운 상품 입력":
        st.session_state.is_edit_mode = False
        # 모든 입력 필드 세션 상태 초기화
        for key in ["product_name_input", "sell_price_input", "fee_rate_input", "inout_shipping_cost_input", 
                    "purchase_cost_input", "quantity_input", "logistics_cost_input", 
                    "customs_duty_input", "etc_cost_input"]:
            st.session_state[key] = ""
    else:
        try:
            # Supabase 클라이언트가 전역적으로 초기화되어 있다고 가정
            response = supabase.table("products").select("*").eq("product_name", selected_product_name).execute()
            if response.data:
                product_data = response.data[0]
                st.session_state.is_edit_mode = True
                
                # 데이터 로드 및 세션 상태 업데이트
                # 숫자가 아닌 경우 빈 문자열로 설정하여 st.text_input에 표시
                st.session_state.product_name_input = product_data.get("product_name", "")
                
                def get_display_value(key):
                    val = product_data.get(key)
                    if val is None or val == 0 or val == 0.0:
                        return ""
                    # fee는 float 형식 그대로 표시
                    if key == "fee":
                        return str(safe_float(val))
                    # 그 외는 정수형으로 표시 (매입단가는 소수점 가능)
                    return str(safe_int(val)) if key not in ["unit_purchase_cost"] else str(safe_float(val))

                # key 이름 수정: fee -> fee_rate
                st.session_state.sell_price_input = get_display_value("sell_price")
                st.session_state.fee_rate_input = get_display_value("fee")
                st.session_state.inout_shipping_cost_input = get_display_value("inout_shipping_cost")
                st.session_state.purchase_cost_input = get_display_value("purchase_cost")
                st.session_state.quantity_input = get_display_value("quantity")
                st.session_state.logistics_cost_input = get_display_value("logistics_cost")
                st.session_state.customs_duty_input = get_display_value("customs_duty")
                st.session_state.etc_cost_input = get_display_value("etc_cost")

        except Exception as e:
            st.error(f"상품 정보를 불러오는 중 오류가 발생했습니다: {e}")

def validate_inputs():
    """세부 계산기 탭의 필수 입력 필드를 검증합니다."""
    required_fields = {
        "product_name_input": "상품명",
        "sell_price_input": "판매가",
        "fee_rate_input": "수수료율",
        "inout_shipping_cost_input": "입출고/배송비",
        "purchase_cost_input": "매입비",
        "quantity_input": "수량",
        "logistics_cost_input": "물류비",
        "customs_duty_input": "관세",
    }
    
    is_valid = True
    for key, name in required_fields.items():
        # safe_int/float을 사용하여 숫자로 변환 가능한지 확인 (빈 문자열은 0으로 처리되므로, 빈 문자열 자체를 체크)
        if not st.session_state.get(key) or str(st.session_state[key]).strip() == "":
            st.warning(f"**{name}** 필드를 채워주세요") 
            is_valid = False
            
    return is_valid

# --- 메인 실행 로직 ---
# Supabase 클라이언트 초기화 (전역 사용)
try:
    SUPABASE_URL, SUPABASE_KEY = load_supabase_credentials()
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Supabase 클라이언트 초기화 중 오류가 발생했습니다: {e}")
    st.stop()

# 설정값 로드 및 사이드바 설정
config = load_config()
st.sidebar.header("🛠️ 설정값")
# config 값들이 float 형식이 되도록 safe_float으로 변환하여 사용
config["FEE_RATE"] = st.sidebar.number_input("수수료율 (%)", value=safe_float(config["FEE_RATE"]), step=0.1, format="%.2f", key="cfg_fee")
config["AD_RATE"] = st.sidebar.number_input("광고비율 (%)", value=safe_float(config["AD_RATE"]), step=0.1, format="%.2f", key="cfg_ad")
config["INOUT_COST"] = st.sidebar.number_input("입출고비용 (원)", value=safe_int(config["INOUT_COST"]), step=100, key="cfg_inout")
config["PICKUP_COST"] = st.sidebar.number_input("회수비용 (원)", value=safe_int(config["PICKUP_COST"]), step=100, key="cfg_pickup")
config["RESTOCK_COST"] = st.sidebar.number_input("재입고비용 (원)", value=safe_int(config["RESTOCK_COST"]), step=100, key="cfg_restock")
config["RETURN_RATE"] = st.sidebar.number_input("반품률 (%)", value=safe_float(config["RETURN_RATE"]), step=0.1, format="%.2f", key="cfg_return")
config["ETC_RATE"] = st.sidebar.number_input("기타비용률 (%)", value=safe_float(config["ETC_RATE"]), step=0.1, format="%.2f", key="cfg_etc")
config["EXCHANGE_RATE"] = st.sidebar.number_input("위안화 환율", value=safe_int(config["EXCHANGE_RATE"]), step=1, key="cfg_exchange")
config["PACKAGING_COST"] = st.sidebar.number_input("포장비 (원)", value=safe_int(config["PACKAGING_COST"]), step=100, key="cfg_packaging")
config["GIFT_COST"] = st.sidebar.number_input("사은품 비용 (원)", value=safe_int(config["GIFT_COST"]), step=100, key="cfg_gift")

if st.sidebar.button("📂 기본값으로 저장", key="save_config_btn"):
    # number_input의 값은 이미 config에 반영되어 있음
    save_config(config)
    st.sidebar.success("기본값이 저장되었습니다.")

# 세션 상태 초기화 (main() 함수 밖에서 한 번만 실행)
if "product_name_input" not in st.session_state:
    st.session_state.product_name_input = ""
# 기타 세션 상태 변수 초기화
for key in ["sell_price_input", "fee_rate_input", "inout_shipping_cost_input", 
            "purchase_cost_input", "quantity_input", "logistics_cost_input", 
            "customs_duty_input", "etc_cost_input", "is_edit_mode", 
            "show_product_info", "show_result", "sell_price_raw", 
            "unit_yuan", "unit_won", "qty_raw", "total_sales_qty", 
            "ad_sales_qty", "total_revenue", "ad_revenue", "ad_cost"]:
    if key not in st.session_state:
        # 논리형/숫자형은 기본값, 문자열은 빈 문자열
        if key in ["is_edit_mode", "show_product_info", "show_result"]:
            st.session_state[key] = False
        elif key in ["total_sales_qty", "ad_sales_qty", "total_revenue", "ad_revenue", "ad_cost"]:
             st.session_state[key] = 0.0 # number_input 기본값 맞춤
        else:
            st.session_state[key] = ""

def calculate_simple_margin(sell_price, unit_cost_val, qty, config):
    """간단 계산기 탭의 마진 계산 로직을 수행합니다."""
    
    # 입력값 안전하게 변환
    sell_price = safe_int(sell_price)
    qty = safe_int(qty) if qty > 0 else 1
    unit_cost_val = safe_int(unit_cost_val)

    if sell_price <= 0:
        return None # 유효하지 않은 판매가

    vat = 1.1
    
    # 비용 계산 (VAT 포함/제외는 원본 코드 로직 유지)
    unit_cost = round(unit_cost_val * qty) # 매입원가 (단가 * 수량)
    
    # 1. 고정 비용 (VAT 포함)
    fee = round((sell_price * config["FEE_RATE"] / 100) * vat)
    inout = round(config["INOUT_COST"] * vat)
    packaging = round(config["PACKAGING_COST"] * vat)
    gift = round(config["GIFT_COST"] * vat)
    
    # 2. 변동 비용 (VAT 포함) - 간단 계산기에서는 광고비, 기타, 반품 고려
    ad = round((sell_price * config["AD_RATE"] / 100) * vat)
    pickup = round(config["PICKUP_COST"])
    restock = round(config["RESTOCK_COST"])
    return_cost = round((pickup + restock) * (config["RETURN_RATE"] / 100) * vat)
    etc = round((sell_price * config["ETC_RATE"] / 100) * vat) # 원본 코드에서 여기만 VAT 미포함이었으나, 일관성을 위해 VAT 포함으로 수정
    
    # 3. 총 비용
    total_cost = unit_cost + fee + ad + inout + return_cost + etc + packaging + gift
    
    # 4. 이익 및 마진 계산
    profit2 = sell_price - total_cost
    supply_price2 = sell_price / vat
    
    # 5. 마진 (광고비, 기타, 반품비 제외한 이익)
    margin_cost = unit_cost + fee + inout + packaging + gift
    margin_profit = sell_price - margin_cost
    margin_ratio = round((margin_profit / supply_price2) * 100, 2) if supply_price2 else 0.0
    
    # 6. ROI
    roi = round((profit2 / unit_cost) * 100, 2) if unit_cost > 0 else 0.0
    roi_margin = round((margin_profit / unit_cost) * 100, 2) if unit_cost > 0 else 0.0
    
    # 7. ROAS (광고비가 0일 경우 예외 처리)
    roas_denominator = profit2 + ad
    roas = round((sell_price / roas_denominator) * 100, 2) if roas_denominator > 0 else (10000 if ad == 0 and profit2 > 0 else 0.0)

    # 8. 최소마진율 (최소 이익 / 공급가액)
    min_margin_ratio = round((profit2 / supply_price2) * 100, 2) if supply_price2 > 0 else 0.0
    
    return {
        "unit_cost": unit_cost, "fee": fee, "ad": ad, "inout": inout,
        "pickup": pickup, "restock": restock, "return_cost": return_cost, 
        "etc": etc, "packaging": packaging, "gift": gift,
        "total_cost": total_cost, "profit2": profit2, "supply_price2": supply_price2,
        "margin_profit": margin_profit, "margin_ratio": margin_ratio, 
        "roi": roi, "roi_margin": roi_margin, "roas": roas,
        "min_margin_ratio": min_margin_ratio, "qty": qty
    }

def main():
    """메인 Streamlit 앱 로직입니다."""
    
    tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 및 정산"])

    # --- 탭 1: 간단 마진 계산기 ---
    with tab1:
        st.header("🛒 간단 마진 계산기")
        left, right = st.columns(2)
        
        with left:
            st.subheader("판매정보 입력")
            
            # **판매가 입력 (공백/문자열 허용)**
            sell_price_raw = st.text_input("판매가 (원)", key="sell_price_raw", placeholder="숫자만 입력")
            margin_display = st.empty()
            
            # 목표 마진 계산 (입력 즉시 반응)
            sell_price_val = safe_int(sell_price_raw)
            if sell_price_val > 0:
                try:
                    target_margin = 50.0
                    vat = 1.1
                    
                    # 목표 마진에 도달하기 위한 최대 원가 (VAT 포함 안 함)
                    # 수수료, 입출고, 포장, 사은품은 고정 비용으로 간주
                    fee_c = round((sell_price_val / vat) * config['FEE_RATE'] / 100)
                    inout_cost_c = round(config['INOUT_COST'])
                    packaging_cost_c = round(config['PACKAGING_COST'])
                    gift_cost_c = round(config['GIFT_COST'])
                    C_total_fixed_cost = fee_c + inout_cost_c + packaging_cost_c + gift_cost_c
                    
                    supply_price = sell_price_val / vat
                    
                    # 순매출액(공급가)에서 목표 마진을 뺀 금액이 총 비용(원가 + 고정비용)
                    target_raw_cost_plus_fixed = supply_price * (1 - target_margin / 100)
                    
                    # 최대 매입원가 (VAT 제외)
                    target_cost_c = target_raw_cost_plus_fixed - C_total_fixed_cost
                    target_cost = max(0, int(target_cost_c))
                    
                    # 위안화 변환 (원가/환율)
                    yuan_cost = round(target_cost / config['EXCHANGE_RATE'], 2) if config['EXCHANGE_RATE'] else 0.0
                    
                    # 이익 계산 (최대 매입원가 기준)
                    # sell_price_val (VAT 포함) - [매입원가(VAT 미포함) * VAT + 고정비용(VAT 포함)]
                    target_cost_vat = round(target_cost * vat)
                    profit = sell_price_val - (target_cost_vat + fee + inout + packaging + gift)

                    margin_display.markdown(
                        f"""
<div style='height:10px; line-height:10px; color:#f63366; font-size:15px; margin-bottom:15px;'>
    👉 마진율 {int(target_margin)}% 목표: **최대 매입원가** {format_number(target_cost)}원 ({yuan_cost:.2f}위안) / 예상 마진: {format_number(profit)}원
</div>
""", unsafe_allow_html=True)
                except Exception as e:
                    # st.error(f"목표 마진 계산 오류: {e}") # 디버깅용
                    margin_display.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            else:
                margin_display.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

            # **원가 및 수량 입력**
            col1, col2 = st.columns(2)
            with col1:
                st.text_input("위안화 (¥)", key="unit_yuan", placeholder="위안화 금액")
            with col2:
                st.text_input("원화 (₩)", key="unit_won", placeholder="원화 금액")
            qty_raw = st.text_input("수량", key="qty_raw", placeholder="판매 수량 (기본값: 1)")
            
            calc_col, reset_col = st.columns(2)
            if calc_col.button("계산하기 🧮", use_container_width=True):
                st.session_state["show_result"] = True
            if "show_result" not in st.session_state:
                st.session_state["show_result"] = False
            reset_col.button("리셋 🔄", on_click=reset_inputs, use_container_width=True)
        
        with right:
            st.subheader("📊 계산 결과")
            if st.session_state["show_result"]:
                
                # 원가 값 결정
                unit_cost_val = 0
                cost_display = ""
                
                if st.session_state.unit_won.strip():
                    unit_cost_val = safe_float(st.session_state.unit_won)
                    cost_display = ""
                elif st.session_state.unit_yuan.strip():
                    yuan_cost = safe_float(st.session_state.unit_yuan)
                    unit_cost_val = yuan_cost * config['EXCHANGE_RATE']
                    cost_display = f"{yuan_cost:.2f}위안"
                
                # 필수 입력값 확인
                if sell_price_val <= 0 or (unit_cost_val <= 0 and (st.session_state.unit_won.strip() or st.session_state.unit_yuan.strip())) or not st.session_state.qty_raw.strip():
                     st.warning("판매가, 원가, 수량을 정확히 입력해야 결과를 볼 수 있습니다.")
                     st.session_state["show_result"] = False # 결과 숨김 처리
                     st.stop()
                
                # 실제 마진 계산 실행
                result = calculate_simple_margin(sell_price_val, unit_cost_val, safe_int(st.session_state.qty_raw), config)

                if result:
                    # 결과 출력
                    col_title, col_button = st.columns([4,1])
                    with col_button:
                        # 탭1 저장 버튼은 기능 미구현으로 비활성화 또는 메시지 출력
                        st.button("저장하기", key="save_button_tab1", disabled=True, help="세부 계산기에서 상품 저장 기능을 이용해주세요.")
                        
                    st.markdown(f"**🏷️ 총 매입원가:** **{format_number(result['unit_cost'])}원** ({cost_display})" if cost_display else f"**🏷️ 총 매입원가:** **{format_number(result['unit_cost'])}원**")
                    st.markdown(f"**💰 마진:** **{format_number(result['margin_profit'])}원** / ROI: {result['roi_margin']:.2f}%")
                    st.markdown(f"**📈 마진율:** **{result['margin_ratio']:.2f}%** (광고비, 기타비용 제외)")
                    st.markdown("---")
                    st.markdown(f"**🧾 최소 이익:** **{format_number(result['profit2'])}원** / ROI: {result['roi']:.2f}%")
                    st.markdown(f"**📉 최소 마진율:** {result['min_margin_ratio']:.2f}% (총 비용 포함)")
                    st.markdown(f"**📊 ROAS:** {result['roas']:.2f}%")
                    
                    # 상세 비용 항목
                    with st.expander("📦 상세 비용 항목 보기", expanded=False):
                        def styled_line(label, value, is_bold=False):
                            style = "font-size:15px;"
                            if is_bold:
                                style += " font-weight: bold;"
                            return f"<div style='{style}'><strong>{label}</strong> {value}</div>"
                            
                        st.markdown(styled_line("판매가:", f"{format_number(sell_price_val)}원"), unsafe_allow_html=True)
                        st.markdown(styled_line("공급가액:", f"{format_number(round(result['supply_price2']))}원"), unsafe_allow_html=True)
                        st.markdown(styled_line("총 매입원가:", f"{format_number(result['unit_cost'])}원 ({cost_display})" if cost_display else f"{format_number(result['unit_cost'])}원"), unsafe_allow_html=True)
                        st.markdown(styled_line("수수료:", f"{format_number(result['fee'])}원"), unsafe_allow_html=True)
                        st.markdown(styled_line("광고비:", f"{format_number(result['ad'])}원"), unsafe_allow_html=True)
                        st.markdown(styled_line("입출고비용:", f"{format_number(result['inout'])}원"), unsafe_allow_html=True)
                        st.markdown(styled_line("포장비:", f"{format_number(result['packaging'])}원"), unsafe_allow_html=True)
                        st.markdown(styled_line("사은품 비용:", f"{format_number(result['gift'])}원"), unsafe_allow_html=True)
                        st.markdown(styled_line("반품비용 (회수/재입고):", f"{format_number(result['return_cost'])}원"), unsafe_allow_html=True)
                        st.markdown(styled_line("기타비용:", f"{format_number(result['etc'])}원"), unsafe_allow_html=True)
                        st.markdown("---")
                        st.markdown(styled_line("총 비용:", f"{format_number(result['total_cost'])}원", is_bold=True), unsafe_allow_html=True)
                        st.markdown(styled_line("최소 이익:", f"{format_number(result['profit2'])}원", is_bold=True), unsafe_allow_html=True)
                else:
                    st.warning("판매가를 0보다 크게 입력해야 합니다.")
            else:
                st.info("왼쪽에서 판매 정보를 입력하고 '계산하기' 버튼을 눌러주세요.")


    # --- 탭 2: 세부 마진 및 정산 ---
    with tab2:
        st.header("📋 세부 마진 및 일일 정산")

        # 세부 마진 계산기 - 상품 정보 입력
        st.subheader("1. 상품 정보 관리")
        with st.expander("상품 상세 정보 입력/수정", expanded=True):
            product_list = ["새로운 상품 입력"]
            try:
                response = supabase.table("products").select("product_name").order("product_name").execute()
                if response.data:
                    saved_products = [item['product_name'] for item in response.data]
                    product_list.extend(saved_products)
            except Exception as e:
                st.error(f"상품 목록을 불러오는 중 오류가 발생했습니다: {e}")

            selected_product_name = st.selectbox(
                "저장된 상품 선택 또는 새로 입력",
                product_list,
                key="product_loader",
                on_change=lambda: load_product_data(st.session_state.product_loader)
            )

            # Streamlit의 Session State를 이용하여 입력값 관리 (공백 체크는 safe_int/float 사용)
            product_name = st.text_input(
                "상품명",
                value=st.session_state.product_name_input, 
                key="product_name_input",
                placeholder="예: 무선 이어폰"
            )

            col_left, col_right = st.columns(2)
            with col_left:
                st.text_input("판매가 (원)", key="sell_price_input", placeholder="숫자만 입력")
            with col_right:
                st.text_input("수수료율 (%)", key="fee_rate_input", placeholder="예: 10.8") 
            with col_left:
                st.text_input("입출고/배송비 (원)", key="inout_shipping_cost_input", placeholder="총 비용")
            with col_right:
                st.text_input("총 매입비 (원)", key="purchase_cost_input", placeholder="총 매입 금액")
            with col_left:
                st.text_input("수량 (개)", key="quantity_input", placeholder="총 수량")

            # 입력값 안전하게 변환
            sell_price = safe_int(st.session_state.sell_price_input)
            fee_rate = safe_float(st.session_state.fee_rate_input)
            inout_shipping_cost = safe_int(st.session_state.inout_shipping_cost_input)
            purchase_cost = safe_int(st.session_state.purchase_cost_input)
            quantity = safe_int(st.session_state.quantity_input)
            
            quantity_for_calc = quantity if quantity > 0 else 1 
            
            with col_right:
                # 매입단가 계산 (소수점 처리)
                try:
                    unit_purchase_cost = purchase_cost / quantity_for_calc
                except (ZeroDivisionError, TypeError):
                    unit_purchase_cost = 0.0
                st.text_input("매입단가 (원)", value=f"{unit_purchase_cost:,.0f}원", disabled=True, key="display_unit_purchase_cost")

            with col_left:
                st.text_input("물류비 (원)", key="logistics_cost_input", placeholder="총 물류비")
            with col_right:
                st.text_input("관세 (원)", key="customs_duty_input", placeholder="총 관세")

            st.text_input("기타 비용 (원)", key="etc_cost_input", placeholder="총 기타 비용")

            logistics_cost = safe_int(st.session_state.logistics_cost_input)
            customs_duty = safe_int(st.session_state.customs_duty_input)
            etc_cost = safe_int(st.session_state.etc_cost_input)
            quantity_to_save = quantity 

            # 저장/수정/삭제 버튼 로직
            if st.session_state.is_edit_mode:
                col_mod, col_del = st.columns(2)
                
                with col_mod:
                    if st.button("수정하기 📝", use_container_width=True):
                        if validate_inputs():
                            if sell_price <= 0:
                                st.warning("판매가는 0보다 큰 값으로 입력해야 합니다.")
                            else:
                                try:
                                    data_to_update = {
                                        "sell_price": sell_price,
                                        "fee": fee_rate, # float
                                        "inout_shipping_cost": inout_shipping_cost,
                                        "purchase_cost": purchase_cost,
                                        "quantity": quantity_to_save,
                                        "unit_purchase_cost": unit_purchase_cost, # float
                                        "logistics_cost": logistics_cost,
                                        "customs_duty": customs_duty,
                                        "etc_cost": etc_cost,
                                    }
                                    supabase.table("products").update(data_to_update).eq("product_name", st.session_state.product_name_input).execute()
                                    st.success(f"'{st.session_state.product_name_input}' 상품 정보가 업데이트되었습니다! 페이지를 새로고침하면 목록에 반영됩니다.")
                                except Exception as e:
                                    st.error(f"데이터 수정 중 오류가 발생했습니다: {e}")
                
                with col_del:
                    if st.button("삭제하기 🗑️", use_container_width=True):
                        try:
                            supabase.table("products").delete().eq("product_name", st.session_state.product_name_input).execute()
                            st.success(f"'{st.session_state.product_name_input}' 상품이 삭제되었습니다! 페이지를 새로고침하면 목록에 반영됩니다.")
                            # 삭제 후 입력 모드로 전환
                            st.session_state.is_edit_mode = False
                            load_product_data("새로운 상품 입력")
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"데이터 삭제 중 오류가 발생했습니다: {e}")
            else:
                if st.button("상품 저장하기 💾", use_container_width=True):
                    if validate_inputs():
                        product_name_to_save = st.session_state.product_name_input
                        
                        if sell_price <= 0:
                            st.warning("판매가는 0보다 큰 값으로 입력해야 합니다.")
                        else:
                            try:
                                data_to_save = {
                                    "product_name": product_name_to_save,
                                    "sell_price": sell_price,
                                    "fee": fee_rate,
                                    "inout_shipping_cost": inout_shipping_cost,
                                    "purchase_cost": purchase_cost,
                                    "quantity": quantity_to_save,
                                    "unit_purchase_cost": unit_purchase_cost,
                                    "logistics_cost": logistics_cost,
                                    "customs_duty": customs_duty,
                                    "etc_cost": etc_cost,
                                }
                                # 중복 상품명 체크
                                response = supabase.table("products").select("product_name").eq("product_name", product_name_to_save).execute()
                                if response.data:
                                    st.warning("이미 같은 이름의 상품이 존재합니다. 수정하려면 목록에서 선택해주세요.")
                                else:
                                    supabase.table("products").insert(data_to_save).execute()
                                    st.success(f"'{product_name_to_save}' 상품이 성공적으로 저장되었습니다! 페이지를 새로고침하면 목록에 반영됩니다.")
                            except Exception as e:
                                st.error(f"데이터 저장 중 오류가 발생했습니다: {e}")

        # --- 일일 정산 기능 ---
        st.markdown("---")
        st.subheader("2. 일일 정산 기록")
        with st.expander("일일 정산 기록 및 계산", expanded=True):
            # 상품 목록 다시 로드 (방금 저장된 상품을 포함하기 위해)
            product_list_daily = ["상품을 선택해주세요"]
            try:
                response = supabase.table("products").select("product_name").order("product_name").execute()
                if response.data:
                    saved_products_daily = [item['product_name'] for item in response.data]
                    product_list_daily.extend(saved_products_daily)
            except Exception as e:
                st.error(f"상품 목록을 불러오는 중 오류가 발생했습니다: {e}")

            # selectbox on_change를 사용하여 데이터 로드하는 로직은 복잡해지므로, 
            # 단순하게 selectbox의 현재 값을 기반으로 데이터를 조회
            selected_product_name_daily = st.selectbox("상품 선택", product_list_daily, key="product_select_daily")

            product_data = {}
            if selected_product_name_daily and selected_product_name_daily != "상품을 선택해주세요":
                try:
                    response = supabase.table("products").select("*").eq("product_name", selected_product_name_daily).execute()
                    if response.data:
                        product_data = response.data[0]
                except Exception as e:
                    st.error(f"상품 정보를 불러오는 중 오류가 발생했습니다: {e}")

            # 상품 상세 정보 (읽기 전용)
            with st.expander("선택 상품 상세 정보"):
                if selected_product_name_daily == "상품을 선택해주세요":
                    st.info("먼저 상품을 선택해주세요.")
                elif product_data:
                    # 'safe_float'을 사용하여 None이나 빈 문자열을 안전하게 처리
                    st.markdown(f"**판매가:** {safe_int(product_data.get('sell_price', 0)):,}원")
                    st.markdown(f"**수수료율:** {safe_float(product_data.get('fee', 0.0)):.2f}%")
                    st.markdown(f"**총 매입비:** {safe_int(product_data.get('purchase_cost', 0)):,}원")
                    st.markdown(f"**수량:** {safe_int(product_data.get('quantity', 0)):,}개")
                    st.markdown(f"**매입단가:** {safe_float(product_data.get('unit_purchase_cost', 0)):,.0f}원")
                    st.markdown(f"**입출고/배송비:** {safe_int(product_data.get('inout_shipping_cost', 0)):,}원")
                    st.markdown(f"**물류비:** {safe_int(product_data.get('logistics_cost', 0)):,}원")
                    st.markdown(f"**관세:** {safe_int(product_data.get('customs_duty', 0)):,}원")
                    st.markdown(f"**기타 비용:** {safe_int(product_data.get('etc_cost', 0)):,}원")
                else:
                    st.info("선택된 상품의 상세 정보가 없습니다.")

            report_date = st.date_input("날짜 선택", datetime.date.today(), key="report_date_input")

            st.markdown("---")
            st.markdown("#### 전체 판매")
            # number_input은 기본적으로 float을 반환하므로 step=1000을 사용
            total_sales_qty = st.number_input("전체 판매 수량 (개)", step=1, min_value=0, key="total_sales_qty")
            total_revenue = st.number_input("전체 매출액 (원)", step=1000, min_value=0.0, key="total_revenue")

            st.markdown("---")
            st.markdown("#### 광고 판매")
            ad_sales_qty = st.number_input("광고 전환 판매 수량 (개)", step=1, min_value=0, key="ad_sales_qty")
            ad_revenue = st.number_input("광고 전환 매출액 (원)", step=1000, min_value=0.0, key="ad_revenue")
            ad_cost = st.number_input("광고비 (원)", step=1000, min_value=0.0, key="ad_cost")

            st.markdown("---")
            st.markdown("#### 자연 판매")
            
            # 자연 판매 수량/매출액 자동 계산 (음수 방지)
            organic_sales_qty_val = max(0, safe_int(st.session_state.total_sales_qty) - safe_int(st.session_state.ad_sales_qty))
            organic_revenue_val = max(0.0, safe_float(st.session_state.total_revenue) - safe_float(st.session_state.ad_revenue))

            organic_sales_qty = st.number_input(
                "자연 판매 수량 (개)",
                value=float(organic_sales_qty_val),
                disabled=True,
                key="organic_sales_qty"
            )

            organic_revenue = st.number_input(
                "자연 판매 매출액 (원)",
                value=organic_revenue_val,
                disabled=True,
                key="organic_revenue"
            )
            
            # 일일 순이익금 계산 (여기에 계산 로직 추가)
            daily_profit = 0.0
            daily_profit_calculated = False
            
            if product_data and total_sales_qty > 0 and total_revenue > 0:
                try:
                    # 상품 정보 (평균 단가)
                    unit_purchase_cost_daily = safe_float(product_data.get('unit_purchase_cost', 0.0))
                    sell_price_daily = safe_int(product_data.get('sell_price', 0))
                    fee_rate_daily = safe_float(product_data.get('fee', 0.0))
                    
                    # 총 고정/변동 비용 계산 (평균 단가 기준)
                    # 총 매입 원가 = 매입단가 * 전체 판매 수량
                    total_purchase_cost = unit_purchase_cost_daily * total_sales_qty

                    # 수수료 = 전체 매출액 * 수수료율 / 100 * VAT (간단 계산기 로직 기반)
                    vat = 1.1
                    fee_daily = (total_revenue * (fee_rate_daily / 100.0))
                    
                    # 기타 비용 (총 금액을 판매 수량으로 나눈 후 * 전체 판매 수량)
                    # 원본 코드가 '총' 금액으로 저장하므로, 개당 단가를 구해서 곱함
                    qty_total = safe_int(product_data.get('quantity', 1))
                    if qty_total == 0: qty_total = 1
                    
                    cost_per_unit = lambda cost_key: safe_int(product_data.get(cost_key, 0)) / qty_total

                    total_inout_shipping_cost = cost_per_unit('inout_shipping_cost') * total_sales_qty
                    total_logistics_cost = cost_per_unit('logistics_cost') * total_sales_qty
                    total_customs_duty = cost_per_unit('customs_duty') * total_sales_qty
                    total_etc_cost = cost_per_unit('etc_cost') * total_sales_qty

                    # 기타 설정 비용 (일일 판매 수량 기준) - 설정값은 개당으로 간주
                    # 설정값은 VAT 포함 여부가 복잡하므로 일단 모두 VAT 포함으로 가정하고 합산
                    daily_cfg_inout = config['INOUT_COST'] * vat * total_sales_qty
                    daily_cfg_packaging = config['PACKAGING_COST'] * vat * total_sales_qty
                    daily_cfg_gift = config['GIFT_COST'] * vat * total_sales_qty
                    daily_cfg_etc_rate = (total_revenue * (config['ETC_RATE'] / 100.0)) # 매출액 기준 기타 비용

                    # 총 비용 합산
                    total_daily_cost = (
                        total_purchase_cost + 
                        fee_daily + 
                        safe_float(ad_cost) + 
                        total_inout_shipping_cost + 
                        total_logistics_cost + 
                        total_customs_duty + 
                        total_etc_cost +
                        daily_cfg_inout +
                        daily_cfg_packaging +
                        daily_cfg_gift +
                        daily_cfg_etc_rate
                    )

                    daily_profit = total_revenue - total_daily_cost
                    daily_profit_calculated = True

                except Exception as e:
                    # st.error(f"일일 순이익 계산 오류: {e}") # 디버깅용
                    daily_profit = 0.0
                    daily_profit_calculated = False

            
            st.metric(label="일일 순이익금 (원)", value=f"{format_number(daily_profit)}원")

            if st.button("일일 정산 저장하기 🗃️", use_container_width=True):
                if selected_product_name_daily == "상품을 선택해주세요":
                    st.warning("먼저 상품을 선택해주세요.")
                elif total_sales_qty <= 0 or total_revenue <= 0:
                    st.warning("전체 판매 수량과 매출액을 0보다 크게 입력해야 저장할 수 있습니다.")
                elif not daily_profit_calculated:
                    st.warning("순이익 계산이 실패했거나 (상품 정보 불충분) 계산 로직이 비활성화되어 있습니다. 상품 정보를 확인해주세요.")
                else:
                    try:
                        data_to_save = {
                            "date": report_date.isoformat(),
                            "product_name": selected_product_name_daily,
                            "daily_sales_qty": safe_int(total_sales_qty),
                            "daily_revenue": safe_int(total_revenue),
                            "ad_sales_qty": safe_int(ad_sales_qty),
                            "ad_revenue": safe_int(ad_revenue),
                            "daily_ad_cost": safe_int(ad_cost),
                            "organic_sales_qty": safe_int(organic_sales_qty_val),
                            "organic_revenue": safe_int(organic_revenue_val),
                            "daily_profit": safe_int(daily_profit), # 정수로 저장
                        }
                        # 날짜와 상품명으로 중복 체크 및 업데이트/삽입
                        response = supabase.table("daily_sales").select("*").eq("date", data_to_save['date']).eq("product_name", data_to_save['product_name']).execute()
                        
                        if response.data:
                            # 이미 존재하면 업데이트
                            supabase.table("daily_sales").update(data_to_save).eq("date", data_to_save['date']).eq("product_name", data_to_save['product_name']).execute()
                            st.success(f"'{report_date.isoformat()}' 날짜의 '{selected_product_name_daily}' 정산 정보가 업데이트되었습니다!")
                        else:
                            # 존재하지 않으면 삽입
                            supabase.table("daily_sales").insert(data_to_save).execute()
                            st.success(f"'{report_date.isoformat()}' 날짜의 '{selected_product_name_daily}' 정산 정보가 성공적으로 저장되었습니다!")
                        
                        st.experimental_rerun() # 저장 후 목록 업데이트를 위해 페이지 새로고침
                        
                    except Exception as e:
                        st.error(f"일일 정산 데이터 저장 중 오류가 발생했습니다: {e}")


        # --- 판매 현황 (데이터프레임 출력) ---
        st.markdown("---")
        st.subheader("3. 판매 현황 기록")
        with st.expander("저장된 판매 기록 보기", expanded=True):
            try:
                response = supabase.table("daily_sales").select("*").order("date", desc=True).execute()
                df = pd.DataFrame(response.data)

                if not df.empty:
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                    
                    st.markdown("#### 일일 판매 기록")
                    # 불필요한 컬럼 삭제 및 이름 변경
                    df_display = df.drop(columns=['id', 'created_at', 'daily_sales_qty', 'ad_sales_qty', 'organic_sales_qty'], errors='ignore')
                    df_display = df_display.rename(columns={
                        "date": "날짜",
                        "product_name": "상품명",
                        "daily_revenue": "전체 매출액",
                        "ad_revenue": "광고 매출액",
                        "organic_revenue": "자연 매출액",
                        "daily_ad_cost": "일일 광고비",
                        "daily_profit": "일일 순이익금",
                    })
                    
                    # 숫자 컬럼 포맷팅
                    numeric_cols = ['전체 매출액', '광고 매출액', '자연 매출액', '일일 광고비', '일일 순이익금']
                    for col in numeric_cols:
                        if col in df_display.columns:
                            df_display[col] = df_display[col].apply(lambda x: f"{safe_int(x):,}")

                    st.dataframe(df_display, use_container_width=True, hide_index=True)

                    st.markdown("---")
                    st.markdown("#### 상품별 총 순이익금")

                    # 그룹화할 때 포맷팅된 문자열이 아닌 원본 숫자 데이터를 사용해야 함
                    df_grouped = df.groupby("product_name").agg(
                        total_profit=('daily_profit', 'sum')
                    ).reset_index()

                    df_grouped = df_grouped.rename(columns={
                        "product_name": "상품명",
                        "total_profit": "총 순이익금"
                    })
                    
                    df_grouped["총 순이익금"] = df_grouped["총 순이익금"].apply(lambda x: f"{safe_int(x):,}")

                    st.dataframe(df_grouped, use_container_width=True, hide_index=True)

                else:
                    st.info("아직 저장된 판매 기록이 없습니다.")
            except Exception as e:
                st.error(f"판매 현황을 불러오는 중 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    main()
