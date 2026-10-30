from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError
from app.models import Category, OrderItem, Product, StockMovement, Supplier
from app.services.base import apply_sort, paginate, transaction


def _check_refs(db: Session, category_id: int | None, supplier_id: int | None) -> None:
    if category_id is not None and not db.get(Category, category_id):
        raise NotFoundError(f"Category {category_id} not found")
    if supplier_id is not None and not db.get(Supplier, supplier_id):
        raise NotFoundError(f"Supplier {supplier_id} not found")


def get_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if not product:
        raise NotFoundError(f"Product {product_id} not found")
    return product


def list_products(
    db: Session, page: int, size: int, *, search: str | None, category_id: int | None, supplier_id: int | None,
    min_price: Decimal | None, max_price: Decimal | None, low_stock: bool, in_stock: bool | None,
    sort_by: str, order: str,
):
    stmt = select(Product)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Product.name.ilike(like), Product.sku.ilike(like), Product.description.ilike(like)))
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if supplier_id:
        stmt = stmt.where(Product.supplier_id == supplier_id)
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if low_stock:
        stmt = stmt.where(Product.quantity <= Product.reorder_level)
    if in_stock is True:
        stmt = stmt.where(Product.quantity > 0)
    elif in_stock is False:
        stmt = stmt.where(Product.quantity == 0)
    return paginate(db, apply_sort(stmt, Product, sort_by, order), page, size)


def create_product(db: Session, data: dict) -> Product:
    data["sku"] = data["sku"].upper()
    if db.scalar(select(Product.id).where(Product.sku == data["sku"])):
        raise ConflictError(f"SKU '{data['sku']}' already exists")
    _check_refs(db, data["category_id"], data.get("supplier_id"))
    product = Product(**data, quantity=0)
    with transaction(db):
        db.add(product)
    db.refresh(product)
    return product


def update_product(db: Session, product_id: int, data: dict) -> Product:
    product = get_product(db, product_id)
    data = {k: v for k, v in data.items() if v is not None}
    _check_refs(db, data.get("category_id"), data.get("supplier_id"))
    with transaction(db):
        for k, v in data.items():
            setattr(product, k, v)
    db.refresh(product)
    return product


def delete_product(db: Session, product_id: int) -> None:
    product = get_product(db, product_id)
    has_history = db.scalar(select(func.count()).select_from(StockMovement).where(StockMovement.product_id == product_id)) \
        or db.scalar(select(func.count()).select_from(OrderItem).where(OrderItem.product_id == product_id))
    if has_history:
        raise ConflictError("Cannot delete a product that has stock or order history")
    with transaction(db):
        db.delete(product)
