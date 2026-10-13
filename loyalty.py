from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import POINTS_PER_REAIS, TIERS
from app.models import Consent, Customer, LoyaltyTransaction, Order


def current_consents(db: Session, customer_id: int) -> list[Consent]:
    rows = db.scalars(select(Consent).where(Consent.customer_id == customer_id).order_by(Consent.id)).all()
    state: dict[str, Consent] = {}
    for r in rows:
        state[r.purpose] = r
    return list(state.values())


def consent_active(db: Session, customer_id: int, purpose: str = "LOYALTY") -> bool:
    last = db.scalar(select(Consent).where(Consent.customer_id == customer_id, Consent.purpose == purpose)
                     .order_by(Consent.id.desc()).limit(1))
    return bool(last and last.granted)


def lifetime_points(db: Session, customer_id: int) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(LoyaltyTransaction.points), 0))
                         .where(LoyaltyTransaction.customer_id == customer_id,
                                LoyaltyTransaction.type == "EARN")))


def tier_for(db: Session, customer_id: int) -> tuple[str, int]:
    lp = lifetime_points(db, customer_id)
    for name, min_points, pct in TIERS:
        if lp >= min_points:
            return name, pct
    return "BRONZE", 0


def is_eligible(db: Session, customer: Customer | None) -> bool:
    return bool(customer and not customer.anonymized and consent_active(db, customer.id))


def accrue(db: Session, order: Order, customer: Customer | None) -> int:
    if not is_eligible(db, customer):
        return 0
    pts = int(order.total // POINTS_PER_REAIS)
    if pts > 0:
        customer.loyalty_points += pts
        db.add(LoyaltyTransaction(customer_id=customer.id, order_id=order.id, points=pts, type="EARN"))
    return pts
