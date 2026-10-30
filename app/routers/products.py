from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, File, UploadFile, status

from app.deps import DB, AdminOnly, CurrentUser, ManagerUp, Paging
from app.schemas import Page, ProductCreate, ProductOut, ProductUpdate
from app.services import product_service, upload_service
from app.services.base import transaction

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=Page[ProductOut], summary="Search, filter, sort and paginate products")
def list_products(
    db: DB, _: CurrentUser, pg: Paging,
    search: str | None = None, category_id: int | None = None, supplier_id: int | None = None,
    min_price: Decimal | None = None, max_price: Decimal | None = None,
    low_stock: bool = False, in_stock: bool | None = None,
    sort_by: Literal["id", "name", "sku", "price", "quantity", "created_at"] = "id",
    order: Literal["asc", "desc"] = "asc",
):
    return product_service.list_products(
        db, pg.page, pg.size, search=search, category_id=category_id, supplier_id=supplier_id,
        min_price=min_price, max_price=max_price, low_stock=low_stock, in_stock=in_stock,
        sort_by=sort_by, order=order,
    )


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: DB, _: CurrentUser):
    return product_service.get_product(db, product_id)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, db: DB, _: ManagerUp):
    return product_service.create_product(db, data.model_dump())


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: int, data: ProductUpdate, db: DB, _: ManagerUp):
    return product_service.update_product(db, product_id, data.model_dump(exclude_unset=True))


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: DB, _: AdminOnly):
    product_service.delete_product(db, product_id)


@router.post("/{product_id}/image", response_model=ProductOut,
             summary="Upload product image (JPEG/PNG/WEBP, max size from MAX_UPLOAD_SIZE_MB)")
def upload_image(product_id: int, db: DB, _: ManagerUp, file: UploadFile = File(...)):
    product = product_service.get_product(db, product_id)
    new_path = upload_service.save_product_image(file, product.image_path)
    with transaction(db):
        product.image_path = new_path
    db.refresh(product)
    return product
