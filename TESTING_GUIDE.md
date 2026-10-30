# StockFlow – Setup & Complete Testing Guide

Every expected result in this guide was verified by running the real application against a real
MySQL-compatible database (93 live HTTP checks + 43 pytest tests, 0 failures, 0 server errors).

Windows commands are shown. On Mac/Linux use `source venv/bin/activate` instead of `venv\Scripts\activate`.

---

## PART A – ONE-TIME SETUP

### A1. Requirements
- Python 3.10 or newer (`python --version`)
- MySQL 8 server running (Windows: `services.msc` → **MySQL80** → Running)

### A2. Install the project
```bash
cd C:\Users\venka\Desktop\stockflow
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
You should now see `(venv)` at the start of your prompt.

### A3. Create the database (7 tables)
Open a **normal Command Prompt** (not the `mysql>` prompt) in the project folder:
```bash
mysql -u root -p < schema.sql
mysql -u root -p < sample_data.sql
```
Or inside the `mysql>` prompt (use forward slashes, end with `;`):
```sql
source C:/Users/venka/Desktop/stockflow/schema.sql;
source C:/Users/venka/Desktop/stockflow/sample_data.sql;
```
Check:
```sql
USE stockflow;
SHOW TABLES;
SELECT username, role FROM users;
SELECT COUNT(*) FROM products;   -- 10
SELECT COUNT(*) FROM orders;     -- 5
```
Expected tables: `categories, order_items, orders, products, stock_movements, suppliers, users`.

### A4. Configure `.env`
```bash
copy .env.example .env
```
Edit `.env`:
```
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/stockflow
SECRET_KEY=paste-a-long-random-text-here
```
Special characters in the password must be URL-encoded: `@`→`%40`, `#`→`%23`, `/`→`%2F`.
Generate a key: `python -c "import secrets; print(secrets.token_hex(32))"`

### A5. Start the server
```bash
uvicorn app.main:app --reload
```
Expected: `Application startup complete.` Open **http://127.0.0.1:8000/docs**. Keep this terminal open.
Quick check: http://127.0.0.1:8000/health shows `{"status":"ok"}`.

---

## PART B – HOW TO USE SWAGGER

1. Click **Try it out** on an endpoint, edit the JSON, click **Execute**.
2. The status code is shown under **Server response**; the body is below it.
3. **Switching user:** click **Authorize** → **Logout** → enter username/password → **Authorize** → Close.
   Leave `client_id` and `client_secret` empty.
4. Not sure who you are? Run `GET /auth/me`.
5. A padlock icon on an endpoint means it needs login.

| User | Password | Role |
|---|---|---|
| admin | Admin@123 | admin |
| manager | Manager@123 | manager |
| staff | Staff@1234 | staff |

**Start from a fresh database** (re-run A3) before this walkthrough so that IDs and quantities match.
In the fresh sample data: products have ids 1–10, orders 1–5, and **product 1 has 70 units (Q = 70)**.

---

## PART C – THE TESTS

### C1. Auth (not logged in)

| # | Endpoint | Body | Expect |
|---|---|---|---|
| 1 | POST /auth/register | `{"username":"newuser","email":"newuser@example.com","password":"Secret123"}` | **201**, role `staff` |
| 2 | POST /auth/register | same body again | **409** |
| 3 | POST /auth/register | `{"username":"weak1","email":"weak@example.com","password":"abc"}` | **422** |
| 4 | POST /auth/register | `{"username":"bad2","email":"not-an-email","password":"Secret123"}` | **422** |
| 5 | POST /auth/login | admin / `wrongpass1` | **401** |
| 6 | GET /products | no login | **401** |
| 6b | POST /auth/register | add `"role":"admin"` to a valid body | **201** but role is still `staff` (no privilege escalation) |

### C2. Staff (log in as staff)

| # | Endpoint | Expect |
|---|---|---|
| 7 | GET /auth/me | 200, role staff |
| 8 | GET /products | 200 |
| 9 | POST /categories `{"name":"Toys"}` | **403** |
| 10 | GET /reports/summary | **403** |
| 11 | GET /users | **403** |
| 12 | POST /stock/in `{"product_id":1,"quantity":5}` | **403** |

### C3. Manager (log in as manager)

**Categories and suppliers**

| # | Endpoint | Body | Expect |
|---|---|---|---|
| 13 | POST /categories | `{"name":"Test Category","description":"demo"}` | 201 |
| 14 | POST /categories | same again | 409 |
| 15 | POST /suppliers | `{"name":"Demo Supplier","email":"demo@sup.com","phone":"+91 98765 43210"}` | 201 |
| 16 | POST /suppliers | `{"name":"Bad Phone","phone":"abc"}` | 422 |

**Products**

