import re
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_token(user_id: int, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.token_minutes)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": exp}, settings.secret_key, settings.algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def validate_cpf(cpf: str) -> bool:
    if not re.fullmatch(r"\d{11}", cpf) or cpf == cpf[0] * 11:
        return False
    for n in (9, 10):
        s = sum(int(cpf[i]) * (n + 1 - i) for i in range(n))
        if int(cpf[n]) != (s * 10 % 11) % 10:
            return False
    return True


def mask_cpf(cpf: str | None) -> str | None:
    return f"***.***.***-{cpf[-2:]}" if cpf else None
