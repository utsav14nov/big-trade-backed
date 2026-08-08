"""Request/response schemas. Validation happens here, before anything touches the DB."""
from datetime import date, datetime
from decimal import Decimal
import uuid
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.models.models import UserRole, TradeStatus, BrokerageUnit
from app.core.config import settings


# ---------- Auth ----------
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: str | None = None
    password: str = Field(min_length=settings.PASSWORD_MIN_LENGTH, max_length=128)
    role: UserRole = UserRole.broker

    @field_validator("password")
    @classmethod
    def strong(cls, v: str) -> str:
        if not (any(c.isdigit() for c in v) and any(c.isalpha() for c in v)):
            raise ValueError("Password must contain letters and numbers")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str
    email: str | None
    role: UserRole
    is_active: bool


# ---------- Party ----------
class PartyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    location: str | None


# ---------- Trade ----------
class BrokerageSide(BaseModel):
    unit: BrokerageUnit = BrokerageUnit.per100
    value: Decimal = Field(ge=0, decimal_places=2)


class TradeBase(BaseModel):
    trade_date: date
    from_party: str = Field(min_length=1, max_length=255)
    to_party: str = Field(min_length=1, max_length=255)
    commodity: str = "Groundnut"
    rate_per_kg: Decimal | None = Field(default=None, ge=0)
    quantity_tonnes: Decimal | None = Field(default=None, ge=0)
    quantity_text: str | None = None
    count: str | None = None
    moisture: str | None = None
    loading_days: str | None = None
    category: str | None = None
    dryer: str | None = None
    options: list[str] = []
    gst: str | None = None
    cash_discount_pct: Decimal | None = Field(default=None, ge=0, le=100)
    brokerage_self: BrokerageSide | None = None
    brokerage_other: BrokerageSide | None = None


class TradeCreate(TradeBase):
    pass


class TradeUpdate(BaseModel):
    # all optional — partial update
    trade_date: date | None = None
    rate_per_kg: Decimal | None = None
    quantity_tonnes: Decimal | None = None
    quantity_text: str | None = None
    count: str | None = None
    moisture: str | None = None
    loading_days: str | None = None
    category: str | None = None
    dryer: str | None = None
    options: list[str] | None = None
    cash_discount_pct: Decimal | None = None
    brokerage_self: BrokerageSide | None = None
    brokerage_other: BrokerageSide | None = None
    status: TradeStatus | None = None
    payment_collected: bool | None = None
    brokerage_collected: bool | None = None


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    trade_date: date
    from_party: PartyOut
    to_party: PartyOut
    commodity: str
    rate_per_kg: Decimal | None
    quantity_tonnes: Decimal | None
    quantity_text: str | None
    count: str | None
    moisture: str | None
    loading_days: str | None
    category: str | None
    dryer: str | None
    options: list[str] | None
    gst: str | None
    cash_discount_pct: Decimal | None
    brokerage_self_unit: BrokerageUnit | None
    brokerage_self_value: Decimal | None
    brokerage_other_unit: BrokerageUnit | None
    brokerage_other_value: Decimal | None
    status: TradeStatus
    payment_collected: bool
    brokerage_collected: bool
    source: str
    review_flag: str | None
    # computed
    trade_value: Decimal | None = None
    brokerage_total: Decimal | None = None


class TradeList(BaseModel):
    items: list[TradeOut]
    total: int
    page: int
    page_size: int


class AnalyticsSummary(BaseModel):
    total_trade_value: Decimal
    total_quantity: Decimal
    total_brokerage: Decimal
    brokerage_collected: Decimal
    brokerage_pending: Decimal
    active_trades: int
    cancelled_trades: int
    series: list[dict]        # [{period, value, qty, brokerage, count}]
    by_category: list[dict]
    top_parties: list[dict]
