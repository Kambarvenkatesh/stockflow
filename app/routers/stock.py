from fastapi import APIRouter, status

from app.deps import DB, ManagerUp, Paging
from app.models import MovementType
from app.schemas import Page, StockChange, StockMovementOut
from app.services import stock_service

router = APIRouter(prefix="/stock", tags=["Stock & Inventory"])


@router.post("/in", response_model=StockMovementOut, status_code=status.HTTP_201_CREATED,
             summary="Add stock (purchase / restock)")
def stock_in(data: StockChange, db: DB, user: ManagerUp):
    return stock_service.stock_in(db, data.model_dump(), user.id)


@router.post("/out", response_model=StockMovementOut, status_code=status.HTTP_201_CREATED,
             summary="Remove stock (damage / loss / adjustment). Rejects if it would go below zero")
def stock_out(data: StockChange, db: DB, user: ManagerUp):
    return stock_service.stock_out(db, data.model_dump(), user.id)


@router.get("/movements", response_model=Page[StockMovementOut], summary="Inventory ledger / history")
def movements(db: DB, _: ManagerUp, pg: Paging, product_id: int | None = None, movement_type: MovementType | None = None):
    return stock_service.list_movements(db, pg.page, pg.size, product_id, movement_type)
