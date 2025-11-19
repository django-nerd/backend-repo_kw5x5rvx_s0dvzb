import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product, Customer, Supplier, Sale, Purchase, StockMovement, SaleItem, PurchaseItem

app = FastAPI(title="Simple Shop ERP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Shop ERP Backend Running"}


@app.get("/test")
def test_database():
    response = {"backend": "✅ Running", "database": "❌ Not Available"}
    try:
        if db is not None:
            response["database"] = "✅ Connected"
            response["collections"] = db.list_collection_names()
        else:
            response["database"] = "❌ Not Configured"
    except Exception as e:
        response["database"] = f"⚠️ Error: {str(e)[:80]}"
    return response


# Utility

def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")


# Products
@app.post("/api/products")
def create_product(product: Product):
    # Ensure unique sku
    existing = db["product"].find_one({"sku": product.sku}) if db else None
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")
    new_id = create_document("product", product)
    return {"id": new_id}


@app.get("/api/products")
def list_products(q: Optional[str] = None, limit: int = 100):
    query = {}
    if q:
        query = {"$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"sku": {"$regex": q, "$options": "i"}},
            {"category": {"$regex": q, "$options": "i"}},
        ]}
    docs = get_documents("product", query, limit)
    # Convert ObjectId to str
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


@app.put("/api/products/{product_id}")
def update_product(product_id: str, product: Product):
    pid = oid(product_id)
    update = product.model_dump()
    update["updated_at"] = os.times()
    res = db["product"].update_one({"_id": pid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


@app.delete("/api/products/{product_id}")
def delete_product(product_id: str):
    pid = oid(product_id)
    res = db["product"].delete_one({"_id": pid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


# Customers
@app.post("/api/customers")
def create_customer(customer: Customer):
    new_id = create_document("customer", customer)
    return {"id": new_id}


@app.get("/api/customers")
def list_customers(q: Optional[str] = None, limit: int = 100):
    query = {}
    if q:
        query = {"name": {"$regex": q, "$options": "i"}}
    docs = get_documents("customer", query, limit)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


# Suppliers
@app.post("/api/suppliers")
def create_supplier(supplier: Supplier):
    new_id = create_document("supplier", supplier)
    return {"id": new_id}


@app.get("/api/suppliers")
def list_suppliers(q: Optional[str] = None, limit: int = 100):
    query = {}
    if q:
        query = {"name": {"$regex": q, "$options": "i"}}
    docs = get_documents("supplier", query, limit)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


# Sales: create sale => decrement stock and record movement
@app.post("/api/sales")
def create_sale(sale: Sale):
    # compute totals
    subtotal = 0.0
    for item in sale.items:
        if item.line_total is None:
            item.line_total = item.quantity * item.price
        subtotal += item.line_total
    tax = sale.tax or 0
    total = subtotal + tax

    sale.subtotal = subtotal
    sale.total = total

    # Validate stock and decrement
    for item in sale.items:
        prod = db["product"].find_one({"_id": oid(item.product_id)})
        if not prod:
            raise HTTPException(status_code=400, detail=f"Product not found: {item.product_id}")
        if prod.get("quantity", 0) < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {prod.get('name')}")

    # Apply stock changes and insert docs
    sale_id = create_document("sale", sale)

    for item in sale.items:
        pid = oid(item.product_id)
        db["product"].update_one({"_id": pid}, {"$inc": {"quantity": -item.quantity}})
        create_document("stockmovement", StockMovement(
            product_id=item.product_id,
            type="sale",
            quantity_change=-item.quantity,
            reason="Sale",
            ref_id=sale_id
        ))

    return {"id": sale_id, "subtotal": subtotal, "tax": tax, "total": total}


# Purchases: create purchase => increment stock and record movement
@app.post("/api/purchases")
def create_purchase(purchase: Purchase):
    subtotal = 0.0
    for item in purchase.items:
        if item.line_total is None:
            item.line_total = item.quantity * item.cost
        subtotal += item.line_total
    tax = purchase.tax or 0
    total = subtotal + tax

    purchase.subtotal = subtotal
    purchase.total = total

    purchase_id = create_document("purchase", purchase)

    for item in purchase.items:
        pid = oid(item.product_id)
        db["product"].update_one({"_id": pid}, {"$inc": {"quantity": item.quantity}})
        create_document("stockmovement", StockMovement(
            product_id=item.product_id,
            type="purchase",
            quantity_change=item.quantity,
            reason="Purchase",
            ref_id=purchase_id
        ))

    return {"id": purchase_id, "subtotal": subtotal, "tax": tax, "total": total}


# Simple dashboard stats
@app.get("/api/stats")
def get_stats():
    products = db["product"].count_documents({}) if db else 0
    customers = db["customer"].count_documents({}) if db else 0
    suppliers = db["supplier"].count_documents({}) if db else 0
    sales = db["sale"].count_documents({}) if db else 0
    purchases = db["purchase"].count_documents({}) if db else 0

    inv_value = 0.0
    if db:
        for p in db["product"].find({}):
            inv_value += float(p.get("cost", 0) or 0) * int(p.get("quantity", 0) or 0)

    return {
        "counts": {
            "products": products,
            "customers": customers,
            "suppliers": suppliers,
            "sales": sales,
            "purchases": purchases,
        },
        "inventory_value": inv_value,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
