import streamlit as st
import json
import os
import math

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

DEFAULT_CONFIG_FILE = "default_config.json"
default_config = {
    "FEE_RATE": 10.8,
    "AD_RATE": 20.0,
    "INOUT_COST": 3000,
    "PICKUP_COST": 1500,
    "RESTOCK_COST": 500,
    "RETURN_RATE": 0.1,
    "ETC_RATE": 2.0,
    "EXCHANGE_RATE": 350,
    "PACKAGING_COST": 500,
    "GIFT_COST": 0
}

def load_config():
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, "r") as f:
                data = json.load(f)
                return {k: v for k, v in data.items()}
        except:
            return default_config.copy()
    else:
        return default_config.copy()

config = load_config()
# 기본값에 없는 키 채워넣기
for k, v in default_config.items():
    if k not in config:
        config[k] = v

def save_config(cfg):
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        json.dump(cfg, f)

def format_number(val):
    return f"{int(val):,}" if float(val).is_integer() else f"{val:,.2f}"

def format_input_value(val):
    return str(int(val)) if float(val).is_integer() else str(val)

def reset_inputs():
    for key in ["sell_price_raw", "unit_yuan", "unit_won", "qty_raw"]:
        if key in st.session_state:
            st.session_state[key] = ""

# ─── 사이드바: 문자열 입력 → float 변환 ───
st.sidebar.header("🛠️ 설정값")
for key, label in [
    ("FEE_RATE", "수수료율 (%)"),
    ("AD_RATE", "광고비율 (%)"),
    ("INOUT_COST", "입출고비용 (원)"),
    ("PICKUP_COST", "회수비용 (원)"),
    ("RESTOCK_COST", "재입고비용 (원)"),
    ("RETURN_RATE", "반품률 (%)"),
    ("ETC_RATE", "기타비용률 (%)"),
    ("EXCHANGE_RATE", "위안화 환율"),
    ("PACKAGING_COST", "포장비용 (원)"),
    ("GIFT_COST", "사은품 비용 (원)")
]:
    val_str = st.sidebar.text_input(label, value=format_input_value(config[key]), key=key)
    try:
        config[key] = float(val_str)
    except ValueError:
        pass

if st.sidebar.button("📂 기본값으로 저장"):
    save_config(config)
    st.sidebar.success("기본값이 저장되었습니다.")

tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

