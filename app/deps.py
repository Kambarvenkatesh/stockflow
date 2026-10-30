from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import ForbiddenError, UnauthorizedError
from app.models import Role, User
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

DB = Annotated[Session, Depends(get_db)]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DB) -> User:
    payload = decode_token(token)
    try:
        user = db.get(User, int(payload["sub"]))
    except (KeyError, ValueError):
        raise UnauthorizedError("Invalid token payload")
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role):
    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            allowed = ", ".join(r.value for r in roles)
            raise ForbiddenError(f"Requires one of these roles: {allowed}")
        return user

    return checker


AdminOnly = Annotated[User, Depends(require_roles(Role.ADMIN))]
ManagerUp = Annotated[User, Depends(require_roles(Role.ADMIN, Role.MANAGER))]


class Pagination:
    def __init__(self, page: int = Query(1, ge=1), size: int = Query(10, ge=1, le=100)):
        self.page = page
        self.size = size


Paging = Annotated[Pagination, Depends()]
