from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer,
                        Numeric, String, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class Store(Base):
    __tablename__ = "stores"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(40), index=True)
    kitchen_type: Mapped[str] = mapped_column(String(20), default="COMPLETA")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    customer: Mapped[Optional["Customer"]] = relationship(back_populates="user", uselist=False)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    cpf: Mapped[str | None] = mapped_column(String(11), unique=True, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0)
    anonymized: Mapped[bool] = mapped_column(Boolean, default=False)
    user: Mapped[User] = relationship(back_populates="customer")
    __table_args__ = (CheckConstraint("loyalty_points >= 0", name="ck_points_nonneg"),)


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))
    granted: Mapped[bool] = mapped_column(Boolean)
    terms_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(40))
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    seasonal: Mapped[bool] = mapped_column(Boolean, default=False)
    season_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    season_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    __table_args__ = (CheckConstraint("base_price > 0", name="ck_product_price_pos"),)


class StoreProduct(Base):
    __tablename__ = "store_products"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    stock_qty: Mapped[int] = mapped_column(Integer, default=0)
    price_override: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        UniqueConstraint("store_id", "product_id", name="uq_store_product"),
        CheckConstraint("stock_qty >= 0", name="ck_stock_nonneg"),
    )


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    channel: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    points_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    order: Mapped[Order] = relationship(back_populates="items")
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_item_qty_pos"),)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    status: Mapped[str] = mapped_column(String(15))
    method: Mapped[str] = mapped_column(String(15))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    provider_ref: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    points: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(15))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20))
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
