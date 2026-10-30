from datetime import date
from typing import Literal

from fastapi import APIRouter, status

from app.deps import DB, CurrentUser, ManagerUp, Paging
from app.models import OrderStatus
from app.schemas import OrderCreate, OrderOut, OrderStatusUpdate, Page
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED,
             summary="Create an order (atomic: stock is deducted in the same DB transaction)")
def create_order(data: OrderCreate, db: DB, user: CurrentUser):
    return order_service.create_order(db, data.model_dump(), user)


@router.get("", response_model=Page[OrderOut], summary="List orders (staff see only their own)")
def list_orders(db: DB, user: CurrentUser, pg: Paging, status: OrderStatus | None = None, customer: str | None = None,
                date_from: date | None = None, date_to: date | None = None,
                sort_by: Literal["id", "created_at", "total_amount"] = "id", order: Literal["asc", "desc"] = "desc"):
    return order_service.list_orders(db, user, pg.page, pg.size, status=status, customer=customer,
                                     date_from=date_from, date_to=date_to, sort_by=sort_by, order=order)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: DB, user: CurrentUser):
    return order_service.get_order(db, order_id, user)


@router.patch("/{order_id}/status", response_model=OrderOut,
              summary="Complete or cancel an order (cancel restores stock)")
def update_status(order_id: int, data: OrderStatusUpdate, db: DB, user: ManagerUp):
    return order_service.update_status(db, order_id, data.status, user)
