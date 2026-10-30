from fastapi import APIRouter, status

from app.deps import DB, AdminOnly, Paging
from app.schemas import Page, UserAdminCreate, UserOut, UserUpdate
from app.services import auth_service

router = APIRouter(prefix="/users", tags=["Users (admin)"])


@router.get("", response_model=Page[UserOut])
def list_users(db: DB, _: AdminOnly, pg: Paging):
    return auth_service.list_users(db, pg.page, pg.size)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: UserAdminCreate, db: DB, _: AdminOnly):
    return auth_service.create_user(db, data.username, data.email, data.password, data.role)


@router.patch("/{user_id}", response_model=UserOut, summary="Change a user's role or active flag")
def update_user(user_id: int, data: UserUpdate, db: DB, admin: AdminOnly):
    return auth_service.update_user(db, user_id, data.model_dump(exclude_unset=True), admin)
