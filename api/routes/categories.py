from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import Category, Product
from api.security import authorize
router=APIRouter(prefix="/categories",tags=["categories"])
class CategoryIn(BaseModel): name:str=Field(min_length=1,max_length=120); slug:str=Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"); parent_id:UUID|None=None; icon:str|None=None; sort_order:int=0
class CategoryOut(CategoryIn): model_config=ConfigDict(from_attributes=True); id:UUID
def item(db,id):
    x=db.get(Category,id)
    if not x: raise HTTPException(404,"Category not found")
    return x
@router.get("",response_model=list[CategoryOut])
def list_categories(db:Session=Depends(get_db)): return db.scalars(select(Category).order_by(Category.sort_order,Category.name)).all()
@router.post("",response_model=CategoryOut,dependencies=[Depends(authorize)])
def create(data:CategoryIn,db:Session=Depends(get_db)):
    x=Category(**data.model_dump()); db.add(x)
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(409,"Slug already exists")
    return x
@router.put("/{id}",response_model=CategoryOut,dependencies=[Depends(authorize)])
def update(id:UUID,data:CategoryIn,db:Session=Depends(get_db)):
    x=item(db,id)
    for k,v in data.model_dump().items(): setattr(x,k,v)
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(409,"Slug already exists")
    return x
@router.delete("/{id}",dependencies=[Depends(authorize)])
def delete(id:UUID,db:Session=Depends(get_db)):
    x=item(db,id)
    if db.scalar(select(Product.id).where(Product.category_id==id).limit(1)): raise HTTPException(409,"Category has products")
    db.delete(x); db.commit(); return {"ok":True}
