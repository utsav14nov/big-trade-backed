"""Unit tests for the money math — the part that must never be wrong."""
from decimal import Decimal
from types import SimpleNamespace

from app.services.calc import trade_value, brokerage_side, brokerage_total
from app.models.models import BrokerageUnit


def mk(rate, qty, su=None, sv=None, ou=None, ov=None):
    return SimpleNamespace(
        rate_per_kg=Decimal(str(rate)) if rate is not None else None,
        quantity_tonnes=Decimal(str(qty)) if qty is not None else None,
        brokerage_self_unit=su, brokerage_self_value=Decimal(str(sv)) if sv is not None else None,
        brokerage_other_unit=ou, brokerage_other_value=Decimal(str(ov)) if ov is not None else None,
    )


def test_trade_value():
    # 15 tonnes @ 108 = 15000 kg * 108 = 16,20,000
    assert trade_value(mk(108, 15)) == Decimal("1620000.00")


def test_trade_value_missing():
    assert trade_value(mk(None, 15)) == Decimal(0)
    assert trade_value(mk(108, None)) == Decimal(0)


def test_brokerage_per100():
    # 15 t = 15000 kg; ₹50 per 100kg = 150 * 50 = 7500
    t = mk(108, 15, BrokerageUnit.per100, 50)
    assert brokerage_side(t, t.brokerage_self_unit, t.brokerage_self_value) == Decimal("7500.00")


def test_brokerage_per50():
    # 15000 kg / 50 = 300 units * 40 = 12000
    t = mk(108, 15, BrokerageUnit.per50, 40)
    assert brokerage_side(t, t.brokerage_self_unit, t.brokerage_self_value) == Decimal("12000.00")


def test_brokerage_pct():
    # 1% of 16,20,000 = 16,200
    t = mk(108, 15, BrokerageUnit.pct, 1)
    assert brokerage_side(t, t.brokerage_self_unit, t.brokerage_self_value) == Decimal("16200.00")


def test_brokerage_total_both_sides():
    t = mk(100, 10, BrokerageUnit.per100, 50, BrokerageUnit.per100, 50)
    # each side: 10000/100*50 = 5000 -> total 10000
    assert brokerage_total(t) == Decimal("10000.00")
