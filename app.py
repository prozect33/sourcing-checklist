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

# --- [New Functions for tab4] ---
def calculate_profit_for_period(start_date: datetime.date, end_date: datetime.date, supabase: Client) -> int:
    """Supabase에서 지정된 기간 동안의 모든 상품의 총 순이익을 계산합니다."""
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()
    
    try:
        # daily_sales 테이블에서 지정된 날짜 범위의 daily_profit만 가져옴
        response = supabase.table("daily_sales").select("daily_profit") \
            .gte("date", start_str) \
            .lte("date", end_str) \
            .execute()

        if response.data:
            df = pd.DataFrame(response.data)
            # daily_profit이 int/float형인지 확인하고 합산
            profit_sum = df["daily_profit"].sum() if "daily_profit" in df.columns else 0
            return int(profit_sum)
        return 0
    except Exception as e:
        # Supabase 연동 오류 발생 시 기본값 0 반환
        return 0

def get_date_range(period: str) -> tuple[datetime.date, datetime.date]:
    """오늘을 포함한 지정된 기간의 시작일과 종료일(오늘)을 반환합니다."""
    today = datetime.date.today()
    
    if period == "today": # 오늘
        return today, today
    elif period == "yesterday": # 어제
        yesterday = today - datetime.timedelta(days=1)
        return yesterday, yesterday
    elif period == "7days":
        # 오늘 포함 7일: 오늘 - 6일 = 시작일
        start_date = today - datetime.timedelta(days=6)
        return start_date, today
    elif period == "30days":
        # 오늘 포함 30일: 오늘 - 29일 = 시작일
        start_date = today - datetime.timedelta(days=29)
        return start_date, today
    elif period == "90days": # 90일 (기존 3months 대체)
        # 오늘 포함 90일: 오늘 - 89일 = 시작일
        start_date = today - datetime.timedelta(days=89) 
        return start_date, today
    elif period == "180days": # 180일
        start_date = today - datetime.timedelta(days=179)
        return start_date, today
    elif period == "365days": # 365일
        start_date = today - datetime.timedelta(days=364)
        return start_date, today
    else:
        return today, today # 기본값

# Note: display_profit_metric 함수는 박스형 출력 요청이 없어 제거되었습니다.
# --- [End of New Functions] ---