| # | Endpoint | Body | Expect |
|---|---|---|---|
| 17 | POST /products | `{"sku":"TST-001","name":"Test Product","price":"99.50","reorder_level":5,"category_id":1,"supplier_id":1}` | 201, quantity 0, **id 11** |
| 18 | POST /products | same again | 409 (duplicate SKU) |
| 19 | POST /products | `{"sku":"TST-002","name":"Test Product","price":"-5","category_id":1}` | 422 |
| 20 | POST /products | `{"sku":"TST-003","name":"Test Product","price":"5","category_id":999}` | 404 |
| 21 | PUT /products/11 | `{"price":"120.00"}` | 200, price 120 |
| 22 | GET /products/9999 | | 404 |
| 23 | DELETE /products/11 | | **403** (manager cannot delete) |

**Search, filter, sort, pagination (`GET /products`)**

| # | Parameters | Expect |
|---|---|---|
| 24 | `search=pen` | only "Ball Pen Pack (10)" |
| 25 | `min_price=100&max_price=1000&sort_by=price&order=desc` | prices 799, 450, 399, 349, 299, 120, 120 |
| 26 | `page=1&size=3` then `page=2&size=3` | 3 items each, different items, `total` 11, `pages` 4 |
| 27 | `low_stock=true` | ELE-003, STA-002, FUR-002, GRO-002, TST-001 |
| 28 | `sort_by=abc` | 422 |
| 29 | `size=1000` | 422 |

**Stock in/out (product 11)**

| # | Endpoint | Body | Expect |
|---|---|---|---|
| 30 | POST /stock/in | `{"product_id":11,"quantity":20,"reference":"PO-100"}` | 201, `balance_after` 20 |
| 31 | POST /stock/out | `{"product_id":11,"quantity":5,"note":"damaged"}` | 201, `balance_after` 15 |
| 32 | POST /stock/out | `{"product_id":11,"quantity":999}` | **409** |
| 33 | POST /stock/in | `{"product_id":11,"quantity":0}` | 422 |
| 34 | POST /stock/in | `{"product_id":9999,"quantity":5}` | 404 |
| 35 | GET /stock/movements?product_id=11 | | 200, 2 rows |

**File upload (`POST /products/11/image`, choose a file)**

| # | File | Expect |
|---|---|---|
| 36 | a real .jpg/.png under 2 MB | 200, `image_path` filled; open `http://127.0.0.1:8000/uploads/<image_path>` to see it |
| 37 | a .pdf or .txt | **415** |
| 38 | an image over 2 MB | **413** |
| 39 | a text file renamed to .png | **415** (real file content is checked) |

### C4. Orders (manager)

| # | Endpoint | Body | Expect |
|---|---|---|---|
| 40 | POST /orders | `{"customer_name":"Demo Customer","items":[{"product_id":1,"quantity":2}]}` | 201, `CONFIRMED`, total 1598.0, **order id 6** |
| 41 | GET /products/1 | | quantity **68** (70 − 2) |
| 42 | POST /orders | `{"customer_name":"Rollback Test","items":[{"product_id":1,"quantity":1},{"product_id":10,"quantity":1}]}` | **409** (product 10 has 0 stock) |
| 43 | GET /products/1 | | still **68** – the first item was rolled back |
| 44 | POST /orders | `{"customer_name":"Dup","items":[{"product_id":1,"quantity":1},{"product_id":1,"quantity":2}]}` | 422 |
| 45 | POST /orders | `{"customer_name":"Empty","items":[]}` | 422 |
| 46 | POST /orders | `{"customer_name":"Ghost","items":[{"product_id":9999,"quantity":1}]}` | 404 |
| 47 | PATCH /orders/6/status | `{"status":"CANCELLED"}` | 200; GET /products/1 → **70** again |
| 48 | PATCH /orders/6/status | same again | **409** |
| 49 | GET /orders?status=CANCELLED&sort_by=total_amount&order=desc | | 200 |

**Role checks on orders (log in as staff)**

| # | Endpoint | Expect |
|---|---|---|
| R1 | GET /orders | 200, only orders created by staff |
| R2 | GET /orders/3 (created by manager) | 403 |
| R3 | PATCH /orders/1/status `{"status":"COMPLETED"}` | 403 |

### C5. Admin (log in as admin)

**Reports – all must return 200:** `GET /reports/summary`, `/sales-by-day`, `/top-products?limit=3`, `/low-stock`, `/inventory-by-category`, `/orders-by-status`.
Invalid: `/top-products?limit=0` → 422, `/sales-by-day?date_from=xx` → 422.
On a fresh database the summary shows 10 products, 5 orders (cancelled orders excluded from revenue).

