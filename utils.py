import math

def compute_50pct_cost(
    sell_price: int,
    cfg: dict,
    qty: int
) -> tuple[int, int]:
    """
    50% 목표 마진용 최대 단가(cost_before_vat)와 실제 마진 계산 (수식 버전).
    수량(qty)에 맞춰 단가·물류비·포장비·사은품비 등 반영.
    """
    VAT = 1.1

    # 수수료·광고비
    fee = round((sell_price * cfg["FEE_RATE"] * VAT) / 100)
    ad  = round((sell_price * cfg["AD_RATE"] * VAT) / 100)

    # 물류비 등 (qty 단위)
    inout       = round(cfg["INOUT_COST"] * VAT) * qty
    pickup      = round(cfg["PICKUP_COST"] * VAT) * qty
    restock     = round(cfg["RESTOCK_COST"] * VAT) * qty
    return_c    = round((cfg["PICKUP_COST"] + cfg["RESTOCK_COST"]) * cfg["RETURN_RATE"] * VAT) * qty
    etc_cost    = round(sell_price * cfg["ETC_RATE"] / 100 * VAT)
    packaging   = round(cfg["PACKAGING_COST"] * VAT) * qty
    gift        = round(cfg["GIFT_COST"] * VAT) * qty

    F = fee + ad + inout + pickup + restock + return_c + etc_cost + packaging + gift
    PV = sell_price / VAT

    max_cost = math.floor((sell_price - F - 0.5 * PV) / VAT)
    profit   = sell_price - (round(max_cost * VAT) + F)

    return max_cost, profit

def format_number(val) -> str:
    v = float(val)
    return f"{int(v):,}" if v.is_integer() else f"{v:,.2f}"
