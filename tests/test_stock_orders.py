def qty(client, h, pid):
    return client.get(f"/products/{pid}", headers=h).json()["quantity"]


def test_stock_in_out_and_ledger(client, manager_h, make_product):
    p = make_product(stock=0)
    r = client.post("/stock/in", json={"product_id": p["id"], "quantity": 20, "reference": "PO-1"}, headers=manager_h)
    assert r.status_code == 201 and r.json()["balance_after"] == 20
    r = client.post("/stock/out", json={"product_id": p["id"], "quantity": 5, "note": "damaged"}, headers=manager_h)
    assert r.json()["balance_after"] == 15
    assert qty(client, manager_h, p["id"]) == 15
    hist = client.get(f"/stock/movements?product_id={p['id']}", headers=manager_h).json()
    assert hist["total"] == 2
    assert client.get("/stock/movements?movement_type=OUT", headers=manager_h).json()["total"] == 1


def test_stock_out_cannot_go_negative(client, manager_h, make_product):
    p = make_product(stock=5)
    r = client.post("/stock/out", json={"product_id": p["id"], "quantity": 6}, headers=manager_h)
    assert r.status_code == 409 and r.json()["error"] == "InsufficientStockError"
    assert qty(client, manager_h, p["id"]) == 5


def test_stock_invalid_inputs(client, manager_h, make_product):
    p = make_product(stock=0)
    assert client.post("/stock/in", json={"product_id": p["id"], "quantity": 0}, headers=manager_h).status_code == 422
    assert client.post("/stock/in", json={"product_id": p["id"], "quantity": -3}, headers=manager_h).status_code == 422
    assert client.post("/stock/in", json={"product_id": 999, "quantity": 3}, headers=manager_h).status_code == 404


def test_staff_cannot_adjust_stock(client, staff_h, make_product):
    p = make_product()
    assert client.post("/stock/in", json={"product_id": p["id"], "quantity": 1}, headers=staff_h).status_code == 403


def test_create_order_deducts_stock_and_computes_total(client, staff_h, manager_h, make_product):
    a, b = make_product(stock=10, price="10.00"), make_product(stock=10, price="2.50")
    r = client.post("/orders", json={"customer_name": "Bob", "items": [
        {"product_id": a["id"], "quantity": 3}, {"product_id": b["id"], "quantity": 4}]}, headers=staff_h)
    assert r.status_code == 201
    assert r.json()["total_amount"] == 40.0 and r.json()["status"] == "CONFIRMED" and len(r.json()["items"]) == 2
    assert qty(client, manager_h, a["id"]) == 7 and qty(client, manager_h, b["id"]) == 6
    assert client.get("/stock/movements?movement_type=SALE", headers=manager_h).json()["total"] == 2


def test_order_is_atomic_rolls_back_on_insufficient_stock(client, staff_h, manager_h, make_product):
    ok, scarce = make_product(stock=10), make_product(stock=1)
    r = client.post("/orders", json={"customer_name": "Bob", "items": [
        {"product_id": ok["id"], "quantity": 5}, {"product_id": scarce["id"], "quantity": 2}]}, headers=staff_h)
    assert r.status_code == 409
    assert qty(client, manager_h, ok["id"]) == 10  # first item NOT deducted
    assert qty(client, manager_h, scarce["id"]) == 1
    assert client.get("/orders", headers=manager_h).json()["total"] == 0
    assert client.get("/stock/movements?movement_type=SALE", headers=manager_h).json()["total"] == 0


def test_order_unknown_product_rolls_back(client, staff_h, manager_h, make_product):
    p = make_product(stock=10)
    r = client.post("/orders", json={"customer_name": "Bob", "items": [
        {"product_id": p["id"], "quantity": 1}, {"product_id": 9999, "quantity": 1}]}, headers=staff_h)
    assert r.status_code == 404
    assert qty(client, manager_h, p["id"]) == 10


def test_order_validation(client, staff_h, make_product):
    p = make_product()
    bad = [
        {"customer_name": "Bob", "items": []},
        {"customer_name": "Bob", "items": [{"product_id": p["id"], "quantity": 0}]},
        {"customer_name": "B", "items": [{"product_id": p["id"], "quantity": 1}]},
        {"customer_name": "Bob", "items": [{"product_id": p["id"], "quantity": 1}, {"product_id": p["id"], "quantity": 2}]},
    ]
    for body in bad:
        assert client.post("/orders", json=body, headers=staff_h).status_code == 422


def test_order_unauthenticated(client):
    assert client.post("/orders", json={"customer_name": "Bob", "items": []}).status_code == 401


def test_cancel_restores_stock_and_cannot_cancel_twice(client, staff_h, manager_h, make_product):
    p = make_product(stock=10)
    oid = client.post("/orders", json={"customer_name": "Bob", "items": [{"product_id": p["id"], "quantity": 4}]}, headers=staff_h).json()["id"]
    assert qty(client, manager_h, p["id"]) == 6
    r = client.patch(f"/orders/{oid}/status", json={"status": "CANCELLED"}, headers=manager_h)
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
    assert qty(client, manager_h, p["id"]) == 10
    assert client.patch(f"/orders/{oid}/status", json={"status": "CANCELLED"}, headers=manager_h).status_code == 409
    assert qty(client, manager_h, p["id"]) == 10


def test_complete_order_and_staff_cannot_change_status(client, staff_h, manager_h, make_product):
    p = make_product(stock=10)
    oid = client.post("/orders", json={"customer_name": "Bob", "items": [{"product_id": p["id"], "quantity": 1}]}, headers=staff_h).json()["id"]
    assert client.patch(f"/orders/{oid}/status", json={"status": "COMPLETED"}, headers=staff_h).status_code == 403
    assert client.patch(f"/orders/{oid}/status", json={"status": "COMPLETED"}, headers=manager_h).json()["status"] == "COMPLETED"
    assert client.patch(f"/orders/{oid}/status", json={"status": "CANCELLED"}, headers=manager_h).status_code == 409


def test_staff_sees_only_own_orders(client, db_session, staff_h, manager_h, make_product):
    p = make_product(stock=10)
    mine = client.post("/orders", json={"customer_name": "Mine", "items": [{"product_id": p["id"], "quantity": 1}]}, headers=staff_h).json()["id"]
    theirs = client.post("/orders", json={"customer_name": "Theirs", "items": [{"product_id": p["id"], "quantity": 1}]}, headers=manager_h).json()["id"]
    assert client.get("/orders", headers=staff_h).json()["total"] == 1
    assert client.get(f"/orders/{mine}", headers=staff_h).status_code == 200
    assert client.get(f"/orders/{theirs}", headers=staff_h).status_code == 403
    assert client.get("/orders", headers=manager_h).json()["total"] == 2


def test_order_filters_and_sorting(client, manager_h, make_product):
    p = make_product(stock=100, price="10.00")
    for name, q in (("Alpha Co", 1), ("Beta Ltd", 5), ("Alpha Inc", 3)):
        client.post("/orders", json={"customer_name": name, "items": [{"product_id": p["id"], "quantity": q}]}, headers=manager_h)
    assert client.get("/orders?customer=alpha", headers=manager_h).json()["total"] == 2
    r = client.get("/orders?sort_by=total_amount&order=desc", headers=manager_h).json()
    assert [o["customer_name"] for o in r["items"]] == ["Beta Ltd", "Alpha Inc", "Alpha Co"]
    assert client.get("/orders?status=CANCELLED", headers=manager_h).json()["total"] == 0
    assert client.get("/orders?status=BOGUS", headers=manager_h).status_code == 422
