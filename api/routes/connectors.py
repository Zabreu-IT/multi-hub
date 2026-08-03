from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import Connector
from api.security import authorize
router=APIRouter(prefix="/connectors",tags=["connectors"])
class ConnectorIn(BaseModel): name:str=Field(min_length=1); platform:str; config:dict={}; sync_interval_minutes:int=Field(default=60,ge=1)
class ConnectorOut(BaseModel): model_config=ConfigDict(from_attributes=True); id:UUID; name:str; platform:str; status:str; last_sync_at:datetime|None; sync_interval_minutes:int; created_at:datetime
def one(db,id):
 x=db.get(Connector,id)
 if not x: raise HTTPException(404,"Connector not found")
 return x
@router.get("",response_model=list[ConnectorOut],dependencies=[Depends(authorize)])
def list_connectors(db:Session=Depends(get_db)): return db.scalars(select(Connector).order_by(Connector.created_at.desc())).all()
@router.post("",response_model=ConnectorOut,dependencies=[Depends(authorize)])
def create(data:ConnectorIn,db:Session=Depends(get_db)):
 if data.platform not in {'prestashop','shopify','woocommerce','native'}: raise HTTPException(422,"Unsupported platform")
 x=Connector(**data.model_dump()); db.add(x); db.commit(); db.refresh(x); return x
@router.post("/{id}/sync",dependencies=[Depends(authorize)])
def sync(id:UUID,db:Session=Depends(get_db)):
 one(db,id)
 try:
  from worker.tasks import sync_connector
  result=sync_connector.delay(str(id)); return {"task_id":result.id}
 except Exception: return {"task_id":None,"detail":"Worker unavailable; sync will run when Celery is available"}
@router.get("/{id}/status",dependencies=[Depends(authorize)])
async def status(id:UUID,db:Session=Depends(get_db)):
 x=one(db,id)
 try:
  from worker.tasks import connector_for
  health=await connector_for(x).healthcheck(); x.status="active" if health["ok"] else "error"; db.commit()
 except Exception as e: health={"ok":False,"detail":str(e)}; x.status="error"; db.commit()
 return {"id":x.id,"status":x.status,"last_sync_at":x.last_sync_at,"health":health}
@router.delete("/{id}",dependencies=[Depends(authorize)])
def disable(id:UUID,db:Session=Depends(get_db)):
 x=one(db,id); x.status="disabled"; db.commit(); return {"ok":True}
