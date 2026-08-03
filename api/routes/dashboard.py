from datetime import date, datetime, time, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import Order, Product
from api.security import authorize
router=APIRouter(prefix="/dashboard",tags=["dashboard"],dependencies=[Depends(authorize)])
@router.get("/stats")
def stats(db:Session=Depends(get_db)):
 today=datetime.combine(date.today(),time.min,tzinfo=timezone.utc)
 return {"active_products":db.scalar(select(func.count()).select_from(Product).where(Product.status=='active')) or 0,"orders_today":db.scalar(select(func.count()).select_from(Order).where(Order.created_at>=today)) or 0,"sales":db.scalar(select(func.coalesce(func.sum(Order.total_amount),0)).where(Order.status.in_(['confirmed','completed']))) or 0}
@router.get("/charts")
def charts(db:Session=Depends(get_db)):
 types=db.execute(select(Product.product_type,func.count()).group_by(Product.product_type)).all()
 sales=db.execute(select(func.date(Order.created_at),func.coalesce(func.sum(Order.total_amount),0)).where(Order.status.in_(['confirmed','completed'])).group_by(func.date(Order.created_at)).order_by(func.date(Order.created_at).desc()).limit(30)).all()
 return {"products_by_type":[{"type":t,"count":n} for t,n in types],"daily_sales":[{"date":str(d),"sales":float(s)} for d,s in reversed(sales)]}
