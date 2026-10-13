from tests.conftest import CPF2


def _reg(client, **over):
    body = {"email": "novo@t.com", "password": "Senha@1234", "name": "Novo Cliente",
            "cpf": CPF2, "accept_terms": True}
    return client.post("/auth/register", json={**body, **over})


def test_register_ok_nao_expoe_senha(client):
    r = _reg(client)
    assert r.status_code == 201
    assert "password" not in r.text and "hash" not in r.text and "cpf" not in r.text


def test_register_exige_aceite_dos_termos(client):
    assert _reg(client, accept_terms=False).status_code == 422


def test_register_cpf_invalido(client):
    assert _reg(client, cpf="11111111111").status_code == 422


def test_register_email_duplicado(client):
    assert _reg(client).status_code == 201
    assert _reg(client, cpf=None).status_code == 409


def test_login_ok_e_senha_errada(client, w):
    assert client.post("/auth/login", json={"email": "c1@t.com", "password": "Senha@1234"}).status_code == 200
    assert client.post("/auth/login", json={"email": "c1@t.com", "password": "errada123"}).status_code == 401


def test_rota_protegida_sem_token_401(client):
    assert client.get("/orders").status_code == 401


def test_token_invalido_401(client):
    assert client.get("/orders", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_cliente_nao_cria_produto_403(client, w):
    r = client.post("/products", headers=w.login("c1@t.com"),
                    json={"name": "X Teste", "category": "PRATO", "base_price": 5})
    assert r.status_code == 403


def test_admin_cria_produto_e_valida_sazonal(client, w):
    h = w.login("admin@t.com")
    ok = client.post("/products", headers=h, json={"name": "Tapioca", "category": "PRATO", "base_price": 12.5})
    assert ok.status_code == 201
    bad = client.post("/products", headers=h, json={"name": "Canjica 2", "category": "DOCE",
                                                    "base_price": 5, "seasonal": True})
    assert bad.status_code == 422


def test_gerente_so_ajusta_estoque_da_propria_loja(client, w):
    h = w.login("gerente1@t.com")
    assert client.put(f"/stores/{w.s1}/stock/{w.cuscuz}", headers=h, json={"stock_qty": 99}).status_code == 200
    assert client.put(f"/stores/{w.s2}/stock/{w.cuscuz}", headers=h, json={"stock_qty": 99}).status_code == 403


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"
