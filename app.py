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
    st.session_state["sell_price_raw"] = ""
    st.session_state["unit_yuan"] = ""
    st.session_state["unit_won"] = ""
    st.session_state["qty_raw"] = ""
    st.session_state["show_result"] = False
    
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

try:
    SUPABASE_URL, SUPABASE_KEY = load_supabase_credentials()
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Supabase 클라이언트 초기화 중 오류가 발생했습니다: {e}")
    st.stop()

def load_config_from_supabase():
    data = supabase.table("settings").select("*").execute().data
    cfg = {}
    for row in data:
        cfg[row["key"]] = float(row["value"])
    return cfg

config = load_config_from_supabase()

st.sidebar.header("🛠️ 설정값")
config["FEE_RATE"]       = st.sidebar.number_input("수수료율 (%)",       value=config.get("FEE_RATE", 10.8), step=0.1, format="%.2f")
config["AD_RATE"]        = st.sidebar.number_input("광고비율 (%)",       value=config.get("AD_RATE", 20.0),  step=0.1, format="%.2f")
config["INOUT_COST"]     = st.sidebar.number_input("입출고비용 (원)",    value=int(config.get("INOUT_COST", 3000)), step=100)
config["PICKUP_COST"]    = st.sidebar.number_input("회수비용 (원)",      value=int(config.get("PICKUP_COST", 0)),    step=100)
config["RESTOCK_COST"]   = st.sidebar.number_input("재입고비용 (원)",    value=int(config.get("RESTOCK_COST", 0)),   step=100)
config["RETURN_RATE"]    = st.sidebar.number_input("반품률 (%)", 
        value=config.get("RETURN_RATE", 0.0), step=0.1, format="%.2f")
config["ETC_RATE"]       = st.sidebar.number_input("기타비용률 (%)",     value=config.get("ETC_RATE", 2.0),  step=0.1, format="%.2f")
config["EXCHANGE_RATE"]  = st.sidebar.number_input("위안화 환율",        value=int(config.get("EXCHANGE_RATE", 300)), step=1)
config["PACKAGING_COST"] = st.sidebar.number_input("포장비 (원)",        value=int(config.get("PACKAGING_COST", 0)), step=100)
config["GIFT_COST"]      = st.sidebar.number_input("사은품 비용 (원)",   value=int(config.get("GIFT_COST", 0)),      step=100)

if st.sidebar.button("📂 기본값으로 저장"):
    for k, v in config.items():
        supabase.table("settings").upsert({"key": k, "value": v}).execute()
    st.sidebar.success("Supabase에 저장 완료 ✅")

