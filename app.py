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
    # 탭1 리셋
    st.session_state["sell_price_raw"] = ""
    st.session_state["unit_yuan"] = ""
    st.session_state["unit_won"] = ""
    st.session_state["qty_raw"] = ""
    st.session_state["show_result"] = False
    
    # 탭2 일일 정산 리셋
    if "total_sales_qty" in st.session_state: st.session_state["total_sales_qty"] = 0
    if "total_revenue" in st.session_state: st.session_state["total_revenue"] = 0
    if "ad_sales_qty" in st.session_state: st.session_state["ad_sales_qty"] = 0
    if "ad_revenue" in st.session_state: st.session_state["ad_revenue"] = 0
    if "ad_cost" in st.session_state: st.session_state["ad_cost"] = 0
    if "product_select_daily" in st.session_state:
        st.session_state["product_select_daily"] = "상품을 선택해주세요"


def load_supabase_credentials():
    try:
        with open("credentials.json", "r") as f:
            creds = json.load(f)
            return creds["SUPABASE_URL"], creds["SUPABASE_KEY"]
    except FileNotFoundError:
        st.error("오류: 'credentials.json' 파일을 찾을 수 없습니다.\n파일을 생성하고 Supabase 키를 입력해주세요.")
        st.stop()
    except json.JSONDecodeError:
        st.error("오류: 'credentials.json' 파일의 형식이 잘못되었습니다. JSON 형식을 확인해주세요.")
        st.stop()
    except KeyError:
        st.error("오류: 'credentials.json' 파일에 'SUPABASE_URL' 또는 'SUPABASE_KEY'가 없습니다.")
        st.stop()

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

try:
    SUPABASE_URL, SUPABASE_KEY = load_supabase_credentials()
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Supabase 클라이언트 초기화 중 오류가 발생했습니다: {e}")
    st.stop()

# 상품 정보 입력 상태 초기화 (탭2)
if "product_name_input" not in st.session_state: st.session_state.product_name_input = ""
if "sell_price_input" not in st.session_state: st.session_state.sell_price_input = ""
if "fee_rate_input" not in st.session_state: st.session_state.fee_rate_input = ""
if "inout_shipping_cost_input" not in st.session_state: st.session_state.inout_shipping_cost_input = ""
if "purchase_cost_input" not in st.session_state: st.session_state.purchase_cost_input = ""
if "quantity_input" not in st.session_state: st.session_state.quantity_input = ""
if "logistics_cost_input" not in st.session_state: st.session_state.logistics_cost_input = ""
if "customs_duty_input" not in st.session_state: st.session_state.customs_duty_input = ""
if "etc_cost_input" not in st.session_state: st.session_state.etc_cost_input = ""
if "is_edit_mode" not in st.session_state: st.session_state.is_edit_mode = False

