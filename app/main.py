import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import models  # noqa: F401  (register tables)
from app.config import settings
from app.database import Base, engine
from app.exceptions import AppError
from app.routers import auth, categories, orders, products, reports, stock, suppliers, users

logger = logging.getLogger("stockflow")
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)  # convenience; schema.sql is the canonical MySQL schema
    yield


app = FastAPI(
    title="StockFlow - Inventory & Order Management",
    version="1.0.0",
    description="JWT auth, RBAC (admin / manager / staff), stock ledger, transactional orders and reports.",
    lifespan=lifespan,
)

for r in (auth, users, categories, suppliers, products, stock, orders, reports):
    app.include_router(r.router)

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "error": type(exc).__name__}, headers=headers)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_: Request, exc: IntegrityError):
    logger.warning("Integrity error: %s", exc)
    return JSONResponse(status_code=409, content={"detail": "Database integrity constraint violated", "error": "IntegrityError"})


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(_: Request, exc: SQLAlchemyError):
    logger.exception("Database error")
    return JSONResponse(status_code=500, content={"detail": "Internal database error", "error": "DatabaseError"})


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
