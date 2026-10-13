from app.models import LoyaltyTransaction, Customer
from tests.conftest import grant_loyalty, make_order, pay


def test_sem_consentimento_nao_acumula_pontos(client, w):
    h = w.login("c1@t.com")
    oid = make_order(client, h, w, qty=2).json()["id"]
    pay(client, h, oid)
    assert client.get("/customers/me/loyalty", headers=h).json()["points"] == 0


def test_com_consentimento_acumula_1_ponto_a_cada_10_reais(client, w):
    h = w.login("c1@t.com")
    grant_loyalty(client, h)
    oid = make_order(client, h, w, qty=2).json()["id"]
    pay(client, h, oid)
    assert client.get("/customers/me/loyalty", headers=h).json()["points"] == 4


def test_revogar_consentimento_interrompe_acumulo(client, w):
    h = w.login("c1@t.com")
    grant_loyalty(client, h)
    client.post("/customers/me/consents", headers=h, json={"purpose": "LOYALTY", "granted": False})
    oid = make_order(client, h, w, qty=2).json()["id"]
    pay(client, h, oid)
    assert client.get("/customers/me/loyalty", headers=h).json()["points"] == 0
    cons = {c["purpose"]: c["granted"] for c in client.get("/customers/me/consents", headers=h).json()}
    assert cons["LOYALTY"] is False


def test_desconto_da_faixa_prata_e_resgate_de_pontos(client, w, db):
    h = w.login("c1@t.com")
    grant_loyalty(client, h)
    cust = db.get(Customer, w.c1)
    cust.loyalty_points = 200
    db.add(LoyaltyTransaction(customer_id=cust.id, points=200, type="EARN"))
    db.commit()
    r = make_order(client, h, w, qty=2, use_points=10)
    assert r.status_code == 201
    assert r.json()["discount"] == 3.0 and r.json()["total"] == 37.0
    loy = client.get("/customers/me/loyalty", headers=h).json()
    assert loy["tier"] == "PRATA" and loy["points"] == 190


def test_resgate_sem_consentimento_422(client, w):
    assert make_order(client, w.login("c1@t.com"), w, use_points=5).status_code == 422


def test_resgate_acima_do_saldo_422(client, w):
    h = w.login("c1@t.com")
    grant_loyalty(client, h)
    assert make_order(client, h, w, use_points=50).status_code == 422


def test_pagamento_recusado_devolve_pontos_resgatados(client, w, db):
    h = w.login("c1@t.com")
    grant_loyalty(client, h)
    cust = db.get(Customer, w.c1)
    cust.loyalty_points = 20
    db.commit()
    oid = make_order(client, h, w, qty=2, use_points=20).json()["id"]
    assert client.get("/customers/me/loyalty", headers=h).json()["points"] == 0
    pay(client, h, oid, token="tok_declined")
    assert client.get("/customers/me/loyalty", headers=h).json()["points"] == 20


def test_dados_do_cliente_com_cpf_mascarado(client, w):
    r = client.get("/customers/me", headers=w.login("c1@t.com")).json()
    assert r["cpf_masked"] == "***.***.***-25" and "52998224725" not in str(r)


def test_anonimizacao_remove_dados_bloqueia_login_e_preserva_pedidos(client, w, db):
    h = w.login("c1@t.com")
    oid = make_order(client, h, w).json()["id"]
    pay(client, h, oid)
    assert client.delete("/customers/me", headers=h).status_code == 204
    db.expire_all()
    cust = db.get(Customer, w.c1)
    assert cust.anonymized and cust.name == "ANONIMIZADO" and cust.cpf is None
    assert client.post("/auth/login", json={"email": "c1@t.com", "password": "Senha@1234"}).status_code == 401
    vendas = client.get("/reports/sales", headers=w.login("admin@t.com")).json()
    assert vendas["by_store"][0]["orders"] == 1


def test_relatorios_restritos_ao_admin(client, w):
    for email in ("c1@t.com", "att1@t.com", "gerente1@t.com"):
        assert client.get("/reports/sales", headers=w.login(email)).status_code == 403
        assert client.get("/audit-logs", headers=w.login(email)).status_code == 403


def test_relatorio_de_vendas_por_loja_e_regiao_e_top_produtos(client, w):
    h = w.login("c1@t.com")
    pay(client, h, make_order(client, h, w, qty=2).json()["id"], key="rel-chave-0001")
    pay(client, h, make_order(client, h, w, qty=1, store=w.s2).json()["id"], key="rel-chave-0002")
    make_order(client, h, w, qty=5)
    admin = w.login("admin@t.com")
    vendas = client.get("/reports/sales", headers=admin).json()
    assert {s["store_id"]: s["revenue"] for s in vendas["by_store"]} == {w.s1: 40.0, w.s2: 20.0}
    assert vendas["by_region"] == [{"region": "Nordeste", "orders": 2, "revenue": 60.0}]
    top = client.get("/reports/top-products", headers=admin).json()
    assert top[0]["product_id"] == w.cuscuz and top[0]["quantity_sold"] == 3


def test_auditoria_registra_login_falho_e_consentimento_sem_dados_pessoais(client, w):
    client.post("/auth/login", json={"email": "c1@t.com", "password": "errada123"})
    grant_loyalty(client, w.login("c1@t.com"))
    logs = client.get("/audit-logs", headers=w.login("admin@t.com")).json()
    actions = {l["action"] for l in logs}
    assert {"LOGIN_FAILED", "LOGIN", "CONSENT_GRANTED"} <= actions
    assert "c1@t.com" not in str(logs)
