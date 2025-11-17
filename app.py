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

# ← 사이드바 시작
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
config["RETURN_RATE"]    = st.sidebar.number_input("반품률 (%)",         value=config.get("RETURN_RATE", 0.0), step=0.1, format="%.2f")
config["ETC_RATE"]       = st.sidebar.number_input("기타비용률 (%)",     value=config.get("ETC_RATE", 2.0),  step=0.1, format="%.2f")
config["EXCHANGE_RATE"]  = st.sidebar.number_input("위안화 환율",        value=int(config.get("EXCHANGE_RATE", 300)), step=1)
config["PACKAGING_COST"] = st.sidebar.number_input("포장비 (원)",        value=int(config.get("PACKAGING_COST", 0)), step=100)
config["GIFT_COST"]      = st.sidebar.number_input("사은품 비용 (원)",   value=int(config.get("GIFT_COST", 0)),      step=100)

if st.sidebar.button("📂 기본값으로 저장"):
    for k, v in config.items():
        supabase.table("settings").upsert({"key": k, "value": v}).execute()
    st.sidebar.success("Supabase에 저장 완료 ✅")

# 상품 정보 입력 상태 초기화 (탭2)
if "product_name_input" not in st.session_state: st.session_state["product_name_input_default"] = ""
if "sell_price_input" not in st.session_state: st.session_state.sell_price_input = ""
if "fee_rate_input" not in st.session_state: st.session_state.fee_rate_input = ""
if "inout_shipping_cost_input" not in st.session_state: st.session_state.inout_shipping_cost_input = ""
if "purchase_cost_input" not in st.session_state: st.session_state.purchase_cost_input = ""
if "quantity_input" not in st.session_state: st.session_state.quantity_input = ""
if "logistics_cost_input" not in st.session_state: st.session_state.logistics_cost_input = ""
if "customs_duty_input" not in st.session_state: st.session_state.customs_duty_input = ""
if "etc_cost_input" not in st.session_state: st.session_state.etc_cost_input = ""

def safe_int(value):
    try:
        return int(value.replace(",", "").strip()) if isinstance(value, str) else int(value)
    except:
        return 0

def clear_product_inputs():
    st.session_state.product_name_input_default = ""
    st.session_state.product_name_input = ""
    st.session_state.sell_price_input = ""
    st.session_state.fee_rate_input = ""
    st.session_state.inout_shipping_cost_input = ""
    st.session_state.purchase_cost_input = ""
    st.session_state.quantity_input = ""
    st.session_state.logistics_cost_input = ""
    st.session_state.customs_duty_input = ""
    st.session_state.etc_cost_input = ""

def load_product_data(selected_product):
    if selected_product == "새로운 상품 입력":
        clear_product_inputs()
    else:
        try:
            response = supabase.table("products").select("*").eq("product_name", selected_product).execute()
            if response.data:
                product = response.data[0]
                st.session_state.product_name_input_default = product.get("product_name", "")
                st.session_state.sell_price_input = format_number(product.get("sell_price", 0))
                st.session_state.fee_rate_input = str(product.get("fee_rate", 0))
                st.session_state.inout_shipping_cost_input = format_number(product.get("inout_shipping_cost", 0))
                st.session_state.purchase_cost_input = format_number(product.get("purchase_cost", 0))
                st.session_state.quantity_input = format_number(product.get("quantity", 0))
                st.session_state.logistics_cost_input = format_number(product.get("logistics_cost", 0))
                st.session_state.customs_duty_input = format_number(product.get("customs_duty", 0))
                st.session_state.etc_cost_input = format_number(product.get("etc_cost", 0))
        except Exception as e:
            st.error(f"상품 정보를 불러오는 중 오류가 발생했습니다: {e}")

