# Raízes do Nordeste — API Back-end

API REST da rede de lanchonetes **Raízes do Nordeste** (trilha Back-end · Projeto Multidisciplinar).
Cobre cardápio e estoque **por loja**, pedidos **multicanal** (APP, PICKUP, BALCAO, TOTEM), pagamento via
**gateway mock desacoplado**, **fidelização com consentimento LGPD**, **auditoria** e **relatórios para a matriz**.

**Stack:** Python 3.11+ · FastAPI · SQLAlchemy 2 · SQLite · JWT (PyJWT) · bcrypt · pytest

## Como executar (3 comandos)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py && uvicorn app.main:app --reload
```

- Swagger/OpenAPI: <http://127.0.0.1:8000/docs> (use **Authorize** e cole o token do `/auth/login`)
- Health check: <http://127.0.0.1:8000/health>

### Credenciais de demonstração (criadas pelo seed)

| Perfil | E-mail | Senha | Escopo |
|---|---|---|---|
| ADMIN (matriz) | admin@raizes.com | Admin@123 | tudo, relatórios, auditoria |
| MANAGER | gerente.recife@raizes.com | Gerente@123 | loja de Recife |
| ATTENDANT | atendente.recife@raizes.com | Atendente@123 | loja de Recife |
| ATTENDANT | atendente.salvador@raizes.com | Atendente@123 | loja de Salvador |
| CUSTOMER | cliente@exemplo.com | Cliente@123 | próprios pedidos |

> Dados fictícios, apenas para demonstração. Em produção, `SECRET_KEY` vem de variável de ambiente.

### Testes automatizados

```bash
pytest -v
```

47 testes (positivos e negativos) usando banco SQLite isolado (`test_raizes.db`, recriado a cada teste).

## Roteiro rápido de demonstração (Swagger)

1. `POST /auth/login` como `cliente@exemplo.com` → copie o token → **Authorize**.
2. `GET /stores/1/menu` → veja o cardápio disponível (a Canjica Junina só aparece entre jun e jul).
3. `POST /customers/me/consents` com `{"purpose":"LOYALTY","granted":true}`.
4. `POST /orders` com `{"store_id":1,"channel":"APP","items":[{"product_id":2,"quantity":2}]}`.
5. `POST /orders/{id}/payment` com header `Idempotency-Key: demo-0001-abcd` e corpo
   `{"method":"PIX","token":"tok_approved"}` → pedido vai para `PAID` e os pontos são creditados.
6. Login como atendente de Recife → `PATCH /orders/{id}/status` com `PREPARING`, `READY`, `DELIVERED`.
7. Login como admin → `GET /reports/sales`, `GET /reports/top-products`, `GET /audit-logs`.

**Tokens do gateway mock:** `tok_approved` aprova · `tok_declined` recusa · `tok_timeout` simula indisponibilidade (HTTP 504).

## Endpoints

| Método | Rota | Perfil | Descrição |
|---|---|---|---|
| POST | `/auth/register` | público | Cadastro de cliente (exige aceite dos termos, valida CPF) |
| POST | `/auth/login` | público | Retorna JWT |
| POST | `/auth/staff` | ADMIN | Cria atendente/gerente vinculado a uma loja |
| GET | `/stores` | público | Lojas ativas |
| POST/PUT | `/stores`, `/stores/{id}` | ADMIN | Cria/edita loja |
| GET/POST/PUT | `/products`, `/products/{id}` | ADMIN | Catálogo global (com sazonalidade) |
| GET | `/stores/{id}/menu` | público | Cardápio: ativo + em estoque + dentro da temporada |
| PUT | `/stores/{id}/stock/{product_id}` | MANAGER (própria loja), ADMIN | Estoque e preço local (auditado) |
| POST | `/orders` | CUSTOMER, ATTENDANT | Cria pedido e baixa estoque atomicamente |
| GET | `/orders`, `/orders/{id}`, `/orders/{id}/history` | autenticado | Somente o que o perfil pode ver |
| POST | `/orders/{id}/payment` | CUSTOMER, ATTENDANT | Pagamento mock (header `Idempotency-Key`) |
| PATCH | `/orders/{id}/status` | ATTENDANT, MANAGER, ADMIN | PAID→PREPARING→READY→DELIVERED |
| POST | `/orders/{id}/cancel` | CUSTOMER, MANAGER, ADMIN | Cancela, devolve estoque/pontos, audita |
| GET | `/customers/me` | CUSTOMER | Dados com CPF mascarado |
| GET/POST | `/customers/me/consents` | CUSTOMER | Consulta, concede ou revoga consentimento |
| GET | `/customers/me/loyalty` | CUSTOMER | Pontos, faixa e extrato |
| DELETE | `/customers/me` | CUSTOMER | Anonimiza a conta (LGPD) |
| GET | `/reports/sales`, `/reports/top-products` | ADMIN | Vendas por loja/região; mais vendidos |
| GET | `/audit-logs` | ADMIN | Auditoria de operações sensíveis |
| GET | `/health` | público | Disponibilidade da API e do banco |

Códigos de erro: `401` sem/ com token inválido · `403` perfil sem permissão · `404` não encontrado
(inclui pedido de outro cliente/loja, para não revelar existência) · `409` transição de status inválida ou
conflito de dados · `422` validação, estoque insuficiente ou regra de negócio · `504` timeout do provedor de pagamento.

## Arquitetura

```
app/
  main.py          # app FastAPI, Swagger, health
  core/            # config, banco, segurança (JWT/bcrypt/CPF), dependências de auth/roles
  models.py        # entidades SQLAlchemy (DER)
  schemas.py       # DTOs Pydantic (contratos; nunca expõem senha/hash)
  routers/         # camada HTTP: valida entrada, autoriza, delega
  services/        # regras de negócio: pedidos, pagamentos, fidelização, auditoria
  gateways/        # interface PaymentGateway + implementação mock
