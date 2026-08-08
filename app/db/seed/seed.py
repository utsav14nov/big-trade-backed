"""
Seed the database with the 714 historical trades extracted from WhatsApp,
plus an initial admin user.

Run once after migrations:
    python -m app.db.seed.seed
"""
import asyncio
import json
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.models import User, Party, Trade, UserRole, TradeStatus, BrokerageUnit
from app.core.security import hash_password

SEED_FILE = Path(__file__).parent / "trades_seed.json"


async def seed():
    async with AsyncSessionLocal() as db:
        # --- admin user (change the password immediately after first login) ---
        admin_user = os.environ.get("SEED_ADMIN_USER", "admin")
        admin_pass = os.environ.get("SEED_ADMIN_PASSWORD")
        if not admin_pass:
            raise SystemExit("Set SEED_ADMIN_PASSWORD env var (min 12 chars) before seeding.")
        exists = (await db.execute(select(User).where(User.username == admin_user))).scalar_one_or_none()
        if not exists:
            db.add(User(username=admin_user, hashed_password=hash_password(admin_pass), role=UserRole.admin))
            await db.flush()
            print(f"Created admin user '{admin_user}'.")

        # --- parties (dedup by lower-cased name) ---
        raw = json.loads(SEED_FILE.read_text(encoding="utf-8"))
        party_cache: dict[str, Party] = {}

        async def party(name: str, loc: str | None) -> Party | None:
            name = (name or "").strip()
            if not name:
                return None
            key = name.lower()
            if key in party_cache:
                return party_cache[key]
            existing = (await db.execute(select(Party).where(Party.name == name))).scalar_one_or_none()
            p = existing or Party(name=name, location=loc or None)
            if not existing:
                db.add(p)
                await db.flush()
            party_cache[key] = p
            return p

        # skip if already seeded
        count = (await db.execute(select(Trade))).first()
        if count:
            print("Trades already present — skipping trade seed.")
            await db.commit()
            return

        n = 0
        for r in raw:
            fp = await party(r["fromParty"], r.get("fromLoc"))
            tp = await party(r["toParty"], r.get("toLoc"))
            if fp is None or tp is None:
                continue
            try:
                td = datetime.strptime(r["date"], "%d/%m/%y").date()
            except Exception:
                continue
            db.add(Trade(
                trade_date=td, from_party_id=fp.id, to_party_id=tp.id,
                commodity=r.get("commodity", "Groundnut"),
                rate_per_kg=Decimal(str(r["rate"])) if r.get("rate") else None,
                quantity_tonnes=Decimal(str(r["qty"])) if r.get("qty") else None,
                quantity_text=r.get("qtyText"),
                count=r.get("count") or None, moisture=r.get("moisture") or None,
                loading_days=r.get("loading") or None,
                category=r.get("category") or None, dryer=r.get("dryer") or None,
                options=r.get("options") or [], gst=r.get("gst") or None,
                status=TradeStatus.active, source="whatsapp",
                original_message=r.get("orig"), review_flag=r.get("flag") or None,
            ))
            n += 1
        await db.commit()
        print(f"Seeded {n} trades and {len(party_cache)} parties.")


if __name__ == "__main__":
    asyncio.run(seed())
