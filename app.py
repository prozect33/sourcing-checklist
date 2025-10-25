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
    # val이 None인 경우 0으로 처리하거나 적절한 예외 처리
    if val is None:
        val = 0
        
    # float() 변환 시도 전에 문자열로 변환 (안전하게 처리)
    val_float = float(val)

    return f"{int(val_float):,}" if val_float.is_integer() else f"{val_float:,.2f}"

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
        
# ----------------------------------------------------------------------
# Helper 함수: 일일 순이익 계산 (이전 요청에서 추가된 로직)
# ----------------------------------------------------------------------
def calculate_daily_profit(product_data, total_sales_qty, total_revenue, ad_cost):
    """
    상품 데이터와 일일 판매/비용 데이터를 기반으로 일일 순이익을 계산합니다.
    """
    if not product_data or total_sales_qty == 0:
        return 0, 0, 0, 0, 0 # profit, total_cost, unit_cost_total, unit_sale_price_avg, margin_ratio

    # 1. 판매가 및 비용 데이터 추출 (VAT 포함)
    vat = 1.1
    
    # 2. 총 매출 (Total Revenue)에서 부가세 제외한 공급가액 (Supply Price)
    total_supply_price = total_revenue / vat

    # 3. 상품 원가 관련 데이터
    total_purchase_cost = product_data.get('purchase_cost', 0) # 총 매입비
    logistics_cost = product_data.get('logistics_cost', 0) # 물류비 (총액)
    customs_duty = product_data.get('customs_duty', 0) # 관세 (총액)
    etc_cost = product_data.get('etc_cost', 0) # 기타 (총액)
    product_quantity = product_data.get('quantity', 1) # 매입 수량

    # 매입된 상품에 대한 총 원가 (매입비 + 물류비 + 관세 + 기타)
    total_cost_of_goods_bought = (total_purchase_cost + logistics_cost + customs_duty + etc_cost)

    # 판매된 상품 수량에 대한 총 판매 원가 (비용 발생 시점을 고려하여 전체 매입 수량으로 나눠 단가 계산 후 판매 수량 곱함)
    if product_quantity > 0:
        unit_cost_total = round(total_cost_of_goods_bought / product_quantity * total_sales_qty)
    else:
        unit_cost_total = 0

    # 4. 매출에 비례하는 비용 (총액)
    # 판매 수수료 = 총 매출액 * 수수료율(Fee Rate) / 100
    fee_rate = product_data.get('fee', 0.0)
    total_fee = round((total_revenue * fee_rate / 100)) # 수수료는 통상 VAT 포함 매출에 부과됨.

    # 5. 고정 비용 (총액)
    # 입출고/배송비: 건당 비용 * 판매 수량
    inout_shipping_cost_per_unit = product_data.get('inout_shipping_cost', 0)
    total_inout_shipping_cost = round(inout_shipping_cost_per_unit * total_sales_qty)
    
    # 기타 비용 (일반 설정값 사용) - '간단 마진 계산기'의 기타 비용률(ETC_RATE)
    etc_rate_from_config = config.get('ETC_RATE', 0)
    total_etc_rate_cost = round((total_revenue * etc_rate_from_config / 100)) 

    # 6. 총 비용
    # 총 비용 = 총 판매 원가 + 총 수수료 + 총 광고비 + 총 입출고/배송비 + 기타비용률 적용 금액
    total_cost = unit_cost_total + total_fee + ad_cost + total_inout_shipping_cost + total_etc_rate_cost

    # 7. 순이익
    daily_profit = total_revenue - total_cost

    # 추가 지표 (평균 판매가, 순마진율)
    unit_sale_price_avg = total_revenue / total_sales_qty
    
    # 순마진율: 순이익 / (총 매출액 / 1.1) * 100
    daily_margin_ratio = (daily_profit / total_supply_price) * 100 if total_supply_price else 0


    return daily_profit, total_cost, unit_cost_total, unit_sale_price_avg, daily_margin_ratio