def save_product_data():
    required_fields = {
        "상품명": st.session_state.product_name_input,
        "판매가": st.session_state.sell_price_input,
        "수수료율": st.session_state.fee_rate_input,
        "입출고/배송비": st.session_state.inout_shipping_cost_input,
        "매입 단가": st.session_state.purchase_cost_input,
        "수량": st.session_state.quantity_input
    }

    for name, value in required_fields.items():
        if not value or (isinstance(value, str) and value.strip() == ""):
            st.warning(f"'{name}' 필드를 채워주세요")
            return False

    return True

def main():
    if 'show_product_info' not in st.session_state:
        st.session_state.show_product_info = False

    tab1, tab2, tab3, tab4 = st.tabs(["간단 마진 계산기", "상품 정보 입력", "일일 정산", "판매 현황"])

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
<div style='height:10px; line-height:10px; color:#f63366; font-weight:bold; margin-top:0px;'>
목표 마진율 {target_margin}% 기준<br>
원가는 <span style='font-size:22px; color:#f63366;'>{target_cost:,}원 ({yuan_cost}위안)</span><br>
예상최소마진은 <span style='font-size:22px; color:#f63366;'>{profit:,}원</span> 입니다.
</div>
                        """,
                        unsafe_allow_html=True
                    )
                except ValueError:
                    st.warning("판매가를 정확히 입력해주세요.")
            else:
                margin_display.markdown(
                    "<div style='height:10px;'></div>",
                    unsafe_allow_html=True
                )

            st.subheader("원가 및 수량 입력")
            col1, col2 = st.columns(2)
            with col1:
                st.text_input("원가 (위안)", key="unit_yuan")
            with col2:
                st.text_input("원가 (원)", key="unit_won")

            st.text_input("수량 (개)", key="qty_raw")

            if st.button("계산하기", key="btn_calc"):
                st.session_state["show_result"] = True

            if st.button("리셋", key="btn_reset"):
                reset_inputs()
                st.rerun()

        with right:
            st.subheader("계산 결과")

            if st.session_state.get("show_result", False):
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
                    cost_display = f"({float(unit_yuan_val)}위안)"
                else:
                    unit_cost_val = 0
                    cost_display = ""

                unit_cost = unit_cost_val
                fee = round(sell_price * (config['FEE_RATE'] / 100))
                ad = round(sell_price * (config['AD_RATE'] / 100))
                inout = config['INOUT_COST']
                pickup = config['PICKUP_COST']
                restock = config['RESTOCK_COST']
                return_rate = config['RETURN_RATE']
                etc = round(sell_price * (config['ETC_RATE'] / 100))
                packaging = config['PACKAGING_COST']
                gift = config['GIFT_COST']

                return_cost = (pickup + restock) * (return_rate / 100.0)
                total_cost = (unit_cost + fee + ad + inout + return_cost + etc + packaging + gift)
                total_cost_q = total_cost * qty

                revenue = sell_price * qty
                supply_price2 = sell_price / 1.1
                profit2 = revenue - (total_cost_q + revenue - supply_price2 * qty)
                margin_rate2 = (profit2 / (supply_price2 * qty)) * 100 if supply_price2 > 0 else 0
                roi = (profit2 / total_cost_q) * 100 if total_cost_q > 0 else 0

                def styled_line(label, value):
                    return f"""
    <div style='display:flex; justify-content:space-between; margin-bottom:0px;'>
        <span style='font-weight:bold;'>{label}</span>
        <span>{value}</span>
    </div>
