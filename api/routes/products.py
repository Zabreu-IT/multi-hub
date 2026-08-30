from datetime import date
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import Availability, Product
from api.security import require_admin

router = APIRouter(prefix="/products", tags=["products"])

class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=250); slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = None; description_short: str | None = None; category_id: UUID | None = None
    base_price: Decimal = Field(default=0, ge=0); currency: str = Field(default="USD", max_length=8); product_type: str = "custom"; status: str = "draft"; images: list[str] = []; metadata: dict = {}
class ProductOut(ProductIn):
    model_config = ConfigDict(from_attributes=True); id: UUID
class AvailabilityIn(BaseModel):
    date: date; slots_total: int = Field(ge=0); slots_available: int = Field(ge=0); price_override: Decimal | None = Field(default=None, ge=0); metadata: dict = {}

def product_out(p: Product): return {**{k: getattr(p, k) for k in ProductIn.model_fields if k not in {"metadata"}}, "metadata": p.metadata_, "id": p.id}
def one(db, id):
    p = db.get(Product, id)
    if not p: raise HTTPException(404, "Product not found")
    return p
@router.get("", response_model=list[ProductOut])
def list_products(category: UUID | None = None, type: str | None = None, status: str | None = None, search: str | None = None, db: Session = Depends(get_db)):
    q = select(Product)
    if category: q = q.where(Product.category_id == category)
    if type: q = q.where(Product.product_type == type)
    if status: q = q.where(Product.status == status)
    if search: q = q.where(or_(Product.name.ilike(f"%{search}%"), Product.description.ilike(f"%{search}%")))
    return [product_out(p) for p in db.scalars(q.order_by(Product.created_at.desc())).all()]
@router.get("/{id}", response_model=ProductOut)
def get_product(id: UUID, db: Session = Depends(get_db)): return product_out(one(db,id))
@router.post("", response_model=ProductOut, dependencies=[Depends(require_admin(["owner", "admin"]))])
def create_product(data: ProductIn, db: Session = Depends(get_db)):
    p = Product(**data.model_dump(exclude={"metadata"}), metadata_=data.metadata); db.add(p)
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(409, "Slug already exists")
    db.refresh(p); return product_out(p)
@router.put("/{id}", response_model=ProductOut, dependencies=[Depends(require_admin(["owner", "admin"]))])
def update_product(id: UUID, data: ProductIn, db: Session = Depends(get_db)):
    p = one(db,id)
    for k,v in data.model_dump(exclude={"metadata"}).items(): setattr(p,k,v)
    p.metadata_ = data.metadata
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(409, "Slug already exists")
    return product_out(p)
@router.delete("/{id}", dependencies=[Depends(require_admin(["owner", "admin"]))])
def archive_product(id: UUID, db: Session = Depends(get_db)):
    one(db,id).status="archived"; db.commit(); return {"ok": True}
@router.post("/{id}/availability", dependencies=[Depends(require_admin(["owner", "admin"]))])
def set_availability(id: UUID, data: AvailabilityIn, db: Session = Depends(get_db)):
    one(db,id)
    if data.slots_available > data.slots_total: raise HTTPException(422, "slots_available cannot exceed slots_total")
    a = db.scalar(select(Availability).where(Availability.product_id==id, Availability.date==data.date))
    if not a: a=Availability(product_id=id, **data.model_dump(exclude={"metadata"}), metadata_=data.metadata); db.add(a)
    else:
        for k,v in data.model_dump(exclude={"metadata"}).items(): setattr(a,k,v)
        a.metadata_=data.metadata
    db.commit(); return {"id": a.id}
@router.get("/{id}/availability")
def get_availability(id: UUID, from_: date | None = None, to: date | None = None, db: Session = Depends(get_db)):
    q=select(Availability).where(Availability.product_id==id)
    if from_: q=q.where(Availability.date>=from_)
    if to: q=q.where(Availability.date<=to)
    return [{"date":a.date,"slots_total":a.slots_total,"slots_available":a.slots_available,"price_override":a.price_override,"metadata":a.metadata_} for a in db.scalars(q.order_by(Availability.date)).all()]
