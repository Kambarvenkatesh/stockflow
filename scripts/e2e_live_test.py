"""Live end-to-end test: runs every API test from TESTING_GUIDE.md against a RUNNING server.
Usage:  (server running)  python scripts/e2e_live_test.py     # needs the sample data loaded and a fresh DB state
"""
import httpx, sys, concurrent.futures as cf
import os
B = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
c = httpx.Client(base_url=B, timeout=30)
results = []

def check(n, desc, resp, expected, note=""):
    ok = resp.status_code == expected
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  #{n:<3} {desc:<62} -> {resp.status_code} (expected {expected}) {note}")
    if not ok:
        print("       body:", resp.text[:300])
    return resp

def login(u, p):
    r = c.post("/auth/login", data={"username": u, "password": p})
    return {"Authorization": f"Bearer {r.json().get('access_token','')}"}, r

def qty(h, pid): return c.get(f"/products/{pid}", headers=h).json()["quantity"]

print("\n=== PART 2: AUTH (no login) ===")
check(1, "register valid", c.post("/auth/register", json={"username":"newuser","email":"newuser@example.com","password":"Secret123"}), 201)
r = c.post("/auth/register", json={"username":"newuser","email":"newuser@example.com","password":"Secret123"})
check(2, "register duplicate", r, 409)
check(3, "register weak password", c.post("/auth/register", json={"username":"weak1","email":"weak@example.com","password":"abc"}), 422)
check(4, "register bad email", c.post("/auth/register", json={"username":"bad2","email":"not-an-email","password":"Secret123"}), 422)
_, r = login("admin", "wrongpass1"); check(5, "login wrong password", r, 401)
check(6, "GET /products without token", c.get("/products"), 401)
check("6b", "garbage token", c.get("/products", headers={"Authorization":"Bearer abc.def.ghi"}), 401)
r = c.post("/auth/register", json={"username":"hack","email":"hack@example.com","password":"Secret123","role":"admin"})
print("      self-register with role=admin ->", r.status_code, "role =", r.json().get("role"), "(must be staff)"); results.append(r.json().get("role")=="staff")

print("\n=== PART 3: STAFF ===")
S, r = login("staff", "Staff@1234"); check("3a", "login staff", r, 200)
check(7, "GET /auth/me", c.get("/auth/me", headers=S), 200)
check(8, "GET /products", c.get("/products", headers=S), 200)
check(9, "staff POST /categories", c.post("/categories", json={"name":"Toys"}, headers=S), 403)
check(10, "staff GET /reports/summary", c.get("/reports/summary", headers=S), 403)
check(11, "staff GET /users", c.get("/users", headers=S), 403)
check(12, "staff POST /stock/in", c.post("/stock/in", json={"product_id":1,"quantity":5}, headers=S), 403)

print("\n=== PART 4: MANAGER ===")
M, r = login("manager", "Manager@123"); check("4a", "login manager", r, 200)
check(13, "create category", c.post("/categories", json={"name":"Test Category","description":"demo"}, headers=M), 201)
tc = c.get("/categories?search=Test Category", headers=M).json()["items"][0]["id"]
check(14, "duplicate category", c.post("/categories", json={"name":"Test Category"}, headers=M), 409)
check(15, "create supplier", c.post("/suppliers", json={"name":"Demo Supplier","email":"demo@sup.com","phone":"+91 98765 43210"}, headers=M), 201)
check(16, "supplier bad phone", c.post("/suppliers", json={"name":"Bad Phone","phone":"abc"}, headers=M), 422)
r = check(17, "create product", c.post("/products", json={"sku":"TST-001","name":"Test Product","price":"99.50","reorder_level":5,"category_id":1,"supplier_id":1}, headers=M), 201)
PID = r.json()["id"]; print("      new product id =", PID, "quantity =", r.json()["quantity"])
check(18, "duplicate SKU", c.post("/products", json={"sku":"TST-001","name":"Test Product","price":"99.50","category_id":1}, headers=M), 409)
check(19, "negative price", c.post("/products", json={"sku":"TST-002","name":"Test Product","price":"-5","category_id":1}, headers=M), 422)
check(20, "unknown category", c.post("/products", json={"sku":"TST-003","name":"Test Product","price":"5","category_id":999}, headers=M), 404)
r = check(21, "update price", c.put(f"/products/{PID}", json={"price":"120.00"}, headers=M), 200, f"price={c.get(f'/products/{PID}',headers=M).json()['price']}")
check(22, "GET /products/9999", c.get("/products/9999", headers=M), 404)
check(23, "manager DELETE product", c.delete(f"/products/{PID}", headers=M), 403)

