# StockFlow – Inventory & Order Management System (FastAPI + MySQL)

JWT auth · role-based access · Product/Category/Supplier/Order CRUD · stock ledger ·
transactional order processing · search/filter/sort/pagination · validated file upload · SQL reports · pytest suite.

## Project structure
```
app/
  main.py            app factory, routers, global exception handlers
  config.py          settings from .env (pydantic-settings)
  database.py        engine, session, Base, get_db
  models.py          SQLAlchemy models, relationships, FKs, check constraints
  schemas.py         Pydantic request/response models + validation
  security.py        bcrypt hashing, JWT create/decode
  deps.py            current user, role guards, pagination dependency
  exceptions.py      AppError hierarchy (404/409/401/403/413/415 ...)
  routers/           thin HTTP layer: auth, users, categories, suppliers, products, stock, orders, reports
  services/          business logic: auth, catalog (generic CRUD), product, stock, order, report, upload
tests/               pytest suite (43 tests, in-memory SQLite)
scripts/generate_sql.py   regenerates schema.sql + sample_data.sql
schema.sql  sample_data.sql  .env.example  requirements.txt
```

## Setup
1. **Python 3.10+** and **MySQL 8**.
2. Install:
   ```bash
   python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Create the database and load schema + sample data:
   ```bash
   mysql -u root -p < schema.sql
   mysql -u root -p < sample_data.sql
   ```
   (Tables are also auto-created at startup, but `schema.sql` is the canonical schema.)
4. Configure:
   ```bash
   cp .env.example .env     # then edit DATABASE_URL and SECRET_KEY
   ```
5. Run: `uvicorn app.main:app --reload` → Swagger UI at **http://127.0.0.1:8000/docs**

### Sample logins (from `sample_data.sql`)
| username | password | role |
|---|---|---|
| admin | Admin@123 | admin |
| manager | Manager@123 | manager |
| staff | Staff@1234 | staff |

In Swagger click **Authorize**, enter username/password (OAuth2 password flow) – the token is attached automatically.

> **Full step-by-step setup and test walkthrough: see `TESTING_GUIDE.md`.** Live test output: `E2E_RESULTS.txt`.

## Roles & permissions
| Action | admin | manager | staff |
|---|:--:|:--:|:--:|
| Register (self → staff), login, `/auth/me` | ✔ | ✔ | ✔ |
| Read categories / suppliers / products | ✔ | ✔ | ✔ |
| Create / update categories, suppliers, products, upload image | ✔ | ✔ | ✘ |
| Delete categories, suppliers, products | ✔ | ✘ | ✘ |
| Stock in / out / movement history | ✔ | ✔ | ✘ |
| Create orders | ✔ | ✔ | ✔ |
| View orders | all | all | own only |
| Complete / cancel orders | ✔ | ✔ | ✘ |
| Reports | ✔ | ✔ | ✘ |
| Manage users (create, change role, deactivate) | ✔ | ✘ | ✘ |

## Key design points
- **Passwords**: bcrypt hashes only; passwords validated (8–72 chars, letter + digit). **JWT**: HS256, expiry, user re-checked from DB on every request (deactivated users are locked out immediately).
- **Order transaction** (`order_service.create_order`): products are locked with `SELECT … FOR UPDATE` in sorted-id order (prevents overselling and deadlocks); order, items, stock deduction and ledger rows commit together – any error (unknown product, insufficient stock) rolls **everything** back. Cancelling an order restores stock via `RETURN` ledger rows, atomically. Unit prices are snapshotted into `order_items`.
- **Inventory ledger**: every change creates a `stock_movements` row (`IN`, `OUT`, `SALE`, `RETURN`) with `balance_after`. DB `CHECK (quantity >= 0)` is a second safety net.
- **Search/filter/sort/pagination**: `/products?search=&category_id=&supplier_id=&min_price=&max_price=&low_stock=&in_stock=&sort_by=&order=&page=&size=`. `sort_by`/`order` are whitelisted via `Literal`, so arbitrary columns / SQL injection are impossible. Responses: `{items,total,page,size,pages}`.
- **File upload** (`POST /products/{id}/image`): allowed JPEG/PNG/WEBP; content-type **and** extension must agree; real **magic bytes** verified; size capped by `MAX_UPLOAD_SIZE_MB` (streamed, rejects early); random server-side filename; old image deleted on replace. Errors: 415 (type/content), 413 (too large).
- **Errors** are uniform JSON: `{"detail": "...", "error": "ConflictError"}`; Pydantic failures → 422.
- **Reports** (SQL aggregations with `GROUP BY`, `SUM`, `COUNT`, joins): `/reports/summary`, `sales-by-day`, `top-products`, `low-stock`, `inventory-by-category`, `orders-by-status`. Cancelled orders are excluded from revenue.

## Running tests
```bash
pytest -v
```
Tests use an isolated in-memory SQLite DB (no MySQL needed): auth, RBAC, validation, duplicates, 404s, pagination/filter/sort, stock rules, **atomic rollback**, cancel/restore, upload type/size/disguised-file checks, and report numbers. Latest output: `TEST_RESULTS.txt`.

## Swagger UI test checklist (for screenshots)
| # | Request | Expected |
|---|---|---|
| 1 | `POST /auth/register` valid | 201 |
| 2 | `POST /auth/register` password `abc` | 422 |
| 3 | `POST /auth/register` same username again | 409 |
| 4 | `POST /auth/login` wrong password | 401 |
| 5 | `POST /auth/login` as admin → Authorize | 200 + token |
| 6 | `GET /products` without Authorize | 401 |
| 7 | `POST /categories` as **staff** | 403 |
| 8 | `POST /products` price `-5` | 422 |
| 9 | `POST /products` duplicate SKU | 409 |
| 10 | `GET /products?search=pen&sort_by=price&order=desc&page=1&size=5` | 200 |
| 11 | `POST /stock/in` qty 20 → `POST /stock/out` qty 999 | 201 → 409 |
| 12 | `POST /orders` valid | 201, stock reduced |
| 13 | `POST /orders` with two items, second exceeds stock | 409, **first item's stock unchanged** |
| 14 | `PATCH /orders/{id}/status` CANCELLED, then again | 200 → 409 |
| 15 | `POST /products/{id}/image` PNG / PDF / >2 MB file | 200 / 415 / 413 |
| 16 | `GET /reports/summary` as admin vs staff | 200 vs 403 |

## Production notes
Change `SECRET_KEY`; serve behind HTTPS; use Alembic for migrations if the schema will evolve; restrict `/auth/register` or add email verification if you don't want open sign-up.
