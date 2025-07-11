import streamlit as st
import json
import os
import math

from config import DEFAULT_CONFIG_FILE, default_config, load_config, save_config
from utils  import compute_50pct_cost, format_number

st.set_page_config(page_title="간단 마진 계산기", layout="wide")

DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_FILE
default_config     = default_config

# ── 설정 로드 (mtime 기반 캐시) ──
file_mtime = os.path.getmtime(DEFAULT_CONFIG_FILE) if os.path.exists(DEFAULT_CONFIG_FILE) else 0
config     = load_config(file_mtime)
# 기본값에 없는 키 채워넣기
for k, v in default_config.items():
    if k not in config:
        config[k] = v

def save_config_wrapper(cfg):
    save_config(cfg)

def format_input_value(val):
    return str(int(val)) if float(val).is_integer() else str(val)

def reset_inputs():
    for key in ["sell_price_raw", "unit_yuan", "unit_won", "qty_raw"]:
        if key in st.session_state:
            st.session_state[key] = ""

st.sidebar.header("🛠️ 설정값")
for key, label in [
    ("FEE_RATE",         "수수료율 (%)"),
    ("AD_RATE",          "광고비율 (%)"),
    ("INOUT_COST",       "입출고비용 (원)"),
    ("PICKUP_COST",      "회수비용 (원)"),
    ("RESTOCK_COST",     "재입고비용 (원)"),
    ("RETURN_RATE",      "반품률 (%)"),
    ("ETC_RATE",         "기타비용률 (%)"),
    ("EXCHANGE_RATE",    "위안화 환율"),
    ("PACKAGING_COST",   "포장비용 (원)"),
    ("GIFT_COST",        "사은품 비용 (원)")
]:
    val_str = st.sidebar.text_input(
        label,
        value=format_input_value(config[key]),
        key=key
    )
    try:
        config[key] = float(val_str)
    except:
        pass

if st.sidebar.button("📂 기본값으로 저장"):
    save_config_wrapper(config)
    st.sidebar.success("기본값이 저장되었습니다.")

tab1, tab2 = st.tabs(["간단 마진 계산기", "세부 마진 계산기"])

with tab1:
    left, right = st.columns(2)

    with left:
        st.subheader("판매정보 입력")

        # ── 개선 1) 판매가만 number_input ──
        sell_price_raw = st.number_input(
            "판매가",
            min_value=0, step=100,
            value=0, format="%d",
            key="sell_price_raw"
        )
        # ── 개선 1) 수량만 number_input ──
        qty_raw = st.number_input(
            "수량",
            min_value=1, step=1,
            value=1, format="%d",
            key="qty_raw"
        )

        # ── 원본처럼 col1/col2에 단가 입력 ──
        col1, col2 = st.columns(2)
        with col1:
            unit_yuan = st.text_input(
                "위안화 (¥)",
                value=st.session_state.get("unit_yuan",""),
                key="unit_yuan"
            )
        with col2:
            unit_won  = st.text_input(
                "원화 (₩)",
                value=st.session_state.get("unit_won",""),
                key="unit_won"
            )

        # ── 50% 마진 표시 자리 확보 ──
        margin_display = st.empty()
        if sell_price_raw:
            sell_price = int(sell_price_raw)
            qty        = int(qty_raw)
            target_cost, target_profit = compute_50pct_cost(sell_price, config, qty)
            yuan_cost = math.ceil(target_cost / config["EXCHANGE_RATE"])
            margin_display.markdown(f"""
<div style='height:10px; line-height:10px; color:#f63366; font-size:15px; margin-bottom:15px;'>
  마진율 50% 기준: {format_number(target_cost)}원 ({yuan_cost}위안) / 마진: {format_number(target_profit)}원
</div>""", unsafe_allow_html=True)
        else:
            margin_display.markdown(
                "<div style='height:10px; margin-bottom:15px;'>&nbsp;</div>",
                unsafe_allow_html=True
            )

        calc_col, reset_col = st.columns(2)
        with calc_col:
            result = st.button("계산하기")
        with reset_col:
            st.button("리셋", on_click=reset_inputs)

    with right:
        if 'result' in locals() and result:
            try:
                sell_price = int(float(sell_price_raw))
                qty        = int(float(qty_raw))
            except:
                st.warning("판매가와 수량을 정확히 입력해주세요.")
                st.stop()

            # ── 개선 5) 단가 계산에 qty 곱하기 ──
            if unit_yuan:
                unit_cost_val = round(float(unit_yuan) * config["EXCHANGE_RATE"])
                cost_disp     = f"{format_number(unit_cost_val)}원 ({unit_yuan}위안) × {qty}"
            elif unit_won:
                unit_cost_val = round(float(unit_won))
                cost_disp     = f"{format_number(unit_cost_val)}원 × {qty}"
            else:
                unit_cost_val = 0
                cost_disp     = f"0원 × {qty}"

            vat = 1.1
            unit_cost = round(unit_cost_val * vat) * qty

            fee         = round((sell_price * config["FEE_RATE"] / 100) * vat)
            ad          = round((sell_price * config["AD_RATE"] / 100) * vat)
            inout       = round(config["INOUT_COST"] * vat)
            pickup      = round(config["PICKUP_COST"] * vat)
            restock     = round(config["RESTOCK_COST"] * vat)
            return_cost = round((config["PICKUP_COST"] + config["RESTOCK_COST"]) * config["RETURN_RATE"] * vat)
            etc         = round((sell_price * config["ETC_RATE"] / 100) * vat)
            packaging   = round(config["PACKAGING_COST"] * vat)
            gift        = round(config["GIFT_COST"] * vat)

            total_cost = unit_cost + fee + ad + inout + return_cost + etc + packaging + gift
            profit2    = sell_price - total_cost
            supply2    = sell_price / vat

            margin_pf  = sell_price - (unit_cost + fee + inout)
            margin_rt  = round(margin_pf / supply2 * 100, 2)
            roi_margin = round(margin_pf / unit_cost * 100, 2) if unit_cost else 0
            roi        = round(profit2 / unit_cost * 100, 2) if unit_cost else 0

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
                st.markdown(f"**총비용:** {format_number(total_cost)}원")
                st.markdown(f"**공급가액:** {format_number(round(supply2))}원")
                st.markdown(f"**최소 이익:** {format_number(profit2)}원")
                st.markdown(f"**최소마진율:** {(profit2/supply2*100):.2f}%")
                st.markdown(f"**투자수익률:** {roi:.2f}%")

with tab2:
    st.subheader("세부 마진 계산기")
    st.info("준비 중입니다…")
