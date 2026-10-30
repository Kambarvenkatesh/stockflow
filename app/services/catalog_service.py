from app.models import Category, Product, Supplier
from app.services.base import CrudService

category_service = CrudService(Category, "Category", [Product.category_id])
supplier_service = CrudService(Supplier, "Supplier", [Product.supplier_id])
