from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.models import MovementType, Order, OrderItem, OrderStatus, Product, Role, User
from app.services.base import apply_sort, paginate, transaction
from app.services.stock_service import adjust_stock, lock_product


def create_order(db: Session, data: dict, user: User) -> Order:
    """Atomic: either the order, its items, the stock deductions and the ledger rows all
    persist, or nothing does (any error -> full rollback)."""
    ids = sorted(i["product_id"] for i in data["items"])  # fixed lock order avoids deadlocks
    with transaction(db):
        products = {pid: lock_product(db, pid) for pid in ids}
        order = Order(customer_name=data["customer_name"], created_by=user.id, status=OrderStatus.CONFIRMED, total_amount=Decimal("0"))
        db.add(order)
        db.flush()
        total = Decimal("0")
        for item in data["items"]:
            product = products[item["product_id"]]
            adjust_stock(db, product, -item["quantity"], MovementType.SALE, user.id,
                         reference=f"ORDER-{order.id}", order_id=order.id)
            db.add(OrderItem(order_id=order.id, product_id=product.id, quantity=item["quantity"], unit_price=product.price))
            total += product.price * item["quantity"]
        order.total_amount = total
    return get_order(db, order.id, user)


def get_order(db: Session, order_id: int, user: User) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise NotFoundError(f"Order {order_id} not found")
    if user.role == Role.STAFF and order.created_by != user.id:
        raise ForbiddenError("You can only view your own orders")
    db.refresh(order)
    return order


def list_orders(db: Session, user: User, page: int, size: int, *, status: OrderStatus | None, customer: str | None,
                date_from: date | None, date_to: date | None, sort_by: str, order: str):
    stmt = select(Order)
    if user.role == Role.STAFF:
        stmt = stmt.where(Order.created_by == user.id)
    if status:
        stmt = stmt.where(Order.status == status)
    if customer:
        stmt = stmt.where(Order.customer_name.ilike(f"%{customer}%"))
    if date_from:
        stmt = stmt.where(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        stmt = stmt.where(Order.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    return paginate(db, apply_sort(stmt, Order, sort_by, order), page, size)


def update_status(db: Session, order_id: int, new_status: OrderStatus, user: User) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise NotFoundError(f"Order {order_id} not found")
    if order.status != OrderStatus.CONFIRMED:
        raise ConflictError(f"Order is already {order.status.value} and can no longer change")
    if new_status == OrderStatus.CONFIRMED:
        raise BusinessRuleError("Status can only change to COMPLETED or CANCELLED")
    with transaction(db):
        if new_status == OrderStatus.CANCELLED:
            for item in sorted(order.items, key=lambda i: i.product_id):
                product = lock_product(db, item.product_id)
                adjust_stock(db, product, item.quantity, MovementType.RETURN, user.id,
                             reference=f"ORDER-{order.id}-CANCEL", order_id=order.id)
        order.status = new_status
    return get_order(db, order_id, user)
