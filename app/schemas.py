from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer, field_validator, model_validator

from app.models import MovementType, OrderStatus, Role

Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
T = TypeVar("T")


class InputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class OutModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int


# ---------- Auth / Users ----------
class UserCreate(InputModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not (any(c.isalpha() for c in v) and any(c.isdigit() for c in v)):
            raise ValueError("Password must contain at least one letter and one digit")
        return v


class UserAdminCreate(UserCreate):
    role: Role = Role.STAFF


class UserUpdate(InputModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class UserOut(OutModel):
    id: int
    username: str
    email: str
    role: Role
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Category / Supplier ----------
class CategoryCreate(InputModel):
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)


class CategoryUpdate(InputModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)


class CategoryOut(OutModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime


PHONE = r"^\+?[0-9\- ]{7,20}$"


class SupplierCreate(InputModel):
    name: str = Field(min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, pattern=PHONE)
    address: Optional[str] = Field(default=None, max_length=255)


class SupplierUpdate(InputModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, pattern=PHONE)
    address: Optional[str] = Field(default=None, max_length=255)


class SupplierOut(OutModel):
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    created_at: datetime


# ---------- Product ----------
class ProductCreate(InputModel):
    sku: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=2000)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    reorder_level: int = Field(default=10, ge=0)
    category_id: int = Field(gt=0)
    supplier_id: Optional[int] = Field(default=None, gt=0)


class ProductUpdate(InputModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=2000)
    price: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    reorder_level: Optional[int] = Field(default=None, ge=0)
    category_id: Optional[int] = Field(default=None, gt=0)
    supplier_id: Optional[int] = Field(default=None, gt=0)


class ProductBrief(OutModel):
    id: int
    sku: str
    name: str


class ProductOut(OutModel):
    id: int
    sku: str
    name: str
    description: Optional[str]
    price: Money
    quantity: int
    reorder_level: int
    image_path: Optional[str]
    category: CategoryOut
    supplier: Optional[SupplierOut]
    created_at: datetime
    updated_at: datetime


# ---------- Stock ----------
class StockChange(InputModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=1_000_000)
    reference: Optional[str] = Field(default=None, max_length=100)
    note: Optional[str] = Field(default=None, max_length=255)


class StockMovementOut(OutModel):
    id: int
    product_id: int
    movement_type: MovementType
    quantity: int
    balance_after: int
    reference: Optional[str]
    note: Optional[str]
    order_id: Optional[int]
    created_by: int
    created_at: datetime


# ---------- Orders ----------
class OrderItemIn(InputModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=100_000)


class OrderCreate(InputModel):
    customer_name: str = Field(min_length=2, max_length=120)
    items: list[OrderItemIn] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def no_duplicate_products(self):
        ids = [i.product_id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Each product may appear only once per order; combine quantities instead")
        return self


class OrderStatusUpdate(InputModel):
    status: OrderStatus


class OrderItemOut(OutModel):
    id: int
    product: ProductBrief
    quantity: int
    unit_price: Money


class OrderOut(OutModel):
    id: int
    customer_name: str
    status: OrderStatus
    total_amount: Money
    created_by: int
    created_at: datetime
    items: list[OrderItemOut]


# ---------- Reports ----------
class SummaryReport(BaseModel):
    total_products: int
    total_units_in_stock: int
    inventory_value: Money
    low_stock_products: int
    total_orders: int
    total_revenue: Money


class SalesByDay(BaseModel):
    day: date
    orders: int
    revenue: Money


class TopProduct(BaseModel):
    product_id: int
    sku: str
    name: str
    units_sold: int
    revenue: Money


class CategoryInventory(BaseModel):
    category: str
    products: int
    units: int
    value: Money


class StatusCount(BaseModel):
    status: OrderStatus
    orders: int
    amount: Money


class LowStockItem(BaseModel):
    id: int
    sku: str
    name: str
    quantity: int
    reorder_level: int
    shortfall: int
