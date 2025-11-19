"""
Database Schemas for Simple Shop ERP

Each Pydantic model below represents a MongoDB collection.
Collection name is the lowercase of the class name (e.g., Product -> "product").

This ERP covers:
- Products (catalog with stock on hand)
- Customers
- Suppliers
- Sales (orders with line items)
- Purchases (restocking from suppliers)
- StockMovement (audit of quantity changes)
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class Product(BaseModel):
    sku: str = Field(..., description="Unique stock keeping unit")
    name: str = Field(..., description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    category: Optional[str] = Field(None, description="Category name")
    price: float = Field(..., ge=0, description="Unit sale price")
    cost: Optional[float] = Field(0, ge=0, description="Unit cost price")
    quantity: int = Field(0, ge=0, description="Quantity on hand")
    is_active: bool = Field(True, description="Whether product is active")


class Customer(BaseModel):
    name: str = Field(..., description="Customer name")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    address: Optional[str] = Field(None, description="Address")


class Supplier(BaseModel):
    name: str = Field(..., description="Supplier name")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    address: Optional[str] = Field(None, description="Address")


class SaleItem(BaseModel):
    product_id: str = Field(..., description="Product ObjectId as string")
    sku: Optional[str] = Field(None, description="SKU snapshot at time of sale")
    name: Optional[str] = Field(None, description="Product name snapshot")
    quantity: int = Field(..., ge=1, description="Quantity sold")
    price: float = Field(..., ge=0, description="Unit price at time of sale")
    line_total: Optional[float] = Field(None, ge=0, description="Computed: quantity * price")


class Sale(BaseModel):
    customer_id: Optional[str] = Field(None, description="Customer ObjectId as string")
    items: List[SaleItem] = Field(..., description="List of line items")
    subtotal: Optional[float] = Field(None, ge=0, description="Sum of line totals")
    tax: Optional[float] = Field(0, ge=0, description="Tax amount")
    total: Optional[float] = Field(None, ge=0, description="Grand total")
    notes: Optional[str] = Field(None, description="Additional notes")


class PurchaseItem(BaseModel):
    product_id: str = Field(..., description="Product ObjectId as string")
    quantity: int = Field(..., ge=1, description="Quantity purchased")
    cost: float = Field(..., ge=0, description="Unit cost at time of purchase")
    line_total: Optional[float] = Field(None, ge=0)


class Purchase(BaseModel):
    supplier_id: Optional[str] = Field(None, description="Supplier ObjectId as string")
    items: List[PurchaseItem] = Field(...)
    subtotal: Optional[float] = Field(None, ge=0)
    tax: Optional[float] = Field(0, ge=0)
    total: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = Field(None)


class StockMovement(BaseModel):
    product_id: str = Field(..., description="Product ObjectId as string")
    type: str = Field(..., description="'sale' | 'purchase' | 'adjustment'")
    quantity_change: int = Field(..., description="Negative for sale, positive for purchase/adjustment")
    reason: Optional[str] = Field(None)
    ref_id: Optional[str] = Field(None, description="Related document id (sale/purchase)")
