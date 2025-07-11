# utils.py
import math

def format_number(val):
    # 원본 format_number 그대로
    v = float(val)
    return f"{int(v):,}" if v.is_integer() else f"{v:,.2f}"

def compute_50pct_cost(sell_price, cfg, qty):
    # 원본 compute_50pct_cost 로직 그대로
    VAT = 1.1
    fee       = round((sell_price * cfg["FEE_RATE"] * VAT) / 100)
    inout     = round(cfg["INOUT_COST"] * VAT) * qty
    packaging = round(cfg["PACKAGING_COST"] * VAT) * qty
    gift      = round(cfg["GIFT_COST"] * VAT) * qty
    F = fee + inout + packaging + gift
    PV = sell_price / VAT
    max_cost = math.floor((sell_price - F - 0.5 * PV) / VAT)
    profit   = sell_price - (round(max_cost * VAT) + F)
    return max_cost, profit
