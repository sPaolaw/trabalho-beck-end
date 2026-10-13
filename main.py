from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.core.database import Base, engine, get_db
from app.routers import admin, auth, customers, orders, stores


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Raízes do Nordeste — API Back-end",
    version="1.0.0",
    lifespan=lifespan,
)

for r in (auth.router, stores.router, orders.router, customers.router, admin.router):
    app.include_router(r)


@app.get("/health", tags=["Operação"], summary="Verificação de disponibilidade")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Banco de dados indisponível")
    return {"status": "ok", "database": "up"}
