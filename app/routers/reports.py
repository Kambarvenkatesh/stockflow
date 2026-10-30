from datetime import date

from fastapi import APIRouter, Query

from app.deps import DB, ManagerUp
from app.schemas import CategoryInventory, LowStockItem, SalesByDay, StatusCount, SummaryReport, TopProduct
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/summary", response_model=SummaryReport)
def summary(db: DB, _: ManagerUp):
    return report_service.summary(db)


@router.get("/sales-by-day", response_model=list[SalesByDay])
def sales_by_day(db: DB, _: ManagerUp, date_from: date | None = None, date_to: date | None = None):
    return report_service.sales_by_day(db, date_from, date_to)


@router.get("/top-products", response_model=list[TopProduct])
def top_products(db: DB, _: ManagerUp, limit: int = Query(5, ge=1, le=50)):
    return report_service.top_products(db, limit)


@router.get("/low-stock", response_model=list[LowStockItem])
def low_stock(db: DB, _: ManagerUp):
    return report_service.low_stock(db)


@router.get("/inventory-by-category", response_model=list[CategoryInventory])
def inventory_by_category(db: DB, _: ManagerUp):
    return report_service.inventory_by_category(db)


@router.get("/orders-by-status", response_model=list[StatusCount])
def orders_by_status(db: DB, _: ManagerUp):
    return report_service.orders_by_status(db)
