"""Analytics: server-computed aggregates so the client never trusts its own math."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.models import Trade, User, TradeStatus
from app.schemas.schemas import AnalyticsSummary
from app.api.deps import get_current_user
from app.services.calc import trade_value, brokerage_total

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
async def summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    date_from: date | None = None,
    date_to: date | None = None,
    granularity: str = Query("month", pattern="^(day|month)$"),
):
    stmt = select(Trade).options(selectinload(Trade.from_party), selectinload(Trade.to_party))
    if date_from:
        stmt = stmt.where(Trade.trade_date >= date_from)
    if date_to:
        stmt = stmt.where(Trade.trade_date <= date_to)
    trades = (await db.execute(stmt)).scalars().all()
    active = [t for t in trades if t.status == TradeStatus.active]

    total_val = sum((trade_value(t) for t in active), Decimal(0))
    total_qty = sum((Decimal(t.quantity_tonnes or 0) for t in active), Decimal(0))
    total_brok = sum((brokerage_total(t) for t in active), Decimal(0))
    collected = sum((brokerage_total(t) for t in active if t.brokerage_collected), Decimal(0))

    def key(t: Trade) -> str:
        return t.trade_date.isoformat() if granularity == "day" else t.trade_date.strftime("%Y-%m")

    buckets: dict[str, dict] = {}
    for t in active:
        k = key(t)
        b = buckets.setdefault(k, {"period": k, "value": Decimal(0), "qty": Decimal(0), "brokerage": Decimal(0), "count": 0})
        b["value"] += trade_value(t)
        b["qty"] += Decimal(t.quantity_tonnes or 0)
        b["brokerage"] += brokerage_total(t)
        b["count"] += 1
    series = [
        {**b, "value": float(b["value"]), "qty": float(b["qty"]), "brokerage": float(b["brokerage"])}
        for b in sorted(buckets.values(), key=lambda x: x["period"])
    ]

    cats: dict[str, Decimal] = {}
    for t in active:
        cats[t.category or "Unspecified"] = cats.get(t.category or "Unspecified", Decimal(0)) + Decimal(t.quantity_tonnes or 0)
    by_category = [{"name": k, "value": float(v)} for k, v in cats.items() if v > 0]

    party_val: dict[str, dict] = {}
    for t in active:
        for p in (t.from_party, t.to_party):
            e = party_val.setdefault(p.name, {"party": p.name, "value": Decimal(0), "count": 0})
            e["value"] += trade_value(t)
            e["count"] += 1
    top_parties = [
        {"party": e["party"], "value": float(e["value"]), "count": e["count"]}
        for e in sorted(party_val.values(), key=lambda x: x["value"], reverse=True)[:10]
    ]

    return AnalyticsSummary(
        total_trade_value=total_val, total_quantity=total_qty, total_brokerage=total_brok,
        brokerage_collected=collected, brokerage_pending=total_brok - collected,
        active_trades=len(active), cancelled_trades=len(trades) - len(active),
        series=series, by_category=by_category, top_parties=top_parties,
    )
