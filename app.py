import streamlit as st
import json
import os
import math

# 페이지 설정 및 여백 조정
st.set_page_config(page_title="간단 마진 계산기", layout="wide")
st.markdown(
    """
    <style>
    /* 본문 영역 상단 여백 */
    .block-container {
        padding-top: 0.5rem !important;
    }
    /* 사이드바 헤더 위 공백 제거 via HTML header hack located below */
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
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
        "PACKAGING_COST": 500,    # 포장비 (원)
        "GIFT_COST": 1000         # 사은품 비용 (원)
    }

def load_config():
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, "r") as f:
                data = json.load(f)
                base = default_config()
                for k, v in data.items():
                    if isinstance(v, (str, int, float)) and str(v).replace('.', '', 1).isdigit():
                        base[k] = float(v)
                    else:
                        base[k] = v
                return base
        except:
            return default_config()
    return default_config()

def save_config(config):
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        json.dump(config, f)

def format_number(val):
    return f"{int(val):,}" if float(val).is_integer() else f"{val:,.2f}"

def format_input_value(val):
    return str(int(val)) if float(val).is_integer() else str(val)

def reset_inputs():
    for key in ["sell_price_raw", "unit_yuan", "unit_won", "qty_raw"]:
        if key in st.session_state:
            st.session_state[key] = ""

# 설정값 불러오기
config = load_config()

# 사이드바: HTML 헤더로 상단 여백 제거
st.sidebar.markdown(
    '<h2 style="margin-top:0rem; margin-bottom:0.5rem;">🛠️ 설정값</h2>',
    unsafe_allow_html=True
)
# 나머지 입력 필드
for key, label in [
    ("FEE_RATE", "수수료율 (%)"),
    ("AD_RATE", "광고비율 (%)"),
    ("INOUT_COST", "입출고비용 (원)"),
    ("PICKUP_COST", "회수비용 (원)"),
    ("RESTOCK_COST", "재입고비용 (원)"),
    ("RETURN_RATE", "반품률 (%)"),
    ("ETC_RATE", "기타비용률 (%)"),
    ("EXCHANGE_RATE", "위안화 환율"),
    ("PACKAGING_COST", "포장비 (원)"),
    ("GIFT_COST", "사은품 비용 (원)")
]:
    config[key] = st.sidebar.text_input(label, value=format_input_value(config.get(key, 0)), key=key)

if st.sidebar.button("📂 기본값으로 저장"):
    save_config(config)
    st.sidebar.success("기본값이 저장되었습니다.")

# 탭 구성
tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

# 탭1: 간단 마진 계산기
with tab1:
    left, right = st.columns(2)

    with left:
        st.subheader("판매정보 입력")
        sell_price_raw = st.text_input("판매가", key="sell_price_raw", value=st.session_state.get("sell_price_raw", ""))
        margin_display = st.empty()

        if sell_price_raw:
            try:
                sell_price = int(float(sell_price_raw))
                vat = 1.1
                target_margin = 50.0

                # 각 항목 VAT 포함 계산
                fee = round((sell_price * config['FEE_RATE'] / 100) * vat)
                ad = round((sell_price * config['AD_RATE'] / 100) * vat)
                inout = round(config['INOUT_COST'] * vat)
                pickup = round(config['PICKUP_COST'] * vat)
                restock = round(config['RESTOCK_COST'] * vat)
                return_cost = round((pickup + restock) * config['RETURN_RATE'])
                etc = round((sell_price * config['ETC_RATE'] / 100) * vat)
                packaging = round(config['PACKAGING_COST'] * vat)
                gift = round(config['GIFT_COST'] * vat)
                supply_price = sell_price / vat

                # 이분 탐색으로 최대 허용 원가
                left_b, right_b = 0, sell_price
                optimum_cost = 0
                while left_b <= right_b:
                    mid = (left_b + right_b) // 2
                    cost_mid = round(mid * vat) + fee + inout + packaging + gift
                    margin_mid = (sell_price - cost_mid) / supply_price * 100
                    if margin_mid < target_margin:
                        right_b = mid - 1
                    else:
                        optimum_cost = mid
                        left_b = mid + 1

                yuan = math.ceil(optimum_cost / config['EXCHANGE_RATE'])
                profit = sell_price - (round(optimum_cost * vat) + fee + inout + packaging + gift)

                margin_display.markdown(f"""
<div style='color:#f63366; font-size:15px;'>
  마진율 {int(target_margin)}% 기준: {format_number(optimum_cost)}원 ({yuan}위안) / 마진: {format_number(profit)}원
</div>
""", unsafe_allow_html=True)
            except:
                margin_display.empty()

        # 원/위안 비용 및 수량 입력 레이아웃 유지
        col1, col2 = st.columns(2)
        with col1:
            unit_yuan = st.text_input("위안화 (¥)", key="unit_yuan", value=st.session_state.get("unit_yuan", ""))
        with col2:
            unit_won = st.text_input("원화 (₩)", key="unit_won", value=st.session_state.get("unit_won", ""))
        qty = st.text_input("수량", key="qty_raw", value=st.session_state.get("qty_raw", "1"))

        calc_btn, reset_btn = st.columns(2)
        calc = calc_btn.button("계산하기")
        reset_btn.button("리셋", on_click=reset_inputs)

    with right:
        if calc:
            try:
                sell_price = int(float(sell_price_raw))
                qty_val = int(float(qty))
            except:
                st.warning("판매가와 수량을 정확히 입력해주세요.")
                st.stop()

            # 단위 원가 변환
            if unit_yuan:
                unit_val = round(float(unit_yuan) * config['EXCHANGE_RATE'])
                cost_disp = f"{format_number(unit_val)}원 ({unit_yuan}위안)"
            elif unit_won:
                unit_val = round(float(unit_won))
                cost_disp = f"{format_number(unit_val)}원"
            else:
                unit_val = 0
                cost_disp = "0원"

            vat = 1.1
            unit_cost = round(unit_val * vat)
            fee2 = round((sell_price * config['FEE_RATE'] / 100) * vat)
            ad2 = round((sell_price * config['AD_RATE'] / 100) * vat)
            inout2 = round(config['INOUT_COST'] * vat)
            pickup2 = round(config['PICKUP_COST'] * vat)
            restock2 = round(config['RESTOCK_COST'] * vat)
            return2 = round((pickup2 + restock2) * config['RETURN_RATE'])
            etc2 = round((sell_price * config['ETC_RATE'] / 100) * vat)
            packaging2 = round(config['PACKAGING_COST'] * vat)
            gift2 = round(config['GIFT_COST'] * vat)

            total = unit_cost + fee2 + ad2 + inout2 + return2 + etc2 + packaging2 + gift2
            min_profit = sell_price - total
            supply_val = sell_price / vat
            margin_money = sell_price - (unit_cost + fee2 + inout2 + packaging2 + gift2)
            margin_ratio = round(margin_money / supply_val * 100, 2)
            roi = round(min_profit / unit_cost * 100, 2) if unit_cost else 0
            roi_margin = round(margin_money / unit_cost * 100, 2) if unit_cost else 0

            st.markdown("### 📊 계산 결과")
            for bg, stats in [
                ("#e8f5e9", [("💰 마진", f"{format_number(margin_money)}원"), ("📈 마진율", f"{margin_ratio:.2f}%"), ("💹 투자수익률", f"{roi_margin:.2f}%")]),
                ("#e3f2fd", [("🧮 최소 이익", f"{format_number(min_profit)}원"), ("📉 최소마진율", f"{(min_profit/supply_val*100):.2f}%"), ("🧾 투자수익률", f"{roi:.2f}%")])
            ]:
                st.markdown(f"""
<div style='display:grid;grid-template-columns:1fr 1fr 1fr;background:{bg};padding:12px;border-radius:10px;gap:8px;margin-bottom:12px;'>
  <div><div style='font-weight:bold;font-size:15px;'>{stats[0][0]}</div><div style='font-size:15px;'>{stats[0][1]}</div></div>
  <div><div style='font-weight:bold;font-size:15px;'>{stats[1][0]}</div><div style='font-size:15px;'>{stats[1][1]}</div></div>
  <div><div style='font-weight:bold;font-size:15px;'>{stats[2][0]}</div><div style='font-size:15px;'>{stats[2][1]}</div></div>
</div>
""", unsafe_allow_html=True)

            st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
            with st.expander("📦 상세 비용 항목 보기", expanded=False):
                st.markdown(f"**판매가:** {format_number(sell_price)}원")
                st.markdown(f"**원가:** {format_number(unit_cost)}원 ({cost_disp})")
                st.markdown(f"**수수료:** {format_number(fee2)}원")
                st.markdown(f"**광고비:** {format_number(ad2)}원")
                st.markdown(f"**입출고비용:** {format_number(inout2)}원")
                st.markdown(f"**회수비용:** {format_number(pickup2)}원")
                st.markdown(f"**재입고비용:** {format_number(restock2)}원")
                st.markdown(f"**반품비용:** {format_number(return2)}원")
                st.markdown(f"**기타비용:** {format_number(etc2)}원")
                st.markdown(f"**포장비:** {format_number(packaging2)}원")
                st.markdown(f"**사은품 비용:** {format_number(gift2)}원")
                st.markdown(f"**총비용:** {format_number(total)}원")
                st.markdown(f"**공급가액:** {format_number(round(supply_val))}원")
                st.markdown(f"**최소 이익:** {format_number(min_profit)}원")
                st.markdown(f"**최소마진율:** {(min_profit/supply_val*100):.2f}%")
                st.markdown(f"**투자수익률:** {roi:.2f}%")

# 탭2: 준비 중
with tab2:
    st.subheader("세부 마진 계산기")
    st.info("준비 중입니다...")