print("\n--- search / filter / sort / paginate ---")
r = check(24, "search=pen", c.get("/products?search=pen", headers=M), 200); print("      ->", [p["name"] for p in r.json()["items"]])
r = check(25, "price 100-1000 sort desc", c.get("/products?min_price=100&max_price=1000&sort_by=price&order=desc", headers=M), 200)
prices = [p["price"] for p in r.json()["items"]]; print("      prices:", prices); results.append(prices == sorted(prices, reverse=True) and all(100<=x<=1000 for x in prices))
r1 = c.get("/products?page=1&size=3", headers=M).json(); r2 = c.get("/products?page=2&size=3", headers=M).json()
ok = len(r1["items"])==3 and len(r2["items"])==3 and not ({p['id'] for p in r1['items']} & {p['id'] for p in r2['items']})
results.append(ok); print(f"{'PASS' if ok else 'FAIL'}  #26  pagination page1/page2 size3 -> total={r1['total']} pages={r1['pages']}")
r = check(27, "low_stock=true", c.get("/products?low_stock=true", headers=M), 200); print("      ->", [(p['sku'],p['quantity'],p['reorder_level']) for p in r.json()['items']])
check(28, "sort_by=abc", c.get("/products?sort_by=abc", headers=M), 422)
check(29, "size=1000", c.get("/products?size=1000", headers=M), 422)

print("\n--- stock in / out ---")
r = check(30, "stock in 20", c.post("/stock/in", json={"product_id":PID,"quantity":20,"reference":"PO-100"}, headers=M), 201); print("      balance_after =", r.json()["balance_after"]); results.append(r.json()["balance_after"]==20)
r = check(31, "stock out 5", c.post("/stock/out", json={"product_id":PID,"quantity":5,"note":"damaged"}, headers=M), 201); print("      balance_after =", r.json()["balance_after"]); results.append(r.json()["balance_after"]==15)
check(32, "stock out 999 (insufficient)", c.post("/stock/out", json={"product_id":PID,"quantity":999}, headers=M), 409)
check(33, "stock in qty 0", c.post("/stock/in", json={"product_id":PID,"quantity":0}, headers=M), 422)
check(34, "stock in unknown product", c.post("/stock/in", json={"product_id":9999,"quantity":5}, headers=M), 404)
r = check(35, "movements for product", c.get(f"/stock/movements?product_id={PID}", headers=M), 200); print("      rows =", r.json()["total"]); results.append(r.json()["total"]==2)

print("\n--- file upload ---")
def up(path, name, ctype, h=M):
    return c.post(f"/products/{PID}/image", files={"file": (name, open(path,"rb"), ctype)}, headers=h)
r = check(36, "upload .png", up("/tmp/ok.png","a.png","image/png"), 200); print("      image_path =", r.json().get("image_path"))
path = r.json().get("image_path")
if path: results.append(c.get(f"/uploads/{path}").status_code == 200); print("      static file served:", c.get(f"/uploads/{path}").status_code)
check("36b", "upload .jpg (replaces old)", up("/tmp/ok.jpg","b.jpg","image/jpeg"), 200)
check(37, "upload .pdf", up("/tmp/doc.pdf","d.pdf","application/pdf"), 415)
check(38, "upload 3MB file", up("/tmp/big.png","big.png","image/png"), 413)
check(39, "upload fake .png (text inside)", up("/tmp/fake.png","fake.png","image/png"), 415)
check("39b", "staff upload", up("/tmp/ok.png","a.png","image/png", S), 403)

print("\n=== PART 5: ORDERS ===")
Q = qty(M, 1); print("      Q (product 1 stock) =", Q)
r = check(40, "create order (2 x product 1)", c.post("/orders", json={"customer_name":"Demo Customer","items":[{"product_id":1,"quantity":2}]}, headers=M), 201)
OID = r.json()["id"]; print("      order id =", OID, "status =", r.json()["status"], "total =", r.json()["total_amount"])
q41 = qty(M,1); results.append(q41==Q-2); print(f"{'PASS' if q41==Q-2 else 'FAIL'}  #41  stock after order = {q41} (expected {Q-2})")
check(42, "rollback test (item 2 out of stock)", c.post("/orders", json={"customer_name":"Rollback Test","items":[{"product_id":1,"quantity":1},{"product_id":10,"quantity":1}]}, headers=M), 409)
q43 = qty(M,1); results.append(q43==Q-2); print(f"{'PASS' if q43==Q-2 else 'FAIL'}  #43  stock after failed order = {q43} (expected {Q-2}, unchanged)")
check(44, "duplicate items", c.post("/orders", json={"customer_name":"Dup","items":[{"product_id":1,"quantity":1},{"product_id":1,"quantity":2}]}, headers=M), 422)
check(45, "empty items", c.post("/orders", json={"customer_name":"Empty","items":[]}, headers=M), 422)
check(46, "unknown product", c.post("/orders", json={"customer_name":"Ghost","items":[{"product_id":9999,"quantity":1}]}, headers=M), 404)
check("46b", "staff cancel order", c.patch(f"/orders/{OID}/status", json={"status":"CANCELLED"}, headers=S), 403)
check(47, "manager cancel order", c.patch(f"/orders/{OID}/status", json={"status":"CANCELLED"}, headers=M), 200)
q47 = qty(M,1); results.append(q47==Q); print(f"{'PASS' if q47==Q else 'FAIL'}  #47b stock restored = {q47} (expected {Q})")
check(48, "cancel again", c.patch(f"/orders/{OID}/status", json={"status":"CANCELLED"}, headers=M), 409)
check(49, "filter+sort orders", c.get("/orders?status=CANCELLED&sort_by=total_amount&order=desc", headers=M), 200)
check("49b", "bad status filter", c.get("/orders?status=BOGUS", headers=M), 422)
r = c.post("/orders", json={"customer_name":"Complete Me","items":[{"product_id":2,"quantity":1}]}, headers=S); check("49c", "staff creates own order", r, 201)
SO = r.json()["id"]
check("49d", "manager completes it", c.patch(f"/orders/{SO}/status", json={"status":"COMPLETED"}, headers=M), 200)
check("49e", "cancel completed order", c.patch(f"/orders/{SO}/status", json={"status":"CANCELLED"}, headers=M), 409)