"""

                st.markdown(styled_line("판매가:", f"{format_number(sell_price)}원"), unsafe_allow_html=True)
                st.markdown(
                    styled_line(
                        "원가:",
                        f"{format_number(unit_cost)}원{cost_display if cost_display else ''}"
                    ),
                    unsafe_allow_html=True
                )
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
                st.markdown(styled_line("최소 마진율:", f"{margin_rate2:.2f}%"), unsafe_allow_html=True)
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
                value=st.session_state.get("product_name_input_default", ""),
                key="product_name_input",
                placeholder="예: 무선 이어폰"
            )


            # 상품 세부 정보
            col1, col2 = st.columns(2)

            with col1:
                st.text_input(
                    "판매가 (원)",
                    value=st.session_state.sell_price_input,
                    key="sell_price_input",
                    placeholder="예: 30,000"
                )
                st.text_input(
                    "수수료율 (%)",
                    value=st.session_state.fee_rate_input,
                    key="fee_rate_input",
                    placeholder="예: 10.8"
                )
                st.text_input(
                    "입출고/배송비 (원)",
                    value=st.session_state.inout_shipping_cost_input,
                    key="inout_shipping_cost_input",
                    placeholder="예: 3,000"
                )
                st.text_input(
                    "매입 단가 (원)",
                    value=st.session_state.purchase_cost_input,
                    key="purchase_cost_input",
                    placeholder="예: 10,000"
                )
            with col2:
                st.text_input(
                    "수량 (개)",
                    value=st.session_state.quantity_input,
                    key="quantity_input",
                    placeholder="예: 100"
                )
                st.text_input(
                    "물류비 (원)",
                    value=st.session_state.logistics_cost_input,
                    key="logistics_cost_input",
                    placeholder="예: 50"
                )
                st.text_input(
                    "관세 (원)",
                    value=st.session_state.customs_duty_input,
                    key="customs_duty_input",
                    placeholder="예: 12"
                )
                st.text_input(
                    "기타 비용 (원)",
                    value=st.session_state.etc_cost_input,
                    key="etc_cost_input",
                    placeholder="예: 2,000"
                )

            st.markdown("---")

            col3, col4 = st.columns(2)

            with col3:
                # 상품 등록 버튼
                if st.button("상품 정보 저장", key="save_product_info"):
                    if save_product_data():
                        try:
                            data_to_save = {
                                "product_name": st.session_state.product_name_input,
                                "sell_price": safe_int(st.session_state.sell_price_input),
                                "fee_rate": safe_int(st.session_state.fee_rate_input),
                                "inout_shipping_cost": safe_int(st.session_state.inout_shipping_cost_input),
                                "purchase_cost": safe_int(st.session_state.purchase_cost_input),
                                "quantity": safe_int(st.session_state.quantity_input),
                                "logistics_cost": safe_int(st.session_state.logistics_cost_input),
                                "customs_duty": safe_int(st.session_state.customs_duty_input),
                                "etc_cost": safe_int(st.session_state.etc_cost_input),
                            }
                            supabase.rpc("upsert_product", {"p_data": data_to_save}).execute()
                            st.success(f"'{st.session_state.product_name_input}' 상품이 저장(또는 수정)되었습니다!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"데이터 저장 중 오류가 발생했습니다: {e}")

    with tab3:
        st.subheader("세부 마진 계산기")
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

            # 날짜 입력
            today_default = datetime.date.today()
            target_date = st.date_input("정산할 날짜를 선택하세요", value=today_default, key="target_date_input")
            str_target_date = target_date.strftime("%Y-%m-%d")

            selected_product = st.selectbox(
                "정산할 상품을 선택하세요",
                product_list,
                key="product_select_daily"
            )

            if selected_product == "상품을 선택해주세요":
                st.info("🔎 정산할 상품을 선택해주세요.")
            else:
                try:
                    response = supabase.table("products").select("*").eq("product_name", selected_product).execute()
                    if not response.data:
                        st.warning("선택한 상품의 정보가 없습니다. 먼저 '상품 정보 입력'에서 저장하세요.")
                    else:
                        product = response.data[0]
                        sell_price = product.get("sell_price", 0)
                        fee_rate = product.get("fee_rate", 0)
                        inout_shipping_cost = product.get("inout_shipping_cost", 0)
                        purchase_cost = product.get("purchase_cost", 0)
                        quantity = product.get("quantity", 0)
                        logistics_cost = product.get("logistics_cost", 0)
                        customs_duty = product.get("customs_duty", 0)
                        etc_cost = product.get("etc_cost", 0)

                        st.markdown("---")
                        st.markdown(f"### 선택된 상품: {selected_product}")
                        st.write(f"- 판매가: {format_number(sell_price)}원")
                        st.write(f"- 수수료율: {fee_rate}%")
                        st.write(f"- 입출고/배송비: {format_number(inout_shipping_cost)}원")
                        st.write(f"- 매입 단가: {format_number(purchase_cost)}원")
                        st.write(f"- 수량: {format_number(quantity)}개")
                        st.write(f"- 물류비: {format_number(logistics_cost)}원")
                        st.write(f"- 관세: {format_number(customs_duty)}원")
                        st.write(f"- 기타비용: {format_number(etc_cost)}원")

                        st.markdown("---")
                        st.subheader("일일 판매 정보 입력")

                        col1, col2 = st.columns(2)

                        with col1:
                            total_sales_qty = st.number_input(
                                "📦 총 판매수량 (개)",
                                min_value=0,
                                step=1,
                                key="total_sales_qty"
                            )
                            total_revenue = st.number_input(
                                "💰 전체 매출액 (원)",
                                min_value=0,
                                step=1000,
                                key="total_revenue"
                            )
                        with col2:
                            ad_sales_qty = st.number_input(
                                "📦 광고매출 판매수량 (개)",
                                min_value=0,
                                step=1,
                                key="ad_sales_qty"
                            )
                            ad_revenue = st.number_input(
                                "💰 광고매출액 (원)",
                                min_value=0,
                                step=1000,
                                key="ad_revenue"
                            )

                        ad_cost = st.number_input(
                            "📢 광고비 (원)",
                            min_value=0,
                            step=1000,
                            key="ad_cost"
                        )

                        st.markdown("---")

                        if st.button("📊 일일 정산 계산하기", key="calculate_daily_settlement"):
                            if total_sales_qty == 0:
                                st.warning("총 판매수량은 0보다 커야 합니다.")
                            else:
                                if ad_sales_qty > total_sales_qty:
                                    st.warning("광고매출 판매수량은 총 판매수량을 초과할 수 없습니다.")
                                if ad_revenue > total_revenue:
                                    st.warning("광고매출액은 전체 매출액을 초과할 수 없습니다.")

                                # --- 계산 시작 ---
                                non_ad_sales_qty = total_sales_qty - ad_sales_qty
                                non_ad_revenue = total_revenue - ad_revenue

                                proportion_sales = total_sales_qty / quantity if quantity > 0 else 0

                                # 각 비용 항목에 대한 일일 비용
                                total_inout_shipping = inout_shipping_cost * proportion_sales
                                total_purchase_cost = purchase_cost * total_sales_qty
                                total_logistics_cost = logistics_cost * total_sales_qty
                                total_customs_duty = customs_duty * total_sales_qty
                                total_etc_cost = etc_cost * total_sales_qty
                                
                                fee_rate_decimal = fee_rate / 100
                                total_fee = total_revenue * fee_rate_decimal

                                total_cost = (
                                    total_inout_shipping +
                                    total_purchase_cost +
                                    total_logistics_cost +
                                    total_customs_duty +
                                    total_etc_cost +
                                    ad_cost +
                                    total_fee
                                )

                                # 총 수익 및 ROI
                                total_profit = total_revenue - total_cost
                                roi = (total_profit / total_cost * 100) if total_cost > 0 else 0

                                # 광고매출 및 비광고매출 비율
                                ad_revenue_ratio = (ad_revenue / total_revenue * 100) if total_revenue > 0 else 0
                                non_ad_revenue_ratio = 100 - ad_revenue_ratio

                                # 총 마진율 계산
                                margin_rate_total = (total_profit / total_revenue * 100) if total_revenue > 0 else 0

                                st.markdown("### 📌 일일 정산 결과")
                                st.write(f"- 총 판매수량: {format_number(total_sales_qty)}개")
                                st.write(f"- 전체 매출액: {format_number(total_revenue)}원")
                                st.write(f"- 광고매출 판매수량: {format_number(ad_sales_qty)}개")
                                st.write(f"- 광고매출액: {format_number(ad_revenue)}원")
                                st.write(f"- 비광고매출 판매수량: {format_number(non_ad_sales_qty)}개")
                                st.write(f"- 비광고매출액: {format_number(non_ad_revenue)}원")
                                st.write(f"- 광고비: {format_number(ad_cost)}원")
                                st.write(f"- 수수료: {format_number(int(total_fee))}원")
                                st.write(f"- 입출고/배송비: {format_number(int(total_inout_shipping))}원")
                                st.write(f"- 매입 단가 총액: {format_number(int(total_purchase_cost))}원")
                                st.write(f"- 물류비 총액: {format_number(int(total_logistics_cost))}원")
                                st.write(f"- 관세 총액: {format_number(int(total_customs_duty))}원")
                                st.write(f"- 기타 비용 총액: {format_number(int(total_etc_cost))}원")
                                st.write(f"- 총 비용: {format_number(int(total_cost))}원")
                                st.write(f"- 총 순이익: {format_number(int(total_profit))}원")
                                st.write(f"- 총 ROI: {roi:.2f}%")
                                st.write(f"- 총 마진율: {margin_rate_total:.2f}%")
                                st.write(f"- 광고매출 비율: {ad_revenue_ratio:.2f}%")
                                st.write(f"- 비광고매출 비율: {non_ad_revenue_ratio:.2f}%")

                                try:
                                    supabase.table("daily_sales").insert({
                                        "date": str_target_date,
                                        "product_name": selected_product,
                                        "total_sales_qty": total_sales_qty,
                                        "total_revenue": total_revenue,
                                        "ad_sales_qty": ad_sales_qty,
                                        "ad_revenue": ad_revenue,
                                        "ad_cost": ad_cost,
                                        "non_ad_sales_qty": non_ad_sales_qty,
                                        "non_ad_revenue": non_ad_revenue,
                                        "total_inout_shipping": int(total_inout_shipping),
                                        "total_purchase_cost": int(total_purchase_cost),
                                        "total_logistics_cost": int(total_logistics_cost),
                                        "total_customs_duty": int(total_customs_duty),
                                        "total_etc_cost": int(total_etc_cost),
                                        "total_fee": int(total_fee),
                                        "total_cost": int(total_cost),
                                        "total_profit": int(total_profit),
                                        "roi": roi,
                                        "margin_rate_total": margin_rate_total,
                                        "ad_revenue_ratio": ad_revenue_ratio,
                                        "non_ad_revenue_ratio": non_ad_revenue_ratio
                                    }).execute()
                                    st.success("✅ 일일 정산 내용이 저장되었습니다.")
                                except Exception as e:
                                    st.error(f"일일 정산 데이터를 저장하는 중 오류가 발생했습니다: {e}")

    with tab4:
        st.subheader("세부 마진 계산기")
        with st.expander("판매 현황"):
            st.markdown("### 📈 판매 현황 조회")

            # 날짜 범위 입력
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("조회 시작일", value=datetime.date.today() - datetime.timedelta(days=7), key="start_date_input")
            with col2:
                end_date = st.date_input("조회 종료일", value=datetime.date.today(), key="end_date_input")

            str_start_date = start_date.strftime("%Y-%m-%d")
            str_end_date = end_date.strftime("%Y-%m-%d")

            # 상품 선택
            product_list = ["(전체 상품)"]
            try:
                response = supabase.table("products").select("product_name").order("product_name").execute()
                if response.data:
                    saved_products = [item['product_name'] for item in response.data]
                    product_list.extend(saved_products)
            except Exception as e:
                st.error(f"상품 목록을 불러오는 중 오류가 발생했습니다: {e}")

            selected_product_filter = st.selectbox(
                "조회할 상품을 선택하세요 (또는 전체)",
                product_list,
                key="product_filter_sales"
            )

            # 조회 버튼
            if st.button("📊 판매 현황 조회하기", key="view_sales_status"):
                try:
                    query = supabase.table("daily_sales").select("*").gte("date", str_start_date).lte("date", str_end_date)

                    if selected_product_filter != "(전체 상품)":
                        query = query.eq("product_name", selected_product_filter)

                    response = query.execute() 
                    df = pd.DataFrame(response.data)

                    if not df.empty:
                        df['date'] = pd.to_datetime(df['date'])
                        
                        # --- 특정 상품 선택 시에만 기록과 총 순이익금 표시 ---
                        if selected_product_filter != "(전체 상품)":
                            
                            # [총 순이익금 + 전체 수량/판매 수량/ROI/마진율 표시]
                            total_profit_sum = df["daily_profit"].sum()
                            
                            total_qty_sum = df["total_sales_qty"].sum()
                            total_revenue_sum = df["total_revenue"].sum()
                            total_cost_sum = df["daily_cost"].sum()
                            
                            overall_roi = (total_profit_sum / total_cost_sum * 100) if total_cost_sum > 0 else 0
                            overall_margin_rate = (total_profit_sum / total_revenue_sum * 100) if total_revenue_sum > 0 else 0
                            
                            st.markdown("### 💰 총 순이익 및 지표")
                            st.write(f"- 기간 내 총 순이익금: {format_number(int(total_profit_sum))}원")
                            st.write(f"- 기간 내 총 판매수량: {format_number(int(total_qty_sum))}개")
                            st.write(f"- 기간 내 총 매출액: {format_number(int(total_revenue_sum))}원")
                            st.write(f"- 기간 내 총 비용: {format_number(int(total_cost_sum))}원")
                            st.write(f"- 전체 ROI: {overall_roi:.2f}%")
                            st.write(f"- 전체 마진율: {overall_margin_rate:.2f}%")
                            st.markdown("---")

                        # --- 판매 현황 표 (일자별) ---
                        st.markdown("### 📅 일자별 판매 현황")

                        # 날짜순 정렬
                        df = df.sort_values(by="date")

                        # 표시용 컬럼 정리
                        df_display = df[[
                            "date", "product_name", "total_sales_qty", "total_revenue",
                            "ad_sales_qty", "ad_revenue", "ad_cost",
                            "non_ad_sales_qty", "non_ad_revenue",
                            "daily_cost", "daily_profit", "roi", "margin_rate"
                        ]].copy()

                        df_display = df_display.rename(columns={
                            "date": "날짜",
                            "product_name": "상품명",
                            "total_sales_qty": "총 판매수량",
                            "total_revenue": "총 매출액",
                            "ad_sales_qty": "광고 판매수량",
                            "ad_revenue": "광고 매출액",
                            "ad_cost": "광고비",
                            "non_ad_sales_qty": "비광고 판매수량",
                            "non_ad_revenue": "비광고 매출액",
                            "daily_cost": "일일 총비용",
                            "daily_profit": "일일 순이익",
                            "roi": "ROI(%)",
                            "margin_rate": "마진율(%)"
                        })

                        # 숫자 포맷팅
                        for col in ["총 판매수량", "총 매출액", "광고 판매수량", "광고 매출액", "광고비",
                                    "비광고 판매수량", "비광고 매출액", "일일 총비용", "일일 순이익"]:
                            df_display[col] = df_display[col].apply(lambda x: format_number(int(x)) if pd.notnull(x) else "")

                        for col in ["ROI(%)", "마진율(%)"]:
                            df_display[col] = df_display[col].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "")

                        df_display["날짜"] = df_display["날짜"].dt.strftime("%Y-%m-%d")

                        st.dataframe(df_display, use_container_width=True)

                    else:
                        st.info("선택한 기간 및 조건에 해당하는 판매 데이터가 없습니다.")
                except Exception as e:
                    st.error(f"판매 현황 데이터를 불러오는 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
