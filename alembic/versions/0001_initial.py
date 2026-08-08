"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "broker", "viewer", name="userrole"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("failed_logins", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "parties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("location", sa.String(128)),
        sa.Column("aliases", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_parties_name", "parties", ["name"])

    op.create_table(
        "trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("from_party_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("to_party_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("commodity", sa.String(64), nullable=False, server_default="Groundnut"),
        sa.Column("rate_per_kg", sa.Numeric(10, 2)),
        sa.Column("quantity_tonnes", sa.Numeric(10, 3)),
        sa.Column("quantity_text", sa.String(64)),
        sa.Column("count", sa.String(32)),
        sa.Column("moisture", sa.String(32)),
        sa.Column("loading_days", sa.String(64)),
        sa.Column("category", sa.String(24)),
        sa.Column("dryer", sa.String(16)),
        sa.Column("options", sa.JSON),
        sa.Column("gst", sa.String(24)),
        sa.Column("cash_discount_pct", sa.Numeric(5, 2)),
        sa.Column("brokerage_self_unit", sa.Enum("per50", "per100", "pct", name="brokerageunit")),
        sa.Column("brokerage_self_value", sa.Numeric(10, 2)),
        sa.Column("brokerage_other_unit", sa.Enum("per50", "per100", "pct", name="brokerageunit", create_type=False)),
        sa.Column("brokerage_other_value", sa.Numeric(10, 2)),
        sa.Column("status", sa.Enum("active", "cancelled", name="tradestatus"), nullable=False, server_default="active"),
        sa.Column("payment_collected", sa.Boolean, server_default=sa.false()),
        sa.Column("brokerage_collected", sa.Boolean, server_default=sa.false()),
        sa.Column("source", sa.String(24), server_default="manual"),
        sa.Column("original_message", sa.Text),
        sa.Column("review_flag", sa.String(32)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_trades_trade_date", "trades", ["trade_date"])
    op.create_index("ix_trades_status", "trades", ["status"])
    op.create_index("ix_trades_date_status", "trades", ["trade_date", "status"])
    op.create_index("ix_trades_from", "trades", ["from_party_id"])
    op.create_index("ix_trades_to", "trades", ["to_party_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("jti", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("revoked", sa.Boolean, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_user", "refresh_tokens", ["user_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity", sa.String(64)),
        sa.Column("entity_id", sa.String(64)),
        sa.Column("detail", sa.JSON),
        sa.Column("ip", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_user", "audit_logs", ["user_id"])
    op.create_index("ix_audit_created", "audit_logs", ["created_at"])


def downgrade() -> None:
    for t in ["audit_logs", "refresh_tokens", "trades", "parties", "users"]:
        op.drop_table(t)
    for e in ["userrole", "tradestatus", "brokerageunit"]:
        op.execute(f"DROP TYPE IF EXISTS {e}")
