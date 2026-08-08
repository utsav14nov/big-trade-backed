"""Database models. All money as Numeric (never float), all times tz-aware UTC."""
import enum
import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, Numeric, Boolean, DateTime, Date, ForeignKey, Text, Enum, JSON, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class UserRole(str, enum.Enum):
    admin = "admin"        # full control, incl. user management
    broker = "broker"      # create/edit trades, mark collections
    viewer = "viewer"      # read-only


class TradeStatus(str, enum.Enum):
    active = "active"
    cancelled = "cancelled"


class BrokerageUnit(str, enum.Enum):
    per50 = "per50"
    per100 = "per100"
    pct = "pct"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.broker, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_logins: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    trades: Mapped[list["Trade"]] = relationship(back_populates="creator")


class Party(Base):
    __tablename__ = "parties"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    location: Mapped[str | None] = mapped_column(String(128))
    aliases: Mapped[list | None] = mapped_column(JSON, default=list)  # merge variants here
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    trade_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)

    from_party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id"), index=True, nullable=False)
    to_party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id"), index=True, nullable=False)

    commodity: Mapped[str] = mapped_column(String(64), default="Groundnut", nullable=False)
    rate_per_kg: Mapped[float | None] = mapped_column(Numeric(10, 2))   # ₹/kg, 2 dp
    quantity_tonnes: Mapped[float | None] = mapped_column(Numeric(10, 3))
    quantity_text: Mapped[str | None] = mapped_column(String(64))       # keeps ranges e.g. "10-12 ton"

    # groundnut-specific
    count: Mapped[str | None] = mapped_column(String(32))
    moisture: Mapped[str | None] = mapped_column(String(32))
    loading_days: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str | None] = mapped_column(String(24))            # Sortex / Non-Sortex
    dryer: Mapped[str | None] = mapped_column(String(16))               # Dryer / Non-Dryer
    options: Mapped[list | None] = mapped_column(JSON, default=list)    # naya katta, machine silai...
    gst: Mapped[str | None] = mapped_column(String(24))
    cash_discount_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # brokerage — captured per side
    brokerage_self_unit: Mapped[BrokerageUnit | None] = mapped_column(Enum(BrokerageUnit))
    brokerage_self_value: Mapped[float | None] = mapped_column(Numeric(10, 2))
    brokerage_other_unit: Mapped[BrokerageUnit | None] = mapped_column(Enum(BrokerageUnit))
    brokerage_other_value: Mapped[float | None] = mapped_column(Numeric(10, 2))

    # lifecycle
    status: Mapped[TradeStatus] = mapped_column(Enum(TradeStatus), default=TradeStatus.active, index=True)
    payment_collected: Mapped[bool] = mapped_column(Boolean, default=False)
    brokerage_collected: Mapped[bool] = mapped_column(Boolean, default=False)

    # provenance
    source: Mapped[str] = mapped_column(String(24), default="manual")   # manual | whatsapp
    original_message: Mapped[str | None] = mapped_column(Text)
    review_flag: Mapped[str | None] = mapped_column(String(32))

    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    creator: Mapped["User"] = relationship(back_populates="trades")
    from_party: Mapped["Party"] = relationship(foreign_keys=[from_party_id])
    to_party: Mapped["Party"] = relationship(foreign_keys=[to_party_id])

    __table_args__ = (
        Index("ix_trades_date_status", "trade_date", "status"),
    )


class RefreshToken(Base):
    """Server-side record of issued refresh tokens, so we can revoke them."""
    __tablename__ = "refresh_tokens"
    jti: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Append-only record of every mutating action on financial data."""
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)     # trade.create, trade.cancel...
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict | None] = mapped_column(JSON)                   # before/after diff
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