# 일일 정산 입력 상태 초기화 (탭 2 number_input의 key를 사용)
if "total_sales_qty" not in st.session_state: st.session_state["total_sales_qty"] = 0
if "total_revenue" not in st.session_state: st.session_state["total_revenue"] = 0
if "ad_sales_qty" not in st.session_state: st.session_state["ad_sales_qty"] = 0
if "ad_revenue" not in st.session_state: st.session_state["ad_revenue"] = 0
if "ad_cost" not in st.session_state: st.session_state["ad_cost"] = 0


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

            # 탭 1 마진 계산 로직
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
                st.text_input("위안화 (¥)", key="unit_yuan")
            with col2:
                st.text_input("원화 (₩)", key="unit_won")
            st.text_input("수량", key="qty_raw", value=st.session_state.get("qty_raw", ""))

            calc_col, reset_col = st.columns(2)
            if calc_col.button("계산하기"):
                st.session_state["show_result"] = True
            if "show_result" not in st.session_state:
                st.session_state["show_result"] = False
            reset_col.button("리셋", on_click=reset_inputs)

        with right:
            # 탭 1 결과 출력 로직
            if st.session_state["show_result"]:
                try:
                    sell_price = int(float(st.session_state.get("sell_price_raw", 0)))
                    qty = int(float(st.session_state.get("qty_raw", 1))) if st.session_state.get("qty_raw") else 1
                except:
                    st.warning("판매가와 수량을 정확히 입력해주세요.")
                    return
                
                # 원가 계산
                unit_won_val = st.session_state.get("unit_won")
                unit_yuan_val = st.session_state.get("unit_yuan")

                if unit_won_val and unit_won_val.strip() != "":
                    unit_cost_val = round(float(unit_won_val))
                    cost_display = ""
                elif unit_yuan_val and unit_yuan_val.strip() != "":
                    unit_cost_val = round(float(unit_yuan_val) * config['EXCHANGE_RATE'])
                    cost_display = f"{unit_yuan_val}위안"
                else:
                    unit_cost_val = 0
                
                
                cost_display = ""
                
                # 비용 계산
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
                roas = round((sell_price / ad) * 100, 2) if ad else 0

                col_title, col_button = st.columns([4,1])
                with col_title:
                    st.markdown("### 📊 계산 결과")
                with col_button:
                    st.button("저장하기", key="save_button_tab1", disabled=True) 

                if cost_display:
                    st.markdown(f"- 🏷️ **원가:** {format_number(unit_cost)}원 ({cost_display})" if unit_cost > 0 else f"- 🏷️ **원가:** {format_number(unit_cost)}원")
                else:
                    st.markdown(f"- 🏷️ **원가:** {format_number(unit_cost)}원")
                st.markdown(f"- 💰 **마진:** {format_number(margin_profit)}원 / ROI: {roi_margin:.2f}%")
                st.markdown(f"- 📈 **마진율:** {margin_ratio:.2f}%")
                st.markdown(f"- 🧾 **최소 이익:** {format_number(profit2)}원 / ROI: {roi:.2f}%")
                st.markdown(f"- 📉 **최소마진율:** {(profit2/supply_price2*100):.2f}%")
                st.markdown(f"- 📊 **ROAS:** {roas:.2f}%")

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
            # 상품 목록 로드
            product_list = ["새로운 상품 입력"]
            try:
                response = supabase.table("products").select("product_name").order("product_name").execute()
                if response.data:
                    saved_products = [item['product_name'] for item in response.data]
                    product_list.extend(saved_products)
            except Exception as e:
                st.error(f"상품 목록을 불러오는 중 오류가 발생했습니다: {e}")

            st.selectbox(
                "저장된 상품 선택 또는 새로 입력",
                product_list,
                key="product_loader",
                on_change=lambda: load_product_data(st.session_state.product_loader)
            )

            st.text_input(
                "상품명",
                value=st.session_state.product_name_input,
                key="product_name_input",
                placeholder="예: 무선 이어폰"
            )

            # 상품 세부 정보 입력
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
           
            # 저장/수정/삭제 버튼 로직
            if st.session_state.is_edit_mode:
                col_mod, col_del = st.columns(2)

                with col_mod:
                    if st.button("수정하기"):
                        if validate_inputs():
                            try:
                                old_name = st.session_state.product_loader  # 기존 상품명
                                new_name = st.session_state.product_name_input  # 새 상품명

                                # 업데이트할 필드 구성
                                data_to_update = {
                                    "product_name": new_name,
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

                                # 1) products 테이블 업데이트 (상품명 포함)
                                supabase.table("products").update(data_to_update).eq("product_name", old_name).execute()

                                # 2) daily_sales 테이블의 상품명 동기화
                                supabase.table("daily_sales").update({"product_name": new_name}).eq("product_name", old_name).execute()

                                # 3) 세션 상태 갱신 (셀렉트박스 선택값 동기화)
                                st.session_state.product_loader = new_name

                                st.success(f"'{old_name}' → '{new_name}' 상품명이 포함된 모든 데이터가 수정되었습니다!")

                            except Exception as e:
                                st.error(f"상품명 수정 중 오류가 발생했습니다: {e}")

                with col_del:
                    if st.button("삭제하기"):
                        try:
                            supabase.table("products").delete().eq("product_name", st.session_state.product_name_input).execute()
                            st.success(f"'{st.session_state.product_name_input}' 상품이 삭제되었습니다!")
                        except Exception as e:
                            st.error(f"데이터 삭제 중 오류가 발생했습니다: {e}")

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
                                st.success(f"'{product_name_to_save}' 상품이 성공적으로 저장되었습니다!")
                            except Exception as e:
                                st.error(f"데이터 저장 중 오류가 발생했습니다: {e}")


        with st.expander("일일 정산"):
            # 상품 선택 로직
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
                    display_qty = product_data.get('quantity') or 0
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
            # 입력 필드: key를 통해 st.session_state에 값을 저장
            st.number_input("전체 판매 수량", step=1, key="total_sales_qty")
            st.number_input("전체 매출액", step=1000, key="total_revenue")

            st.markdown("---")
            st.markdown("#### 광고 판매")
            # 입력 필드: key를 통해 st.session_state에 값을 저장
            st.number_input("광고 전환 판매 수량", step=1, key="ad_sales_qty")
            st.number_input("광고 전환 매출액", step=1000, key="ad_revenue")
            st.number_input("광고비", step=1000, key="ad_cost")

            st.markdown("---")
            st.markdown("#### 자연 판매 (자동 계산)")

            # 계산 로직: 입력 필드의 현재 세션 상태 값을 사용하여 계산
            organic_sales_qty_calc = max(st.session_state.total_sales_qty - st.session_state.ad_sales_qty, 0)
            organic_revenue_calc = max(st.session_state.total_revenue - st.session_state.ad_revenue, 0)
            
            # 출력 필드: 계산된 값을 value로 설정하고 disabled=True
            st.number_input(
                "자연 판매 수량",
                value=organic_sales_qty_calc,
                disabled=True
            )
            st.number_input(
                "자연 판매 매출액",
                value=organic_revenue_calc,
                disabled=True
            )

            # 일일 순이익 계산
            daily_profit = 0
            if selected_product_name != "상품을 선택해주세요" and product_data:
                # 안전하게 세션 상태의 최신 입력값 사용
                current_total_sales_qty = st.session_state.total_sales_qty
                current_total_revenue = st.session_state.total_revenue
                current_ad_cost = st.session_state.ad_cost
                
                quantity_val = product_data.get("quantity", 1)
                quantity_for_calc = quantity_val if quantity_val > 0 else 1
                unit_purchase_cost = product_data.get("purchase_cost", 0) / quantity_for_calc
                unit_logistics = product_data.get("logistics_cost", 0) / quantity_for_calc
                unit_customs = product_data.get("customs_duty", 0) / quantity_for_calc
                unit_etc = product_data.get("etc_cost", 0) / quantity_for_calc
                fee_rate_db = product_data.get("fee", 0.0)

                daily_profit = (
                    current_total_revenue
                    - (current_total_revenue * fee_rate_db / 100 * 1.1)
                    - (unit_purchase_cost * current_total_sales_qty)
                    - (product_data.get("inout_shipping_cost", 0) * current_total_sales_qty * 1.1)
                    - (unit_logistics * current_total_sales_qty)
                    - (unit_customs * current_total_sales_qty)
                    - (unit_etc * current_total_sales_qty)
                    - (current_ad_cost * 1.1)
                )
                daily_profit = round(daily_profit)

            st.metric(label="일일 순이익금", value=f"{daily_profit:,}원")
            
            # --- 일일 순이익 계산 내역 (순수 비용 항목만, 세로, 작은 글씨) ---
            if selected_product_name != "상품을 선택해주세요" and product_data:
                # 1. 계산에 필요한 변수 설정 (daily_profit 계산에 사용된 변수 재사용)
                vat = 1.1
                fee_rate_db = product_data.get("fee", 0.0) 
                current_total_sales_qty = st.session_state.total_sales_qty
                current_total_revenue = st.session_state.total_revenue
                current_ad_cost = st.session_state.ad_cost 
                
                # 2. 단위 비용 재계산 (daily_profit 계산 직전에 이미 계산됨, 여기서는 재정의)
                quantity_val = product_data.get("quantity", 1)
                quantity_for_calc = quantity_val if quantity_val > 0 else 1
                unit_purchase_cost = product_data.get("purchase_cost", 0) / quantity_for_calc
                unit_logistics = product_data.get("logistics_cost", 0) / quantity_for_calc
                unit_customs = product_data.get("customs_duty", 0) / quantity_for_calc
                unit_etc = product_data.get("etc_cost", 0) / quantity_for_calc

                # 3. 총 비용 항목 계산 (daily_profit 계산의 개별 비용 항목)
                fee_cost = round(current_total_revenue * fee_rate_db / 100 * vat)
                purchase_cost_total = round(unit_purchase_cost * current_total_sales_qty)
                inout_shipping_cost_total = round(product_data.get("inout_shipping_cost", 0) * current_total_sales_qty * vat)
                logistics_cost_total = round(unit_logistics * current_total_sales_qty)
                customs_cost_total = round(unit_customs * current_total_sales_qty)
                etc_cost_total = round(unit_etc * current_total_sales_qty)
                ad_cost_total = round(current_ad_cost * vat) 

                # 4. HTML과 Markdown을 결합하여 작은 글씨로 상세 출력 (제목 없이 항목만 세로 나열)
                st.markdown(
                    f"""                    
                    <small>
                    - 판매 수수료 (VAT 포함): {fee_cost:,}원 (매출액 기준)<br>
                    - 매입비: {purchase_cost_total:,}원 ({current_total_sales_qty:,}개)<br>
                    - 입출고/배송비 (VAT 포함): {inout_shipping_cost_total:,}원 ({current_total_sales_qty:,}개)<br>
                    - 물류비: {logistics_cost_total:,}원 ({current_total_sales_qty:,}개)<br>
                    - 관세: {customs_cost_total:,}원 ({current_total_sales_qty:,}개)<br>
                    - 기타 비용: {etc_cost_total:,}원 ({current_total_sales_qty:,}개)<br>
                    - 광고비 (VAT 포함): {ad_cost_total:,}원 (입력값 기준)<br>
                    <br>
                    </small>
                    """,
                    unsafe_allow_html=True
                )
                
            # --- 일일 순이익 계산 내역 (순수 비용 항목만, 세로, 작은 글씨) 끝 ---

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
                        # organic_sales_qty_calc, organic_revenue_calc, daily_profit 등의 변수는 
                        # 이 코드가 실행되는 시점에 상위 코드에서 계산되어 있어야 합니다.
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
                        # 수정된 코드 (이전 Supabase 버전과 호환)
                        # on_conflict 대신 upsert를 사용하고 conflict_target 인자를 추가합니다.
                        # 수정된 코드 (가장 오래된 Supabase 버전과 호환 가능성 높음)
                        # Primary Key 또는 Unique Constraint를 자동으로 사용하도록 유도합니다.
                        # 이 코드를 위의 지운 코드 자리에 붙여넣습니다.
                        # --- 최종 UPSERT(덮어쓰기) 적용: 최신 .insert().on_conflict() 문법 ---
                        # --- 최종 UPSERT(덮어쓰기) 적용: 서버 함수(RPC) 호출 ---
                        supabase.rpc(
                            'upsert_daily_sales', 
                            {'p_data': data_to_save} # 데이터를 'p_data'라는 이름으로 함수에 전달
                        ).execute()
                        
                        st.success(f"'{selected_product_name}'의 {report_date} 판매 기록이 **성공적으로 저장/수정**되었습니다!")
                    
                    except Exception as e:
                        st.error(f"데이터 저장 중 오류가 발생했습니다: {e}")
                        st.error(f"일일 정산 저장 중 오류가 발생했습니다: {e}")


        with st.expander("판매 현황"):
            
            # --- 페이지네이션 초기화 및 설정 ---
            def reset_page():
                st.session_state.daily_sales_page = 1
            
            if 'daily_sales_page' not in st.session_state:
                st.session_state.daily_sales_page = 1
            PAGE_SIZE = 10 # 한 페이지에 표시할 일수 (10일치)
            
            # --- 상품 목록 로드 ---
            product_list = ["(상품을 선택해주세요)"]
            try:
                response_prods = supabase.table("products").select("product_name").order("product_name").execute()
                if response_prods.data:
                    product_list.extend([item['product_name'] for item in response_prods.data])
            except Exception as e:
                st.warning("상품 목록을 불러올 수 없습니다. 상품 정보를 먼저 저장해주세요.")


            # --- 상품 필터 셀렉트 박스 ---
            selected_product_filter = st.selectbox(
                "조회할 상품 선택", 
                product_list, 
                key="sales_status_product_filter",
                on_change=reset_page  # 필터 변경 시 페이지 1로 리셋
            )

            # 판매 현황 로직 시작
            try:
                # 1. 데이터 로드 및 선택된 상품으로 필터링
                query = supabase.table("daily_sales").select("*").order("date", desc=True)
                
                # '상품을 선택해주세요'이 아닌 경우에만 쿼리에 필터 조건 추가
                if selected_product_filter != "(상품을 선택해주세요)":
                    query = query.eq("product_name", selected_product_filter)

                response = query.execute() 
                df = pd.DataFrame(response.data)

                if not df.empty:
                    df['date'] = pd.to_datetime(df['date'])
                    
                    # --- 특정 상품 선택 시에만 기록과 총 순이익금 표시 ---
                    if selected_product_filter != "(상품을 선택해주세요)":
                        
                        # [요청 2. 반영: 총 순이익금 섹션을 일일 판매 기록 위에 표시]
                        total_profit_sum = df['daily_profit'].sum()
                        st.metric(label=f"'{selected_product_filter}' 총 순이익금", value=f"{total_profit_sum:,.0f}원") 
                        
                        st.markdown("---") # 순이익금과 기록 섹션 구분

                        st.markdown("#### 일일 판매 기록")
                        
                        # 2. 페이지네이션 적용 로직
                        total_rows = len(df)
                        total_pages = (total_rows + PAGE_SIZE - 1) // PAGE_SIZE 
                        
                        if st.session_state.daily_sales_page > total_pages:
                            st.session_state.daily_sales_page = total_pages
                        if st.session_state.daily_sales_page < 1:
                            st.session_state.daily_sales_page = 1
                            
                        start_index = (st.session_state.daily_sales_page - 1) * PAGE_SIZE
                        end_index = start_index + PAGE_SIZE
                        
                        # 페이지에 맞는 데이터프레임 슬라이싱 (10일치)
                        df_paged = df.iloc[start_index:end_index].copy() 

                        # --- 1부터 시작하는 번호 추가 ---
                        df_display = df_paged.copy()
                        # 1부터 시작하는 번호 컬럼을 맨 앞에 추가
                        df_display.insert(0, '번호', range(start_index + 1, start_index + len(df_display) + 1))
                        
                        # 3. 데이터프레임 표시 (기존 컬럼명 변경 로직 재사용)
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
                        df_display['날짜'] = df_display['날짜'].dt.strftime('%Y-%m-%d')
                        # '번호' 컬럼 추가 (display_cols 재정의)
                        display_cols = ['번호', '날짜', '상품명', '전체 매출액', '전체 수량', '광고 매출액', '자연 매출액', '일일 광고비', '일일 순이익금']
                        
                        # --- 숫자 컬럼 포맷팅 및 문자열 변환 ---
                        # (이 코드는 콤마와 '원'을 추가하여 다른 컬럼의 좌측 정렬 효과를 유지합니다.)
                        format_cols = ['전체 매출액', '전체 수량', '광고 매출액', '자연 매출액', '일일 광고비', '일일 순이익금']

                        for col in format_cols:
                            if '수량' in col:
                                df_display[col] = df_display[col].fillna(0).astype(int).apply(lambda x: f"{x:,}")
                            else:
                                df_display[col] = df_display[col].fillna(0).astype(int).apply(lambda x: f"{x:,}원")
                        
                        # Streamlit DataFrame의 인덱스를 표시하지 않기 위해 index를 reset
                        df_display.reset_index(drop=True, inplace=True) 
                        
                        # 깔끔한 st.dataframe 호출 (hide_index=True는 유지)
                        st.dataframe(
                            df_display[display_cols],
                            use_container_width=True, 
                            hide_index=True
                        )

                        # 4. 페이지네이션 컨트롤러 (이전/다음 버튼)
                        page_cols = st.columns([1, 4, 1])
                        
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
                        # [요청 1. 반영: 안내 메시지 제거, 아무것도 표시하지 않음]
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
    
    main()

                    
