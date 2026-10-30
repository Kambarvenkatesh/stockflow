from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import InsufficientStockError, NotFoundError
from app.models import MovementType, Product, StockMovement
from app.services.base import paginate, transaction


def lock_product(db: Session, product_id: int) -> Product:
    """SELECT ... FOR UPDATE: prevents concurrent requests from overselling."""
    product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if not product:
        raise NotFoundError(f"Product {product_id} not found")
    return product


def adjust_stock(db: Session, product: Product, delta: int, mtype: MovementType, user_id: int,
                 reference: str | None = None, note: str | None = None, order_id: int | None = None) -> StockMovement:
    """Change stock and write the ledger row. Does NOT commit - caller owns the transaction."""
    new_qty = product.quantity + delta
    if new_qty < 0:
        raise InsufficientStockError(
            f"Insufficient stock for '{product.name}' (SKU {product.sku}): available {product.quantity}, requested {-delta}"
        )
    product.quantity = new_qty
    movement = StockMovement(
        product_id=product.id, movement_type=mtype, quantity=abs(delta), balance_after=new_qty,
        reference=reference, note=note, order_id=order_id, created_by=user_id,
    )
    db.add(movement)
    db.flush()
    return movement


def stock_in(db: Session, data: dict, user_id: int) -> StockMovement:
    with transaction(db):
        product = lock_product(db, data["product_id"])
        movement = adjust_stock(db, product, data["quantity"], MovementType.IN, user_id, data.get("reference"), data.get("note"))
    db.refresh(movement)
    return movement


def stock_out(db: Session, data: dict, user_id: int) -> StockMovement:
    with transaction(db):
        product = lock_product(db, data["product_id"])
        movement = adjust_stock(db, product, -data["quantity"], MovementType.OUT, user_id, data.get("reference"), data.get("note"))
    db.refresh(movement)
    return movement


def list_movements(db: Session, page: int, size: int, product_id: int | None, movement_type: MovementType | None):
    stmt = select(StockMovement).order_by(StockMovement.id.desc())
    if product_id:
        stmt = stmt.where(StockMovement.product_id == product_id)
    if movement_type:
        stmt = stmt.where(StockMovement.movement_type == movement_type)
    return paginate(db, stmt, page, size)
