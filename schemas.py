from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.security import validate_cpf

EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterIn(BaseModel):
    email: str = Field(pattern=EMAIL_RE, max_length=120)
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=2, max_length=120)
    cpf: str | None = None
    birth_date: date | None = None
    accept_terms: bool
    terms_version: str = "v1.0"

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v):
        if v is not None and not validate_cpf(v):
            raise ValueError("CPF inválido (informe 11 dígitos, sem pontuação)")
        return v


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    name: str | None = None


class StaffIn(BaseModel):
    email: str = Field(pattern=EMAIL_RE, max_length=120)
    password: str = Field(min_length=8, max_length=72)
    role: Literal["ATTENDANT", "MANAGER"]
    store_id: int


class StoreIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=80)
    region: str = Field(min_length=2, max_length=40)
    kitchen_type: Literal["COMPLETA", "REDUZIDA"] = "COMPLETA"
    active: bool = True


class StoreOut(ORM):
    id: int
    name: str
    city: str
    region: str
    kitchen_type: str
    active: bool


class ProductIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    category: str = Field(min_length=2, max_length=40)
    base_price: float = Field(gt=0)
    active: bool = True
    seasonal: bool = False
    season_start: date | None = None
    season_end: date | None = None

    @model_validator(mode="after")
    def _season(self):
        if self.seasonal:
            if not self.season_start or not self.season_end:
                raise ValueError("Produto sazonal exige season_start e season_end")
            if self.season_start > self.season_end:
                raise ValueError("season_start deve ser <= season_end")
        return self


class ProductOut(ORM):
    id: int
    name: str
    category: str
    base_price: float
    active: bool
    seasonal: bool
    season_start: date | None
    season_end: date | None


class StockIn(BaseModel):
    stock_qty: int = Field(ge=0)
    price_override: float | None = Field(default=None, gt=0)
    active: bool = True


class StockOut(ORM):
    store_id: int
    product_id: int
    stock_qty: int
    price_override: float | None
    active: bool


class MenuItemOut(BaseModel):
    product_id: int
    name: str
    category: str
    price: float
    stock_qty: int


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=50)


class OrderCreate(BaseModel):
    store_id: int
    channel: Literal["APP", "PICKUP", "BALCAO", "TOTEM"]
    items: list[OrderItemIn] = Field(min_length=1, max_length=30)
    use_points: int = Field(default=0, ge=0)
    customer_id: int | None = None


class OrderItemOut(ORM):
    product_id: int
    product_name: str
    quantity: int
    unit_price: float


class OrderOut(ORM):
    id: int
    store_id: int
    customer_id: int | None
    channel: str
    status: str
    subtotal: float
    discount: float
    total: float
    points_used: int
    created_at: datetime
    items: list[OrderItemOut]


class StatusIn(BaseModel):
    status: str


class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


class PaymentIn(BaseModel):
    method: Literal["CREDIT_CARD", "DEBIT_CARD", "PIX"]
    token: str = Field(min_length=3, max_length=60)


class PaymentOut(BaseModel):
    payment_id: int
    order_id: int
    status: str
    method: str
    provider_ref: str | None
    order_status: str


class HistoryOut(ORM):
    from_status: str | None
    to_status: str
    changed_at: datetime


class CustomerOut(BaseModel):
    name: str
    email: str
    cpf_masked: str | None
    birth_date: date | None
    loyalty_points: int


class ConsentIn(BaseModel):
    purpose: Literal["LOYALTY", "MARKETING", "PROFILING"]
    granted: bool
    terms_version: str = "v1.0"


class ConsentOut(ORM):
    purpose: str
    granted: bool
    terms_version: str
    created_at: datetime


class LoyaltyTxOut(ORM):
    order_id: int | None
    points: int
    type: str
    created_at: datetime


class LoyaltyOut(BaseModel):
    points: int
    tier: str
    tier_discount_pct: int
    consent_active: bool
    transactions: list[LoyaltyTxOut]


class AuditOut(ORM):
    id: int
    user_id: int | None
    action: str
    entity: str
    entity_id: int | None
    details: str | None
    created_at: datetime
