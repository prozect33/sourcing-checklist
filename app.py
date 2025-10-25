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

# 사이드바 설정
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
if "product_name_input" not in st.session_state:
    st.session_state.product_name_input = ""
if "sell_price_input" not in st.session_state:
    st.session_state.sell_price_input = ""
if "fee_rate_input" not in st.session_state:
    st.session_state.fee_rate_input = ""
if "inout_shipping_cost_input" not in st.session_state:
    st.session_state.inout_shipping_cost_input = ""
if "purchase_cost_input" not in st.session_state:
    st.session_state.purchase_cost_input = ""
if "quantity_input" not in st.session_state:
    st.session_state.quantity_input = ""
if "logistics_cost_input" not in st.session_state:
    st.session_state.logistics_cost_input = ""
if "customs_duty_input" not in st.session_state:
    st.session_state.customs_duty_input = ""
if "etc_cost_input" not in st.session_state:
    st.session_state.etc_cost_input = ""
if "is_edit_mode" not in st.session_state:
    st.session_state.is_edit_mode = False
if "product_loader_index" not in st.session_state:
    st.session_state.product_loader_index = 0 # '새로운 상품 입력'이 첫 번째 항목이므로 0으로 초기화
if "feedback_message" not in st.session_state:
    st.session_state.feedback_message = ""
if "feedback_type" not in st.session_state:
    st.session_state.feedback_type = ""

def reset_product_inputs():
    """상품 정보 입력 필드를 초기화하고 '새로운 상품 입력' 모드로 전환합니다."""
    st.session_state.is_edit_mode = False
    st.session_state.product_name_input = ""
    st.session_state.sell_price_input = ""
    st.session_state.fee_rate_input = ""
    st.session_state.inout_shipping_cost_input = ""
    st.session_state.purchase_cost_input = ""
    st.session_state.quantity_input = ""
    st.session_state.logistics_cost_input = ""
    st.session_state.customs_duty_input = ""
    st.session_state.etc_cost_input = ""
    st.session_state.product_loader_index = 0 # selectbox를 '새로운 상품 입력'으로 설정

def load_product_data(selected_product_name):
    if selected_product_name == "새로운 상품 입력":
        # 이미 reset_product_inputs와 동일한 로직이 포함되어 있지만, selectbox 변경 시 호출되므로 다시 작성
        st.session_state.is_edit_mode = False
        st.session_state.product_name_input = ""
        st.session_state.sell_price_input = ""
        st.session_state.fee_rate_input = ""
        st.session_state.inout_shipping_cost_input = ""
        st.session_state.purchase_cost_input = ""
        st.session_state.quantity_input = ""
        st.session_state.logistics_cost_input = ""
        st.session_state.customs_duty_input = ""
        st.session_state.etc_cost_input = ""
    else:
        try:
            response = supabase.table("products").select("*").eq("product_name", selected_product_name).execute()
            if response.data:
                product_data = response.data[0]
                st.session_state.is_edit_mode = True
                
                st.session_state.product_name_input = product_data.get("product_name", "")
                
                def get_display_value(key, default=""):
                    val = product_data.get(key)
                    if val is None or val == 0:
                        return ""
                    if key == "fee":
                        return str(float(val))
                    return str(int(val)) if isinstance(val, (int, float)) and val == int(val) else str(val)

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
    
    for key, name in required_fields.items():
        if not st.session_state.get(key) or safe_float(st.session_state.get(key)) == 0 and key in ["sell_price_input", "fee_rate_input", "quantity_input"]:
            st.warning(f"**{name}** 필드를 채워주세요 (0이 아닌 값 필요)") 
            return False
            
    return True

