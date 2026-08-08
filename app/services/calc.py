"""Money math. Uses Decimal throughout — never float — for financial accuracy."""
from decimal import Decimal, ROUND_HALF_UP

from app.models.models import Trade, BrokerageUnit

KG_PER_TONNE = Decimal(1000)


def q(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def trade_value(trade: Trade) -> Decimal:
    """Gross value = rate (₹/kg) × quantity (kg)."""
    if trade.rate_per_kg is None or trade.quantity_tonnes is None:
        return Decimal(0)
    return q(Decimal(trade.rate_per_kg) * Decimal(trade.quantity_tonnes) * KG_PER_TONNE)


def brokerage_side(trade: Trade, unit: BrokerageUnit | None, value: Decimal | None) -> Decimal:
    if unit is None or value is None or trade.quantity_tonnes is None:
        return Decimal(0)
    kg = Decimal(trade.quantity_tonnes) * KG_PER_TONNE
    value = Decimal(value)
    if unit == BrokerageUnit.pct:
        return q(trade_value(trade) * value / Decimal(100))
    if unit == BrokerageUnit.per50:
        return q(kg / Decimal(50) * value)
    return q(kg / Decimal(100) * value)  # per100


def brokerage_total(trade: Trade) -> Decimal:
    """Both sides combined — the broker's gross earning on the trade."""
    return q(
        brokerage_side(trade, trade.brokerage_self_unit, trade.brokerage_self_value)
        + brokerage_side(trade, trade.brokerage_other_unit, trade.brokerage_other_value)
    )
