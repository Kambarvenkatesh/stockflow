import os

os.environ["BCRYPT_ROUNDS"] = "4"  # fast hashing in tests; must be set before app import

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Role, User
from app.security import hash_password

PASSWORD = "Passw0rd!"


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    yield TestClient(app)  # no 'with' -> lifespan (real DB create_all) is not triggered
    app.dependency_overrides.clear()


def _headers(client, db, role: Role):
    db.add(User(username=role.value, email=f"{role.value}@test.com", hashed_password=hash_password(PASSWORD), role=role))
    db.commit()
    r = client.post("/auth/login", data={"username": role.value, "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin_h(client, db_session):
    return _headers(client, db_session, Role.ADMIN)


@pytest.fixture()
def manager_h(client, db_session):
    return _headers(client, db_session, Role.MANAGER)


@pytest.fixture()
def staff_h(client, db_session):
    return _headers(client, db_session, Role.STAFF)


@pytest.fixture()
def category(client, manager_h):
    return client.post("/categories", json={"name": "Electronics"}, headers=manager_h).json()


@pytest.fixture()
def make_product(client, manager_h, category):
    counter = {"n": 0}

    def _make(stock=50, price="10.00", **extra):
        counter["n"] += 1
        body = {"sku": f"SKU-{counter['n']:03}", "name": f"Product {counter['n']}", "price": price,
                "category_id": category["id"], **extra}
        p = client.post("/products", json=body, headers=manager_h).json()
        if stock:
            client.post("/stock/in", json={"product_id": p["id"], "quantity": stock}, headers=manager_h)
        return p

    return _make
