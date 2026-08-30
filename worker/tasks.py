import asyncio
import logging
import os
from datetime import datetime, timezone
from celery import Celery
from sqlalchemy import select
from core.models import Connector, Lead, Product
from worker.database import SessionLocal
from worker.email_ai import generate_welcome_email, send_email
from connectors.native import NativeConnector
from connectors.prestashop import PrestashopConnector
from connectors.shopify import ShopifyConnector
from connectors.woocommerce import WooCommerceConnector

celery = Celery("multihub", broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"), backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"))
celery.conf.beat_schedule = {
    "sync-active-connectors-every-minute": {
        "task": "worker.tasks.reconcile_connectors",
        "schedule": 60.0,
    }
}
logger = logging.getLogger(__name__)
def connector_for(record): return {"native": NativeConnector, "prestashop": PrestashopConnector, "shopify": ShopifyConnector, "woocommerce": WooCommerceConnector}[record.platform](record.config)

@celery.task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def sync_connector(connector_id: str):
    db = SessionLocal()
    try:
        record = db.get(Connector, connector_id)
        if not record or record.status == "disabled": return {"skipped": True}
        products = asyncio.run(connector_for(record).fetch_products()); created = updated = 0
        for data in products:
            item = db.scalar(select(Product).where(Product.source_connector_id == record.id, Product.external_id == data.external_id))
            if item: item.name, item.slug, item.base_price, item.description, updated = data.name, data.slug, data.price, data.description, updated + 1
            else: db.add(Product(name=data.name, slug=f"{record.id.hex[:8]}-{data.slug}", base_price=data.price, description=data.description, source_connector_id=record.id, external_id=data.external_id, status="active")); created += 1
        record.last_sync_at = datetime.now(timezone.utc); record.status = "active"; db.commit(); return {"created": created, "updated": updated}
    except Exception:
        db.rollback()
        if 'record' in locals() and record: record.status = "error"; db.commit()
        raise
    finally: db.close()

@celery.task
def reconcile_connectors():
    db = SessionLocal()
    try: return [sync_connector.delay(str(x.id)).id for x in db.scalars(select(Connector).where(Connector.status == "active")).all()]
    finally: db.close()


@celery.task
def send_welcome_email(lead_id: str):
    db = SessionLocal()
    try:
        lead = db.get(Lead, lead_id)
        if not lead: return {"success": False, "error": "Lead not found"}
        if lead.status == "contacted": return {"success": True, "error": "", "skipped": True}
        subject, body = generate_welcome_email({key: getattr(lead, key) for key in ("name", "business_name", "email")})
        result = send_email(lead.email, subject, body)
        if result["success"]:
            lead.status = "contacted"
            lead.metadata_ = {**(lead.metadata_ or {}), "email_subject": subject, "email_body": body}
            db.commit()
        else:
            logger.error("Welcome email for lead %s failed: %s", lead_id, result["error"])
        return result
    except Exception:
        db.rollback()
        logger.exception("Welcome email task for lead %s failed", lead_id)
        raise
    finally:
        db.close()