seed.py            # dados de demonstração (idempotente)
tests/             # pytest
```

Fluxo: `router → service → ORM`. Regras de negócio ficam nos *services*, não nos routers.

## Decisões de projeto (e por quê)

| Decisão | Justificativa (ligada ao estudo de caso) |
|---|---|
| Cardápio e estoque em `StoreProduct` (loja × produto) | "Nem todas as unidades são idênticas": cada loja decide o que vende, quanto tem e pode ter preço local |
| Sazonalidade em `Product` (janela de datas) | Itens juninos só existem em certas épocas; validado no cardápio **e** no pedido |
| Baixa de estoque por `UPDATE ... WHERE stock_qty >= n` dentro de transação | Evita venda acima do estoque em pedidos simultâneos (horário de pico) e garante tudo-ou-nada |
| `PaymentGateway` como interface + mock | Pagamento é externo e desacoplado; trocar por provedor real não altera os serviços |
| `Idempotency-Key` + registro de tentativas | Tolerância a falhas: retentativa após timeout não cobra nem pontua em duplicidade |
| Pedido continua `CREATED` após timeout | Resultado desconhecido não é recusa; o cliente pode tentar de novo |
| Canal × perfil (cliente: APP/PICKUP; equipe: BALCAO/TOTEM) | Rastreabilidade de origem do pedido em cada canal |
| Consentimento append-only por finalidade | LGPD: prova de quando e qual versão do termo foi aceita/revogada |
| Pontos só acumulam/resgatam com consentimento `LOYALTY` | "Respeitar a privacidade é obrigatório" |
| Anonimização preserva pedidos | Equilíbrio entre direito ao esquecimento e obrigação fiscal/relatórios da matriz |
| `AuditLog` sem dados pessoais nos detalhes | Auditoria (cancelamentos, descontos, ajustes, logins) sem criar novo risco de vazamento |
| 404 em vez de 403 para pedido alheio | Não confirma a existência do recurso |
| Snapshot de nome/preço em `OrderItem` | Histórico fiel mesmo se o catálogo mudar |

### Regras de negócio

- **Status:** `CREATED → PAID → PREPARING → READY → DELIVERED`. Recusa de pagamento → `PAYMENT_FAILED` (estoque e pontos devolvidos).
  `CANCELLED` a partir de `CREATED`, `PAID` ou `PREPARING`. Cliente só cancela pedido não pago; após o pagamento, só gerente/admin (com motivo, auditado).
- **Fidelização (premissas do projeto):** 1 ponto a cada R$ 10 pagos · 1 ponto = R$ 0,10 no resgate ·
  faixas por pontos acumulados: BRONZE (0%), PRATA ≥ 200 (5%), OURO ≥ 500 (10%).
- **Campanhas segmentadas por idade/frequência:** documentadas como evolução (os dados e o consentimento `PROFILING` já existem), não implementadas.

## Limitações conhecidas e evolução

- **Banco:** SQLite por praticidade. Para produção, PostgreSQL (basta alterar `DATABASE_URL`) com **Alembic** para migrations
  versionadas; hoje as tabelas são criadas via ORM (`create_all`) e o `seed.py` popula os dados.
- **Escala/alta disponibilidade:** API é *stateless* (JWT), então escala horizontalmente atrás de um balanceador;
  evoluir para cache de cardápio (Redis), fila para pagamentos/relatórios e réplica de leitura.
- **Segurança:** faltam limite de tentativas de login (rate limit), refresh token e criptografia do CPF em repouso.
- **Sazonalidade:** janela com datas absolutas; recorrência anual automática seria uma evolução.
- **Pagamento:** mock síncrono; um provedor real normalmente usa *webhook* de confirmação assíncrona.
