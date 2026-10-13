from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import Consent, Customer, Product, Store, StoreProduct, User


def main():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if db.scalar(select(User).where(User.email == "admin@raizes.com")):
        print("Seed já aplicado.")
        return

    lojas = [
        Store(name="Raízes Recife Boa Viagem", city="Recife", region="Nordeste", kitchen_type="COMPLETA"),
        Store(name="Raízes Salvador Barra", city="Salvador", region="Nordeste", kitchen_type="REDUZIDA"),
        Store(name="Raízes São Paulo Paulista", city="São Paulo", region="Sudeste", kitchen_type="REDUZIDA"),
    ]
    db.add_all(lojas)
    db.flush()

    ano = date.today().year
    produtos = [
        Product(name="Tapioca de Queijo Coalho", category="PRATO", base_price=Decimal("14.90")),
        Product(name="Cuscuz Recheado", category="PRATO", base_price=Decimal("18.50")),
        Product(name="Bolo de Macaxeira", category="SOBREMESA", base_price=Decimal("9.90")),
        Product(name="Suco de Caju", category="BEBIDA", base_price=Decimal("8.00")),
        Product(name="Café da Manhã Completo", category="COMBO", base_price=Decimal("24.90")),
        Product(name="Canjica Junina", category="SOBREMESA", base_price=Decimal("10.00"), seasonal=True,
                season_start=date(ano, 6, 1), season_end=date(ano, 7, 31)),
    ]
    db.add_all(produtos)
    db.flush()

    for loja in lojas:
        for p in produtos:
            if loja.kitchen_type == "REDUZIDA" and p.name == "Café da Manhã Completo":
                continue
            db.add(StoreProduct(store_id=loja.id, product_id=p.id, stock_qty=50))

    def user(email, senha, role, store_id=None):
        u = User(email=email, password_hash=hash_password(senha), role=role, store_id=store_id)
        db.add(u)
        db.flush()
        return u

    user("admin@raizes.com", "Admin@123", "ADMIN")
    user("gerente.recife@raizes.com", "Gerente@123", "MANAGER", lojas[0].id)
    user("atendente.recife@raizes.com", "Atendente@123", "ATTENDANT", lojas[0].id)
    user("atendente.salvador@raizes.com", "Atendente@123", "ATTENDANT", lojas[1].id)
    cu = user("cliente@exemplo.com", "Cliente@123", "CUSTOMER")
    c = Customer(user_id=cu.id, name="Maria da Silva", cpf="52998224725")
    db.add(c)
    db.flush()
    db.add(Consent(customer_id=c.id, purpose="TERMS", granted=True, terms_version="v1.0"))
    db.commit()
    print("Seed aplicado.")


if __name__ == "__main__":
    main()
