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
    },
    "vinko-ai-growth-scan-6h": {
        "task": "worker.tasks.ai_growth_scan",
        "schedule": 21600.0,
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


# ===== VINKO AI Growth Engine (Guaica-Growth) =====
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select, func
from core.models import AiAgentDecision, Order, Product, Space, SpaceAvailability, SpaceBooking, Coupon, User


@celery.task
def ai_growth_scan():
    """Escaneo de crecimiento: churn de clientes + dead hours de espacios + cupones.
    Corre cada 6h via beat. Registra decisiones en ai_agent_decisions."""
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    results = {"churn": 0, "dead_hours": 0, "coupons": 0}

    # 1. CHURN: clientes que reservaron antes pero no en los últimos 15 días
    cutoff = now - timedelta(days=15)
    active_emails = set(db.scalars(select(Order.customer_email).where(Order.created_at >= cutoff)).all())
    past_orders = db.scalars(select(Order).where(Order.created_at < cutoff)).all()
    seen = set()
    for o in past_orders:
        if o.customer_email in active_emails or o.customer_email in seen:
            continue
        seen.add(o.customer_email)
        db.add(AiAgentDecision(
            agent_role="MARKETING", target_id=o.id, decision_type="CHURN",
            reasoning=f"Cliente {o.customer_email} sin reservas en 15 días",
        ))
        results["churn"] += 1

    # 2. DEAD HOURS: slots de espacios sin reserva en los próximos 7 días
    spaces = db.scalars(select(Space).where(Space.is_active == True)).all()
    for s in spaces:
        slots = db.scalars(select(SpaceAvailability).where(SpaceAvailability.space_id == s.id)).all()
        if not slots:
            continue
        booked = db.scalars(select(SpaceBooking).where(
            SpaceBooking.space_id == s.id,
            SpaceBooking.start_at >= now,
            SpaceBooking.start_at <= now + timedelta(days=7),
        )).all()
        booked_slots = {(b.start_at.weekday(), b.start_at.time().strftime("%H:%M")) for b in booked}
        for a in slots:
            key = (a.day_of_week, a.start_time.strftime("%H:%M"))
            if key not in booked_slots:
                db.add(AiAgentDecision(
                    agent_role="MARKETING", target_id=s.id, decision_type="DEAD_HOUR",
                    reasoning=f"Espacio {s.name}: slot {a.day_of_week} {a.start_time}-{a.end_time} sin reserva en 7 días",
                ))
                results["dead_hours"] += 1

    # 3. CUPONES: generar cupón temporal para experiencias con poca demanda
    exp_count = db.scalar(select(func.count()).select_from(Product).where(Product.product_type == "experience", Product.status == "active")) or 0
    if exp_count > 0:
        code = f"GROWTH{now.strftime('%m%d')}{uuid4().hex[:4].upper()}"
        db.add(Coupon(code=code, discount_percent=10, expires_at=now + timedelta(days=7)))
        db.add(AiAgentDecision(
            agent_role="MARKETING", target_id=uuid4(), decision_type="COUPON",
            reasoning=f"Cupón {code} generado (10% off, 7 días)",
        ))
        results["coupons"] += 1

    db.commit()
    return results
