# Backend Rules — SA Healthcare Admin

> Read before writing code. Follow without exception. When in doubt, read an existing file in the same layer for the pattern.

## Hard Constraints

1. **No PII/PHI in logs** — ever.
2. **No `ForeignKey` in models** — service layer enforces referential integrity. Includes `scheme_id`.
3. **No bare string literals for roles/statuses** — import from `app/constants.py`. Add new ones there first.
4. **No DB queries in routers** — routers call services or repositories only.
5. **No direct external API calls** — use contracts in `app/integrations/contracts.py`; tests use `mocks.py`.
6. **No floats for money** — store cents as `int`. Frontend formats to rands.
7. **No `commit()` in repositories** — use `flush()`; session lifecycle handles commit/rollback.
8. **All queries filter by `scheme_id`** via `_effective_scheme_id(current_user)`. No unscoped reads.
9. **Seed data must be business-valid** — e.g. a PMB-flagged claim must reference a real PMB diagnosis code.

## Layers

`Router → Service → Repository → DB`. Nothing depends upward.

- **Router** (`app/routers/`): HTTP in/out, auth, status codes. No logic.
- **Service** (`app/services/`): Business rules, validation, audit. No HTTP imports.
- **Repository** (`app/repositories/`): Queries, eager-loads, pagination. No business decisions, no `HTTPException`.
- **Model** (`app/models/`): Table definitions + mixins. No logic.
- **Schema** (`app/schemas/`): Pydantic `Base`/`Create`/`Update`/`Read` per entity. `from_attributes = True` on Read.

## Model Rules

- New business entities inherit `MultiTenant` + `Auditable` (from `app/models/mixins.py`).
- Reference data (ICD-10, tariffs, disciplines) inherits neither — shared across schemes.
- Add `SoftDeletable` for regulatory entities that must never be hard-deleted.
- Columns: `snake_case`, money in cents (`int`), timestamps as `DateTime(timezone=True)`, booleans prefixed `is_`/`has_`.

## Domain Gotchas

- **Underwriting = member enrollment only.** Waiting periods, late-joiner penalties, Regulation 8. Has nothing to do with claims. Never wire them together.
- **Rules engine** (`app/services/rules_engine.py`): 7-stage pipeline (admin → industry → PMB → clinical → scheme → PMB-override → rate). New rules go in the correct stage. Each `ClaimLine` evaluated independently. PMB override (Stage 6) can reverse Stage 5 — this is legally required (MSA s.29(1)(o)).
- **Benefit balances**: per-member, per-category, per-year. `PMB_RISK` and `MEMBER_LIABILITY` are labels, not decremented.
- **Multi-tenancy**: JWT embeds `scheme_id`; `_effective_scheme_id()` resolves it. TPA users pick a scheme at login.
- **Role permissions**: defined as `CAN_<ACTION>` lists on `Role` in `constants.py`. Add new ones there — don't scatter ad-hoc checks.

## New Entity Checklist

1. Model in `app/models/` with mixins
2. Schemas in `app/schemas/` (Base/Create/Update/Read)
3. Repository in `app/repositories/` with scheme filtering
4. Service in `app/services/` if business logic needed
5. Router in `app/routers/` with auth + scheme scoping
6. Register router in `main.py`
7. `alembic revision --autogenerate -m "add_<entity>"` — review the output
8. Constants in `app/constants.py` for any new statuses/types
9. Seed data in appropriate seed script
10. At least one test per endpoint

## Migrations

Run: `cd backend/ && alembic upgrade head`. Create: `alembic revision --autogenerate -m "desc"`. Always review. Always test against Postgres — SQLite hides constraint bugs.

## Testing

`cd backend/ && pytest`. Real DB sessions, not mocks. `session.begin_nested()` for isolation. External calls use `app/integrations/mocks.py`. 90%+ coverage on new code. No untested adjudication or billing logic.

## Style

- `async def` for all endpoints and DB operations. `def` only for pure CPU/utility.
- Long operations (batch adjudication, reports) go to `BackgroundTasks` — never block the request thread.
- 100% type hints on function args and returns.
- Errors caught in services, raised as `HTTPException` with non-sensitive messages. Never leak tracebacks.
