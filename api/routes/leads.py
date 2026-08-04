from datetime import datetime
import logging
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import Lead

router = APIRouter(prefix="/leads", tags=["leads"])
logger = logging.getLogger(__name__)


class LeadIn(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str = Field(min_length=1)
    business_name: str = Field(min_length=1)
    business_type: str = Field(pattern=r"^(hotel|restaurante|tour|spa|transporte|eventos|otro)$")
    message: str | None = None


class LeadCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
    created_at: datetime


class LeadOut(LeadIn, LeadCreated):
    updated_at: datetime


@router.post("", response_model=LeadCreated)
def create(data: LeadIn, db: Session = Depends(get_db)):
    lead = Lead(**data.model_dump())
    db.add(lead); db.commit(); db.refresh(lead)
    try:
        from worker.tasks import send_welcome_email
        send_welcome_email.delay(str(lead.id))
    except Exception:
        logger.exception("Could not enqueue welcome email for lead %s", lead.id)
    return lead


@router.get("", response_model=list[LeadOut])
def list_leads(db: Session = Depends(get_db)):
    return db.scalars(select(Lead).order_by(Lead.created_at.desc())).all()
