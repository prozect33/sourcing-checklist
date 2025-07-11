import math

def compute_cost_for_target_margin_simple(
    sell_price: int,
    target_margin_pct: float,
    cfg: dict,
    qty: int
) -> tuple[int, int]:
    """
    50% 목표 마진 산출 (수식 버전).
    - 단위 원가 × qty, 수수료·입출고·포장·사은품 모두 qty 단위 반영
    """
    VAT = 1.1

    # 1) 단위 원가 VAT 포함 후 qty 반영
    #    (unit_cost_val은 caller에서 환율 적용해 넘겨줌)
    # 2) 수수료·광고비: 판매가 × 요율 × VAT
    fee = round((sell_price * cfg["FEE_RATE"] * VAT) / 100)
    ad  = round((sell_price * cfg["AD_RATE"] * VAT) / 100)
    # 3) 물류·포장·사은품·반품·기타 모두 qty 단위로 반영
    inout       = round(cfg["INOUT_COST"] * VAT) * qty
    pickup      = round(cfg["PICKUP_COST"] * VAT) * qty
    restock     = round(cfg["RESTOCK_COST"] * VAT) * qty
    return_cost = round((cfg["PICKUP_COST"] + cfg["RESTOCK_COST"]) * cfg["RETURN_RATE"] * VAT) * qty
    etc_cost    = round(sell_price * cfg["ETC_RATE"] / 100 * VAT)  # 기타비용은 전체 판매가 기준
    packaging   = round(cfg["PACKAGING_COST"] * VAT) * qty
    gift        = round(cfg["GIFT_COST"] * VAT) * qty

    # 고정비 총합
    F = fee + ad + inout + pickup + restock + return_cost + etc_cost + packaging + gift

    # VAT 제외 판매가
    PV = sell_price / VAT

    # 수식으로 최대 원가 계산
    max_cost = math.floor((sell_price - F - (target_margin_pct / 100) * PV) / VAT)
    # 실제 마진
    profit   = sell_price - (round(max_cost * VAT) + F)

    return max_cost, profit

def format_number(val) -> str:
    """정수는 천 단위 콤마, 소수점 2자리까지 포맷."""
    v = float(val)
    if v.is_integer():
        return f"{int(v):,}"
    else:
        return f"{v:,.2f}"
