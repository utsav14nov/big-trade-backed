"""Trade endpoints: create, list (filter/paginate), get, update, lifecycle actions."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.models import Trade, Party, User, UserRole, TradeStatus, BrokerageUnit
from app.schemas.schemas import TradeCreate, TradeUpdate, TradeOut, TradeList
from app.api.deps import get_current_user, require_role
from app.services.calc import trade_value, brokerage_total
from app.services.audit import log_action

router = APIRouter(prefix="/trades", tags=["trades"])


async def _get_or_create_party(db: AsyncSession, name: str, location: str | None) -> Party:
    name = name.strip()
    result = await db.execute(select(Party).where(func.lower(Party.name) == name.lower()))
    party = result.scalar_one_or_none()
    if party is None:
        party = Party(name=name, location=location)
        db.add(party)
        await db.flush()
    return party


def _to_out(t: Trade) -> TradeOut:
    out = TradeOut.model_validate(t)
    out.trade_value = trade_value(t)
    out.brokerage_total = brokerage_total(t)
    return out


@router.post("", response_model=TradeOut, status_code=201)
async def create_trade(
    body: TradeCreate, request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.broker)),
):
    from_p = await _get_or_create_party(db, body.from_party, None)
    to_p = await _get_or_create_party(db, body.to_party, None)
    t = Trade(
        trade_date=body.trade_date, from_party_id=from_p.id, to_party_id=to_p.id,
        commodity=body.commodity, rate_per_kg=body.rate_per_kg,
        quantity_tonnes=body.quantity_tonnes, quantity_text=body.quantity_text,
        count=body.count, moisture=body.moisture, loading_days=body.loading_days,
        category=body.category, dryer=body.dryer, options=body.options, gst=body.gst,
        cash_discount_pct=body.cash_discount_pct,
        brokerage_self_unit=body.brokerage_self.unit if body.brokerage_self else None,
        brokerage_self_value=body.brokerage_self.value if body.brokerage_self else None,
        brokerage_other_unit=body.brokerage_other.unit if body.brokerage_other else None,
        brokerage_other_value=body.brokerage_other.value if body.brokerage_other else None,
        source="manual", created_by=user.id,
    )
    db.add(t)
    await db.flush()
    await log_action(db, user.id, "trade.create", "trade", str(t.id), request)
    await db.commit()
    await db.refresh(t, ["from_party", "to_party"])
    return _to_out(t)


@router.get("", response_model=TradeList)
async def list_trades(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    q: str | None = Query(None, description="party name search"),
    date_from: date | None = None,
    date_to: date | None = None,
    status: TradeStatus | None = None,
    category: str | None = None,
    payment_collected: bool | None = None,
    brokerage_collected: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    stmt = select(Trade).options(selectinload(Trade.from_party), selectinload(Trade.to_party))
    if status:
        stmt = stmt.where(Trade.status == status)
    if category:
        stmt = stmt.where(Trade.category == category)
    if date_from:
        stmt = stmt.where(Trade.trade_date >= date_from)
    if date_to:
        stmt = stmt.where(Trade.trade_date <= date_to)
    if payment_collected is not None:
        stmt = stmt.where(Trade.payment_collected == payment_collected)
    if brokerage_collected is not None:
        stmt = stmt.where(Trade.brokerage_collected == brokerage_collected)
    if q:
        like = f"%{q.lower()}%"
        sub = select(Party.id).where(func.lower(Party.name).like(like))
        stmt = stmt.where(or_(Trade.from_party_id.in_(sub), Trade.to_party_id.in_(sub)))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Trade.trade_date.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    return TradeList(items=[_to_out(t) for t in rows], total=total, page=page, page_size=page_size)


@router.get("/{trade_id}", response_model=TradeOut)
async def get_trade(trade_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Trade).where(Trade.id == trade_id).options(selectinload(Trade.from_party), selectinload(Trade.to_party))
    t = (await db.execute(stmt)).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    return _to_out(t)


@router.patch("/{trade_id}", response_model=TradeOut)
async def update_trade(
    trade_id: uuid.UUID, body: TradeUpdate, request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.broker)),
):
    stmt = select(Trade).where(Trade.id == trade_id).options(selectinload(Trade.from_party), selectinload(Trade.to_party))
    t = (await db.execute(stmt)).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="Trade not found")

    data = body.model_dump(exclude_unset=True)
    before = {k: str(getattr(t, k, None)) for k in data.keys() if hasattr(t, k)}
    for k, v in data.items():
        if k == "brokerage_self" and v is not None:
            t.brokerage_self_unit, t.brokerage_self_value = v["unit"], v["value"]
        elif k == "brokerage_other" and v is not None:
            t.brokerage_other_unit, t.brokerage_other_value = v["unit"], v["value"]
        elif hasattr(t, k):
            setattr(t, k, v)

    await log_action(db, user.id, "trade.update", "trade", str(t.id), request,
                     detail={"before": before, "after": {k: str(v) for k, v in data.items()}})
    await db.commit()
    await db.refresh(t, ["from_party", "to_party"])
    return _to_out(t)
