import os

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
JPG = b"\xff\xd8\xff\xe0" + b"0" * 100


def up(client, h, pid, name, data, ctype):
    return client.post(f"/products/{pid}/image", files={"file": (name, data, ctype)}, headers=h)


def test_upload_valid_png_and_replace(client, manager_h, make_product, tmp_path):
    p = make_product(stock=0)
    r = up(client, manager_h, p["id"], "pic.png", PNG, "image/png")
    assert r.status_code == 200
    first = r.json()["image_path"]
    assert os.path.exists(tmp_path / first) and "pic" not in first  # server-generated filename
    second = up(client, manager_h, p["id"], "new.jpg", JPG, "image/jpeg").json()["image_path"]
    assert not os.path.exists(tmp_path / first) and os.path.exists(tmp_path / second)  # old file cleaned up


def test_upload_wrong_type_rejected(client, manager_h, make_product):
    p = make_product(stock=0)
    assert up(client, manager_h, p["id"], "doc.pdf", b"%PDF-1.4", "application/pdf").status_code == 415
    assert up(client, manager_h, p["id"], "pic.gif", PNG, "image/png").status_code == 415  # extension mismatch


def test_upload_disguised_file_rejected(client, manager_h, make_product):
    p = make_product(stock=0)
    r = up(client, manager_h, p["id"], "evil.png", b"MZ\x90\x00 not really an image", "image/png")
    assert r.status_code == 415


def test_upload_too_large_rejected(client, manager_h, make_product):
    p = make_product(stock=0)
    big = PNG + b"0" * (2 * 1024 * 1024)
    assert up(client, manager_h, p["id"], "big.png", big, "image/png").status_code == 413


def test_upload_empty_and_unknown_product_and_staff(client, manager_h, staff_h, make_product):
    p = make_product(stock=0)
    assert up(client, manager_h, p["id"], "e.png", b"", "image/png").status_code == 415
    assert up(client, manager_h, 9999, "a.png", PNG, "image/png").status_code == 404
    assert up(client, staff_h, p["id"], "a.png", PNG, "image/png").status_code == 403


def test_reports(client, manager_h, staff_h, make_product):
    a = make_product(stock=10, price="10.00", reorder_level=5)
    b = make_product(stock=2, price="4.00", reorder_level=5)
    client.post("/orders", json={"customer_name": "C1", "items": [{"product_id": a["id"], "quantity": 6}]}, headers=staff_h)
    cancelled = client.post("/orders", json={"customer_name": "C2", "items": [{"product_id": a["id"], "quantity": 1}]}, headers=staff_h).json()["id"]
    client.patch(f"/orders/{cancelled}/status", json={"status": "CANCELLED"}, headers=manager_h)

    s = client.get("/reports/summary", headers=manager_h).json()
    assert s["total_products"] == 2 and s["total_units_in_stock"] == 6  # a:4 + b:2
    assert s["inventory_value"] == 4 * 10 + 2 * 4
    assert s["total_orders"] == 1 and s["total_revenue"] == 60.0  # cancelled excluded
    assert s["low_stock_products"] == 2

    top = client.get("/reports/top-products?limit=1", headers=manager_h).json()
    assert top[0]["product_id"] == a["id"] and top[0]["units_sold"] == 6 and top[0]["revenue"] == 60.0

    days = client.get("/reports/sales-by-day", headers=manager_h).json()
    assert len(days) == 1 and days[0]["orders"] == 1 and days[0]["revenue"] == 60.0

    low = client.get("/reports/low-stock", headers=manager_h).json()
    assert {i["id"] for i in low} == {a["id"], b["id"]} and low[0]["shortfall"] > 0

    cats = client.get("/reports/inventory-by-category", headers=manager_h).json()
    assert cats[0]["category"] == "Electronics" and cats[0]["units"] == 6

    by_status = {r["status"]: r for r in client.get("/reports/orders-by-status", headers=manager_h).json()}
    assert by_status["CONFIRMED"]["orders"] == 1 and by_status["CANCELLED"]["orders"] == 1

    assert client.get("/reports/top-products?limit=0", headers=manager_h).status_code == 422
    assert client.get("/reports/sales-by-day?date_from=notadate", headers=manager_h).status_code == 422
