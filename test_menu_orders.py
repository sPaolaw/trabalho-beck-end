from tests.conftest import make_order, stock_of


def test_cardapio_exclui_fora_de_temporada_e_sem_estoque(client, w):
    ids1 = {i["product_id"] for i in client.get(f"/stores/{w.s1}/menu").json()}
    assert w.cuscuz in ids1 and w.bolo in ids1
    assert w.canjica not in ids1
    ids2 = {i["product_id"] for i in client.get(f"/stores/{w.s2}/menu").json()}
    assert w.suco not in ids2
    assert w.bolo not in ids2


def test_criar_pedido_baixa_estoque_e_calcula_total(client, w):
    r = make_order(client, w.login("c1@t.com"), w, qty=3)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "CREATED" and body["total"] == 60.0
    assert stock_of(client, w.s1, w.cuscuz) == 7


def test_estoque_insuficiente_422_e_nada_e_baixado(client, w):
    h = w.login("c1@t.com")
    body = {"store_id": w.s1, "channel": "APP",
            "items": [{"product_id": w.cuscuz, "quantity": 2}, {"product_id": w.suco, "quantity": 11}]}
    assert client.post("/orders", json=body, headers=h).status_code == 422
    assert stock_of(client, w.s1, w.cuscuz) == 10
    assert stock_of(client, w.s1, w.suco) == 10


def test_produto_fora_de_temporada_nao_pode_ser_pedido(client, w):
    assert make_order(client, w.login("c1@t.com"), w, product=w.canjica).status_code == 422


def test_canal_incompativel_com_perfil_422(client, w):
    assert make_order(client, w.login("c1@t.com"), w, channel="BALCAO").status_code == 422
    assert make_order(client, w.login("att1@t.com"), w, channel="APP").status_code == 422


def test_atendente_registra_pedido_de_balcao_sem_cliente(client, w):
    r = make_order(client, w.login("att1@t.com"), w, channel="BALCAO")
    assert r.status_code == 201 and r.json()["customer_id"] is None


def test_atendente_nao_cria_pedido_em_outra_loja_403(client, w):
    assert make_order(client, w.login("att2@t.com"), w, channel="BALCAO", store=w.s1).status_code == 403


def test_quantidade_invalida_422(client, w):
    assert make_order(client, w.login("c1@t.com"), w, qty=0).status_code == 422


def test_cliente_nao_ve_pedido_de_outro_cliente(client, w):
    oid = make_order(client, w.login("c1@t.com"), w).json()["id"]
    assert client.get(f"/orders/{oid}", headers=w.login("c2@t.com")).status_code == 404
    assert client.get("/orders", headers=w.login("c2@t.com")).json() == []
    assert client.get(f"/orders/{oid}", headers=w.login("c1@t.com")).status_code == 200


def test_equipe_so_ve_pedidos_da_propria_loja(client, w):
    oid = make_order(client, w.login("c1@t.com"), w).json()["id"]
    assert client.get(f"/orders/{oid}", headers=w.login("att1@t.com")).status_code == 200
    assert client.get(f"/orders/{oid}", headers=w.login("att2@t.com")).status_code == 404
    assert len(client.get("/orders", headers=w.login("admin@t.com")).json()) == 1
