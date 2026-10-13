from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.constants import ADMIN, REVENUE_STATUSES
from app.core.database import get_db
from app.core.deps import require_roles
from app.models import AuditLog, Order, OrderItem, Product, Store
from app.schemas import AuditOut

router = APIRouter(tags=["Matriz: relatórios e auditoria"])


@router.get("/reports/sales", summary="Vendas por loja e por região (pedidos pagos em diante)")
def sales(region: str | None = None, db: Session = Depends(get_db), _=Depends(require_roles(ADMIN))):
    q = (select(Store.id, Store.name, Store.region, func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
         .join(Order, Order.store_id == Store.id).where(Order.status.in_(REVENUE_STATUSES))
         .group_by(Store.id).order_by(Store.id))
    if region:
        q = q.where(Store.region == region)
    by_store = [{"store_id": i, "store": n, "region": r, "orders": c, "revenue": round(float(t), 2)}
                for i, n, r, c, t in db.execute(q).all()]
    regions: dict[str, dict] = {}
    for s in by_store:
        agg = regions.setdefault(s["region"], {"region": s["region"], "orders": 0, "revenue": 0.0})
        agg["orders"] += s["orders"]
        agg["revenue"] = round(agg["revenue"] + s["revenue"], 2)
    return {"by_store": by_store, "by_region": list(regions.values())}


@router.get("/reports/top-products", summary="Produtos mais vendidos")
def top_products(store_id: int | None = None, limit: int = Query(5, ge=1, le=50),
                 db: Session = Depends(get_db), _=Depends(require_roles(ADMIN))):
    q = (select(Product.id, Product.name, func.sum(OrderItem.quantity).label("qty"))
         .join(OrderItem, OrderItem.product_id == Product.id).join(Order, Order.id == OrderItem.order_id)
         .where(Order.status.in_(REVENUE_STATUSES)).group_by(Product.id).order_by(desc("qty")).limit(limit))
    if store_id:
        q = q.where(Order.store_id == store_id)
    return [{"product_id": i, "product": n, "quantity_sold": int(q_)} for i, n, q_ in db.execute(q).all()]


@router.get("/audit-logs", response_model=list[AuditOut], summary="Consulta de auditoria (ADMIN)")
def audit_logs(action: str | None = None, limit: int = Query(100, ge=1, le=500),
               db: Session = Depends(get_db), _=Depends(require_roles(ADMIN))):
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        q = q.where(AuditLog.action == action)
    return db.scalars(q).all()
