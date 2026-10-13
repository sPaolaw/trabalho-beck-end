from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import ADMIN, CUSTOMER
from app.core.database import get_db
from app.core.deps import require_roles
from app.core.security import create_token, hash_password, verify_password
from app.models import Consent, Customer, Store, User
from app.schemas import LoginIn, RegisterIn, StaffIn, TokenOut, UserOut
from app.services.audit import log

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/register", response_model=UserOut, status_code=201,
             summary="Cadastro de cliente (exige aceite dos termos)")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if not data.accept_terms:
        raise HTTPException(422, "É necessário aceitar os termos de uso e a política de privacidade")
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "E-mail já cadastrado")
    if data.cpf and db.scalar(select(Customer).where(Customer.cpf == data.cpf)):
        raise HTTPException(409, "CPF já cadastrado")
    user = User(email=email, password_hash=hash_password(data.password), role=CUSTOMER)
    db.add(user)
    db.flush()
    customer = Customer(user_id=user.id, name=data.name, cpf=data.cpf, birth_date=data.birth_date)
    db.add(customer)
    db.flush()
    db.add(Consent(customer_id=customer.id, purpose="TERMS", granted=True, terms_version=data.terms_version))
    log(db, user.id, "REGISTER", "User", user.id)
    db.commit()
    return UserOut(id=user.id, email=user.email, role=user.role, name=customer.name)


@router.post("/login", response_model=TokenOut, summary="Autentica e devolve o JWT")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not user.active or not verify_password(data.password, user.password_hash):
        log(db, None, "LOGIN_FAILED", "User", None, "credenciais inválidas")
        db.commit()
        raise HTTPException(401, "Credenciais inválidas")
    log(db, user.id, "LOGIN", "User", user.id)
    db.commit()
    return TokenOut(access_token=create_token(user.id, user.role))


@router.post("/staff", response_model=UserOut, status_code=201,
             summary="Cria atendente ou gerente de uma loja (ADMIN)")
def create_staff(data: StaffIn, db: Session = Depends(get_db), admin=Depends(require_roles(ADMIN))):
    if not db.get(Store, data.store_id):
        raise HTTPException(404, "Loja não encontrada")
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "E-mail já cadastrado")
    user = User(email=email, password_hash=hash_password(data.password), role=data.role, store_id=data.store_id)
    db.add(user)
    db.flush()
    log(db, admin.id, "STAFF_CREATED", "User", user.id, f"role={data.role} loja={data.store_id}")
    db.commit()
    return UserOut(id=user.id, email=user.email, role=user.role)
