from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import ADMIN, MANAGER
from app.core.database import get_db
from app.core.deps import require_roles
from app.models import Product, Store, StoreProduct
from app.schemas import (MenuItemOut, ProductIn, ProductOut, StockIn, StockOut, StoreIn, StoreOut)
from app.services.audit import log
from app.services.orders import in_season

router = APIRouter(tags=["Lojas, produtos e estoque"])


def _money(v: float) -> Decimal:
    return Decimal(str(round(v, 2)))


@router.get("/stores", response_model=list[StoreOut], summary="Lista lojas ativas")
def list_stores(db: Session = Depends(get_db)):
    return db.scalars(select(Store).where(Store.active.is_(True)).order_by(Store.id)).all()


@router.post("/stores", response_model=StoreOut, status_code=201, summary="Cria loja (ADMIN)")
def create_store(data: StoreIn, db: Session = Depends(get_db), admin=Depends(require_roles(ADMIN))):
    store = Store(**data.model_dump())
    db.add(store)
    db.flush()
    log(db, admin.id, "STORE_CREATED", "Store", store.id)
    db.commit()
    return store


@router.put("/stores/{store_id}", response_model=StoreOut, summary="Edita loja (ADMIN)")
def update_store(store_id: int, data: StoreIn, db: Session = Depends(get_db), admin=Depends(require_roles(ADMIN))):
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(404, "Loja não encontrada")
    for k, v in data.model_dump().items():
        setattr(store, k, v)
    log(db, admin.id, "STORE_UPDATED", "Store", store.id)
    db.commit()
    return store


@router.get("/products", response_model=list[ProductOut], summary="Catálogo global (ADMIN)")
def list_products(db: Session = Depends(get_db), _=Depends(require_roles(ADMIN))):
    return db.scalars(select(Product).order_by(Product.id)).all()


@router.post("/products", response_model=ProductOut, status_code=201, summary="Cria produto (ADMIN)")
def create_product(data: ProductIn, db: Session = Depends(get_db), admin=Depends(require_roles(ADMIN))):
    product = Product(**{**data.model_dump(), "base_price": _money(data.base_price)})
    db.add(product)
    db.flush()
    log(db, admin.id, "PRODUCT_CREATED", "Product", product.id)
    db.commit()
    return product


@router.put("/products/{product_id}", response_model=ProductOut, summary="Edita produto (ADMIN)")
def update_product(product_id: int, data: ProductIn, db: Session = Depends(get_db),
                   admin=Depends(require_roles(ADMIN))):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Produto não encontrado")
    for k, v in {**data.model_dump(), "base_price": _money(data.base_price)}.items():
        setattr(product, k, v)
    log(db, admin.id, "PRODUCT_UPDATED", "Product", product.id)
    db.commit()
    return product


@router.get("/stores/{store_id}/menu", response_model=list[MenuItemOut],
            summary="Cardápio da loja: só itens ativos, em estoque e dentro da temporada")
def menu(store_id: int, db: Session = Depends(get_db)):
    store = db.get(Store, store_id)
    if not store or not store.active:
        raise HTTPException(404, "Loja não encontrada")
    rows = db.execute(select(StoreProduct, Product).join(Product, Product.id == StoreProduct.product_id)
                      .where(StoreProduct.store_id == store_id, StoreProduct.active.is_(True),
                             StoreProduct.stock_qty > 0, Product.active.is_(True))
                      .order_by(Product.name)).all()
    today = date.today()
    return [MenuItemOut(product_id=p.id, name=p.name, category=p.category,
                        price=float(sp.price_override if sp.price_override is not None else p.base_price),
                        stock_qty=sp.stock_qty)
            for sp, p in rows if in_season(p, today)]


@router.put("/stores/{store_id}/stock/{product_id}", response_model=StockOut,
            summary="Define estoque/preço local de um produto (GERENTE da loja ou ADMIN)")
def set_stock(store_id: int, product_id: int, data: StockIn, db: Session = Depends(get_db),
              user=Depends(require_roles(MANAGER, ADMIN))):
    if user.role == MANAGER and user.store_id != store_id:
        raise HTTPException(403, "Gerente só ajusta o estoque da própria loja")
    if not db.get(Store, store_id) or not db.get(Product, product_id):
        raise HTTPException(404, "Loja ou produto não encontrado")
    sp = db.scalar(select(StoreProduct).where(StoreProduct.store_id == store_id,
                                              StoreProduct.product_id == product_id))
    before = sp.stock_qty if sp else None
    if sp is None:
        sp = StoreProduct(store_id=store_id, product_id=product_id)
        db.add(sp)
    sp.stock_qty = data.stock_qty
    sp.active = data.active
    sp.price_override = _money(data.price_override) if data.price_override is not None else None
    log(db, user.id, "STOCK_ADJUSTED", "StoreProduct", None,
        f"loja={store_id} produto={product_id} antes={before} depois={data.stock_qty}")
    db.commit()
    return sp
