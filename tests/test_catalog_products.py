def test_category_duplicate_and_validation(client, manager_h):
    assert client.post("/categories", json={"name": "Books"}, headers=manager_h).status_code == 201
    assert client.post("/categories", json={"name": "books"}, headers=manager_h).status_code == 409
    assert client.post("/categories", json={"name": "x"}, headers=manager_h).status_code == 422


def test_supplier_validation(client, manager_h):
    ok = client.post("/suppliers", json={"name": "Acme", "email": "a@acme.com", "phone": "+91 98765 43210"}, headers=manager_h)
    assert ok.status_code == 201
    assert client.post("/suppliers", json={"name": "Bad", "phone": "abc"}, headers=manager_h).status_code == 422
    assert client.post("/suppliers", json={"name": "Bad2", "email": "nope"}, headers=manager_h).status_code == 422


def test_cannot_delete_category_with_products(client, admin_h, category, make_product):
    make_product(stock=0)
    r = client.delete(f"/categories/{category['id']}", headers=admin_h)
    assert r.status_code == 409


def test_create_product_normalises_sku_and_starts_at_zero_stock(client, manager_h, category):
    r = client.post("/products", json={"sku": "abc-1", "name": "Widget", "price": "9.99", "category_id": category["id"]}, headers=manager_h)
    assert r.status_code == 201
    assert r.json()["sku"] == "ABC-1" and r.json()["quantity"] == 0 and r.json()["price"] == 9.99


def test_product_invalid_inputs(client, manager_h, category):
    base = {"sku": "ABC-2", "name": "Widget", "price": "5", "category_id": category["id"]}
    assert client.post("/products", json={**base, "price": "-1"}, headers=manager_h).status_code == 422
    assert client.post("/products", json={**base, "price": "1.999"}, headers=manager_h).status_code == 422
    assert client.post("/products", json={**base, "sku": "a b"}, headers=manager_h).status_code == 422
    assert client.post("/products", json={**base, "category_id": 999}, headers=manager_h).status_code == 404
    assert client.post("/products", json={**base, "supplier_id": 999}, headers=manager_h).status_code == 404


def test_duplicate_sku_conflict(client, manager_h, category):
    body = {"sku": "DUP-1", "name": "One", "price": "5", "category_id": category["id"]}
    assert client.post("/products", json=body, headers=manager_h).status_code == 201
    assert client.post("/products", json={**body, "name": "Two"}, headers=manager_h).status_code == 409


def test_update_and_get_product(client, manager_h, make_product):
    p = make_product(stock=0)
    r = client.put(f"/products/{p['id']}", json={"price": "19.50", "name": "Renamed"}, headers=manager_h)
    assert r.status_code == 200 and r.json()["price"] == 19.5 and r.json()["name"] == "Renamed"
    assert client.get("/products/9999", headers=manager_h).status_code == 404


def test_search_filter_sort_paginate(client, manager_h, make_product):
    make_product(price="5.00", name="Red Pen")
    make_product(price="15.00", name="Blue Pen")
    make_product(price="25.00", name="Notebook")
    make_product(price="35.00", name="Stapler")

    r = client.get("/products?search=pen", headers=manager_h).json()
    assert r["total"] == 2

    r = client.get("/products?min_price=10&max_price=30&sort_by=price&order=desc", headers=manager_h).json()
    assert [p["name"] for p in r["items"]] == ["Notebook", "Blue Pen"]

    r = client.get("/products?size=2&page=2&sort_by=price", headers=manager_h).json()
    assert r["total"] == 4 and r["pages"] == 2 and len(r["items"]) == 2 and r["items"][0]["name"] == "Notebook"

    assert client.get("/products?sort_by=password", headers=manager_h).status_code == 422
    assert client.get("/products?page=0", headers=manager_h).status_code == 422
    assert client.get("/products?size=1000", headers=manager_h).status_code == 422


def test_low_stock_filter(client, manager_h, make_product):
    make_product(stock=3, reorder_level=5)
    make_product(stock=100, reorder_level=5)
    r = client.get("/products?low_stock=true", headers=manager_h).json()
    assert r["total"] == 1


def test_delete_product_rules(client, admin_h, make_product):
    fresh = make_product(stock=0)
    used = make_product(stock=5)
    assert client.delete(f"/products/{fresh['id']}", headers=admin_h).status_code == 204
    assert client.delete(f"/products/{used['id']}", headers=admin_h).status_code == 409