print("\n--- staff role checks on orders ---")
r = check("R1", "staff GET /orders (own only)", c.get("/orders", headers=S), 200)
ids = {o["created_by"] for o in r.json()["items"]}; staff_id = c.get("/auth/me", headers=S).json()["id"]
results.append(ids <= {staff_id}); print("      creators seen:", ids, "(staff id =", staff_id, ")")
check("R2", "staff GET /orders/3 (manager's order)", c.get("/orders/3", headers=S), 403)
check("R3", "staff PATCH order status", c.patch("/orders/1/status", json={"status":"COMPLETED"}, headers=S), 403)

print("\n=== PART 6: ADMIN ===")
A, r = login("admin", "Admin@123"); check("6a", "login admin", r, 200)
for ep in ("summary","sales-by-day","top-products?limit=3","low-stock","inventory-by-category","orders-by-status"):
    r = check(f"REP", f"GET /reports/{ep}", c.get(f"/reports/{ep}", headers=A), 200); print("      ", str(r.json())[:230])
check("REP", "top-products limit=0", c.get("/reports/top-products?limit=0", headers=A), 422)
check("REP", "sales-by-day bad date", c.get("/reports/sales-by-day?date_from=xx", headers=A), 422)
check(50, "GET /users", c.get("/users", headers=A), 200)
nid = [u for u in c.get("/users", headers=A).json()["items"] if u["username"]=="newuser"][0]["id"]
r = check(51, "promote newuser to manager", c.patch(f"/users/{nid}", json={"role":"manager"}, headers=A), 200); print("      role =", r.json()["role"])
aid = c.get("/auth/me", headers=A).json()["id"]
check(52, "admin demotes self", c.patch(f"/users/{aid}", json={"role":"staff"}, headers=A), 403)
check("52b", "admin creates user (valid)", c.post("/users", json={"username":"spuser","email":"spuser@gmail.com","password":"Sp123456","role":"manager"}, headers=A), 201)
check("52c", "admin creates user (weak pw + bad role)", c.post("/users", json={"username":"sp2","email":"sp2@gmail.com","password":"sp123","role":"User"}, headers=A), 422)
check(53, "delete product with history", c.delete(f"/products/{PID}", headers=A), 409)
check(54, "delete category with products", c.delete("/categories/1", headers=A), 409)
check(55, "delete empty Test Category", c.delete(f"/categories/{tc}", headers=A), 204)
check("55b", "delete it again", c.delete(f"/categories/{tc}", headers=A), 404)
fresh = c.post("/products", json={"sku":"DEL-001","name":"Delete Me","price":"1.00","category_id":1}, headers=M).json()["id"]
check("55c", "delete product with no history", c.delete(f"/products/{fresh}", headers=A), 204)
nu = c.post("/users", json={"username":"off","email":"off@gmail.com","password":"Off12345","role":"staff"}, headers=A).json()["id"]
T, _ = login("off","Off12345"); check("55d", "new user token works", c.get("/auth/me", headers=T), 200)
c.patch(f"/users/{nu}", json={"is_active": False}, headers=A)
check("55e", "deactivated user's token rejected", c.get("/auth/me", headers=T), 401)
_, r = login("off","Off12345"); check("55f", "deactivated user cannot login", r, 403)

print("\n=== BONUS: CONCURRENCY (real DB row locking) ===")
p = c.post("/products", json={"sku":"RACE-1","name":"Last Unit","price":"10","category_id":1}, headers=M).json()["id"]
c.post("/stock/in", json={"product_id":p,"quantity":1}, headers=M)
def buy(i): return httpx.post(B+"/orders", json={"customer_name":f"Racer {i}","items":[{"product_id":p,"quantity":1}]}, headers=M, timeout=30).status_code
with cf.ThreadPoolExecutor(8) as ex: codes = list(ex.map(buy, range(8)))
print("      8 simultaneous orders for 1 unit ->", sorted(codes), "| final stock =", qty(M,p))
ok = codes.count(201)==1 and codes.count(409)==7 and qty(M,p)==0; results.append(ok); print("PASS" if ok else "FAIL", " exactly one order wins, no overselling")

print(f"\n==== {sum(results)}/{len(results)} checks passed ====")
sys.exit(0 if all(results) else 1)
