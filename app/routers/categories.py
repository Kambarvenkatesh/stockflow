from typing import Literal

from fastapi import APIRouter, status

from app.deps import DB, AdminOnly, CurrentUser, ManagerUp, Paging
from app.schemas import CategoryCreate, CategoryOut, CategoryUpdate, Page
from app.services.catalog_service import category_service as svc

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=Page[CategoryOut])
def list_categories(db: DB, _: CurrentUser, pg: Paging, search: str | None = None,
                    sort_by: Literal["id", "name", "created_at"] = "id", order: Literal["asc", "desc"] = "asc"):
    return svc.list(db, pg.page, pg.size, search, sort_by, order)


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(category_id: int, db: DB, _: CurrentUser):
    return svc.get(db, category_id)


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, db: DB, _: ManagerUp):
    return svc.create(db, data.model_dump())


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, data: CategoryUpdate, db: DB, _: ManagerUp):
    return svc.update(db, category_id, data.model_dump(exclude_unset=True))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: DB, _: AdminOnly):
    svc.delete(db, category_id)