| # | Endpoint | Body | Expect |
|---|---|---|---|
| 50 | GET /users | | 200 |
| 51 | PATCH /users/{newuser id} | `{"role":"manager"}` | 200, role manager |
| 52 | PATCH /users/1 (yourself) | `{"role":"staff"}` | **403** (admin cannot demote self) |
| 52b | POST /users | `{"username":"spuser","email":"spuser@gmail.com","password":"Sp123456","role":"manager"}` | 201 |
| 52c | POST /users | `{"username":"sp2","email":"sp2@gmail.com","password":"sp123","role":"User"}` | 422 |
| 53 | DELETE /products/11 | | 409 (has stock history) |
| 54 | DELETE /categories/1 | | 409 (has products) |
| 55 | DELETE /categories/{Test Category id} | | 204 |

**User body rules** (cause of most 422 errors): username **3–50 chars** (letters, digits, `_ . -`), valid email,
password **8–72 chars with a letter and a digit**, role exactly `admin`, `manager` or `staff` (lowercase).

---

## PART D – VERIFY INSIDE MYSQL (strong proof for your viva)

```sql
USE stockflow;

-- 1. Passwords are bcrypt hashes, never plain text
SELECT username, role, LEFT(hashed_password,7) AS hash_prefix FROM users;     -- $2b$12$

-- 2. Stock always equals the last ledger balance  (must return 0)
SELECT COUNT(*) AS mismatches FROM products p
WHERE p.quantity <> COALESCE((SELECT balance_after FROM stock_movements m
                              WHERE m.product_id=p.id ORDER BY m.id DESC LIMIT 1),0);

-- 3. Each order total equals the sum of its items (must return 0)
SELECT COUNT(*) AS mismatches FROM orders o
WHERE o.total_amount <> (SELECT SUM(quantity*unit_price) FROM order_items i WHERE i.order_id=o.id);

-- 4. Ledger for one product
SELECT id, movement_type, quantity, balance_after, reference FROM stock_movements WHERE product_id=1;
```

---

## PART E – AUTOMATED TESTS

**E1. pytest (43 tests, no MySQL needed – uses in-memory SQLite)**
```bash
pytest -v
```
Expect `43 passed`. Save proof: `pytest -v > TEST_RESULTS.txt`

**E2. Live end-to-end script (93 checks against your running server and MySQL)**
Re-load the database first (A3), keep the server running in one terminal, then in a second terminal:
```bash
cd C:\Users\venka\Desktop\stockflow
venv\Scripts\activate
python scripts\e2e_live_test.py
```
Expect `93/93 checks passed`. It includes a **concurrency test**: 8 simultaneous orders for the last
1 unit – exactly one succeeds and 7 are rejected, so stock can never be oversold.
It must run on a fresh database (it registers `newuser`, so a second run gives 409 on that step).
Its last full output is in `E2E_RESULTS.txt`.

---

## PART F – SCREENSHOTS TO SUBMIT

Capture request + status code + response body. Save as `screenshots/01_register_201.png`, etc.

| Group | Tests |
|---|---|
| Success | 1, 8, 13, 17, 30, 31, 36, 40, 47, one report, 51, 52b |
| Validation errors (422) | 3, 4, 19, 28, 44, 52c |
| Unauthorized (401) | 5, 6 |
| Forbidden (403) | 9, 10, 11, 23, R2, 52 |
| Edge cases | 18 (409), 32 (409), 37 (415), 38 (413), 39 (415), 42 **then** 43 (rollback proof), 48 (409), 53, 54 |
| Tests | terminal showing `43 passed`; terminal showing `93/93 checks passed` |

---

## PART G – TROUBLESHOOTING

| Problem | Cause / fix |
|---|---|
| `mysql` not recognized | Use MySQL Workbench: File → Open SQL Script → run `schema.sql`, then `sample_data.sql` |
| Lines starting `->` at `mysql>` | You typed a Command Prompt command inside MySQL. Type `\c`, then `exit` |
| `Access denied for user 'root'` | Wrong password in `.env` |
| `Can't connect to MySQL server` | MySQL service not running (`services.msc` → MySQL80 → Start) |
| `Unknown database 'stockflow'` | `schema.sql` not loaded (A3) |
| `Table ... doesn't exist` | `schema.sql` failed – check the exact path, forward slashes |
| `No module named ...` | venv not activated, or `pip install -r requirements.txt` not run |
| `cryptography package is required` | `pip install cryptography` |
| Login 401 right after changing a password | Hash not pasted correctly in `hashed_password` – see "Change a password" |
| Every request 403 | Logged in as the wrong role – check `GET /auth/me` |
| 422 on user/product creation | Read the `msg` in the response: it names the field and the rule broken |
| Port 8000 busy | `uvicorn app.main:app --reload --port 8001` |

### Change a password (admin / manager)
```bash
python -c "import bcrypt,getpass; print(bcrypt.hashpw(getpass.getpass('New password: ').encode(), bcrypt.gensalt(12)).decode())"
```
```sql
USE stockflow;
UPDATE users SET hashed_password='PASTE_HASH' WHERE username='admin';
```
New passwords must be 8–72 characters with a letter and a digit. The demo passwords in `sample_data.sql`
and this guide are for testing only – state that in your submission, or change them first.
