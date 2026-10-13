import secrets

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import current_customer
from app.core.security import hash_password, mask_cpf
from app.models import Consent, Customer, LoyaltyTransaction
from app.schemas import ConsentIn, ConsentOut, CustomerOut, LoyaltyOut
from app.services import loyalty
from app.services.audit import log

router = APIRouter(prefix="/customers/me", tags=["Cliente, LGPD e fidelização"])


@router.get("", response_model=CustomerOut, summary="Dados do cliente (CPF mascarado)")
def me(customer: Customer = Depends(current_customer)):
    return CustomerOut(name=customer.name, email=customer.user.email, cpf_masked=mask_cpf(customer.cpf),
                       birth_date=customer.birth_date, loyalty_points=customer.loyalty_points)


@router.get("/consents", response_model=list[ConsentOut], summary="Estado atual de cada consentimento")
def list_consents(db: Session = Depends(get_db), customer: Customer = Depends(current_customer)):
    return loyalty.current_consents(db, customer.id)


@router.post("/consents", response_model=ConsentOut, status_code=201,
             summary="Concede ou revoga consentimento (histórico preservado)")
def set_consent(data: ConsentIn, db: Session = Depends(get_db), customer: Customer = Depends(current_customer)):
    consent = Consent(customer_id=customer.id, purpose=data.purpose, granted=data.granted,
                      terms_version=data.terms_version)
    db.add(consent)
    log(db, customer.user_id, "CONSENT_GRANTED" if data.granted else "CONSENT_REVOKED",
        "Customer", customer.id, f"finalidade={data.purpose}")
    db.commit()
    return consent


@router.get("/loyalty", response_model=LoyaltyOut, summary="Pontos, faixa e extrato")
def loyalty_summary(db: Session = Depends(get_db), customer: Customer = Depends(current_customer)):
    tier, pct = loyalty.tier_for(db, customer.id)
    txs = db.scalars(select(LoyaltyTransaction).where(LoyaltyTransaction.customer_id == customer.id)
                     .order_by(LoyaltyTransaction.id.desc())).all()
    return LoyaltyOut(points=customer.loyalty_points, tier=tier, tier_discount_pct=pct,
                      consent_active=loyalty.consent_active(db, customer.id), transactions=txs)


@router.delete("", status_code=204, summary="Anonimiza a conta (direito ao esquecimento)")
def anonymize(db: Session = Depends(get_db), customer: Customer = Depends(current_customer)):
    user = customer.user
    customer.name = "ANONIMIZADO"
    customer.cpf = None
    customer.birth_date = None
    customer.anonymized = True
    user.email = f"anon-{user.id}@anonimizado.invalid"
    user.password_hash = hash_password(secrets.token_urlsafe(32))
    user.active = False
    for c in loyalty.current_consents(db, customer.id):
        if c.granted:
            db.add(Consent(customer_id=customer.id, purpose=c.purpose, granted=False, terms_version=c.terms_version))
    log(db, user.id, "CUSTOMER_ANONYMIZED", "Customer", customer.id)
    db.commit()
    return Response(status_code=204)
