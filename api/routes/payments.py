from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import Product, User, OrganizerTier, Order
from api.routes.auth import create_jwt
import os

router = APIRouter(prefix="/payments", tags=["payments"])

# Credenciales MercadoPago (Marketplace). Vacías = modo simulado honesto.
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
MP_PUBLIC_KEY = os.getenv("MP_PUBLIC_KEY", "")


class PreferenceIn(BaseModel):
    product_id: UUID
    quantity: int = Field(default=1, ge=1)
    coupon_code: str | None = None


def get_commission_rate(db: Session, organizer_id: UUID | None) -> Decimal:
    """Comisión según tier del organizador. Sin organizador = 15% (tier 1)."""
    if not organizer_id:
        return Decimal("15.00")
    u = db.get(User, organizer_id)
    if not u:
        return Decimal("15.00")
    if u.is_saas_subscriber:
        return Decimal("4.00")
    tier = db.get(OrganizerTier, u.tier_id or 1)
    return tier.commission_rate if tier else Decimal("15.00")


@router.post("/create-preference")
def create_preference(data: PreferenceIn, db: Session = Depends(get_db)):
    """Crea preferencia de pago con split (application_fee = comisión del organizador).
    Sin MP_ACCESS_TOKEN devuelve estructura simulada (modo demo honesto)."""
    p = db.get(Product, data.product_id)
    if not p or p.status != "active":
        raise HTTPException(404, "Producto no encontrado")

    # Cupón
    discount = Decimal("0")
    if data.coupon_code:
        from core.models import Coupon
        from datetime import datetime, timezone
        c = db.scalar(select(Coupon).where(Coupon.code == data.coupon_code.upper()))
        if not c or c.expires_at < datetime.now(timezone.utc):
            raise HTTPException(422, "Cupón inválido o vencido")
        discount = c.discount_percent

    unit_price = p.base_price * (1 - discount / 100)
    total = unit_price * data.quantity
    rate = get_commission_rate(db, p.organizer_id)
    fee = total * rate / 100

    if not MP_ACCESS_TOKEN:
        # Modo simulado: devolvemos la estructura exacta que usará MP real
        return {
            "mode": "simulated",
            "message": "MercadoPago no configurado (MP_ACCESS_TOKEN vacío). Estructura de split lista.",
            "preference": {
                "items": [{"title": p.name, "quantity": data.quantity, "unit_price": float(unit_price), "currency_id": p.currency}],
                "application_fee": float(fee),
                "commission_rate": float(rate),
                "organizer_id": str(p.organizer_id) if p.organizer_id else None,
                "total": float(total),
            },
            "init_point": None,
        }

    # Modo real: crear preferencia en MercadoPago
    import requests
    payload = {
        "items": [{"title": p.name, "quantity": data.quantity, "unit_price": float(unit_price), "currency_id": p.currency}],
        "marketplace_fee": float(fee),
        "notification_url": "https://hub.zabreuit.com/api/v1/payments/webhook",
        "back_urls": {"success": "https://hub.zabreuit.com/checkout.html?status=success", "failure": "https://hub.zabreuit.com/checkout.html?status=failure"},
        "auto_return": "approved",
    }
    r = requests.post("https://api.mercadopago.com/checkout/preferences",
                      headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}, json=payload, timeout=15)
    if r.status_code not in (200, 201):
        raise HTTPException(502, f"MercadoPago error: {r.text[:200]}")
    pref = r.json()
    return {"mode": "real", "preference_id": pref["id"], "init_point": pref["init_point"]}


class WebhookIn(BaseModel):
    type: str | None = None
    data: dict = {}


@router.post("/webhook")
def mp_webhook(data: WebhookIn, db: Session = Depends(get_db)):
    """Webhook de MercadoPago: marca pago aprobado y actualiza GMV del organizador."""
    if data.type != "payment":
        return {"ok": True}
    payment_id = data.data.get("id")
    if not payment_id:
        return {"ok": True}
    if not MP_ACCESS_TOKEN:
        return {"ok": True, "mode": "simulated"}
    import requests
    r = requests.get(f"https://api.mercadopago.com/v1/payments/{payment_id}",
                     headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}, timeout=15)
    if r.status_code != 200:
        return {"ok": False}
    pay = r.json()
    if pay.get("status") != "approved":
        return {"ok": True}
    # Buscar orden por metadata.external_payment_id
    from sqlalchemy import text
    rows = db.execute(text("SELECT id FROM orders WHERE metadata->>'mp_payment_id' = :pid"), {"pid": str(payment_id)}).all()
    if not rows:
        return {"ok": True}
    order = db.get(Order, rows[0][0])
    if order:
        order.payment_status = "paid"
        order.status = "confirmed"
        order.metadata_ = {**order.metadata_, "mp_payment_id": str(payment_id), "mp_status": "approved"}
        # GMV del organizador
        p = db.get(Product, order.product_id)
        if p and p.organizer_id:
            org = db.get(User, p.organizer_id)
            if org:
                org.gmv_total = (org.gmv_total or 0) + order.total_amount
                org.current_month_gmv = (org.current_month_gmv or 0) + order.total_amount
                org.last_transaction_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        db.commit()
    return {"ok": True}
