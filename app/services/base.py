from contextlib import contextmanager
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError


@contextmanager
def transaction(db: Session):
    """Commit on success, roll back everything on any error."""
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise


def paginate(db: Session, stmt, page: int, size: int) -> dict:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(stmt.offset((page - 1) * size).limit(size)).all()
    return {"items": items, "total": total, "page": page, "size": size, "pages": ceil(total / size) if total else 0}


def apply_sort(stmt, model, sort_by: str, order: str):
    col = getattr(model, sort_by)
    return stmt.order_by(col.desc() if order == "desc" else col.asc(), model.id)


class CrudService:
    """Reusable CRUD for simple 'named' entities (Category, Supplier)."""

    def __init__(self, model, label: str, dependent_fk_columns: list):
        self.model = model
        self.label = label
        self.dependent_fk_columns = dependent_fk_columns

    def get(self, db: Session, obj_id: int):
        obj = db.get(self.model, obj_id)
        if not obj:
            raise NotFoundError(f"{self.label} {obj_id} not found")
        return obj

    def _name_taken(self, db: Session, name: str, exclude_id: int | None = None) -> bool:
        stmt = select(self.model.id).where(func.lower(self.model.name) == name.lower())
        if exclude_id:
            stmt = stmt.where(self.model.id != exclude_id)
        return db.scalar(stmt) is not None

    def list(self, db: Session, page: int, size: int, search: str | None, sort_by: str, order: str):
        stmt = select(self.model)
        if search:
            stmt = stmt.where(self.model.name.ilike(f"%{search}%"))
        return paginate(db, apply_sort(stmt, self.model, sort_by, order), page, size)

    def create(self, db: Session, data: dict):
        if self._name_taken(db, data["name"]):
            raise ConflictError(f"{self.label} '{data['name']}' already exists")
        obj = self.model(**data)
        with transaction(db):
            db.add(obj)
        db.refresh(obj)
        return obj

    def update(self, db: Session, obj_id: int, data: dict):
        obj = self.get(db, obj_id)
        data = {k: v for k, v in data.items() if v is not None}
        if "name" in data and self._name_taken(db, data["name"], exclude_id=obj_id):
            raise ConflictError(f"{self.label} '{data['name']}' already exists")
        with transaction(db):
            for k, v in data.items():
                setattr(obj, k, v)
        db.refresh(obj)
        return obj

    def delete(self, db: Session, obj_id: int) -> None:
        obj = self.get(db, obj_id)
        for col in self.dependent_fk_columns:
            if db.scalar(select(func.count()).select_from(col.class_).where(col == obj_id)):
                raise ConflictError(f"Cannot delete {self.label.lower()} that still has products assigned")
        with transaction(db):
            db.delete(obj)
