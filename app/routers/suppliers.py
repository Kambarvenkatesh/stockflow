from typing import Literal

from fastapi import APIRouter, status

from app.deps import DB, AdminOnly, CurrentUser, ManagerUp, Paging
from app.schemas import Page, SupplierCreate, SupplierOut, SupplierUpdate
from app.services.catalog_service import supplier_service as svc

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("", response_model=Page[SupplierOut])
def list_suppliers(db: DB, _: CurrentUser, pg: Paging, search: str | None = None,
                   sort_by: Literal["id", "name", "created_at"] = "id", order: Literal["asc", "desc"] = "asc"):
    return svc.list(db, pg.page, pg.size, search, sort_by, order)


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(supplier_id: int, db: DB, _: CurrentUser):
    return svc.get(db, supplier_id)


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(data: SupplierCreate, db: DB, _: ManagerUp):
    return svc.create(db, data.model_dump())


@router.put("/{supplier_id}", response_model=SupplierOut)
def update_supplier(supplier_id: int, data: SupplierUpdate, db: DB, _: ManagerUp):
    return svc.update(db, supplier_id, data.model_dump(exclude_unset=True))


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(supplier_id: int, db: DB, _: AdminOnly):
    svc.delete(db, supplier_id)