# ----------------------------------------------------------------------

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
if "product_loader" not in st.session_state: # Selectbox 키를 세션 상태에 추가
    st.session_state.product_loader = "새로운 상품 입력"


# 상품 정보 불러오기/리셋 함수
def load_product_data(selected_product_name):
    """선택된 상품의 정보를 불러와 세션 상태를 업데이트합니다."""
    # product_loader 값이 변경될 때마다 호출됨
    if selected_product_name == "새로운 상품 입력":
        st.session_state.is_edit_mode = False
        st.session_state.product_name_edit = ""
        st.session_state.sell_price_edit = 0
        st.session_state.fee_rate_edit = 0.0
        st.session_state.inout_shipping_cost_edit = 0
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
                
                st.session_state.quantity_edit = int(product_data.get("quantity", 0)) if "quantity" in product_data and product_data.get("quantity") is not None else 0
                
                st.session_state.logistics_cost_edit = int(product_data.get("logistics_cost", 0))
                st.session_state.customs_duty_edit = int(product_data.get("customs_duty", 0))
                st.session_state.etc_cost_edit = int(product_data.get("etc_cost", 0))
        except Exception as e:
            st.error(f"상품 정보를 불러오는 중 오류가 발생했습니다: {e}")

# Helper 함수: 상품 로더를 '새로운 상품 입력'으로 리셋하고 페이지를 재실행
def reset_to_new_product_mode():
    st.session_state.product_loader = "새로운 상품 입력"
    st.session_state.is_edit_mode = False
    st.session_state.product_name_edit = ""
    # 입력 필드의 세션 상태를 직접 초기화 (load_product_data가 재실행 시 호출되지만 안전하게 처리)
    st.session_state.sell_price_edit = 0
    st.session_state.fee_rate_edit = 0.0
    st.session_state.inout_shipping_cost_edit = 0
    st.session_state.purchase_cost_edit = 0
    st.session_state.quantity_edit = 1
    st.session_state.logistics_cost_edit = 0
    st.session_state.customs_duty_edit = 0
    st.session_state.etc_cost_edit = 0
    
    st.rerun() # 변경된 목록을 반영하고 상태를 초기화하기 위해 페이지를 다시 로드


