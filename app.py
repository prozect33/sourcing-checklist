import streamlit as st
import json
import os
import math

# 페이지 설정 및 여백 조정
st.set_page_config(page_title="간단 마진 계산기", layout="wide")
st.markdown(
    """
    <style>
      /* 1) 헤더(로고) 통째로 제거 */
      [data-testid="stSidebarHeader"] {
        display: none !important;
      }
      /* 2) 사이드바 위젯 시작 위치를 15px 아래로 내리기 */
      [data-testid="stSidebarContent"] {
        padding-top: 15px !important;
      }
      /* 3) “🛠️ 설정값” 헤더와 첫 번째 입력 칸 사이 간격 조정 */
      [data-testid="stHeading"] {
        margin-bottom: 15px !important;
      }
      /* number_input 옆 +/– 버튼 숨기기 */
      [data-testid="stNumberInput"] button {
        display: none !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

DEFAULT_CONFIG_FILE = "default_config.json"

def default_config():
    return {
        "FEE_RATE": 10.8,
        "AD_RATE": 20.0,
        "INOUT_COST": 3000,
        "PICKUP_COST": 1500,
        "RESTOCK_COST": 500,
        "RETURN_RATE": 0.1,
        "ETC_RATE": 2.0,
        "EXCHANGE_RATE": 350,
        "PACKAGING_COST": 500,
        "GIFT_COST": 1000
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
    return f"{int(val):,}" if float(val).is_integer() else f"{val:,.2f}"

def reset_inputs():
    for key in ["sell_price_raw", "unit_yuan", "unit_won", "qty_raw"]:
        if key in st.session_state:
            st.session_state[key] = ""

config = load_config()

# 사이드바: 설정값
st.sidebar.header("🛠️ 설정값")
config["FEE_RATE"]      = st.sidebar.number_input("수수료율 (%)", value=config["FEE_RATE"], step=0.1, format="%.2f")
config["AD_RATE"]       = st.sidebar.number_input("광고비율 (%)", value=config["AD_RATE"], step=0.1, format="%.2f")
config["INOUT_COST"]    = st.sidebar.number_input("입출고비용 (원)", value=int(config["INOUT_COST"]), step=100)
config["PICKUP_COST"]   = st.sidebar.number_input("회수비용 (원)", value=int(config["PICKUP_COST"]), step=100)
config["RESTOCK_COST"]  = st.sidebar.number_input("재입고비용 (원)", value=int(config["RESTOCK_COST"]), step=100)
config["RETURN_RATE"]   = st.sidebar.number_input("반품률 (%)", value=config["RETURN_RATE"], step=0.1, format="%.2f")
config["ETC_RATE"]      = st.sidebar.number_input("기타비용률 (%)", value=config["ETC_RATE"], step=0.1, format="%.2f")
config["EXCHANGE_RATE"] = st.sidebar.number_input("위안화 환율", value=int(config["EXCHANGE_RATE"]), step=1)
config["PACKAGING_COST"]= st.sidebar.number_input("포장비 (원)", value=int(config["PACKAGING_COST"]), step=100)
config["GIFT_COST"]     = st.sidebar.number_input("사은품 비용 (원)", value=int(config["GIFT_COST"]), step=100)

if st.sidebar.button("📂 기본값으로 저장"):
    save_config(config)
    st.sidebar.success("기본값이 저장되었습니다.")

# 탭 구성
tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

with tab1:
    left, right = st.columns(2)

    with left:
        st.subheader("판매정보 입력")
        sell_price_raw = st.text_input("판매가 (원)", value=st.session_state.get("sell_price_raw", ""))
        unit_yuan      = st.text_input("위안화 (¥)", value=st.session_state.get("unit_yuan", ""))
        unit_won       = st.text_input("원화 (₩)", value=st.session_state.get("unit_won", ""))
        qty_raw        = st.text_input("수량", value=st.session_state.get("qty_raw", "1"))

        calc_col, reset_col = st.columns(2)
        result_btn = calc_col.button("계산하기")
        reset_col.button("리셋", on_click=reset_inputs)

    with right:
        if result_btn:
            # 입력 파싱
            try:
                sell_price = int(float(sell_price_raw))
                qty        = int(float(qty_raw))
            except:
                st.warning("판매가와 수량을 정확히 입력해주세요.")
                st.stop()

            # 단위당 원가 산정
            if unit_yuan:
                unit_cost_val = round(float(unit_yuan) * config["EXCHANGE_RATE"])
                cost_display  = f"{format_number(unit_cost_val)}원 ({unit_yuan}위안)"
            elif unit_won:
                unit_cost_val = round(float(unit_won))
                cost_display  = f"{format_number(unit_cost_val)}원"
            else:
                unit_cost_val = 0
                cost_display  = "0원"

            vat = 1.1

            # 1) 단위당 비용 항목 계산
            unit_costs = {
                "unit_cost":  round(unit_cost_val * vat),
                "fee":        round((sell_price * config["FEE_RATE"] / 100) * vat),
                "ad":         round((sell_price * config["AD_RATE"]  / 100) * vat),
                "inout":      round(config["INOUT_COST"] * vat),
                "pickup":     round(config["PICKUP_COST"] * vat),
                "restock":    round(config["RESTOCK_COST"] * vat),
                "etc":        round((sell_price * config["ETC_RATE"]  / 100) * vat),
                "packaging":  round(config["PACKAGING_COST"] * vat),
                "gift":       round(config["GIFT_COST"] * vat),
            }
            # 반품비용은 pickup+restock 에 반품률 적용
            unit_costs["return"] = round(
                (unit_costs["pickup"] + unit_costs["restock"]) * (config["RETURN_RATE"] / 100)
            )

            # 2) qty 곱해서 총합 계산
            total_costs = {name: cost * qty for name, cost in unit_costs.items()}

            # 3) 매출·비용·이익
            total_rev  = sell_price * qty
            total_cost = sum(total_costs.values())
            profit     = total_rev - total_cost

            # 4) 공급가액(부가세 제외) 및 마진·ROI
            supply_price_total = (sell_price / vat) * qty
            margin_profit      = total_rev - (
                total_costs["unit_cost"]
                + total_costs["fee"]
                + total_costs["inout"]
                + total_costs["packaging"]
                + total_costs["gift"]
            )
            margin_ratio = round(margin_profit / supply_price_total * 100, 2) if supply_price_total else 0
            roi_total    = round(profit / total_costs["unit_cost"] * 100, 2) if total_costs["unit_cost"] else 0
            roi_margin   = round(margin_profit / total_costs["unit_cost"] * 100, 2) if total_costs["unit_cost"] else 0

            # 5) 화면 출력
            st.markdown("### 📊 계산 결과")
            st.write(f"**수량:** {qty}개")
            st.write(f"**총매출:** {format_number(total_rev)}원")
            st.write(f"**총비용:** {format_number(total_cost)}원")
            st.write(f"**총이익:** {format_number(profit)}원")
            st.write(f"**마진율:** {margin_ratio:.2f}%")
            st.write(f"**투자수익률 (ROI):** {roi_total:.2f}%")
            st.write(f"**마진 기준 ROI:** {roi_margin:.2f}%")

            with st.expander("📦 상세 비용 항목 보기", expanded=False):
                st.write(f"**판매가(총):** {format_number(total_rev)}원")
                st.write(f"**원가(총):** {format_number(total_costs['unit_cost'])}원 ({cost_display} × {qty})")
                st.write(f"**수수료(총):** {format_number(total_costs['fee'])}원")
                st.write(f"**광고비(총):** {format_number(total_costs['ad'])}원")
                st.write(f"**입출고비용(총):** {format_number(total_costs['inout'])}원")
                st.write(f"**반품비용(총):** {format_number(total_costs['return'])}원")
                st.write(f"**기타비용(총):** {format_number(total_costs['etc'])}원")
                st.write(f"**포장비(총):** {format_number(total_costs['packaging'])}원")
                st.write(f"**사은품(총):** {format_number(total_costs['gift'])}원")
                st.write(f"**총비용:** {format_number(total_cost)}원")
                st.write(f"**공급가액 (총):** {format_number(round(supply_price_total))}원")
                st.write(f"**총이익:** {format_number(profit)}원")
                st.write(f"**마진율:** {margin_ratio:.2f}%")
                st.write(f"**투자수익률 (ROI):** {roi_total:.2f}%")

with tab2:
    st.subheader("세부 마진 계산기")
    st.info("준비 중입니다...")
