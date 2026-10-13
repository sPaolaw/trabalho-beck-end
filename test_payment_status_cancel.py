from tests.conftest import grant_loyalty, make_order, pay, stock_of


def _order(client, w, qty=2):
    h = w.login("c1@t.com")
    return h, make_order(client, h, w, qty=qty).json()["id"]


def test_pagamento_aprovado_marca_pedido_como_pago(client, w):
    h, oid = _order(client, w)
    r = pay(client, h, oid)
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED" and r.json()["order_status"] == "PAID"


def test_pagamento_recusado_devolve_estoque(client, w):
    h, oid = _order(client, w, qty=3)
    assert stock_of(client, w.s1, w.cuscuz) == 7
    r = pay(client, h, oid, token="tok_declined")
    assert r.json()["status"] == "DECLINED" and r.json()["order_status"] == "PAYMENT_FAILED"
    assert stock_of(client, w.s1, w.cuscuz) == 10


def test_timeout_retorna_504_pedido_continua_created_e_permite_retentativa(client, w):
    h, oid = _order(client, w)
    assert pay(client, h, oid, token="tok_timeout").status_code == 504
    assert client.get(f"/orders/{oid}", headers=h).json()["status"] == "CREATED"
    assert pay(client, h, oid, token="tok_approved").json()["order_status"] == "PAID"


def test_idempotencia_mesma_chave_nao_cobra_nem_pontua_duas_vezes(client, w):
    h = w.login("c1@t.com")
    grant_loyalty(client, h)
    oid = make_order(client, h, w, qty=2).json()["id"]
    first = pay(client, h, oid, key="idem-chave-0001").json()
    again = pay(client, h, oid, key="idem-chave-0001").json()
    assert first["payment_id"] == again["payment_id"]
    assert client.get("/customers/me/loyalty", headers=h).json()["points"] == 4


def test_pagar_pedido_ja_pago_com_chave_nova_409(client, w):
    h, oid = _order(client, w)
    pay(client, h, oid, key="chave-aaaa-0001")
    assert pay(client, h, oid, key="chave-bbbb-0002").status_code == 409


def test_pagamento_sem_idempotency_key_422(client, w):
    h, oid = _order(client, w)
    r = client.post(f"/orders/{oid}/payment", json={"method": "PIX", "token": "tok_approved"}, headers=h)
    assert r.status_code == 422


def test_fluxo_completo_de_status_e_historico(client, w):
    h, oid = _order(client, w)
    pay(client, h, oid)
    att = w.login("att1@t.com")
    for s in ("PREPARING", "READY", "DELIVERED"):
        r = client.patch(f"/orders/{oid}/status", json={"status": s}, headers=att)
        assert r.status_code == 200 and r.json()["status"] == s
    hist = client.get(f"/orders/{oid}/history", headers=h).json()
    assert [x["to_status"] for x in hist] == ["CREATED", "PAID", "PREPARING", "READY", "DELIVERED"]


def test_transicao_invalida_409(client, w):
    h, oid = _order(client, w)
    att = w.login("att1@t.com")
    assert client.patch(f"/orders/{oid}/status", json={"status": "READY"}, headers=att).status_code == 409
    pay(client, h, oid)
    assert client.patch(f"/orders/{oid}/status", json={"status": "DELIVERED"}, headers=att).status_code == 409


def test_cliente_nao_altera_status_403(client, w):
    h, oid = _order(client, w)
    assert client.patch(f"/orders/{oid}/status", json={"status": "PAID"}, headers=h).status_code == 403


def test_atendente_de_outra_loja_nao_acessa_pedido(client, w):
    h, oid = _order(client, w)
    pay(client, h, oid)
    r = client.patch(f"/orders/{oid}/status", json={"status": "PREPARING"}, headers=w.login("att2@t.com"))
    assert r.status_code == 404


def test_cliente_cancela_pedido_nao_pago_e_estoque_volta(client, w):
    h, oid = _order(client, w, qty=4)
    r = client.post(f"/orders/{oid}/cancel", json={"reason": "desisti"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
    assert stock_of(client, w.s1, w.cuscuz) == 10


def test_cliente_nao_cancela_pedido_pago_403(client, w):
    h, oid = _order(client, w)
    pay(client, h, oid)
    assert client.post(f"/orders/{oid}/cancel", json={"reason": "desisti"}, headers=h).status_code == 403


def test_gerente_cancela_pedido_pago_estorna_e_gera_auditoria(client, w):
    h = w.login("c1@t.com")
    grant_loyalty(client, h)
    oid = make_order(client, h, w, qty=2).json()["id"]
    pay(client, h, oid)
    assert client.get("/customers/me/loyalty", headers=h).json()["points"] == 4
    r = client.post(f"/orders/{oid}/cancel", json={"reason": "erro de preparo"}, headers=w.login("gerente1@t.com"))
    assert r.status_code == 200
    assert stock_of(client, w.s1, w.cuscuz) == 10
    assert client.get("/customers/me/loyalty", headers=h).json()["points"] == 0
    logs = client.get("/audit-logs?action=ORDER_CANCELLED", headers=w.login("admin@t.com")).json()
    assert len(logs) == 1 and "erro de preparo" in logs[0]["details"]


def test_cancelar_pedido_entregue_409(client, w):
    h, oid = _order(client, w)
    pay(client, h, oid)
    att = w.login("att1@t.com")
    for s in ("PREPARING", "READY", "DELIVERED"):
        client.patch(f"/orders/{oid}/status", json={"status": s}, headers=att)
    r = client.post(f"/orders/{oid}/cancel", json={"reason": "tarde demais"}, headers=w.login("gerente1@t.com"))
    assert r.status_code == 409
