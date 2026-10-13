from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import ADMIN, ATTENDANT, CUSTOMER, MANAGER
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.gateways.payment import PaymentGateway, get_gateway
from app.models import OrderStatusHistory
from app.schemas import (CancelIn, HistoryOut, OrderCreate, OrderOut, PaymentIn, PaymentOut, StatusIn)
from app.services import orders as svc
from app.services.payments import pay_order

router = APIRouter(prefix="/orders", tags=["Pedidos e pagamento"])


@router.post("", response_model=OrderOut, status_code=201,
             summary="Cria pedido, valida estoque e sazonalidade e baixa o estoque (transação atômica)")
def create(data: OrderCreate, db: Session = Depends(get_db), user=Depends(require_roles(CUSTOMER, ATTENDANT))):
    return svc.create_order(db, user, data)


@router.get("", response_model=list[OrderOut], summary="Lista pedidos visíveis ao perfil")
def list_(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return svc.list_orders(db, user)


@router.get("/{order_id}", response_model=OrderOut, summary="Detalha um pedido")
def get(order_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return svc.get_visible_order(db, user, order_id)


@router.get("/{order_id}/history", response_model=list[HistoryOut], summary="Histórico de status")
def history(order_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    order = svc.get_visible_order(db, user, order_id)
    return db.scalars(select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id)
                      .order_by(OrderStatusHistory.id)).all()


@router.post("/{order_id}/payment", response_model=PaymentOut,
             summary="Pagamento do pedido")
def pay(order_id: int, data: PaymentIn, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=80),
        db: Session = Depends(get_db), user=Depends(require_roles(CUSTOMER, ATTENDANT)),
        gateway: PaymentGateway = Depends(get_gateway)):
    return pay_order(db, user, order_id, data, idempotency_key, gateway)


@router.patch("/{order_id}/status", response_model=OrderOut,
              summary="Avança o status: PAID→PREPARING→READY→DELIVERED")
def update_status(order_id: int, data: StatusIn, db: Session = Depends(get_db),
                  user=Depends(require_roles(ATTENDANT, MANAGER, ADMIN))):
    order = svc.get_visible_order(db, user, order_id)
    return svc.advance_status(db, user, order, data.status)


@router.post("/{order_id}/cancel", response_model=OrderOut,
             summary="Cancela, devolve estoque/pontos e audita")
def cancel(order_id: int, data: CancelIn, db: Session = Depends(get_db),
           user=Depends(require_roles(CUSTOMER, MANAGER, ADMIN))):
    order = svc.get_visible_order(db, user, order_id)
    return svc.cancel_order(db, user, order, data.reason)
