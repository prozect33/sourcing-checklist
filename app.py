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
if "total_sales_qty" not in st.session_state:
    st.session_state.total_sales_qty = 0
if "ad_sales_qty" not in st.session_state:
    st.session_state.ad_sales_qty = 0
if "total_revenue" not in st.session_state:
    st.session_state.total_revenue = 0
if "ad_revenue" not in st.session_state:
    st.session_state.ad_revenue = 0

def load_product_data(selected_product_name):
    if selected_product_name == "새로운 상품 입력":
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
        if not st.session_state.get(key):
            st.warning(f"**{name}** 필드를 채워주세요") 
            return False
            
    return True

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
                    C_total_fixed_cost = fee + inout_cost + packaging_cost + gift_cost
                    
                    # 목표 마진 50%를 달성하기 위한 최대 원가 (Raw Cost)
                    raw_cost2 = supply_price - (supply_price * (target_margin / 100))
                    target_cost = max(0, int(raw_cost2) - int(C_total_fixed_cost/vat)) 
                    
                    yuan_cost = round((target_cost / config['EXCHANGE_RATE']) / vat, 2)
                    
                    # 판매가에서 모든 비용을 제외한 순이익 (광고, 기타 제외)
                    profit = sell_price_val - (
                        target_cost + fee + inout_cost + packaging_cost + gift_cost
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
                    st.stop()
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
                
                # 마진 계산: 광고비, 기타비용, 반품비 등을 제외한 기본 마진
                margin_profit = sell_price - (unit_cost + fee + inout + packaging + gift)
                margin_ratio = round((margin_profit / supply_price2) * 100, 2)
                
                roi = round((profit2 / unit_cost) * 100, 2) if unit_cost else 0
                roi_margin = round((margin_profit / unit_cost) * 100, 2) if unit_cost else 0
                roas = round((sell_price / (ad)) * 100, 2) if ad else 0 # ROAS 계산 수정 (광고비만으로)

                # 결과 출력
                col_title, col_button = st.columns([4,1])
                with col_title:
                    st.markdown("### 📊 계산 결과")
                with col_button:
                    # '간단 마진 계산기'의 계산 결과를 저장하는 로직은 복잡하여 일단 버튼만 둡니다.
                    st.button("저장하기", key="save_button_tab1", disabled=True, help="세부 마진 계산기 탭에서 상품 정보를 저장해주세요.")
                
                if cost_display:
                    st.markdown(f"- 🏷️ 원가: **{format_number(unit_cost)}원** ({cost_display})" if unit_cost > 0 else f"- 🏷️ 원가: **{format_number(unit_cost)}원**")
                else:
                    st.markdown(f"- 🏷️ 원가: **{format_number(unit_cost)}원**")
                st.markdown(f"- 💰 마진 (광고/기타 제외): **{format_number(margin_profit)}원** / ROI: {roi_margin:.2f}%")
                st.markdown(f"- 📈 마진율 (공급가 기준): **{margin_ratio:.2f}%**")
                st.markdown(f"- 🧾 최소 이익 (모든 비용 포함): **{format_number(profit2)}원** / ROI: {roi:.2f}%")
                st.markdown(f"- 📉 최소마진율: **{(profit2/supply_price2*100):.2f}%**")
                st.markdown(f"- 📊 ROAS: **{roas:.2f}%**")
                
                with st.expander("📦 상세 비용 항목 보기", expanded=False):
                    def styled_line(label, value):
                        return f"<div style='font-size:15px;'><strong>{label}</strong> {value}</div>"
                    st.markdown(styled_line("판매가:", f"{format_number(sell_price)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("원가:", f"{format_number(unit_cost)}원 ({cost_display})" if cost_display else f"{format_number(unit_cost)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("수수료:", f"{format_number(fee)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("광고비:", f"{format_number(ad)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("입출고비용:", f"{format_number(inout)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("반품비용:", f"{format_number(return_cost)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("기타비용:", f"{format_number(etc)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("포장비:", f"{format_number(packaging)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("사은품 비용:", f"{format_number(gift)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("총비용:", f"{format_number(total_cost)}원"), unsafe_allow_html=True)
                    st.markdown("---")
                    st.markdown(styled_line("공급가액:", f"{format_number(round(supply_price2))}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("최소 이익:", f"{format_number(profit2)}원"), unsafe_allow_html=True)
                    st.markdown(styled_line("최소마진율:", f"{(profit2/supply_price2*100):.2f}%"), unsafe_allow_html=True)
                    st.markdown(styled_line("투자수익률 (ROI):", f"{roi:.2f}%"), unsafe_allow_html=True)


    with tab2:
        st.subheader("세부 마진 계산기")

        # tab2 전용 초기화 함수 (main() 내부에 정의)
        def reset_tab2_inputs():
            keys_to_reset = [
                "product_name_input", "sell_price_input", "fee_rate_input",
                "inout_shipping_cost_input", "purchase_cost_input", "quantity_input",
                "logistics_cost_input", "customs_duty_input", "etc_cost_input",
                "product_loader"
            ]
            for key in keys_to_reset:
                if key in st.session_state:
                    st.session_state[key] = ""
            st.session_state.is_edit_mode = False

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
                on_change=lambda: load_product_data(st.session_state.product_loader)
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
                                reset_tab2_inputs()
                                st.success("상품 정보가 수정되었습니다. 새로운 상품 입력 상태로 돌아갑니다.")
                            except Exception as e:
                                st.error(f"데이터 수정 중 오류: {e}")
                with col_del:
                    if st.button("삭제하기"):
                        try:
                            supabase.table("products").delete().eq("product_name", st.session_state.product_name_input).execute()
                            reset_tab2_inputs()
                            st.success("상품이 삭제되었습니다. 새로운 상품 입력 상태로 돌아갑니다.")
                        except Exception as e:
                            st.error(f"데이터 삭제 중 오류: {e}")
            else:
                if st.button("상품 저장하기"):
                    if validate_inputs():
                        product_name_to_save = st.session_state.product_name_input
                        
                        if sell_price == 0:
                            st.warning("판매가는 0이 아닌 값으로 입력해야 합니다.")
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
                                    reset_tab2_inputs()
                                    st.success("상품이 저장되었습니다. 새로운 상품 입력 상태로 돌아갑니다.")
                            except Exception as e:
                                st.error(f"데이터 저장 중 오류: {e}")
        
        # ----------------------------------------------
        # **추가된 세부 마진 계산 결과 표시 로직**
        # ----------------------------------------------
        if sell_price > 0 and (purchase_cost > 0 or unit_purchase_cost > 0):
            st.markdown("---")
            st.subheader("마진 계산 결과 (단위: 1개)")

            # 계산에 사용할 1개당 비용
            unit_inout_cost = inout_shipping_cost / quantity_for_calc
            unit_logistics_cost = logistics_cost / quantity_for_calc
            unit_customs_duty = customs_duty / quantity_for_calc
            unit_etc_cost = etc_cost / quantity_for_calc
            
            # 1. 원가 계산 (매입 + 부대 비용)
            unit_cost_raw = unit_purchase_cost + unit_logistics_cost + unit_customs_duty
            
            # 2. 총 판매 비용 (수수료, 배송비, 기타 비용 포함)
            vat_rate = 1.1
            fee_amount = (sell_price * fee_rate / 100) # VAT 여부는 로직에 따라 다름. 여기서는 판매가 기준 단순 계산.
            
            # 총 단위 비용 = 원가(매입+부대) + 판매비용(수수료+입출고/배송+기타)
            total_unit_cost = unit_cost_raw + fee_amount + unit_inout_cost + unit_etc_cost
            
            # 3. 마진 계산
            profit_margin_amount = sell_price - total_unit_cost
            
            # 4. 마진율 계산 (공급가액 기준)
            supply_price_unit = sell_price / vat_rate
            margin_ratio = (profit_margin_amount / supply_price_unit) * 100 if supply_price_unit else 0
            
            # 5. 투자수익률 (ROI)
            roi_ratio = (profit_margin_amount / unit_purchase_cost) * 100 if unit_purchase_cost else 0

            col_res1, col_res2, col_res3 = st.columns(3)
            
            col_res1.metric("단위 판매가 (VAT 포함)", f"{sell_price:,.0f}원")
            col_res1.metric("총 비용 (1개당)", f"{total_unit_cost:,.0f}원")
            
            col_res2.metric("순이익금 (1개당)", f"{profit_margin_amount:,.0f}원", 
                            delta=f"{margin_ratio:,.2f}% (공급가 마진율)", delta_color="normal")
            
            col_res3.metric("매입단가", f"{unit_purchase_cost:,.0f}원")
            col_res3.metric("투자수익률 (ROI)", f"{roi_ratio:,.2f}%")
            
            with st.expander("세부 비용 Breakdown"):
                st.markdown(f"**- 원가 (매입단가 + 부대비용):** {unit_cost_raw:,.0f}원")
                st.markdown(f"**- 판매 수수료 ({fee_rate:.2f}%):** {fee_amount:,.0f}원")
                st.markdown(f"**- 입출고/배송비:** {unit_inout_cost:,.0f}원")
                st.markdown(f"**- 물류비:** {unit_logistics_cost:,.0f}원")
                st.markdown(f"**- 관세:** {unit_customs_duty:,.0f}원")
                st.markdown(f"**- 기타:** {unit_etc_cost:,.0f}원")
                st.markdown(f"**- 총 이익:** {profit_margin_amount:,.0f}원")


        else:
            st.info("판매가와 매입비(또는 수량)을 입력하면 마진 결과가 표시됩니다.")
        # ----------------------------------------------
        
        with st.expander("일일 정산"):
            product_list = ["상품을 선택해주세요"]
            try:
                response = supabase.table("products").select("product_name").order("product_name").execute()
                if response.data:
                    saved_products = [item['product_name'] for item in response.data]
                    product_list.extend(saved_products)
            except Exception as e:
                st.error(f"상품 목록을 불러오는 중 오류가 발생했습니다: {e}")

            selected_product_name = st.selectbox("상품 선택", product_list, key="product_select_daily")

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

            organic_sales_qty = st.number_input(
                "자연 판매 수량",
                value=st.session_state.total_sales_qty - st.session_state.ad_sales_qty if st.session_state.total_sales_qty >= st.session_state.ad_sales_qty else 0,
                disabled=True,
                key="organic_sales_qty"
            )

            organic_revenue = st.number_input(
                "자연 판매 매출액",
                value=st.session_state.total_revenue - st.session_state.ad_revenue if st.session_state.total_revenue >= st.session_state.ad_revenue else 0,
                disabled=True,
                key="organic_revenue"
            )

            st.metric(label="일일 순이익금", value="0")

            if st.button("일일 정산 저장하기"):
                st.warning("계산 로직이 비활성화되어 있습니다. 순이익 계산 로직을 추가한 후 저장할 수 있습니다.")

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
                    st.dataframe(df_grouped, use_container_width=True)

                else:
                    st.info("아직 저장된 판매 기록이 없습니다.")
            except Exception as e:
                st.error(f"판매 현황을 불러오는 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
