# Mandi Ledger — Backend (FastAPI + Postgres)

Secure REST API for the groundnut brokerage trade manager. Async FastAPI, SQLAlchemy 2.0, Postgres, JWT auth with rotating refresh tokens, role-based access, per-trade audit trail.

## Stack
- **FastAPI** (async) + **Uvicorn/Gunicorn**
- **PostgreSQL 16** via **SQLAlchemy 2.0 async** + **asyncpg**
- **Alembic** migrations
- **JWT** (short access token + rotating refresh token in httpOnly cookie)
- **passlib/bcrypt**, **slowapi** rate limiting

## Quick start (local)
```bash
cp .env.example .env
# edit .env: set JWT_SECRET_KEY (openssl rand -hex 32) and SEED_ADMIN_PASSWORD

docker compose up -d db          # start Postgres
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

alembic upgrade head             # create tables
python -m app.db.seed.seed       # import the 714 historical trades + admin user

uvicorn app.main:app --reload    # http://localhost:8000/docs
```

Or run the whole stack: `docker compose up --build`.

## API (v1, prefix `/api/v1`)
| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/auth/login` | public | login → access token + refresh cookie |
| POST | `/auth/refresh` | cookie | rotate refresh, new access token |
| POST | `/auth/logout` | cookie | revoke refresh token |
| GET | `/auth/me` | any | current user |
| GET | `/trades` | any | list with filters (date range, party `q`, status, category, collection flags) + pagination |
| POST | `/trades` | admin/broker | create trade |
| GET | `/trades/{id}` | any | single trade |
| PATCH | `/trades/{id}` | admin/broker | edit / cancel / mark payment or brokerage collected |
| GET | `/analytics/summary` | any | server-computed aggregates (value/qty/brokerage series, category split, top parties) |

## Security posture
This handles financial data. Controls in place:

- **Auth** — short-lived access tokens (15 min), refresh tokens rotated on every use and revocable server-side (theft/replay detection). Refresh token stored in an **httpOnly, Secure, SameSite=strict** cookie — not reachable by JS, so XSS can't steal it.
- **Passwords** — bcrypt (cost 12), min length 12 with complexity check. **Account lockout** after 5 failed logins.
- **Brute force** — login rate-limited (5/min per IP) via slowapi.
- **RBAC** — `admin` / `broker` / `viewer` roles enforced per route.
- **Money** — all amounts are `Numeric`/`Decimal`, never float; computed **server-side** so a tampered client can't fake values.
- **Audit** — append-only `audit_logs` records every create/update/cancel/collect with user, IP, and before/after diff.
- **Input** — Pydantic validates every payload; SQLAlchemy parameterizes all queries (no SQL injection).
- **Transport/headers** — HSTS, `X-Content-Type-Options`, `X-Frame-Options: DENY`, referrer policy, restrictive CORS allow-list (no wildcard with credentials). Swagger/OpenAPI disabled in production.
- **Secrets** — read from env / secret manager; `.env` is gitignored. Rotate `JWT_SECRET_KEY` via secret manager.
- **Container** — runs as a non-root user.
- **CI** — Ruff, mypy, **Bandit** (SAST) and **pip-audit** (dependency CVEs) run on every push.

### Before going live — hardening checklist
- [ ] Put the API behind HTTPS only; set `COOKIE_SECURE=true`, `ENV=production`.
- [ ] Move `JWT_SECRET_KEY`, DB creds into **GCP Secret Manager** (see infra notes).
- [ ] Restrict Postgres to private IP / VPC; enforce SSL (`sslmode=require`).
- [ ] Set `CORS_ORIGINS` to your real frontend domain only.
- [ ] Enable Postgres automated backups + PITR.
- [ ] Add Sentry (or Cloud Error Reporting) for error tracking.
- [ ] Review `TrustedHostMiddleware` allowed hosts for your domain.

## Migrations
```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Tests
```bash
pytest -q          # money math + auth flows
ruff check app/    # lint
bandit -r app/     # security scan
```