# 메인 함수
def main():
    if 'show_product_info' not in st.session_state:
        st.session_state.show_product_info = False

    tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

    with tab1:
        left, right = st.columns(2)
        with left:
            st.subheader("판매정보 입력")
            sell_price_raw = st.text_input("판매가 (원)", key="sell_price_raw")
            margin_display = st.empty()
            if sell_price_raw.strip():
                try:
                    target_margin = 50.0
                    sell_price_val = int(float(sell_price_raw))
                    vat = 1.1
                    fee = round((sell_price_val * config['FEE_RATE'] / 100) * vat)
                    ad_fee = round((sell_price_val * config['AD_RATE'] / 100) * vat)
                    inout_cost = round(config['INOUT_COST'] * vat)
                    return_cost = round((config['PICKUP_COST'] + config['RESTOCK_COST']) * (config['RETURN_RATE'] / 100) * vat)
                    etc_cost = round((sell_price_val * config['ETC_RATE'] / 100) * vat)
                    packaging_cost = round(config['PACKAGING_COST'] * vat)
                    gift_cost = round(config['GIFT_COST'] * vat)
                    supply_price = sell_price_val / vat
                    C = fee + inout_cost + packaging_cost + gift_cost
                    C_total_fixed_cost = fee + inout_cost + packaging_cost + gift_cost
                    
                    # 목표 마진율을 달성하기 위한 원가 계산 (공급가액 기준)
                    raw_cost2 = sell_price_val \
                                - (supply_price * (target_margin / 100)) \
                                - C_total_fixed_cost
                                
                    target_cost = max(0, int(raw_cost2))
                    
                    # 원가를 VAT 제외한 위안화로 환산
                    yuan_cost = round((target_cost / config['EXCHANGE_RATE']) / vat, 2)
                    
                    # 목표 마진율 달성 시 최소 이익금 (VAT 포함 매출 - (VAT 포함 원가 + VAT 포함 고정비용))
                    profit = sell_price_val - (
                        round(target_cost * vat) + fee + inout_cost + packaging_cost + gift_cost
                    )
                    
                    margin_display.markdown(
                        f"""
<div style='height:10px; line-height:10px; color:#f63366; font-size:15px; margin-bottom:15px;'>
    마진율 {int(target_margin)}% 기준: {format_number(target_cost)}원 ({yuan_cost:.2f}위안) / 마진: {format_number(profit)}원
</div>
""", unsafe_allow_html=True)
                except:
                    margin_display.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            else:
                margin_display.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                unit_yuan = st.text_input("위안화 (¥)", key="unit_yuan")
            with col2:
                unit_won = st.text_input("원화 (₩)", key="unit_won")
            qty_raw = st.text_input("수량", value="1", key="qty_raw")
            calc_col, reset_col = st.columns(2)
            if calc_col.button("계산하기"):
                st.session_state["show_result"] = True
            if "show_result" not in st.session_state:
                st.session_state["show_result"] = False
            reset_col.button("리셋", on_click=reset_inputs)
        with right:
            if st.session_state["show_result"]:
                try:
                    sell_price = int(float(sell_price_raw))
                    qty = int(float(qty_raw)) if qty_raw else 1
                except:
                    st.warning("판매가와 수량을 정확히 입력해주세요.")
                    st.stop()
                
                # 원가 계산
                unit_cost_val = 0
                cost_display = ""
                if unit_won.strip() != "":
                    unit_cost_val = round(float(unit_won))
                    cost_display = ""
                elif unit_yuan.strip() != "":
                    unit_cost_val = round(
                        float(unit_yuan)
                        * config['EXCHANGE_RATE']
                    )
                    cost_display = f"{unit_yuan}위안"
                
                vat = 1.1
                unit_cost = round(unit_cost_val * qty) # 총 원가 (VAT 미포함으로 가정)

                # 총 비용 계산 (VAT 포함된 금액을 계산하는 것이 일반적)
                fee = round((sell_price * config["FEE_RATE"] / 100) * vat)
                ad = round((sell_price * config["AD_RATE"] / 100) * vat)
                inout = round(config["INOUT_COST"] * vat)
                pickup = round(config["PICKUP_COST"])
                restock = round(config["RESTOCK_COST"])
                return_cost = round((pickup + restock) * (config["RETURN_RATE"] / 100) * vat)
                etc = round((sell_price * config["ETC_RATE"] / 100) * vat) # 기타비용도 VAT 포함 가정
                packaging = round(config["PACKAGING_COST"] * vat)
                gift = round(config["GIFT_COST"] * vat)
                
                # 총 비용: (원가*VAT) + 수수료 + 광고 + 입출고 + 반품 + 기타 + 포장비 + 사은품
                # 원가(unit_cost)는 위안화->원화로 환산 시 VAT 제외된 금액으로 가정하고 VAT를 다시 곱해줍니다.
                total_cost = (unit_cost * vat) + fee + ad + inout + return_cost + etc + packaging + gift
                total_cost = round(total_cost)

                profit2 = sell_price - total_cost
                supply_price2 = sell_price / vat
                
                # 광고비, 반품비, 기타비용을 제외한 "마진" (순이익이 아닌 광고 투입 전 이익)
                margin_profit = sell_price - ((unit_cost * vat) + fee + inout + packaging + gift)
                margin_profit = round(margin_profit)
                
                # 마진율: (마진 / 공급가액) * 100
                margin_ratio = round((margin_profit / supply_price2) * 100, 2)
                
                # ROI: (최소 이익 / (원가 * VAT)) * 100
                roi = round((profit2 / (unit_cost * vat)) * 100, 2) if (unit_cost * vat) else 0
                
                # ROI (마진 기준): (마진 / (원가 * VAT)) * 100
                roi_margin = round((margin_profit / (unit_cost * vat)) * 100, 2) if (unit_cost * vat) else 0
                
                # ROAS: (매출 / 광고비) * 100
                roas = round((sell_price / ad) * 100, 2) if ad else 0
                
                col_title, col_button = st.columns([4,1])
                with col_title:
                    st.markdown("### 📊 계산 결과")
                with col_button:
                    st.button("저장하기", key="save_button_tab1")
                if cost_display:
                    st.markdown(f"- 🏷️ 원가: {format_number(unit_cost)}원 ({cost_display})" if unit_cost > 0 else f"- 🏷️ 원가: {format_number(unit_cost)}원")
                else:
                    st.markdown(f"- 🏷️ 원가: {format_number(unit_cost)}원")
                
                st.markdown(f"- 💰 마진: {format_number(margin_profit)}원 / ROI(마진): {roi_margin:.2f}%")
                st.markdown(f"- 📈 마진율: {margin_ratio:.2f}%")
                st.markdown(f"- 🧾 최소 이익: {format_number(profit2)}원 / ROI(최소): {roi:.2f}%")
                st.markdown(f"- 📉 최소마진율: {(profit2/supply_price2*100):.2f}%")
                st.markdown(f"- 📊 ROAS: {roas:.2f}%")
                
                with st.expander("📦 상세 비용 항목 보기", expanded=False):
                    def styled_line(label, value):
                        return f"<div style='font-size:15px;'><strong>{label}</strong> {value}</div>"
                    st.markdown(styled_line("판매가:", f"{format_number(sell_price)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("원가 (VAT 미포함):", f"{format_number(unit_cost)}원 ({cost_display})" if cost_display else f"{format_number(unit_cost)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("원가 (VAT 포함):", f"{format_number(round(unit_cost * vat))}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("수수료:", f"{format_number(fee)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("광고비:", f"{format_number(ad)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("입출고비용:", f"{format_number(inout)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("회수비용:", f"{format_number(pickup)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("재입고비용:", f"{format_number(restock)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("반품비용:", f"{format_number(return_cost)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("기타비용:", f"{format_number(etc)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("포장비:", f"{format_number(packaging)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("사은품 비용:", f"{format_number(gift)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("총비용:", f"{format_number(total_cost)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("공급가액:", f"{format_number(round(supply_price2))}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("최소 이익:", f"{format_number(profit2)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("최소마진율:", f"{(profit2/supply_price2*100):.2f}%"), unsafe_allow_html=True)
                    st.markdown(styled_line("투자수익률:", f"{roi:.2f}%"), unsafe_allow_html=True)
    
    with tab2:
        st.subheader("세부 마진 계산기")
        
        with st.expander("상품 정보 입력"):
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
                # on_change 대신 load_product_data를 직접 호출하도록 구현함
                index=product_list.index(st.session_state.product_loader) if st.session_state.product_loader in product_list else 0
            )

            # selectbox 값이 변경되었는지 확인하고 수동으로 데이터 로드
            if selected_product_name != st.session_state.product_name_edit and selected_product_name == "새로운 상품 입력" and st.session_state.is_edit_mode:
                # '새로운 상품 입력'을 선택했으나, 기존 모드가 편집 모드였던 경우
                load_product_data("새로운 상품 입력")
            elif selected_product_name != st.session_state.product_name_edit and selected_product_name != "새로운 상품 입력":
                # 다른 상품을 선택한 경우
                load_product_data(selected_product_name)
            elif selected_product_name != st.session_state.product_loader:
                # 키가 바뀌었을 때도 데이터 로드
                load_product_data(selected_product_name)
            
            # 입력 값 업데이트를 위한 로직 (수정 모드일 때만 적용되도록)
            current_product_name = st.text_input(
                "상품명",
                value=st.session_state.product_name_edit,
                placeholder="예: 무선 이어폰",
                key="product_name_input_key"
            )
            # st.session_state.product_name_edit을 직접 업데이트하여 다음 재실행 시 반영되도록 함
            st.session_state.product_name_edit = current_product_name
            
            col_left, col_right = st.columns(2)
            with col_left:
                sell_price = st.number_input("판매가", step=1000, value=st.session_state.sell_price_edit, key="sell_price_input")
            with col_right:
                fee_rate = st.number_input("수수료율 (%)", max_value=100.0, step=0.1, format="%.2f", value=st.session_state.fee_rate_edit, key="fee_rate_input")
            with col_left:
                inout_shipping_cost = st.number_input("입출고/배송비", step=100, value=st.session_state.inout_shipping_cost_edit, key="inout_shipping_cost_input")
            with col_right:
                purchase_cost = st.number_input("매입비 (총액)", step=100, value=st.session_state.purchase_cost_edit, key="purchase_cost_input")
            with col_left:
                quantity = st.number_input("수량 (매입 수량)", step=1, value=st.session_state.quantity_edit, key="quantity_input")
            
            with col_right:
                try:
                    unit_purchase_cost = purchase_cost / quantity if quantity != 0 else 0
                except (TypeError):
                    unit_purchase_cost = 0
                st.text_input("매입단가", value=f"{unit_purchase_cost:,.0f}원", disabled=True)
            with col_left:
                logistics_cost = st.number_input("물류비 (총액)", step=100, value=st.session_state.logistics_cost_edit, key="logistics_cost_input")
            with col_right:
                customs_duty = st.number_input("관세 (총액)", step=100, value=st.session_state.customs_duty_edit, key="customs_duty_input")
            
            etc_cost = st.number_input("기타 (총액)", step=100, value=st.session_state.etc_cost_edit, key="etc_cost_input")
            
            if st.session_state.is_edit_mode:
                col_mod, col_del = st.columns(2)
                with col_mod:
                    if st.button("수정하기"):
                        if not current_product_name or sell_price == 0:
                            st.warning("상품명과 판매가를 입력해 주세요.")
                        elif current_product_name != st.session_state.product_name_edit:
                            st.warning("수정 모드에서는 상품명을 변경할 수 없습니다. 새 상품으로 저장하거나 삭제 후 다시 등록해 주세요.")
                        else:
                            try:
                                data_to_update = {
                                    "sell_price": sell_price,
                                    "fee": fee_rate,
                                    "inout_shipping_cost": inout_shipping_cost,
                                    "purchase_cost": purchase_cost,
                                    "quantity": quantity,
                                    "unit_purchase_cost": unit_purchase_cost,
                                    "logistics_cost": logistics_cost,
                                    "customs_duty": customs_duty,
                                    "etc_cost": etc_cost,
                                }
                                supabase.table("products").update(data_to_update).eq("product_name", st.session_state.product_name_edit).execute()
                                st.success(f"'{st.session_state.product_name_edit}' 상품 정보가 업데이트되었습니다!")
                                
                                # 수정 후 '새로운 상품 입력' 모드로 리셋
                                reset_to_new_product_mode()
                                
                            except Exception as e:
                                st.error(f"데이터 수정 중 오류가 발생했습니다: {e}")
                with col_del:
                    if st.button("삭제하기"):
                        try:
                            supabase.table("products").delete().eq("product_name", st.session_state.product_name_edit).execute()
                            st.success(f"'{st.session_state.product_name_edit}' 상품이 삭제되었습니다!")
                            
                            # 삭제 후 '새로운 상품 입력' 모드로 리셋
                            reset_to_new_product_mode()

                        except Exception as e:
                            st.error(f"데이터 삭제 중 오류가 발생했습니다: {e}")
            else:
                if st.button("상품 저장하기"):
                    if not current_product_name or sell_price == 0:
                        st.warning("상품명과 판매가를 입력해 주세요.")
                    else:
                        try:
                            data_to_save = {
                                "product_name": current_product_name,
                                "sell_price": sell_price,
                                "fee": fee_rate,
                                "inout_shipping_cost": inout_shipping_cost,
                                "purchase_cost": purchase_cost,
                                "quantity": quantity,
                                "unit_purchase_cost": unit_purchase_cost,
                                "logistics_cost": logistics_cost,
                                "customs_duty": customs_duty,
                                "etc_cost": etc_cost,
                            }
                            response = supabase.table("products").select("product_name").eq("product_name", current_product_name).execute()
                            if response.data:
                                st.warning("이미 같은 이름의 상품이 존재합니다. 수정하려면 목록에서 선택해주세요.")
                            else:
                                supabase.table("products").insert(data_to_save).execute()
                                st.success(f"'{current_product_name}' 상품이 성공적으로 저장되었습니다!")
                                
                                # 저장 후 '새로운 상품 입력' 모드로 리셋
                                reset_to_new_product_mode()
                                
                        except Exception as e:
                            st.error(f"데이터 저장 중 오류가 발생했습니다: {e}")

        with st.expander("일일 정산"):
            product_list_daily = ["상품을 선택해주세요"]
            try:
                response = supabase.table("products").select("product_name").order("product_name").execute()
                if response.data:
                    saved_products_daily = [item['product_name'] for item in response.data]
                    product_list_daily.extend(saved_products_daily)
            except Exception as e:
                st.error(f"상품 목록을 불러오는 중 오류가 발생했습니다: {e}")
            
            selected_product_name_daily = st.selectbox("상품 선택", product_list_daily, key="product_select_daily")

            product_data = {}
            if selected_product_name_daily and selected_product_name_daily != "상품을 선택해주세요":
                try:
                    response = supabase.table("products").select("*").eq("product_name", selected_product_name_daily).execute()
                    if response.data:
                        product_data = response.data[0]
                except Exception as e:
                    st.error(f"상품 정보를 불러오는 중 오류가 발생했습니다: {e}")
            
            with st.expander("상품 상세 정보"):
                if selected_product_name_daily == "상품을 선택해주세요":
                    st.info("먼저 상품을 선택해주세요.")
                elif product_data:
                    st.markdown(f"**판매가:** {product_data.get('sell_price', 0):,}원")
                    st.markdown(f"**수수료율:** {product_data.get('fee', 0.0):.2f}%")
                    st.markdown(f"**매입비 (총액):** {product_data.get('purchase_cost', 0):,}원")
                    st.markdown(f"**수량 (매입):** {product_data.get('quantity', 0):,}개")
                    st.markdown(f"**매입단가:** {product_data.get('unit_purchase_cost', 0):,.0f}원")
                    st.markdown(f"**입출고/배송비 (건당):** {product_data.get('inout_shipping_cost', 0):,}원")
                    st.markdown(f"**물류비 (총액):** {product_data.get('logistics_cost', 0):,}원")
                    st.markdown(f"**관세 (총액):** {product_data.get('customs_duty', 0):,}원")
                    st.markdown(f"**기타 (총액):** {product_data.get('etc_cost', 0):,}원")
                else:
                    st.info("선택된 상품의 상세 정보가 없습니다.")
            
            report_date = st.date_input("날짜 선택", datetime.date.today())
            
            st.markdown("---")
            st.markdown("#### 전체 판매")
            total_sales_qty = st.number_input("전체 판매 수량", step=1, key="total_sales_qty")
            total_revenue = st.number_input("전체 매출액", step=1000, key="total_revenue")
            
            st.markdown("---")
            st.markdown("#### 광고 판매")
            ad_sales_qty = st.number_input("광고 전환 판매 수량", step=1, key="ad_sales_qty")
            ad_revenue = st.number_input("광고 전환 매출액", step=1000, key="ad_revenue")
            ad_cost = st.number_input("광고비", step=1000, key="ad_cost")
            
            st.markdown("---")
            st.markdown("#### 자연 판매")
            
            organic_sales_qty = st.number_input(
                "자연 판매 수량",
                value=total_sales_qty - ad_sales_qty if total_sales_qty >= ad_sales_qty else 0,
                disabled=True,
                key="organic_sales_qty"
            )
            
            organic_revenue = st.number_input(
                "자연 판매 매출액",
                value=total_revenue - ad_revenue if total_revenue >= ad_revenue else 0,
                disabled=True,
                key="organic_revenue"
            )
            
            # 순이익 계산 및 표시
            daily_profit, total_cost, unit_cost_total, unit_sale_price_avg, daily_margin_ratio = calculate_daily_profit(
                product_data, total_sales_qty, total_revenue, ad_cost
            )

            st.metric(label="일일 순이익금", value=f"{int(daily_profit):,}원")
            st.metric(label="순마진율", value=f"{daily_margin_ratio:.2f}%")

            if st.button("일일 정산 저장하기"):
                if selected_product_name_daily == "상품을 선택해주세요" or total_sales_qty <= 0 or total_revenue <= 0:
                    st.warning("상품을 선택하고 판매 수량 및 매출액을 0보다 크게 입력해주세요.")
                else:
                    try:
                        data_to_save = {
                            "date": report_date.isoformat(),
                            "product_name": selected_product_name_daily,
                            "daily_sales_qty": total_sales_qty,
                            "daily_revenue": total_revenue,
                            "daily_ad_cost": ad_cost,
                            "ad_sales_qty": ad_sales_qty,
                            "ad_revenue": ad_revenue,
                            "organic_sales_qty": organic_sales_qty,
                            "organic_revenue": organic_revenue,
                            "daily_profit": int(daily_profit),
                            "daily_margin_ratio": daily_margin_ratio
                        }
                        # Supabase에 데이터 삽입
                        supabase.table("daily_sales").insert(data_to_save).execute()
                        st.success(f"{report_date} 날짜의 '{selected_product_name_daily}' 일일 정산이 저장되었습니다! 순이익: {int(daily_profit):,}원")
                    except Exception as e:
                        st.error(f"일일 정산 저장 중 오류가 발생했습니다: {e}")

        with st.expander("판매 현황"):
            try:
                response = supabase.table("daily_sales").select("*").order("date", desc=True).execute()
                df = pd.DataFrame(response.data)

                if not df.empty:
                    st.markdown("#### 일일 판매 기록")
                    df_display = df.rename(columns={
                        "date": "날짜",
                        "product_name": "상품명",
                        "daily_revenue": "전체 매출액",
                        "daily_ad_cost": "일일 광고비",
                        "daily_profit": "일일 순이익금",
                        "ad_revenue": "광고 매출액",
                        "organic_revenue": "자연 매출액",
                        "daily_margin_ratio": "순마진율(%)"
                    })
                    # 날짜 형식 조정
                    df_display['날짜'] = pd.to_datetime(df_display['날짜']).dt.strftime('%Y-%m-%d')
                    # 숫자 열 포맷팅 (정수형으로 표시할 열 선택)
                    cols_to_format_int = ["전체 매출액", "일일 광고비", "일일 순이익금", "광고 매출액", "자연 매출액"]
                    for col in cols_to_format_int:
                        if col in df_display.columns:
                            df_display[col] = df_display[col].apply(lambda x: f'{int(x):,}')
                            
                    st.dataframe(df_display, use_container_width=True)

                    st.markdown("---")
                    st.markdown("#### 상품별 총 순이익금")
                    
                    df_grouped = df.groupby("product_name").agg(
                        total_profit=('daily_profit', 'sum')
                    ).reset_index()
                    
                    df_grouped = df_grouped.rename(columns={
                        "product_name": "상품명",
                        "total_profit": "총 순이익금"
                    })
                    
                    df_grouped["총 순이익금"] = df_grouped["총 순이익금"].apply(lambda x: f'{int(x):,}')
                    
                    st.dataframe(df_grouped, use_container_width=True)

                else:
                    st.info("아직 저장된 판매 기록이 없습니다.")
            except Exception as e:
                st.error(f"판매 현황을 불러오는 중 오류가 발생했습니다: {e}")

# 메인 함수 호출
if __name__ == "__main__":
    main()
