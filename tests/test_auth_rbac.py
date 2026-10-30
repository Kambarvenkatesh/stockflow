def register(client, **over):
    body = {"username": "alice", "email": "alice@example.com", "password": "Secret123", **over}
    return client.post("/auth/register", json=body)


def test_register_success_gets_staff_role(client):
    r = register(client)
    assert r.status_code == 201
    assert r.json()["role"] == "staff"
    assert "password" not in r.text and "hashed_password" not in r.text


def test_register_duplicate_username_conflict(client):
    register(client)
    assert register(client, email="other@example.com").status_code == 409


def test_register_weak_password_rejected(client):
    assert register(client, password="onlyletters").status_code == 422
    assert register(client, password="short1").status_code == 422


def test_register_invalid_email(client):
    assert register(client, email="not-an-email").status_code == 422


def test_login_success_and_me(client):
    register(client)
    r = client.post("/auth/login", data={"username": "alice", "password": "Secret123"})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["username"] == "alice"


def test_login_wrong_password_401(client):
    register(client)
    r = client.post("/auth/login", data={"username": "alice", "password": "Wrong1234"})
    assert r.status_code == 401


def test_no_token_401(client):
    assert client.get("/products").status_code == 401


def test_garbage_token_401(client):
    r = client.get("/products", headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code == 401


def test_staff_cannot_create_category(client, staff_h):
    assert client.post("/categories", json={"name": "Toys"}, headers=staff_h).status_code == 403


def test_manager_can_create_but_not_delete(client, manager_h):
    cat = client.post("/categories", json={"name": "Toys"}, headers=manager_h)
    assert cat.status_code == 201
    assert client.delete(f"/categories/{cat.json()['id']}", headers=manager_h).status_code == 403


def test_admin_can_delete_category(client, manager_h, admin_h):
    cid = client.post("/categories", json={"name": "Toys"}, headers=manager_h).json()["id"]
    assert client.delete(f"/categories/{cid}", headers=admin_h).status_code == 204
    assert client.get(f"/categories/{cid}", headers=admin_h).status_code == 404


def test_staff_cannot_access_reports_or_users(client, staff_h):
    assert client.get("/reports/summary", headers=staff_h).status_code == 403
    assert client.get("/users", headers=staff_h).status_code == 403


def test_admin_can_promote_user_and_cannot_demote_self(client, admin_h):
    uid = register(client).json()["id"]
    r = client.patch(f"/users/{uid}", json={"role": "manager"}, headers=admin_h)
    assert r.status_code == 200 and r.json()["role"] == "manager"
    me = client.get("/auth/me", headers=admin_h).json()
    assert client.patch(f"/users/{me['id']}", json={"role": "staff"}, headers=admin_h).status_code == 403


def test_deactivated_user_token_rejected(client, admin_h):
    uid = register(client).json()["id"]
    token = client.post("/auth/login", data={"username": "alice", "password": "Secret123"}).json()["access_token"]
    client.patch(f"/users/{uid}", json={"is_active": False}, headers=admin_h)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
