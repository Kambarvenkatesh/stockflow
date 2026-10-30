from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Order, OrderItem, OrderStatus, Product

_ACTIVE = Order.status != OrderStatus.CANCELLED


def summary(db: Session) -> dict:
    products, units, value = db.execute(
        select(func.count(Product.id), func.coalesce(func.sum(Product.quantity), 0),
               func.coalesce(func.sum(Product.price * Product.quantity), 0))
    ).one()
    low = db.scalar(select(func.count(Product.id)).where(Product.quantity <= Product.reorder_level))
    orders, revenue = db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0)).where(_ACTIVE)
    ).one()
    return {"total_products": products, "total_units_in_stock": int(units), "inventory_value": value,
            "low_stock_products": low, "total_orders": orders, "total_revenue": revenue}


def sales_by_day(db: Session, date_from: date | None, date_to: date | None) -> list[dict]:
    day = func.date(Order.created_at)
    stmt = select(day.label("day"), func.count(Order.id), func.sum(Order.total_amount)).where(_ACTIVE)
    if date_from:
        stmt = stmt.where(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        stmt = stmt.where(Order.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    rows = db.execute(stmt.group_by(day).order_by(day)).all()
    return [{"day": r[0], "orders": r[1], "revenue": r[2]} for r in rows]


def top_products(db: Session, limit: int) -> list[dict]:
    units = func.sum(OrderItem.quantity)
    revenue = func.sum(OrderItem.quantity * OrderItem.unit_price)
    stmt = (
        select(Product.id, Product.sku, Product.name, units, revenue)
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(_ACTIVE)
        .group_by(Product.id, Product.sku, Product.name)
        .order_by(units.desc(), Product.id)
        .limit(limit)
    )
    return [{"product_id": r[0], "sku": r[1], "name": r[2], "units_sold": int(r[3]), "revenue": r[4]}
            for r in db.execute(stmt)]


def low_stock(db: Session) -> list[dict]:
    stmt = select(Product).where(Product.quantity <= Product.reorder_level).order_by(Product.quantity, Product.id)
    return [{"id": p.id, "sku": p.sku, "name": p.name, "quantity": p.quantity,
             "reorder_level": p.reorder_level, "shortfall": p.reorder_level - p.quantity}
            for p in db.scalars(stmt)]


def inventory_by_category(db: Session) -> list[dict]:
    stmt = (
        select(Category.name, func.count(Product.id), func.coalesce(func.sum(Product.quantity), 0),
               func.coalesce(func.sum(Product.price * Product.quantity), 0))
        .outerjoin(Product, Product.category_id == Category.id)
        .group_by(Category.id, Category.name)
        .order_by(Category.name)
    )
    return [{"category": r[0], "products": r[1], "units": int(r[2]), "value": r[3]} for r in db.execute(stmt)]


def orders_by_status(db: Session) -> list[dict]:
    stmt = select(Order.status, func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0)).group_by(Order.status)
    return [{"status": r[0], "orders": r[1], "amount": r[2]} for r in db.execute(stmt)]
