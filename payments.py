from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import constants as C
from app.gateways.payment import GatewayTimeout, PaymentGateway
from app.models import Customer, Order, Payment, User
from app.schemas import PaymentIn, PaymentOut
from app.services import loyalty
from app.services.audit import log
from app.services.orders import get_visible_order, refund_points, restock, set_status


def _out(p: Payment, order: Order) -> PaymentOut:
    return PaymentOut(payment_id=p.id, order_id=order.id, status=p.status, method=p.method,
                      provider_ref=p.provider_ref, order_status=order.status)


def pay_order(db: Session, user: User, order_id: int, data: PaymentIn,
              idem_key: str, gateway: PaymentGateway) -> PaymentOut:
    order = get_visible_order(db, user, order_id)

    existing = db.scalar(select(Payment).where(Payment.idempotency_key == idem_key))
    if existing:
        if existing.order_id != order.id:
            raise HTTPException(409, "Idempotency-Key já utilizada em outro pedido")
        return _out(existing, order)

    if order.status != C.CREATED:
        raise HTTPException(409, f"Pedido em {order.status} não aceita pagamento")

    try:
        result = gateway.charge(order.id, float(order.total), data.method, data.token)
    except GatewayTimeout:
        db.add(Payment(order_id=order.id, status="TIMEOUT", method=data.method, amount=order.total))
        log(db, user.id, "PAYMENT_TIMEOUT", "Order", order.id)
        db.commit()
        raise HTTPException(504, "Provedor de pagamento indisponível. Tente novamente com a mesma Idempotency-Key.")

    payment = Payment(order_id=order.id, method=data.method, amount=order.total, idempotency_key=idem_key,
                      provider_ref=result.provider_ref, status="APPROVED" if result.approved else "DECLINED")
    db.add(payment)
    db.flush()

    if result.approved:
        set_status(db, order, C.PAID, user.id)
        customer = db.get(Customer, order.customer_id) if order.customer_id else None
        loyalty.accrue(db, order, customer)
    else:
        set_status(db, order, C.PAYMENT_FAILED, user.id)
        restock(db, order)
        refund_points(db, order)
        log(db, user.id, "PAYMENT_DECLINED", "Order", order.id)
    db.commit()
    return _out(payment, order)