if "product_name_input" not in st.session_state: st.session_state["product_name_input_default"] = ""
if "sell_price_input" not in st.session_state: st.session_state.sell_price_input = ""
if "fee_rate_input" not in st.session_state: st.session_state.fee_rate_input = ""
if "inout_shipping_cost_input" not in st.session_state: st.session_state.inout_shipping_cost_input = ""
if "purchase_cost_input" not in st.session_state: st.session_state.purchase_cost_input = ""
if "quantity_input" not in st.session_state: st.session_state.quantity_input = ""
if "logistics_cost_input" not in st.session_state: st.session_state.logistics_cost_input = ""
if "customs_duty_input" not in st.session_state: st.session_state.customs_duty_input = ""
if "etc_cost_input" not in st.session_state: st.session_state.etc_cost_input = ""
if "is_edit_mode" not in st.session_state: st.session_state.is_edit_mode = False

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

    tab1, tab_product, tab_daily, tab_status = st.tabs(["간단 마진 계산기", "상품 정보 입력", "일일정산", "판매 현황"])

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
            if st.session_state["show_result"]:
                try:
                    sell_price = int(float(st.session_state.get("sell_price_raw", 0)))
                    qty = int(float(st.session_state.get("qty_raw", 1))) if st.session_state.get("qty_raw") else 1
                except:
                    st.warning("판매가와 수량을 정확히 입력해주세요.")
                    return
                
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

    with tab_product:
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
            value=st.session_state.get("product_name_input_default", ""),
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
        unit_purchase_cost = purchase_cost / max(quantity, 1)

        st.markdown("---")
        st.subheader("기타 비용 (포함시 마진에 반영)")
        col_left_etc, col_right_etc = st.columns(2)
        with col_left_etc:
            st.text_input("물류비", key="logistics_cost_input")
        with col_right_etc:
            st.text_input("관세", key="customs_duty_input")
        st.text_input("기타 비용", key="etc_cost_input")

        st.markdown("---")

        if st.session_state.is_edit_mode:
            col_save, col_delete = st.columns(2)
            if col_save.button("상품 수정하기"):
                if validate_inputs():
                    try:
                        data_to_update = {
                            "product_name": st.session_state.product_name_input,
                            "sell_price": safe_int(st.session_state.sell_price_input),
                            "fee": safe_float(st.session_state.fee_rate_input),
                            "inout_shipping_cost": safe_int(st.session_state.inout_shipping_cost_input),
                            "purchase_cost": safe_int(st.session_state.purchase_cost_input),
                            "quantity": safe_int(st.session_state.quantity_input),
                            "unit_purchase_cost": (
                                safe_int(st.session_state.purchase_cost_input) / max(safe_int(st.session_state.quantity_input), 1)
                            ),
                            "logistics_cost": safe_int(st.session_state.logistics_cost_input),
                            "customs_duty": safe_int(st.session_state.customs_duty_input),
                            "etc_cost": safe_int(st.session_state.etc_cost_input),
                        }
                        supabase.rpc("upsert_product", {"p_data": data_to_update}).execute()
                        st.success(f"'{st.session_state.product_name_input}' 상품이 수정되었습니다!")
                        st.session_state.is_edit_mode = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"데이터 수정 중 오류가 발생했습니다: {e}")

            if col_delete.button("상품 삭제하기"):
                try:
                    supabase.table("products").delete().eq("product_name", st.session_state.product_loader).execute()
                    st.success(f"'{st.session_state.product_loader}' 상품이 삭제되었습니다.")
                    st.session_state.is_edit_mode = False
                    st.session_state.product_loader = "새로운 상품 입력"
                    st.rerun()
                except Exception as e:
                    st.error(f"상품 삭제 중 오류가 발생했습니다: {e}")
        else:
            if st.button("상품 저장하기"):
                if validate_inputs():
                    try:
                        data_to_save = {
                            "product_name": st.session_state.product_name_input,
                            "sell_price": safe_int(st.session_state.sell_price_input),
                            "fee": safe_float(st.session_state.fee_rate_input),
                            "inout_shipping_cost": safe_int(st.session_state.inout_shipping_cost_input),
                            "purchase_cost": safe_int(st.session_state.purchase_cost_input),
                            "quantity": safe_int(st.session_state.quantity_input),
                            "unit_purchase_cost": (
                                safe_int(st.session_state.purchase_cost_input) / max(safe_int(st.session_state.quantity_input), 1)
                            ),
                            "logistics_cost": safe_int(st.session_state.logistics_cost_input),
                            "customs_duty": safe_int(st.session_state.customs_duty_input),
                            "etc_cost": safe_int(st.session_state.etc_cost_input),
                        }
                        supabase.rpc("upsert_product", {"p_data": data_to_save}).execute()
                        st.success(f"'{st.session_state.product_name_input}' 상품이 저장(또는 수정)되었습니다!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"데이터 저장 중 오류가 발생했습니다: {e}")

    with tab_daily:
        st.markdown("### 일일 정산")
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
                st.markdown(f"**기타 비용:** {product_data.get('etc_cost', 0):,}원")


        col_date, col_qty = st.columns(2)
        with col_date:
            report_date = st.date_input("정산 날짜", value=datetime.date.today(), key="report_date")
        with col_qty:
            st.number_input("총 판매 수량", value=st.session_state.get("total_sales_qty", 0), key="total_sales_qty", min_value=0)
        
        st.number_input("총 매출액 (원)", value=st.session_state.get("total_revenue", 0), key="total_revenue", min_value=0)
        
        col_ad_qty, col_ad_rev = st.columns(2)
        with col_ad_qty:
            st.number_input("광고 판매 수량", value=st.session_state.get("ad_sales_qty", 0), key="ad_sales_qty", min_value=0)
        with col_ad_rev:
            st.number_input("광고 매출액 (원)", value=st.session_state.get("ad_revenue", 0), key="ad_revenue", min_value=0)

        st.number_input("총 광고 비용 (원)", value=st.session_state.get("ad_cost", 0), key="ad_cost", min_value=0)

        if selected_product_name != "상품을 선택해주세요" and product_data:
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
            
            if st.button("일일 정산 기록 저장"):
                try:
                    data_to_save = {
                        "date": report_date.strftime("%Y-%m-%d"),
                        "product_name": selected_product_name,
                        "daily_sales_qty": current_total_sales_qty,
                        "daily_revenue": current_total_revenue,
                        "ad_sales_qty": st.session_state.ad_sales_qty,
                        "ad_revenue": st.session_state.ad_revenue,
                        "organic_sales_qty": current_total_sales_qty - st.session_state.ad_sales_qty,
                        "organic_revenue": current_total_revenue - st.session_state.ad_revenue,
                        "daily_ad_cost": current_ad_cost,
                        "daily_profit": daily_profit,
                    }
                    
                    supabase.rpc(
                        'upsert_daily_sales',
                        {'p_data': data_to_save}
                    ).execute()
                    st.success(f"'{selected_product_name}'의 {report_date} 판매 기록이 **성공적으로 저장/수정**되었습니다!")
                except Exception as e:
                    st.error(f"일일 정산 기록 저장 중 오류: {e}")

            with st.expander("순이익 계산 내역"):
                vat = 1.1
                fee_rate_db = product_data.get("fee", 0.0)
                current_total_sales_qty = st.session_state.total_sales_qty
                current_total_revenue = st.session_state.total_revenue
                current_ad_cost = st.session_state.ad_cost
                
                quantity_val = product_data.get("quantity", 1)
                quantity_for_calc = quantity_val if quantity_val > 0 else 1
                unit_purchase_cost = product_data.get("purchase_cost", 0) / quantity_for_calc
                unit_logistics = product_data.get("logistics_cost", 0) / quantity_for_calc
                unit_customs = product_data.get("customs_duty", 0) / quantity_for_calc
                unit_etc = product_data.get("etc_cost", 0) / quantity_for_calc

                st.markdown("#### 일일 매출액 및 비용 내역")
                st.markdown(f"- **총 매출액:** {current_total_revenue:,}원")
                st.markdown(f"- **판매 수량:** {current_total_sales_qty:,}개")
                st.markdown("---")

                total_fee = round(current_total_revenue * fee_rate_db / 100 * vat)
                total_purchase_cost = round(unit_purchase_cost * current_total_sales_qty)
                total_inout_shipping_cost = round(product_data.get("inout_shipping_cost", 0) * current_total_sales_qty * vat)
                total_logistics_cost = round(unit_logistics * current_total_sales_qty)
                total_customs_duty = round(unit_customs * current_total_sales_qty)
                total_etc_cost = round(unit_etc * current_total_sales_qty)
                total_ad_cost = round(current_ad_cost * vat)

                st.markdown(f"- **총 수수료:** -{total_fee:,}원")
                st.markdown(f"- **총 매입 비용:** -{total_purchase_cost:,}원")
                st.markdown(f"- **총 입출고/배송비:** -{total_inout_shipping_cost:,}원")
                st.markdown(f"- **총 물류비:** -{total_logistics_cost:,}원")
                st.markdown(f"- **총 관세:** -{total_customs_duty:,}원")
                st.markdown(f"- **총 기타 비용:** -{total_etc_cost:,}원")
                st.markdown(f"- **총 광고 비용:** -{total_ad_cost:,}원")

                total_expenses = total_fee + total_purchase_cost + total_inout_shipping_cost + total_logistics_cost + total_customs_duty + total_etc_cost + total_ad_cost
                st.markdown("---")
                st.markdown(f"**순이익**: {current_total_revenue:,}원 - {total_expenses:,}원 = **{daily_profit:,}원**")
        else:
            if selected_product_name == "상품을 선택해주세요":
                st.warning("먼저 '상품 정보 입력' 탭에서 상품을 저장하거나, 상품을 선택해주세요.")

    with tab_status:
        try:
            product_list = ["(상품을 선택해주세요)"]
            response = supabase.table("products").select("product_name").order("product_name").execute()
            if response.data:
                product_list.extend([item['product_name'] for item in response.data])
            
            st.markdown("### 판매 현황 조회")
            
            st.markdown("#### 📅 기간별 전체 순이익 조회")
            
            today = datetime.date.today()
            default_start_date = today - datetime.timedelta(days=6)

            if "profit_start_date_val" not in st.session_state: st.session_state.profit_start_date_val = default_start_date
            if "profit_end_date_val" not in st.session_state: st.session_state.profit_end_date_val = today
            
            col_date1, col_date2 = st.columns(2)
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

            if start_date and end_date and start_date <= end_date:
                try:
                    response = supabase.table("daily_sales").select("daily_profit, date").gte("date", start_date.strftime("%Y-%m-%d")).lte("date", end_date.strftime("%Y-%m-%d")).execute()
                    
                    if response.data:
                        df_all = pd.DataFrame(response.data)
                        total_profit = int(df_all["daily_profit"].sum())
                        st.metric(label=f"기간({start_date} ~ {end_date}) 총 순이익", value=f"{total_profit:,}원")
                    else:
                        st.metric(label=f"기간({start_date} ~ {end_date}) 총 순이익", value="0원")

                except Exception as e:
                    st.error(f"기간별 순이익을 불러오는 중 오류가 발생했습니다: {e}")

            st.markdown("---")
            st.markdown("#### 📈 상품별 일일 정산 기록")
            
            selected_product_filter = st.selectbox(
                "상품 선택 (기록 조회)",
                product_list,
                key="product_select_filter"
            )

            if "daily_sales_page" not in st.session_state:
                st.session_state.daily_sales_page = 1
            
            items_per_page = 10
            offset = (st.session_state.daily_sales_page - 1) * items_per_page
            
            query = supabase.table("daily_sales").select("*", count='exact')
            
            if selected_product_filter != "(상품을 선택해주세요)":
                query = query.eq("product_name", selected_product_filter)

            query = query.order("date", desc=True).limit(items_per_page).offset(offset)
            
            response = query.execute()
            
            if response.data:
                df = pd.DataFrame(response.data)
                df = df.rename(columns={
                    "date": "날짜",
                    "product_name": "상품명",
                    "daily_sales_qty": "총 판매 수량",
                    "daily_revenue": "총 매출액",
                    "ad_sales_qty": "광고 판매 수량",
                    "ad_revenue": "광고 매출액",
                    "organic_sales_qty": "오가닉 판매 수량",
                    "organic_revenue": "오가닉 매출액",
                    "daily_ad_cost": "총 광고 비용",
                    "daily_profit": "일일 순이익"
                })
                
                df['날짜'] = pd.to_datetime(df['날짜']).dt.date
                cols_to_format = ['총 매출액', '광고 매출액', '오가닉 매출액', '총 광고 비용', '일일 순이익']
                for col in cols_to_format:
                    df[col] = df[col].apply(lambda x: f"{int(x):,}")

                cols_to_format_qty = ['총 판매 수량', '광고 판매 수량', '오가닉 판매 수량']
                for col in cols_to_format_qty:
                    df[col] = df[col].apply(lambda x: f"{int(x):,}")

                display_cols = ['날짜', '상품명', '총 판매 수량', '총 매출액', '일일 순이익', '총 광고 비용']
                
                product_data = {}
                if selected_product_filter != "(상품을 선택해주세요)":
                    product_data_response = supabase.table("products").select("*").eq("product_name", selected_product_filter).execute()
                    if product_data_response.data:
                        product_data = product_data_response.data[0]
                    else:
                        st.error("선택된 상품의 상세 정보를 불러올 수 없습니다.")
                        df = pd.DataFrame()

                if not df.empty:
                    df["ROI"] = 0.0
                    df["마진율"] = 0.0
                    
                    if selected_product_filter != "(상품을 선택해주세요)":
                        total_profit_sum = int(df["일일 순이익"].str.replace(",", "").astype(int).sum())
                        total_sales_qty = int(df["총 판매 수량"].str.replace(",", "").astype(int).sum())
                        total_revenue_sum = int(df["총 매출액"].str.replace(",", "").astype(int).sum())

                        quantity_for_calc = product_data.get("quantity", 1) or 1
                        unit_purchase_cost = product_data.get("purchase_cost", 0) / quantity_for_calc
                        
                        total_unit_cost = unit_purchase_cost * total_sales_qty
                        
                        if total_unit_cost > 0:
                            total_roi = round(total_profit_sum / total_unit_cost * 100, 2)
                        else:
                            total_roi = 0.0

                        total_supply_price = total_revenue_sum / 1.1
                        if total_supply_price > 0:
                            total_margin_ratio = round(total_profit_sum / total_supply_price * 100, 2)
                        else:
                            total_margin_ratio = 0.0

                        st.markdown(f"**기간({df['날짜'].min()} ~ {df['날짜'].max()}) 합산 결과:**")
                        st.markdown(f"- **총 순이익:** {format_number(total_profit_sum)}원")
                        st.markdown(f"- **ROI:** {total_roi:.2f}% (총 순이익/총 매입원가)")
                        st.markdown(f"- **마진율:** {total_margin_ratio:.2f}% (총 순이익/총 공급가액)")
                        st.markdown("---")

                    st.dataframe(df[display_cols], hide_index=True, use_container_width=True)

                    total_rows = response.count
                    total_pages = (total_rows + items_per_page - 1) // items_per_page
                    
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

            else:
                st.info("아직 저장된 판매 기록이 없습니다.")
        except Exception as e:
            st.error(f"판매 현황을 불러오는 중 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    if "sell_price_raw" not in st.session_state: st.session_state["sell_price_raw"] = ""
    if "unit_yuan" not in st.session_state: st.session_state["unit_yuan"] = ""
    if "unit_won" not in st.session_state: st.session_state["unit_won"] = ""
    if "qty_raw" not in st.session_state: st.session_state["qty_raw"] = ""
    if "show_result" not in st.session_state: st.session_state["show_result"] = False
    
    main()
