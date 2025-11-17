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

def safe_float(value):
    try:
        return float(value.replace(",", "").strip()) if isinstance(value, str) else float(value)
    except:
        return 0.0

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
                st.session_state.fee_rate_input = str(product.get("fee", 0))
                st.session_state.inout_shipping_cost_input = format_number(product.get("inout_shipping_cost", 0))
                st.session_state.purchase_cost_input = format_number(product.get("purchase_cost", 0))
                st.session_state.quantity_input = format_number(product.get("quantity", 0))
                st.session_state.logistics_cost_input = format_number(product.get("logistics_cost", 0))
                st.session_state.customs_duty_input = format_number(product.get("customs_duty", 0))
                st.session_state.etc_cost_input = format_number(product.get("etc_cost", 0))
        except Exception as e:
            st.error(f"상품 정보를 불러오는 중 오류가 발생했습니다: {e}")

def validate_inputs():
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
<div style='height:10px; line-height:10px; color:#f63366; font-size:15px; margin-bottom:15px;'>
    마진율 {int(target_margin)}% 기준: {format_number(target_cost)}원 ({yuan_cost:.2f}위안) / 마진: {format_number(profit)}원
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
                if st.button("새로 입력"):
                    clear_product_inputs()
                    st.session_state.product_loader = "새로운 상품 입력"

            with col4:
                st.checkbox(
                    "저장된 상품 정보 표시",
                    key="show_product_info"
                )

            if st.session_state.show_product_info:
                st.markdown("#### 저장된 상품 정보 목록")

                try:
                    response = supabase.table("products").select("*").order("product_name").execute()
                    if response.data:
                        df = pd.DataFrame(response.data)
                        df_display = df[[
                            "product_name", "sell_price", "fee", "inout_shipping_cost",
                            "purchase_cost", "quantity", "logistics_cost",
                            "customs_duty", "etc_cost", "unit_purchase_cost"
                        ]].copy()

                        df_display = df_display.rename(columns={
                            "product_name": "상품명",
                            "sell_price": "판매가",
                            "fee": "수수료율(%)",
                            "inout_shipping_cost": "입출고/배송비",
                            "purchase_cost": "매입 단가",
                            "quantity": "수량",
                            "logistics_cost": "물류비",
                            "customs_duty": "관세",
                            "etc_cost": "기타 비용",
                            "unit_purchase_cost": "단위 매입비"
                        })

                        num_cols = [
                            "판매가", "입출고/배송비", "매입 단가",
                            "수량", "물류비", "관세", "기타 비용", "단위 매입비"
                        ]
                        for col in num_cols:
                            df_display[col] = df_display[col].apply(
                                lambda x: format_number(x) if pd.notnull(x) else ""
                            )

                        st.dataframe(df_display, use_container_width=True)
                    else:
                        st.info("저장된 상품 정보가 없습니다.")
                except Exception as e:
                    st.error(f"상품 정보 목록을 불러오는 중 오류가 발생했습니다: {e}")

            st.markdown("---")

            col_save, col_edit, col_del = st.columns(3)

            with col_save:
                if st.button("상품 저장하기"):
                    if validate_inputs():
                        try:
                            quantity_value = safe_int(st.session_state.quantity_input)
                            unit_purchase_cost = (
                                safe_int(st.session_state.purchase_cost_input) / quantity_value
                                if quantity_value > 0 else 0
                            )
                            data_to_save = {
                                "product_name": st.session_state.product_name_input,
                                "sell_price": safe_int(st.session_state.sell_price_input),
                                "fee": safe_float(st.session_state.fee_rate_input),
                                "inout_shipping_cost": safe_int(st.session_state.inout_shipping_cost_input),
                                "purchase_cost": safe_int(st.session_state.purchase_cost_input),
                                "quantity": quantity_value,
                                "unit_purchase_cost": unit_purchase_cost,
                                "logistics_cost": safe_int(st.session_state.logistics_cost_input),
                                "customs_duty": safe_int(st.session_state.customs_duty_input),
                                "etc_cost": safe_int(st.session_state.etc_cost_input),
                            }
                            supabase.rpc("upsert_product", {"p_data": data_to_save}).execute()
                            st.success(f"'{st.session_state.product_name_input}' 상품이 저장(또는 수정)되었습니다!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"데이터 저장 중 오류가 발생했습니다: {e}")

            with col_edit:
                if st.button("수정하기"):
                    if validate_inputs():
                        try:
                            old_name = st.session_state.product_loader
                            new_name = st.session_state.product_name_input

                            data_to_update = {
                                "product_name": new_name,
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

                            # ✅ 제품 이름이 변경된 경우에만 rename 로직 실행
                            if old_name != new_name:
                                # 1) products 테이블에서 이름 변경
                                supabase.rpc("update_product_by_old_name", {
                                    "old_name": old_name,
                                    "p_data": data_to_update
                                }).execute()

                                # 2) daily_sales 테이블에서 product_name 동기화
                                supabase.rpc(
                                    "update_daily_sales_name",
                                    {"old_name": old_name, "new_name": new_name}
                                ).execute()
                            else:
                                # ✅ 이름이 같으면 기존 upsert 그대로
                                supabase.rpc("upsert_product", {"p_data": data_to_update}).execute()

                            st.success("데이터가 수정되었습니다!")
                            st.rerun()

                        except Exception as e:
                            st.error(f"상품명 수정 중 오류가 발생했습니다: {e}")

            with col_del:
                if st.button("삭제하기"):
                    try:
                        product_to_delete = st.session_state.product_name_input
                        supabase.rpc("delete_product_and_sales", {"p_name": product_to_delete}).execute()
                        st.success(f"'{product_to_delete}' 상품과 관련된 모든 데이터가 삭제되었습니다!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"데이터 삭제 중 오류가 발생했습니다: {e}")

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

            selected_product_name = st.selectbox(
                "정산할 상품을 선택하세요",
                product_list,
                key="product_select_daily"
            )

            if "total_sales_qty" not in st.session_state: st.session_state.total_sales_qty = 0
            if "total_revenue" not in st.session_state: st.session_state.total_revenue = 0
            if "ad_sales_qty" not in st.session_state: st.session_state.ad_sales_qty = 0
            if "ad_revenue" not in st.session_state: st.session_state.ad_revenue = 0
            if "ad_cost" not in st.session_state: st.session_state.ad_cost = 0

            report_date = st.date_input("날짜 선택", datetime.date.today(), key="report_date_input")

            if selected_product_name != "상품을 선택해주세요":
                try:
                    product_info = supabase.table("products").select("*").eq("product_name", selected_product_name).execute()
                    if product_info.data:
                        product_data = product_info.data[0]

                        st.markdown("#### 상품 기본 정보")
                        st.write(f"- 상품명: {product_data.get('product_name', '')}")
                        st.write(f"- 판매가: {format_number(product_data.get('sell_price', 0))}원")
                        st.write(f"- 수수료율: {product_data.get('fee', 0.0)}%")
                        st.write(f"- 입출고/배송비: {format_number(product_data.get('inout_shipping_cost', 0))}원")
                        st.write(f"- 매입 단가: {format_number(product_data.get('purchase_cost', 0))}원")
                        st.write(f"- 재고 수량: {format_number(product_data.get('quantity', 0))}개")
                        st.write(f"- 물류비: {format_number(product_data.get('logistics_cost', 0))}원")
                        st.write(f"- 관세: {format_number(product_data.get('customs_duty', 0))}원")
                        st.write(f"- 기타 비용: {format_number(product_data.get('etc_cost', 0))}원")

                        st.markdown("---")
                        st.markdown("#### 전체 판매")

                        col_total1, col_total2 = st.columns(2)
                        with col_total1:
                            st.number_input("전체 판매수량", min_value=0, step=1, key="total_sales_qty")
                        with col_total2:
                            st.number_input("전체 매출액", step=1000, key="total_revenue")

                        st.markdown("#### 광고 판매")

                        col_ad1, col_ad2 = st.columns(2)
                        with col_ad1:
                            st.number_input("광고 판매수량", min_value=0, step=1, key="ad_sales_qty")
                        with col_ad2:
                            st.number_input("광고 매출액", step=1000, key="ad_revenue")

                        st.markdown("#### 광고비 입력")
                        st.number_input("광고비", step=1000, key="ad_cost")

                        st.markdown("#### 자연 판매 (자동 계산)")

                        total_sales_qty = st.session_state.total_sales_qty
                        total_revenue = st.session_state.total_revenue
                        ad_sales_qty = st.session_state.ad_sales_qty
                        ad_revenue = st.session_state.ad_revenue
                        ad_cost = st.session_state.ad_cost

                        organic_sales_qty_calc = max(total_sales_qty - ad_sales_qty, 0)
                        organic_revenue_calc = max(total_revenue - ad_revenue, 0)

                        st.write(f"- 자연 판매수량: {organic_sales_qty_calc:,}개")
                        st.write(f"- 자연 매출액: {organic_revenue_calc:,}원")

                        st.markdown("### 📌 일일 정산 결과")

                        fee_rate_db = product_data.get("fee", 0.0)
                        vat = 1.1
                        quantity_for_calc = product_data.get("quantity", 1)
                        quantity_for_calc = quantity_for_calc if quantity_for_calc > 0 else 1

                        unit_purchase_cost = product_data.get("purchase_cost", 0) / quantity_for_calc
                        unit_logistics = product_data.get("logistics_cost", 0) / quantity_for_calc
                        unit_customs = product_data.get("customs_duty", 0) / quantity_for_calc
                        unit_etc = product_data.get("etc_cost", 0) / quantity_for_calc

                        if total_sales_qty > 0:
                            inout_shipping_total = round(product_data.get("inout_shipping_cost", 0) * total_sales_qty * vat)
                            purchase_cost_total = round(unit_purchase_cost * total_sales_qty)
                            logistics_cost_total = round(unit_logistics * total_sales_qty)
                            customs_cost_total = round(unit_customs * total_sales_qty)
                            etc_cost_total = round(unit_etc * total_sales_qty)
                            fee_cost = round(total_revenue * fee_rate_db / 100 * vat)
                            ad_cost_total = round(ad_cost * vat)

                            total_cost = (
                                inout_shipping_total +
                                purchase_cost_total +
                                logistics_cost_total +
                                customs_cost_total +
                                etc_cost_total +
                                fee_cost +
                                ad_cost_total
                            )

                            daily_profit = total_revenue - total_cost

                            st.write(f"- 전체 판매수량: {total_sales_qty:,}개")
                            st.write(f"- 전체 매출액: {total_revenue:,}원")
                            st.write(f"- 광고 판매수량: {ad_sales_qty:,}개")
                            st.write(f"- 광고 매출액: {ad_revenue:,}원")
                            st.write(f"- 자연 판매수량: {organic_sales_qty_calc:,}개")
                            st.write(f"- 자연 매출액: {organic_revenue_calc:,}원")
                            st.write(f"- 수수료 (VAT 포함): {fee_cost:,}원")
                            st.write(f"- 입출고/배송비 (VAT 포함): {inout_shipping_total:,}원")
                            st.write(f"- 매입비: {purchase_cost_total:,}원")
                            st.write(f"- 물류비: {logistics_cost_total:,}원")
                            st.write(f"- 관세: {customs_cost_total:,}원")
                            st.write(f"- 기타 비용: {etc_cost_total:,}원")
                            st.write(f"- 광고비 (VAT 포함): {ad_cost_total:,}원")
                            st.write(f"- 총 비용: {total_cost:,}원")
                            st.write(f"- 일일 순이익금: {daily_profit:,}원")

                            purchase_related_cost = purchase_cost_total + logistics_cost_total + customs_cost_total + etc_cost_total
                            roi = (daily_profit / purchase_related_cost * 100) if purchase_related_cost else 0
                            margin = (daily_profit / total_revenue * 100) if total_revenue else 0

                            st.write(f"- ROI (매입+물류+관세+기타 기준): {roi:.2f}%")
                            st.write(f"- 마진율 (총매출 기준): {margin:.2f}%")

                            st.markdown("#### 일일 순이익 계산 내역")

                            fee_cost = round(total_revenue * fee_rate_db / 100 * vat)
                            purchase_cost_total = round(unit_purchase_cost * total_sales_qty)
                            inout_shipping_cost_total = round(product_data.get("inout_shipping_cost", 0) * total_sales_qty * vat)
                            logistics_cost_total = round(unit_logistics * total_sales_qty)
                            customs_cost_total = round(unit_customs * total_sales_qty)
                            etc_cost_total = round(unit_etc * total_sales_qty)
                            ad_cost_total = round(ad_cost * vat)

                            st.markdown(
                                f"""
                                <div style='font-size:12px; line-height:1.4; color:gray;'>
                                <small>
                                - 수수료 (VAT 포함): {fee_cost:,}원 (수수료율 {fee_rate_db}% × 매출액 {total_revenue:,}원 × 1.1)<br>
                                - 매입비: {purchase_cost_total:,}원 (단위 매입비 {unit_purchase_cost:,.2f}원 × 판매수량 {total_sales_qty:,}개)<br>
                                - 입출고/배송비 (VAT 포함): {inout_shipping_cost_total:,}원 (입출고비 {product_data.get("inout_shipping_cost", 0):,}원 × 판매수량 {total_sales_qty:,}개 × 1.1)<br>
                                - 물류비: {logistics_cost_total:,}원 (단위 물류비 {unit_logistics:,.2f}원 × 판매수량 {total_sales_qty:,}개)<br>
                                - 관세: {customs_cost_total:,}원 (단위 관세 {unit_customs:,.2f}원 × 판매수량 {total_sales_qty:,}개)<br>
                                - 기타 비용: {etc_cost_total:,}원 (단위 기타비 {unit_etc:,.2f}원 × 판매수량 {total_sales_qty:,}개)<br>
                                - 광고비 (VAT 포함): {ad_cost_total:,}원 (입력 광고비 {ad_cost:,}원 × 1.1)<br>
                                <br>
                                </small>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                            st.metric(label="일일 순이익금", value=f"{daily_profit:,}원")

                            if st.button("일일 정산 저장하기"):
                                if selected_product_name == "상품을 선택해주세요":
                                    st.warning("상품을 먼저 선택해야 저장할 수 있습니다.")
                                elif not product_data:
                                    st.warning("선택된 상품의 상세 정보가 없습니다.")
                                elif st.session_state.total_sales_qty == 0 and st.session_state.total_revenue == 0:
                                    st.warning("판매 수량 또는 매출액을 입력해야 저장할 수 있습니다.")
                                else:
                                    try:
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
                                            "roi": roi,
                                            "margin_rate": margin,
                                        }

                                        supabase.rpc(
                                            "upsert_daily_sales",
                                            {"p_data": data_to_save}
                                        ).execute()
                                        
                                        st.success(f"'{selected_product_name}'의 {report_date} 판매 기록이 **성공적으로 저장/수정**되었습니다!")
                                    
                                    except Exception as e:
                                        st.error(f"데이터 저장 중 오류가 발생했습니다: {e}")
                                        st.error(f"일일 정산 저장 중 오류가 발생했습니다: {e}")
                        else:
                            st.info("전체 판매수량이 0보다 커야 정산을 진행할 수 있습니다.")
                    else:
                        st.warning("선택된 상품의 상세 정보가 없습니다. 먼저 '상품 정보 입력' 탭에서 저장해주세요.")
                except Exception as e:
                    st.error(f"상품 정보를 불러오는 중 오류가 발생했습니다: {e}")
            else:
                st.info("먼저 정산할 상품을 선택하세요.")

    with tab4:
        st.subheader("세부 마진 계산기")
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
                response = supabase.table("products").select("product_name").order("product_name").execute()
                if response.data:
                    saved_products = [item['product_name'] for item in response.data]
                    product_list.extend(saved_products)
            except Exception as e:
                st.error(f"상품 목록을 불러오는 중 오류가 발생했습니다: {e}")

            selected_product_filter = st.selectbox(
                "조회할 상품을 선택하세요",
                product_list,
                key="product_filter_sales_tab"
            )

            start_date = st.date_input("조회 시작일", value=datetime.date.today() - datetime.timedelta(days=30), key="start_date_sales")
            end_date = st.date_input("조회 종료일", value=datetime.date.today(), key="end_date_sales")

            if start_date > end_date:
                st.error("조회 시작일은 종료일보다 클 수 없습니다.")
                return

            if st.button("판매 현황 조회하기", on_click=reset_page):
                pass

            try:
                query = supabase.table("daily_sales").select("*").gte("date", start_date.isoformat()).lte("date", end_date.isoformat())

                if selected_product_filter != "(상품을 선택해주세요)":
                    query = query.eq("product_name", selected_product_filter)

                response = query.order("date").execute()

                if response.data:
                    df = pd.DataFrame(response.data)
                    df["date"] = pd.to_datetime(df["date"])

                    df = df.rename(columns={
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
                        "roi": "ROI(%)",
                        "margin_rate": "마진율(%)"
                    })

                    df["날짜"] = pd.to_datetime(df["날짜"])

                    if selected_product_filter != "(상품을 선택해주세요)":
                        product_info = supabase.table("products").select("*").eq("product_name", selected_product_filter).execute()
                        product_data = product_info.data[0] if (product_info.data and len(product_info.data) > 0) else {}
                        total_quantity = product_data.get("quantity", 0)
                        total_sales_qty = int(df["전체 수량"].sum()) if "전체 수량" in df.columns else 0
                        total_revenue_sum = int(df["전체 매출액"].sum()) if "전체 매출액" in df.columns else 0

                        quantity_for_calc = product_data.get("quantity", 1) or 1
                        unit_purchase_cost = product_data.get("purchase_cost", 0) / quantity_for_calc
                        unit_logistics = product_data.get("logistics_cost", 0) / quantity_for_calc
                        unit_customs = product_data.get("customs_duty", 0) / quantity_for_calc
                        unit_etc = product_data.get("etc_cost", 0) / quantity_for_calc
                        inout_shipping_cost = product_data.get("inout_shipping_cost", 0)
                        fee_rate_db = product_data.get("fee", 0.0)

                        vat = 1.1
                        inout_shipping_total_period = inout_shipping_cost * total_sales_qty * vat
                        purchase_cost_total_period = unit_purchase_cost * total_sales_qty
                        logistics_total_period = unit_logistics * total_sales_qty
                        customs_total_period = unit_customs * total_sales_qty
                        etc_total_period = unit_etc * total_sales_qty
                        fee_cost_period = total_revenue_sum * fee_rate_db / 100 * vat

                        daily_profit_sum = df["일일 순이익금"].sum() if "일일 순이익금" in df.columns else 0

                        total_cost_period = (
                            inout_shipping_total_period +
                            purchase_cost_total_period +
                            logistics_total_period +
                            customs_total_period +
                            etc_total_period +
                            fee_cost_period
                        )

                        roi_period = (daily_profit_sum / (purchase_cost_total_period + logistics_total_period + customs_total_period + etc_total_period) * 100) if (purchase_cost_total_period + logistics_total_period + customs_total_period + etc_total_period) else 0
                        margin_period = (daily_profit_sum / total_revenue_sum * 100) if total_revenue_sum else 0

                        st.markdown(
                            f"""
                            <div style='color:gray; font-size:14px; line-height:1.6;'>
                            <b>총 순이익 요약</b><br>
                            - 기간 총 판매수량: {total_sales_qty:,}개 / 재고 수량: {total_quantity:,}개<br>
                            - 기간 총 매출액: {total_revenue_sum:,}원<br>
                            - 기간 총 순이익금: {daily_profit_sum:,.0f}원<br>
                            - ROI (매입+물류+관세+기타 기준): {roi_period:.2f}%<br>
                            - 마진율 (총매출 기준): {margin_period:.2f}%<br>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    df = df.sort_values(by="날짜", ascending=False)

                    if 'daily_sales_page' not in st.session_state:
                        st.session_state.daily_sales_page = 1
                    
                    total_rows = len(df)
                    total_pages = (total_rows - 1) // PAGE_SIZE + 1 if total_rows > 0 else 1

                    start_idx = (st.session_state.daily_sales_page - 1) * PAGE_SIZE
                    end_idx = start_idx + PAGE_SIZE
                    df_paged = df.iloc[start_idx:end_idx]

                    def calc_row_roi_margin(row):
                        try:
                            revenue = row["전체 매출액"]
                            profit = row["일일 순이익금"]

                            if selected_product_filter != "(상품을 선택해주세요)":
                                product_info = supabase.table("products").select("*").eq("product_name", selected_product_filter).execute()
                                product_data = product_info.data[0] if product_info.data else {}

                                quantity_for_calc = product_data.get("quantity", 1) or 1
                                unit_purchase_cost = product_data.get("purchase_cost", 0) / quantity_for_calc
                                unit_logistics = product_data.get("logistics_cost", 0) / quantity_for_calc
                                unit_customs = product_data.get("customs_duty", 0) / quantity_for_calc
                                unit_etc = product_data.get("etc_cost", 0) / quantity_for_calc

                                total_sales_qty = row["전체 수량"]
                                purchase_cost_total = unit_purchase_cost * total_sales_qty
                                logistics_total = unit_logistics * total_sales_qty
                                customs_total = unit_customs * total_sales_qty
                                etc_total = unit_etc * total_sales_qty

                                total_cost_row = purchase_cost_total + logistics_total + customs_total + etc_total
                            else:
                                total_cost_row = 0

                            roi_row = (profit / total_cost_row * 100) if total_cost_row else 0
                            margin_row = (profit / revenue * 100) if revenue else 0

                            return pd.Series({"ROI": roi_row, "마진율": margin_row})
                        except Exception as e:
                            st.error(f"ROI/마진율 계산 중 오류 발생: {e}")
                            return pd.Series({"ROI": 0.0, "마진율": 0.0})

                    roi_margin_df = df_paged.apply(calc_row_roi_margin, axis=1)
                    df_paged = pd.concat([df_paged.reset_index(drop=True), roi_margin_df], axis=1)

                    df_display = df_paged.copy()
                    
                    df_display = df_display.rename(columns={
                        "날짜": "날짜",
                        "상품명": "상품명",
                        "전체 수량": "전체 수량",
                        "전체 매출액": "전체 매출액",
                        "광고 수량": "광고 수량",
                        "광고 매출액": "광고 매출액",
                        "자연 수량": "자연 수량",
                        "자연 매출액": "자연 매출액",
                        "일일 광고비": "일일 광고비",
                        "일일 순이익금": "일일 순이익금",
                        "ROI(%)": "ROI(%)",
                        "마진율(%)": "마진율(%)",
                        "ROI": "ROI(%)_재계산",
                        "마진율": "마진율(%)_재계산"
                    })
                    df_display['날짜'] = df_display['날짜'].dt.strftime('%Y-%m-%d')

                    display_cols = [
                        "날짜", "상품명", "전체 수량", "전체 매출액",
                        "광고 수량", "광고 매출액", "자연 수량", "자연 매출액",
                        "일일 광고비", "일일 순이익금", "ROI(%)", "마진율(%)",
                        "ROI(%)_재계산", "마진율(%)_재계산"
                    ]
                    display_cols = [c for c in display_cols if c in df_display.columns]
                    df_display = df_display[display_cols]

                    num_cols = [
                        "전체 수량", "전체 매출액",
                        "광고 수량", "광고 매출액",
                        "자연 수량", "자연 매출액",
                        "일일 광고비", "일일 순이익금"
                    ]
                    for col in num_cols:
                        if col in df_display.columns:
                            df_display[col] = df_display[col].apply(
                                lambda x: format_number(x) if pd.notnull(x) else ""
                            )

                    for col in ["ROI(%)", "마진율(%)", "ROI(%)_재계산", "마진율(%)_재계산"]:
                        if col in df_display.columns:
                            df_display[col] = df_display[col].apply(
                                lambda x: f"{x:.2f}" if pd.notnull(x) else ""
                            )

                    st.dataframe(df_display, use_container_width=True)

                    col_prev, col_page, col_next = st.columns([1, 2, 1])
                    with col_prev:
                        if st.button("이전", disabled=(st.session_state.daily_sales_page <= 1), key="prev_page_btn"):
                            st.session_state.daily_sales_page -= 1
                            st.rerun()
                    with col_page:
                        st.markdown(f"<div style='text-align:center; font-size:16px; margin-top:5px;'>페이지 {st.session_state.daily_sales_page} / {total_pages}</div>", 
                                    unsafe_allow_html=True)
                    with col_next:
                        if st.button("다음", disabled=(st.session_state.daily_sales_page >= total_pages), key="next_page_btn"):
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
