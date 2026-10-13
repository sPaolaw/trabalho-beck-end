import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import Customer, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(401, "Não autenticado", headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorized
    try:
        payload = decode_token(creds.credentials)
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized
    if user is None or not user.active:
        raise unauthorized
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Perfil sem permissão para esta operação")
        return user

    return dependency


def current_customer(user: User = Depends(require_roles("CUSTOMER"))) -> Customer:
    if user.customer is None:
        raise HTTPException(403, "Usuário sem perfil de cliente")
    return user.customer
