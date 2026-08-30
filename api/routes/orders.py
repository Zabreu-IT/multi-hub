from datetime import date
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import Availability, Order, Product
from api.security import require_admin
router=APIRouter(prefix="/orders",tags=["orders"])
class OrderIn(BaseModel):
 product_id:UUID; customer_name:str=Field(min_length=1); customer_email:str=Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"); customer_phone:str|None=None; date_from:date|None=None; date_to:date|None=None; quantity:int=Field(default=1,ge=1); total_amount:Decimal=Field(ge=0); currency:str="USD"; metadata:dict={}
class OrderOut(OrderIn): model_config=ConfigDict(from_attributes=True); id:UUID; status:str; payment_status:str
def out(x): return {**{k:getattr(x,k) for k in OrderIn.model_fields if k!='metadata'},"metadata":x.metadata_,"id":x.id,"status":x.status,"payment_status":x.payment_status}
@router.post("",response_model=OrderOut)
def create(data:OrderIn,db:Session=Depends(get_db)):
 p=db.get(Product,data.product_id)
 if not p or p.status!='active': raise HTTPException(404,"Active product not found")
 if data.date_from:
  a=db.scalar(select(Availability).where(Availability.product_id==p.id,Availability.date==data.date_from).with_for_update())
  if a and a.slots_available<data.quantity: raise HTTPException(409,"Not enough availability")
  if a: a.slots_available-=data.quantity
 x=Order(**data.model_dump(exclude={'metadata'}),metadata_=data.metadata); db.add(x); db.commit(); db.refresh(x); return out(x)
@router.get("",response_model=list[OrderOut],dependencies=[Depends(require_admin())])
def list_orders(status:str|None=None,db:Session=Depends(get_db)):
 q=select(Order); q=q.where(Order.status==status) if status else q
 return [out(x) for x in db.scalars(q.order_by(Order.created_at.desc())).all()]
@router.get("/{id}",response_model=OrderOut,dependencies=[Depends(require_admin())])
def get(id:UUID,db:Session=Depends(get_db)):
 x=db.get(Order,id)
 if not x: raise HTTPException(404,"Order not found")
 return out(x)
class OrderPatch(BaseModel): status:str|None=None; payment_status:str|None=None
@router.patch("/{id}",response_model=OrderOut,dependencies=[Depends(require_admin())])
def update(id:UUID,data:OrderPatch,db:Session=Depends(get_db)):
 x=db.get(Order,id)
 if not x: raise HTTPException(404,"Order not found")
 if data.status and data.status not in {'pending','confirmed','cancelled','completed'}: raise HTTPException(422,"Invalid status")
 if data.payment_status and data.payment_status not in {'unpaid','paid','refunded'}: raise HTTPException(422,"Invalid payment status")
 for k,v in data.model_dump(exclude_none=True).items(): setattr(x,k,v)
 db.commit(); return out(x)