with tab1:
    left, right = st.columns(2)

    # ── 좌측: 판매가 입력 및 50% 기준 단가 표시 ──
    with left:
        st.subheader("판매정보 입력")
        sell_price_raw = st.text_input("판매가", value=st.session_state.get("sell_price_raw",""), key="sell_price_raw")
        margin_display = st.empty()

        if sell_price_raw.strip():
            try:
                target_margin = 50.0
                sell_price = int(float(sell_price_raw))
                fee = round((sell_price * config["FEE_RATE"] * 1.1) / 100)
                inout_cost = round(config["INOUT_COST"] * 1.1)
                return_cost = round((config["PICKUP_COST"] + config["RESTOCK_COST"]) * config["RETURN_RATE"] * 1.1)
                etc_cost = round(sell_price * config["ETC_RATE"] / 100)
                packaging_cost = round(config["PACKAGING_COST"] * 1.1)
                gift_cost = round(config["GIFT_COST"] * 1.1)
                supply_price = sell_price / 1.1

                left_b, right_b = 0, sell_price
                target_cost = 0
                while left_b <= right_b:
                    mid = (left_b + right_b) // 2
                    partial = round(mid * 1.1 + fee + inout_cost + packaging_cost + gift_cost)
                    profit_mid = sell_price - partial
                    if profit_mid / supply_price * 100 < target_margin:
                        right_b = mid - 1
                    else:
                        target_cost = mid
                        left_b = mid + 1

                yuan_cost = math.ceil(target_cost / config["EXCHANGE_RATE"])
                margin_profit = sell_price - (round(target_cost * 1.1) + fee + inout_cost + packaging_cost + gift_cost)

                margin_display.markdown(f"""
<div style='height:10px; line-height:10px; color:#f63366; font-size:15px; margin-bottom:15px;'>
  마진율 {int(target_margin)}% 기준: {format_number(target_cost)}원 ({yuan_cost}위안) / 마진: {format_number(margin_profit)}원
</div>""", unsafe_allow_html=True)

            except:
                margin_display.markdown("<div style='height:10px; margin-bottom:15px;'>&nbsp;</div>", unsafe_allow_html=True)
        else:
            margin_display.markdown("<div style='height:10px; margin-bottom:15px;'>&nbsp;</div>", unsafe_allow_html=True)

        # 원가 직접 입력
        col1, col2 = st.columns(2)
        with col1:
            unit_yuan = st.text_input("위안화 (¥)", value=st.session_state.get("unit_yuan",""), key="unit_yuan")
        with col2:
            unit_won = st.text_input("원화 (₩)", value=st.session_state.get("unit_won",""), key="unit_won")
        qty_raw = st.text_input("수량", value=st.session_state.get("qty_raw","1"), key="qty_raw")

        calc_col, reset_col = st.columns(2)
        with calc_col:
            result = st.button("계산하기")
        with reset_col:
            st.button("리셋", on_click=reset_inputs)

    # ── 우측: 계산 결과 ──
    with right:
        if 'result' in locals() and result:
            try:
                sell_price = int(float(sell_price_raw))
                qty = int(float(qty_raw))
            except:
                st.warning("판매가와 수량을 정확히 입력해주세요.")
                st.stop()

            # 단가 결정
            if unit_yuan:
                unit_cost_val = round(float(unit_yuan) * config["EXCHANGE_RATE"])
                cost_disp = f"{format_number(unit_cost_val)}원 ({unit_yuan}위안)"
            elif unit_won:
                unit_cost_val = round(float(unit_won))
                cost_disp = f"{format_number(unit_cost_val)}원"
            else:
                unit_cost_val = 0
                cost_disp = "0원"

            vat = 1.1
            unit_cost = round(unit_cost_val * vat)
            fee = round((sell_price * config["FEE_RATE"] / 100) * vat)
            ad = round((sell_price * config["AD_RATE"] / 100) * vat)
            inout = round(config["INOUT_COST"] * vat)
            pickup = round(config["PICKUP_COST"] * vat)
            restock = round(config["RESTOCK_COST"] * vat)
            return_cost = round((pickup + restock) * config["RETURN_RATE"])
            etc = round((sell_price * config["ETC_RATE"] / 100) * vat)
            packaging = round(config["PACKAGING_COST"] * vat)
            gift = round(config["GIFT_COST"] * vat)

            total_cost = unit_cost + fee + ad + inout + return_cost + etc + packaging + gift
            profit2 = sell_price - total_cost
            supply2 = sell_price / vat

            margin_pf = sell_price - (unit_cost + fee + inout)
            margin_rt = round(margin_pf / supply2 * 100, 2)
            roi_margin = round(margin_pf / unit_cost * 100, 2) if unit_cost else 0
            roi = round(profit2 / unit_cost * 100, 2) if unit_cost else 0

            st.markdown("### 📊 계산 결과")
            for bg, items in [
                ("#e8f5e9", [
                    ("💰 마진", f"{format_number(margin_pf)}원"),
                    ("📈 마진율", f"{margin_rt:.2f}%"),
                    ("💹 투자수익률", f"{roi_margin:.2f}%")
                ]),
                ("#e3f2fd", [
                    ("🧮 최소 이익", f"{format_number(profit2)}원"),
                    ("📉 최소마진율", f"{(profit2/supply2*100):.2f}%"),
                    ("🧾 투자수익률", f"{roi:.2f}%")
                ])
            ]:
                st.markdown(f"""
<div style='display:grid;grid-template-columns:1fr 1fr 1fr;background:{bg};padding:12px;border-radius:10px;gap:8px;margin-bottom:12px;'>
  <div><div style='font-weight:bold;'>{items[0][0]}</div><div>{items[0][1]}</div></div>
  <div><div style='font-weight:bold;'>{items[1][0]}</div><div>{items[1][1]}</div></div>
  <div><div style='font-weight:bold;'>{items[2][0]}</div><div>{items[2][1]}</div></div>
</div>""", unsafe_allow_html=True)

            with st.expander("📦 상세 비용 항목 보기"):
                st.markdown(f"**판매가:** {format_number(sell_price)}원")
                st.markdown(f"**원가:** {format_number(unit_cost)}원 ({cost_disp})")
                st.markdown(f"**수수료:** {format_number(fee)}원 (판매가 × {config['FEE_RATE']}% × 1.1)")
                st.markdown(f"**광고비:** {format_number(ad)}원 (판매가 × {config['AD_RATE']}% × 1.1)")
                st.markdown(f"**입출고비용:** {format_number(inout)}원")
                st.markdown(f"**회수비용:** {format_number(pickup)}원")
                st.markdown(f"**재입고비용:** {format_number(restock)}원")
                st.markdown(f"**반품비용:** {format_number(return_cost)}원")
                st.markdown(f"**기타비용:** {format_number(etc)}원")
                st.markdown(f"**포장비용:** {format_number(packaging)}원")
                st.markdown(f"**사은품 비용:** {format_number(gift)}원")
                st.markmarkdown(f"**총비용:** {format_number(total_cost)}원")
                st.markdown(f"**공급가액:** {format_number(round(supply2))}원")
                st.markdown(f"**최소 이익:** {format_number(profit2)}원")
                st.markdown(f"**최소마진율:** {(profit2/supply2*100):.2f}%")
                st.markdown(f"**투자수익률:** {roi:.2f}%")

with tab2:
    st.subheader("세부 마진 계산기")
    st.info("준비 중입니다...")
