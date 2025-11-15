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
        
        selected_date = st.date_input(
            "날짜 선택",
            value=datetime.date.today(),
            key="daily_sales_date"
        )
        
        selected_product = st.selectbox(
            "상품 선택",
            product_list,
            key="product_select_daily"
        )
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.number_input("전체 판매 수량", min_value=0, step=1, key="total_sales_qty")
        with col2:
            st.number_input("전체 매출액", min_value=0, step=100, key="total_revenue")
        
        col3, col4, col5 = st.columns(3)
        with col3:
            st.number_input("광고 판매 수량", min_value=0, step=1, key="ad_sales_qty")
        with col4:
            st.number_input("광고 매출액", min_value=0, step=100, key="ad_revenue")
        with col5:
            st.number_input("광고비", min_value=0, step=100, key="ad_cost")

        organic_sales_qty = st.session_state["total_sales_qty"] - st.session_state["ad_sales_qty"]
        organic_revenue = st.session_state["total_revenue"] - st.session_state["ad_revenue"]
        
        # 사용자 요청에 따라 "오가닉 판매 수량/매출액" 표시 UI 제거
        # col6, col7을 사용한 st.markdown 표시는 삭제함
        
        st.markdown("---")

        if st.button("일일 정산 기록"):
            if selected_product == "상품을 선택해주세요":
                st.warning("상품을 선택해주세요.")
            elif st.session_state["total_sales_qty"] < st.session_state["ad_sales_qty"]:
                st.warning("전체 판매 수량은 광고 판매 수량보다 적을 수 없습니다.")
            else:
                try:
                    daily_data = {
                        "date": selected_date.isoformat(),
                        "product_name": selected_product,
                        "daily_sales_qty": st.session_state["total_sales_qty"],
                        "daily_revenue": st.session_state["total_revenue"],
                        "ad_sales_qty": st.session_state["ad_sales_qty"],
                        "ad_revenue": st.session_state["ad_revenue"],
                        "organic_sales_qty": organic_sales_qty,
                        "organic_revenue": organic_revenue,
                        "daily_ad_cost": st.session_state["ad_cost"],
                    }
                    
                    product_response = supabase.table("products").select("*").eq("product_name", selected_product).execute()
                    if product_response.data:
                        product = product_response.data[0]
                        unit_cost = product["unit_purchase_cost"]
                        vat = 1.1
                        
                        sell_price = product["sell_price"]
                        fee_rate = product["fee"]
                        inout_shipping_cost = product["inout_shipping_cost"]
                        logistics_cost = product["logistics_cost"]
                        customs_duty = product["customs_duty"]
                        etc_cost = product["etc_cost"]

                        # 상세 비용 계산 (config 값 사용)
                        unit_total_cost = (
                            round(unit_cost * vat) + 
                            round((sell_price * fee_rate / 100) * vat) + 
                            round(inout_shipping_cost * vat) +
                            round(config["PACKAGING_COST"] * vat) +
                            round(config["GIFT_COST"] * vat) +
                            round(logistics_cost * vat) +
                            round(customs_duty * vat) +
                            round(etc_cost * vat)
                        )
                        
                        return_cost_per_unit = round((config['PICKUP_COST'] + config['RESTOCK_COST']) * (config['RETURN_RATE'] / 100) * vat)
                        
                        total_variable_cost = (unit_total_cost * st.session_state["total_sales_qty"]) + (return_cost_per_unit * st.session_state["total_sales_qty"])
                        total_cost_including_ad = total_variable_cost + st.session_state["ad_cost"]
                        
                        daily_profit = st.session_state["total_revenue"] - total_cost_including_ad
                        daily_data["daily_profit"] = int(daily_profit)
                    
                    supabase.table("daily_sales").insert(daily_data).execute()
                    st.success(f"{selected_product}에 대한 일일 정산 기록이 저장되었습니다. 예상 일일 수익: {format_number(int(daily_profit))}원")
                    st.session_state["total_sales_qty"] = 0
                    st.session_state["total_revenue"] = 0
                    st.session_state["ad_sales_qty"] = 0
                    st.session_state["ad_revenue"] = 0
                    st.session_state["ad_cost"] = 0
                    st.session_state["product_select_daily"] = "상품을 선택해주세요"
                    st.rerun()
                except Exception as e:
                    st.error(f"일일 정산 기록 중 오류가 발생했습니다: {e}")

    with tab_status:
        st.markdown("### 판매 현황")
        
        product_list = ["(상품을 선택해주세요)"]
        try:
            response = supabase.table("products").select("product_name").order("product_name").execute()
            if response.data:
                saved_products = [item['product_name'] for item in response.data]
                product_list.extend(saved_products)
        except Exception as e:
            st.error(f"상품 목록을 불러오는 중 오류가 발생했습니다: {e}")

        selected_product_filter = st.selectbox(
            "상품 필터",
            product_list,
            key="product_filter_status"
        )
        
        st.markdown("---")

        try:
            if "daily_sales_page" not in st.session_state:
                st.session_state.daily_sales_page = 1
            
            items_per_page = 10
            
            query = supabase.table("daily_sales").select("*")
            if selected_product_filter != "(상품을 선택해주세요)":
                query = query.eq("product_name", selected_product_filter)
            
            count_query = query.copy().select("count()").execute()
            total_items = count_query.count if count_query.count is not None else 0
            total_pages = (total_items + items_per_page - 1) // items_per_page
            
            if total_items > 0:
                offset = (st.session_state.daily_sales_page - 1) * items_per_page
                data = query.order("date", desc=True).limit(items_per_page).offset(offset).execute().data
                
                df = pd.DataFrame(data)
                
                if not df.empty:
                    df = df.rename(columns={
                        "date": "날짜",
                        "product_name": "상품명",
                        "daily_sales_qty": "전체 판매 수량",
                        "daily_revenue": "전체 매출액",
                        "ad_sales_qty": "광고 판매 수량",
                        "ad_revenue": "광고 매출액",
                        "organic_sales_qty": "오가닉 판매 수량",
                        "organic_revenue": "오가닉 매출액",
                        "daily_ad_cost": "광고비",
                        "daily_profit": "일일 수익"
                    })
                    
                    df["날짜"] = pd.to_datetime(df["날짜"]).dt.strftime('%Y-%m-%d')
                    
                    columns_to_display = ["날짜", "상품명", "전체 판매 수량", "전체 매출액", "광고 판매 수량", "광고 매출액", "오가닉 판매 수량", "오가닉 매출액", "광고비", "일일 수익"]
                    
                    st.dataframe(df[columns_to_display], use_container_width=True)
                    
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
    main()
