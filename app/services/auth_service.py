from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.models import Role, User
from app.security import create_access_token, hash_password, verify_password
from app.services.base import paginate, transaction


def create_user(db: Session, username: str, email: str, password: str, role: Role = Role.STAFF) -> User:
    exists = db.scalar(
        select(User.id).where((func.lower(User.username) == username.lower()) | (func.lower(User.email) == email.lower()))
    )
    if exists:
        raise ConflictError("Username or email already registered")
    user = User(username=username, email=email.lower(), hashed_password=hash_password(password), role=role)
    with transaction(db):
        db.add(user)
    db.refresh(user)
    return user


def login(db: Session, username: str, password: str) -> str:
    user = db.scalar(select(User).where(func.lower(User.username) == username.lower()))
    if not user or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Incorrect username or password")
    if not user.is_active:
        raise ForbiddenError("Account is disabled")
    return create_access_token(user.id, user.role.value)


def list_users(db: Session, page: int, size: int):
    return paginate(db, select(User).order_by(User.id), page, size)


def update_user(db: Session, user_id: int, data: dict, acting_user: User) -> User:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError(f"User {user_id} not found")
    if user.id == acting_user.id and (data.get("is_active") is False or data.get("role") not in (None, Role.ADMIN)):
        raise ForbiddenError("Admins cannot demote or deactivate themselves")
    with transaction(db):
        for k, v in data.items():
            if v is not None:
                setattr(user, k, v)
    db.refresh(user)
    return user
