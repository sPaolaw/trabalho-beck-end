import os

os.environ["DATABASE_URL"] = "sqlite:///./test_raizes.db"

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.main import app
from app.models import Customer, Product, Store, StoreProduct, User

PWD = "Senha@1234"
CPF1, CPF2 = "52998224725", "11144477735"


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def w(db, client):
    today = date.today()
    s1 = Store(name="Recife Centro", city="Recife", region="Nordeste", kitchen_type="COMPLETA")
    s2 = Store(name="Salvador Barra", city="Salvador", region="Nordeste", kitchen_type="REDUZIDA")
    db.add_all([s1, s2]); db.flush()
    cuscuz = Product(name="Cuscuz Recheado", category="PRATO", base_price=Decimal("20.00"))
    suco = Product(name="Suco de Caju", category="BEBIDA", base_price=Decimal("10.00"))
    canjica = Product(name="Canjica Junina", category="SOBREMESA", base_price=Decimal("8.00"), seasonal=True,
                      season_start=today + timedelta(days=60), season_end=today + timedelta(days=90))
    bolo = Product(name="Bolo Sazonal", category="SOBREMESA", base_price=Decimal("9.00"), seasonal=True,
                   season_start=today - timedelta(days=5), season_end=today + timedelta(days=5))
    db.add_all([cuscuz, suco, canjica, bolo]); db.flush()
    for p in (cuscuz, suco, canjica, bolo):
        db.add(StoreProduct(store_id=s1.id, product_id=p.id, stock_qty=10))
    db.add(StoreProduct(store_id=s2.id, product_id=cuscuz.id, stock_qty=5))
    db.add(StoreProduct(store_id=s2.id, product_id=suco.id, stock_qty=0))

    def mk(email, role, store_id=None):
        u = User(email=email, password_hash=hash_password(PWD), role=role, store_id=store_id)
        db.add(u); db.flush()
        return u

    mk("admin@t.com", "ADMIN")
    mk("gerente1@t.com", "MANAGER", s1.id)
    mk("att1@t.com", "ATTENDANT", s1.id)
    mk("att2@t.com", "ATTENDANT", s2.id)
    u1, u2 = mk("c1@t.com", "CUSTOMER"), mk("c2@t.com", "CUSTOMER")
    c1 = Customer(user_id=u1.id, name="Cliente Um", cpf=CPF1)
    c2 = Customer(user_id=u2.id, name="Cliente Dois", cpf=CPF2)
    db.add_all([c1, c2]); db.commit()

    def login(email):
        r = client.post("/auth/login", json={"email": email, "password": PWD})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return SimpleNamespace(s1=s1.id, s2=s2.id, cuscuz=cuscuz.id, suco=suco.id, canjica=canjica.id,
                           bolo=bolo.id, c1=c1.id, c2=c2.id, login=login)


def stock_of(client, store_id, product_id):
    items = client.get(f"/stores/{store_id}/menu").json()
    return next((i["stock_qty"] for i in items if i["product_id"] == product_id), 0)


def make_order(client, headers, w, qty=1, channel="APP", store=None, product=None, **extra):
    body = {"store_id": store or w.s1, "channel": channel,
            "items": [{"product_id": product or w.cuscuz, "quantity": qty}], **extra}
    return client.post("/orders", json=body, headers=headers)


def pay(client, headers, order_id, token="tok_approved", key="chave-0001-abcd"):
    return client.post(f"/orders/{order_id}/payment", json={"method": "PIX", "token": token},
                       headers={**headers, "Idempotency-Key": key})


def grant_loyalty(client, headers):
    return client.post("/customers/me/consents", headers=headers,
                       json={"purpose": "LOYALTY", "granted": True, "terms_version": "v1.0"})