def main():
    if 'show_product_info' not in st.session_state:
        st.session_state.show_product_info = False
        
    # 피드백 메시지 표시
    if st.session_state.feedback_message:
        if st.session_state.feedback_type == "success":
            st.success(st.session_state.feedback_message)
        elif st.session_state.feedback_type == "warning":
            st.warning(st.session_state.feedback_message)
        st.session_state.feedback_message = "" # 메시지를 표시한 후 초기화
        st.session_state.feedback_type = ""


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
                    C_total_fixed_cost = fee + inout_cost + packaging_cost + gift_cost
                    raw_cost2 = sell_price_val \
                                - supply_price * (target_margin / 100) \
                                - C_total_fixed_cost
                    target_cost = max(0, int(raw_cost2))
                    yuan_cost = round((target_cost / config['EXCHANGE_RATE']) / vat, 2)
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
            qty_raw = st.text_input("수량", key="qty_raw", value=st.session_state.get("qty_raw", ""))
            
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
                    # st.stop() # 계산이 오류나도 앱이 멈추지 않도록 st.stop() 제거
                else:
                    if unit_won.strip() != "":
                        unit_cost_val = round(float(unit_won))
                        cost_display = ""
                    elif unit_yuan.strip() != "":
                        unit_cost_val = round(
                            float(unit_yuan)
                            * config['EXCHANGE_RATE']
                        )
                        cost_display = f"{unit_yuan}위안"
                    else:
                        unit_cost_val = 0
                        cost_display = ""
                    
                    # 상세 계산
                    vat = 1.1
                    unit_cost = round(unit_cost_val * qty)
                    fee = round((sell_price * config["FEE_RATE"] / 100) * vat)
                    ad = round((sell_price * config["AD_RATE"] / 100) * vat)
                    inout = round(config["INOUT_COST"] * vat)
                    pickup = round(config["PICKUP_COST"])
                    restock = round(config["RESTOCK_COST"])
                    return_cost = round((pickup + restock) * (config["RETURN_RATE"] / 100) * vat)
                    etc = round((sell_price * config["ETC_RATE"] / 100))
                    packaging = round(config["PACKAGING_COST"] * vat)
                    gift = round(config["GIFT_COST"] * vat)
                    total_cost = unit_cost + fee + ad + inout + return_cost + etc + packaging + gift
                    profit2 = sell_price - total_cost
                    supply_price2 = sell_price / vat
                    margin_profit = sell_price - (unit_cost + fee + inout + packaging + gift)
                    margin_ratio = round((margin_profit / supply_price2) * 100, 2)
                    roi = round((profit2 / unit_cost) * 100, 2) if unit_cost else 0
                    roi_margin = round((margin_profit / unit_cost) * 100, 2) if unit_cost else 0
                    roas = round((sell_price / (profit2 + ad)) * 100, 2) if (profit2 + ad) else 0 # 0으로 나누기 방지
                    roas = round((sell_price / ad) * 100, 2) if ad else float('inf') # ROAS는 보통 매출/광고비 이므로 수정

                    # 결과 출력
                    col_title, col_button = st.columns([4,1])
                    with col_title:
                        st.markdown("### 📊 계산 결과")
                    with col_button:
                        # 저장하기 버튼 (기능 추가하지 않음, 원본 코드 유지)
                        st.button("저장하기", key="save_button_tab1") 
                    
                    if cost_display:
                        st.markdown(f"- 🏷️ 원가: {format_number(unit_cost)}원 ({cost_display})" if unit_cost > 0 else f"- 🏷️ 원가: {format_number(unit_cost)}원")
                    else:
                        st.markdown(f"- 🏷️ 원가: {format_number(unit_cost)}원")
                    st.markdown(f"- 💰 마진: {format_number(margin_profit)}원 / ROI: {roi_margin:.2f}%")
                    st.markdown(f"- 📈 마진율: {margin_ratio:.2f}%")
                    st.markdown(f"- 🧾 최소 이익: {format_number(profit2)}원 / ROI: {roi:.2f}%")
                    st.markdown(f"- 📉 최소마진율: {(profit2/supply_price2*100):.2f}%")
                    st.markdown(f"- 📊 ROAS: {roas:.2f}%")
                    
                    with st.expander("📦 상세 비용 항목 보기", expanded=False):
                        def styled_line(label, value):
                            return f"<div style='font-size:15px;'><strong>{label}</strong> {value}</div>"
                        st.markdown(styled_line("판매가:", f"{format_number(sell_price)}원"), unsafe_allow_html=True)
                        st.markdown(styled_line("원가:", f"{format_number(unit_cost)}원 ({cost_display})" if cost_display else f"{format_number(unit_cost)}원"), unsafe_allow_html=True)
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
                
            # product_loader_index를 사용하여 selectbox의 현재 선택 상태를 유지/제어
            selected_product_name = st.selectbox(
                "저장된 상품 선택 또는 새로 입력",
                product_list,
                index=st.session_state.product_loader_index, # 인덱스 제어
                key="product_loader",
                on_change=lambda: [load_product_data(st.session_state.product_loader), st.session_state.__setitem__('product_loader_index', product_list.index(st.session_state.product_loader))]
                # on_change에 selectbox의 현재 인덱스도 함께 업데이트
            )

            product_name = st.text_input(
                "상품명",
                value=st.session_state.product_name_input, 
                key="product_name_input",
                placeholder="예: 무선 이어폰"
            )

            col_left, col_right = st.columns(2)
            with col_left:
                st.text_input("판매가", key="sell_price_input")
            with col_right:
                st.text_input("수수료율 (%)", key="fee_rate_input") 
            with col_left:
                st.text_input("입출고/배송비", key="inout_shipping_cost_input")
            with col_right:
                st.text_input("매입비", key="purchase_cost_input")
            with col_left:
                st.text_input("수량", key="quantity_input")

            sell_price = safe_int(st.session_state.sell_price_input)
            fee_rate = safe_float(st.session_state.fee_rate_input)
            inout_shipping_cost = safe_int(st.session_state.inout_shipping_cost_input)
            purchase_cost = safe_int(st.session_state.purchase_cost_input)
            quantity = safe_int(st.session_state.quantity_input)
            
            quantity_for_calc = quantity if quantity > 0 else 1 
            
            with col_right:
                try:
                    unit_purchase_cost = purchase_cost / quantity_for_calc
                except (ZeroDivisionError, TypeError):
                    unit_purchase_cost = 0
                st.text_input("매입단가", value=f"{unit_purchase_cost:,.0f}원", disabled=True)
            with col_left:
                st.text_input("물류비", key="logistics_cost_input")
            with col_right:
                st.text_input("관세", key="customs_duty_input")

            st.text_input("기타", key="etc_cost_input")

            logistics_cost = safe_int(st.session_state.logistics_cost_input)
            customs_duty = safe_int(st.session_state.customs_duty_input)
            etc_cost = safe_int(st.session_state.etc_cost_input)
            
            quantity_to_save = quantity

            # 콜백 함수 정의: 성공 시 메시지 설정 및 입력 초기화
            def update_and_reset(message, type_):
                st.session_state.feedback_message = message
                st.session_state.feedback_type = type_
                reset_product_inputs()
                
            if st.session_state.is_edit_mode:
                col_mod, col_del = st.columns(2)
                with col_mod:
                    if st.button("수정하기"):
                        if validate_inputs():
                            try:
                                data_to_update = {
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
                                supabase.table("products").update(data_to_update).eq("product_name", st.session_state.product_name_input).execute()
                                # 성공 시 리셋 및 메시지 설정
                                update_and_reset(f"'{st.session_state.product_name_input}' 상품 정보가 **성공적으로 수정**되었습니다. ✅", "success")
                            except Exception as e:
                                st.error(f"데이터 수정 중 오류가 발생했습니다: {e}")
            with col_del:
                if st.button("삭제하기"):
                    try:
                        product_name_to_delete = st.session_state.product_name_input
                        supabase.table("products").delete().eq("product_name", product_name_to_delete).execute()
                        # 성공 시 리셋 및 메시지 설정
                        update_and_reset(f"'{product_name_to_delete}' 상품이 **성공적으로 삭제**되었습니다. 🗑️", "success")
                    except Exception as e:
                        st.error(f"데이터 삭제 중 오류가 발생했습니다: {e}")
            else:
                if st.button("상품 저장하기"):
                    if validate_inputs():
                        product_name_to_save = st.session_state.product_name_input
                        
                        if sell_price == 0 or fee_rate == 0 or quantity == 0:
                            # validate_inputs에서 처리되므로, 여기서는 중복 경고 방지
                            pass
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
                                response = supabase.table("products").select("product_name").eq("product_name", product_name_to_save).execute()
                                if response.data:
                                    st.warning("이미 같은 이름의 상품이 존재합니다. 수정하려면 목록에서 선택해주세요.")
                                else:
                                    supabase.table("products").insert(data_to_save).execute()
                                    # 성공 시 리셋 및 메시지 설정
                                    update_and_reset(f"'{product_name_to_save}' 상품이 **성공적으로 저장**되었습니다. 💾", "success")
                            except Exception as e:
                                st.error(f"데이터 저장 중 오류가 발생했습니다: {e}")

        with st.expander("일일 정산"):
            # 상품 목록을 다시 로드하여 selectbox에 반영 (저장/수정/삭제 후)
            product_list_daily = ["상품을 선택해주세요"]
            try:
                response = supabase.table("products").select("product_name").order("product_name").execute()
                if response.data:
                    saved_products = [item['product_name'] for item in response.data]
                    product_list_daily.extend(saved_products)
            except Exception as e:
                st.error(f"상품 목록을 불러오는 중 오류가 발생했습니다: {e}")

            selected_product_name = st.selectbox("상품 선택", product_list_daily, key="product_select_daily")

            product_data = {}
            if selected_product_name and selected_product_name != "상품을 선택해주세요":
                try:
                    response = supabase.table("products").select("*").eq("product_name", selected_product_name).execute()
                    if response.data:
                        product_data = response.data[0]
                except Exception as e:
                    st.error(f"상품 정보를 불러오는 중 오류가 발생했습니다: {e}")

            with st.expander("상품 상세 정보"):
                if selected_product_name == "상품을 선택해주세요":
                    st.info("먼저 상품을 선택해주세요.")
                elif product_data:
                    display_qty = product_data.get('quantity')
                    if display_qty is None:
                        display_qty = 0
                    
                    st.markdown(f"**판매가:** {product_data.get('sell_price', 0):,}원")
                    st.markdown(f"**수수료율:** {product_data.get('fee', 0.0):.2f}%")
                    st.markdown(f"**매입비:** {product_data.get('purchase_cost', 0):,}원")
                    st.markdown(f"**수량:** {display_qty:,}개")
                    st.markdown(f"**매입단가:** {product_data.get('unit_purchase_cost', 0):,.0f}원")
                    st.markdown(f"**입출고/배송비:** {product_data.get('inout_shipping_cost', 0):,}원")
                    st.markdown(f"**물류비:** {product_data.get('logistics_cost', 0):,}원")
                    st.markdown(f"**관세:** {product_data.get('customs_duty', 0):,}원")
                    st.markdown(f"**기타:** {product_data.get('etc_cost', 0):,}원")
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

            # 수량과 매출액의 계산이 이전 필드에 의존하므로, number_input의 value를 session_state를 이용해 계산
            organic_sales_qty_calc = st.session_state.total_sales_qty - st.session_state.ad_sales_qty if st.session_state.total_sales_qty >= st.session_state.ad_sales_qty else 0
            organic_revenue_calc = st.session_state.total_revenue - st.session_state.ad_revenue if st.session_state.total_revenue >= st.session_state.ad_revenue else 0
            
            organic_sales_qty = st.number_input(
                "자연 판매 수량",
                value=organic_sales_qty_calc,
                disabled=True,
                key="organic_sales_qty"
            )

            organic_revenue = st.number_input(
                "자연 판매 매출액",
                value=organic_revenue_calc,
                disabled=True,
                key="organic_revenue"
            )
            
            # 일일 순이익금 계산 로직 (임시: 실제 로직은 상품 데이터 기반으로 복잡하게 구현해야 함)
            daily_profit = 0
            if total_revenue > 0 and product_data:
                # 간단 마진 계산기에서 사용된 비용 요소를 기반으로 일일 전체 비용 추정
                vat = 1.1
                fee_rate = product_data.get('fee', config["FEE_RATE"])
                inout_cost_unit = product_data.get('inout_shipping_cost', config["INOUT_COST"])
                unit_purchase_cost = product_data.get('unit_purchase_cost', 0)
                
                total_purchase_cost = unit_purchase_cost * total_sales_qty
                total_fee = round((total_revenue * fee_rate / 100) * vat)
                total_inout = round(inout_cost_unit * total_sales_qty * vat)
                
                # 기타 고정 비용 (간단 계산기의 설정값 사용)
                packaging = round(config["PACKAGING_COST"] * total_sales_qty * vat)
                gift = round(config["GIFT_COST"] * total_sales_qty * vat)
                etc = round((total_revenue * config["ETC_RATE"] / 100))
                return_cost = round((config['PICKUP_COST'] + config['RESTOCK_COST']) * (config['RETURN_RATE'] / 100) * total_sales_qty * vat)
                
                total_cost_daily = total_purchase_cost + total_fee + total_inout + packaging + gift + etc + ad_cost + return_cost
                daily_profit = total_revenue - total_cost_daily

            st.metric(label="일일 순이익금", value=f"{format_number(daily_profit)}원")

            if st.button("일일 정산 저장하기"):
                if selected_product_name == "상품을 선택해주세요" or total_sales_qty == 0:
                    st.warning("상품을 선택하고 판매 수량을 0보다 크게 입력해야 합니다.")
                else:
                    try:
                        data_to_save = {
                            "date": report_date.isoformat(),
                            "product_name": selected_product_name,
                            "total_sales_qty": total_sales_qty,
                            "daily_revenue": total_revenue,
                            "ad_sales_qty": ad_sales_qty,
                            "ad_revenue": ad_revenue,
                            "daily_ad_cost": ad_cost,
                            "organic_sales_qty": organic_sales_qty,
                            "organic_revenue": organic_revenue,
                            "daily_profit": int(daily_profit) # 계산된 순이익금 저장
                        }
                        supabase.table("daily_sales").insert(data_to_save).execute()
                        st.success(f"{report_date} 날짜의 '{selected_product_name}' 일일 정산이 저장되었습니다! 🎉")
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
                        "organic_revenue": "자연 매출액"
                    })
                    # 금액 열을 정수형으로 변환 후 포맷팅 (display용)
                    cols_to_format = ["전체 매출액", "일일 광고비", "일일 순이익금", "광고 매출액", "자연 매출액"]
                    for col in cols_to_format:
                        if col in df_display.columns:
                            # NaN 값 처리 후 정수형으로 변환
                            df_display[col] = df_display[col].fillna(0).astype(int)
                            df_display[col] = df_display[col].apply(format_number)

                    st.dataframe(df_display, use_container_width=True)

                    st.markdown("---")
                    st.markdown("#### 상품별 총 순이익금")

                    # daily_profit이 이미 정수형 또는 float이므로 바로 집계
                    df_grouped = df.groupby("product_name").agg(
                        total_profit=('daily_profit', 'sum')
                    ).reset_index()

                    df_grouped = df_grouped.rename(columns={
                        "product_name": "상품명",
                        "total_profit": "총 순이익금"
                    })
                    df_grouped["총 순이익금"] = df_grouped["총 순이익금"].fillna(0).astype(int).apply(format_number)
                    st.dataframe(df_grouped, use_container_width=True)

                else:
                    st.info("아직 저장된 판매 기록이 없습니다.")
            except Exception as e:
                st.error(f"판매 현황을 불러오는 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