def main():
    if 'show_product_info' not in st.session_state:
        st.session_state.show_product_info = False

    # 원본 파일의 코드를 4개의 탭으로 분리했습니다.
    tab1, tab2, tab3, tab4 = st.tabs(["간단 마진계산기", "상품 정보 입력", "일일정산", "판매현황"])

    with tab1:  # 간단 마진 계산기 탭

        # 🔹 바깥 2컬럼: 왼쪽은 설정값 패널(가짜 사이드바), 오른쪽은 기존 계산 UI
        c1, c2, c3, c4, c5 = st.columns([1, 1, 2, 1, 1])

        # === 1) 탭1에서만 보이는 설정값 패널 ===
        with c2:
            st.markdown("### 🛠️ 설정값")

            config["FEE_RATE"]       = st.number_input("수수료율 (%)",       value=config.get("FEE_RATE", 10.8), step=0.1, format="%.2f")
            config["AD_RATE"]        = st.number_input("광고비율 (%)",       value=config.get("AD_RATE", 20.0),  step=0.1, format="%.2f")
            config["INOUT_COST"]     = st.number_input("입출고비용 (원)",    value=int(config.get("INOUT_COST", 3000)), step=100)
            config["PICKUP_COST"]    = st.number_input("회수비용 (원)",      value=int(config.get("PICKUP_COST", 0)),    step=100)
            config["RESTOCK_COST"]   = st.number_input("재입고비용 (원)",    value=int(config.get("RESTOCK_COST", 0)),   step=100)
            config["RETURN_RATE"]    = st.number_input("반품률 (%)",         value=config.get("RETURN_RATE", 0.0), step=0.1, format="%.2f")
            config["ETC_RATE"]       = st.number_input("기타비용률 (%)",     value=config.get("ETC_RATE", 2.0),  step=0.1, format="%.2f")
            config["EXCHANGE_RATE"]  = st.number_input("위안화 환율",        value=int(config.get("EXCHANGE_RATE", 300)), step=1)
            config["PACKAGING_COST"] = st.number_input("포장비 (원)",        value=int(config.get("PACKAGING_COST", 0)), step=100)
            config["GIFT_COST"]      = st.number_input("사은품 비용 (원)",   value=int(config.get("GIFT_COST", 0)),      step=100)

            if st.button("📂 기본값으로 저장", key="save_settings_tab1"):
                for k, v in config.items():
                    supabase.table("settings").upsert({"key": k, "value": v}).execute()
                st.success("Supabase에 저장 완료 ✅")

        # === 2) 오른쪽: 기존 탭1 UI (계산기) 그대로 ===
        with c4:
                st.markdown("<div style='margin-left:40px;'>", unsafe_allow_html=True)
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
                        etc_cost = round(sell_price_val * config['ETC_RATE'] / 100)
                        packaging_cost = round(config['PACKAGING_COST'] * vat)
                        gift_cost = round(config['GIFT_COST'] * vat)
                        supply_price = sell_price_val / vat
                        C_total_fixed_cost = fee + inout_cost + packaging_cost + gift_cost
                        raw_cost2 = sell_price_val \
                                    - supply_price * (target_margin / 100) \
                                    - C_total_fixed_cost
                        target_cost = max(0, int(raw_cost2))
                        yuan_cost = round((target_cost / config['EXCHANGE_RATE']) , 2)
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
                st.markdown("</div>", unsafe_allow_html=True)

            # --- 오른쪽: 결과 영역 ---
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
                    margin_profit = sell_price - (unit_cost + fee + inout + packaging + gift + etc)
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


    with tab2: # 원본 파일의 '세부 마진 계산기' 탭 내부의 '상품 정보 입력' 내용
        st.subheader("상품 정보 입력")
        
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

                            if old_name != new_name:
                                # ✅ 이름이 바뀐 경우: 기존 행 update
                                supabase.rpc(
                                    "update_product_by_old_name",
                                    {"old_name": old_name, "p_data": data_to_update}
                                ).execute()

                                # ✅ daily_sales 테이블도 이름 동기화
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

    with tab3: # 원본 파일의 '세부 마진 계산기' 탭 내부의 '일일 정산' 내용
        st.subheader("일일 정산")
        
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
        st.number_input("광고 매출액", step=1000, key="ad_revenue")
        st.number_input("광고비용", step=1000, key="ad_cost")

        # --- 일일 순이익 계산 및 출력 ---
        if selected_product_name != "상품을 선택해주세요" and product_data:
            current_total_sales_qty = st.session_state.total_sales_qty
            current_total_revenue = st.session_state.total_revenue
            current_ad_cost = st.session_state.ad_cost

            # 1. 단위 비용 계산
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
            
            # --- 일일 순이익금 출력 ---
            st.metric(label="일일 순이익금", value=f"{daily_profit:,}원")

            # --- 일일 순이익 계산 내역 ---
            if selected_product_name != "상품을 선택해주세요" and product_data:
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
                      - 판매 수수료 (VAT 포함): {format_number(fee_cost)}원<br>
                      - 상품 매입원가: {format_number(purchase_cost_total)}원<br>
                      - 입출고/배송비 (VAT 포함): {format_number(inout_shipping_cost_total)}원<br>
                      - 물류비: {format_number(logistics_cost_total)}원<br>
                      - 관세: {format_number(customs_cost_total)}원<br>
                      - 기타 비용: {format_number(etc_cost_total)}원<br>
                      - 광고비 (VAT 포함): {format_number(ad_cost_total)}원
                    </small>
                    """, unsafe_allow_html=True
                )
            
            st.markdown("---")

            # --- 일일 판매 기록 저장 로직
            if st.button("판매 기록 저장"):
                if selected_product_name == "상품을 선택해주세요":
                    st.error("상품을 먼저 선택해야 판매 기록을 저장할 수 있습니다.")
                elif st.session_state.total_sales_qty == 0 or st.session_state.total_revenue == 0:
                    st.error("전체 판매 수량과 매출액을 입력해야 저장할 수 있습니다.")
                else:
                    try:
                        # 이미 계산된 daily_profit을 포함하여 저장
                        data_to_save = {
                            "date": report_date.isoformat(),
                            "product_name": selected_product_name,
                            "daily_sales_qty": st.session_state.total_sales_qty,
                            "daily_revenue": st.session_state.total_revenue,
                            "ad_sales_qty": st.session_state.ad_sales_qty,
                            "ad_revenue": st.session_state.ad_revenue,
                            # 자연 판매 수량/매출액 계산
                            "organic_sales_qty": st.session_state.total_sales_qty - st.session_state.ad_sales_qty,
                            "organic_revenue": st.session_state.total_revenue - st.session_state.ad_revenue,
                            "daily_ad_cost": st.session_state.ad_cost,
                            "daily_profit": daily_profit,  # 계산된 순이익 저장
                        }

                        # ✅ 2.txt 원본과 동일하게 p_data로 RPC 호출
                        supabase.rpc(
                            "upsert_daily_sales",
                            {"p_data": data_to_save}
                        ).execute()

                        st.success(f"{report_date} 일일 판매 기록이 저장되었습니다! (순이익: {format_number(daily_profit)}원)")

                        # ⚠️ 여기서 session_state를 직접 0으로 초기화하지 않는다.
                        # 필요하면 나중에 별도 '리셋' 버튼에서 reset_inputs() 같이 처리하는 쪽으로.

                    except Exception as e:
                        st.error(f"판매 기록 저장 중 오류가 발생했습니다: {e}")

    with tab4: # 원본 파일의 '세부 마진 계산기' 탭 내부의 '판매 현황' 내용
        
        # --- [기존 코드 유지] 🗓️ 기간별 모든 상품 순이익 조회 ---
        st.markdown("#### 🗓️ 기간별 모든 상품 순이익 조회")
        # 오늘 날짜
        today = datetime.date.today()
        # 기본값을 오늘부터 일주일(7일)로 변경
        last_7days_start, _ = get_date_range("7days")
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date_input = st.date_input("시작 날짜", value=last_7days_start, # 7일 전을 기본값으로 사용
                                             key="profit_start_date")
        with date_col2:
            end_date_input = st.date_input("종료 날짜", value=today, key="profit_end_date")
            
        custom_profit = 0
        if start_date_input and end_date_input:
            if start_date_input > end_date_input:
                st.warning("시작 날짜는 종료 날짜보다 빠를 수 없습니다.")
            else:
                try:
                    custom_profit = calculate_profit_for_period(start_date_input, end_date_input, supabase)
                except Exception as e:
                    st.error(f"지정 기간 순이익 계산 중 오류가 발생했습니다: {e}")

        # 결과 표시 (1번 아래에 배치)
        st.metric(label=f"선택 기간 ({start_date_input} ~ {end_date_input}) 모든 상품 총 순이익", value=f"{format_number(custom_profit)}원")

        # --- 페이지네이션 초기화 및 설정 --- (기존 코드 유지)
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
            on_change=reset_page # 필터 변경 시 페이지 1로 리셋
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
                    
                    # 1. 총 합산 계산
                    total_profit_sum = df['daily_profit'].sum()
                    total_sales_qty = df['daily_sales_qty'].sum()
                    total_revenue_sum = df['daily_revenue'].sum()
                    
                    # 선택된 상품의 단가 정보를 로드 (ROI/마진율 계산에 필요)
                    product_data = {}
                    response_prod = supabase.table("products").select("*").eq("product_name", selected_product_filter).execute()
                    if response_prod.data:
                        product_data = response_prod.data[0]
                    
                    # 총 순이익금 표시
                    st.metric(label=f"총 순이익금 ({selected_product_filter})", value=f"{total_profit_sum:,}원")
                    
                    try:
                        # ROI / 마진율 계산에 필요한 총 수량과 단가 로드
                        total_quantity = product_data.get("quantity", 0) or 1
                        quantity_for_calc = total_quantity if total_quantity > 0 else 1
                        unit_purchase_cost = product_data.get("purchase_cost", 0) / quantity_for_calc
                        unit_logistics = product_data.get("logistics_cost", 0) / quantity_for_calc
                        unit_customs = product_data.get("customs_duty", 0) / quantity_for_calc
                        unit_etc = product_data.get("etc_cost", 0) / quantity_for_calc
                        inout_shipping_cost = product_data.get("inout_shipping_cost", 0)
                        fee_rate_db = product_data.get("fee", 0.0)

                        # ROI 분모 = 매입 + 물류 + 관세 + 기타 (총 순이익 블록과 동일)
                        purchase_cost_total = unit_purchase_cost * total_sales_qty
                        logistics_total = unit_logistics * total_sales_qty
                        customs_total = unit_customs * total_sales_qty
                        etc_total = unit_etc * total_sales_qty
                        total_cost_sum = purchase_cost_total + logistics_total + customs_total + etc_total # 이익이 아닌 총 원가/비용

                        # ROI / 마진율 계산 (총 순이익 블록)
                        roi = (total_profit_sum / total_cost_sum * 100) if total_cost_sum else 0
                        margin = (total_profit_sum / total_revenue_sum * 100) if total_revenue_sum else 0
                        
                        # 표시 블록 (세로 정렬)
                        st.markdown(
                            f"""
                            <div style='color:gray; font-size:14px; line-height:1.6;'>
                                {total_quantity:,} / {total_sales_qty:,} (전체 수량 / 판매 수량)<br>
                                ROI: {roi:.2f}%<br>
                                마진율: {margin:.2f}%
                            </div>
                            """, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"ROI/마진율 계산 중 오류 발생: {e}")
                    
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

                # 3. 컬럼명 변경 및 포맷팅
                df_display = df_paged.rename(columns={
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
                    # ROI / 마진율은 그대로 사용 (컬럼명 동일)
                })
                df_display['날짜'] = df_display['날짜'].dt.strftime('%Y-%m-%d')

                # --- 최종 표시 컬럼 순서 지정 (번호 제거, 요청 순서대로) ---
                display_cols = [
                    '날짜',
                    '상품명',
                    '전체 매출액',
                    '광고 매출액',
                    '자연 매출액',
                    '일일 광고비',
                    '일일 순이익금'
                ]

                # --- 숫자 컬럼 포맷팅 (금액, 수량) ---
                money_cols = ['전체 매출액', '광고 매출액', '자연 매출액', '일일 광고비', '일일 순이익금']
                for col in money_cols:
                    if col in df_display.columns:
                        df_display[col] = (
                            df_display[col]
                            .fillna(0) # NaN 값을 0으로 채움
                            .apply(lambda x: f"{int(x):,}") # 정수 포맷팅
                        )
                
                # ROI/마진율 포맷팅
                for col in ['ROI', '마진율']:
                     if col in df_display.columns:
                        df_display[col] = (
                            df_display[col]
                            .fillna(0.0) # NaN 값을 0.0으로 채움
                            .apply(lambda x: f"{x:.2f}%") # 소수점 두 자리 및 % 표시
                        )
                
                # 수량 포맷팅
                qty_cols = ['전체 수량', '광고 수량', '자연 수량']
                for col in qty_cols:
                    if col in df_display.columns:
                        df_display[col] = (
                            df_display[col]
                            .fillna(0)
                            .astype(int)
                            .apply(lambda x: f"{x:,}개")
                        )
                
                # 4. 최종 데이터프레임 출력
                st.dataframe(df_display[display_cols], hide_index=True)
                
                # 5. 페이지네이션 버튼
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
    # 메인 실행 전에 탭 1의 세션 상태 키 초기화 보장
    if "sell_price_raw" not in st.session_state: st.session_state["sell_price_raw"] = ""
    if "unit_yuan" not in st.session_state: st.session_state["unit_yuan"] = ""
    if "unit_won" not in st.session_state: st.session_state["unit_won"] = ""
    if "qty_raw" not in st.session_state: st.session_state["qty_raw"] = ""
    main()
