from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import (
    User, Product, Country, OrganizerTier, Profile, Space,
    SpaceAvailability, SpaceBooking, Coupon, AiAgentDecision, EventEvidence,
)
from api.security import require_admin

router = APIRouter(tags=["vinko"])

ROLES = {"CLIENT", "ORGANIZER", "SPACE_OWNER", "ADMIN"}


def get_current_user_id(authorization: str | None = Header(default=None)):
    from api.routes.auth import verify_jwt
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "No autenticado")
    return verify_jwt(authorization.split(" ", 1)[1])["sub"]


# ============ USERS / ROLES ============
class UserPatch(BaseModel):
    role: str | None = None
    tier_id: int | None = None
    kyc_status: str | None = None
    country_id: UUID | None = None
    preferred_language: str | None = None
    slug: str | None = None


def user_out(u: User) -> dict:
    return {
        "id": str(u.id), "name": u.name, "email": u.email, "avatar": u.avatar_url,
        "role": u.role, "tier_id": u.tier_id, "gmv_total": float(u.gmv_total or 0),
        "current_month_gmv": float(u.current_month_gmv or 0),
        "is_saas_subscriber": u.is_saas_subscriber, "kyc_status": u.kyc_status,
        "preferred_language": u.preferred_language, "slug": u.slug,
    }


@router.get("/users/me")
def me(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    uid = get_current_user_id(authorization)
    u = db.get(User, UUID(uid))
    if not u:
        raise HTTPException(404, "User not found")
    return user_out(u)


@router.patch("/users/me")
def update_me(data: UserPatch, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    uid = get_current_user_id(authorization)
    u = db.get(User, UUID(uid))
    if not u:
        raise HTTPException(404, "User not found")
    if data.role is not None:
        if data.role not in ROLES:
            raise HTTPException(422, "Rol inválido")
        u.role = data.role
    for k, v in data.model_dump(exclude_none=True).items():
        if k != "role":
            setattr(u, k, v)
    db.commit()
    return user_out(u)


@router.get("/users", dependencies=[Depends(require_admin())])
def list_users(role: str | None = None, db: Session = Depends(get_db)):
    q = select(User)
    if role:
        q = q.where(User.role == role)
    return [user_out(u) for u in db.scalars(q.order_by(User.created_at.desc())).all()]


@router.patch("/users/{user_id}", dependencies=[Depends(require_admin(["owner", "admin"]))])
def admin_update_user(user_id: UUID, data: UserPatch, db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if data.role is not None:
        if data.role not in ROLES:
            raise HTTPException(422, "Rol inválido")
        u.role = data.role
    for k, v in data.model_dump(exclude_none=True).items():
        if k != "role":
            setattr(u, k, v)
    db.commit()
    return user_out(u)


# ============ TIERS ============
@router.get("/tiers")
def list_tiers(db: Session = Depends(get_db)):
    return [
        {"level": t.level, "name": t.name, "commission_rate": float(t.commission_rate), "min_gmv": float(t.min_gmv)}
        for t in db.scalars(select(OrganizerTier).order_by(OrganizerTier.level)).all()
    ]


@router.get("/tiers/{level}")
def get_tier(level: int, db: Session = Depends(get_db)):
    t = db.get(OrganizerTier, level)
    if not t:
        raise HTTPException(404, "Tier not found")
    return {"level": t.level, "name": t.name, "commission_rate": float(t.commission_rate), "min_gmv": float(t.min_gmv)}


# ============ PROFILES (link-in-bio) ============
class ProfileIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    bio: dict = {}
    avatar_url: str | None = None


@router.get("/profiles/{slug}")
def get_profile(slug: str, db: Session = Depends(get_db)):
    p = db.scalar(select(Profile).where(Profile.slug == slug))
    if not p:
        raise HTTPException(404, "Profile not found")
    u = db.get(User, p.user_id)
    experiences = db.scalars(
        select(Product).where(Product.organizer_id == u.id, Product.status == "active")
    ).all()
    return {
        "slug": p.slug, "bio": p.bio, "avatar_url": p.avatar_url,
        "rating_average": float(p.rating_average or 0),
        "user": {"name": u.name, "role": u.role, "tier_id": u.tier_id},
        "experiences": [
            {"id": str(x.id), "name": x.name, "base_price": float(x.base_price), "currency": x.currency,
             "location_type": x.location_type, "images": x.images}
            for x in experiences
        ],
    }


@router.put("/profiles/me", dependencies=[Depends(require_admin())])
def upsert_profile(data: ProfileIn, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    uid = get_current_user_id(authorization)
    u = db.get(User, UUID(uid))
    if not u:
        raise HTTPException(404, "User not found")
    p = db.get(Profile, u.id)
    if not p:
        p = Profile(user_id=u.id, **data.model_dump())
        db.add(p)
    else:
        for k, v in data.model_dump().items():
            setattr(p, k, v)
    u.slug = data.slug
    db.commit()
    return {"slug": p.slug}


# ============ SPACES (locales) ============
class SpaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=250)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    country_id: UUID | None = None
    description: dict = {}
    capacity: int = Field(ge=1)
    equipment: list[str] = []
    address: str = Field(min_length=1)
    pricing_model: str | None = None
    price_per_hour: Decimal | None = Field(default=None, ge=0)
    percentage_fee: Decimal | None = Field(default=None, ge=0, le=100)
    is_active: bool = True


def space_out(s: Space) -> dict:
    return {
        "id": str(s.id), "name": s.name, "slug": s.slug, "country_id": str(s.country_id) if s.country_id else None,
        "description": s.description, "capacity": s.capacity, "equipment": s.equipment, "address": s.address,
        "pricing_model": s.pricing_model, "price_per_hour": float(s.price_per_hour) if s.price_per_hour else None,
        "percentage_fee": float(s.percentage_fee) if s.percentage_fee else None, "is_active": s.is_active,
    }


@router.get("/spaces")
def list_spaces(active: bool | None = None, db: Session = Depends(get_db)):
    q = select(Space)
    if active is not None:
        q = q.where(Space.is_active == active)
    return [space_out(s) for s in db.scalars(q.order_by(Space.created_at.desc())).all()]


@router.get("/spaces/{id}")
def get_space(id: UUID, db: Session = Depends(get_db)):
    s = db.get(Space, id)
    if not s:
        raise HTTPException(404, "Space not found")
    return space_out(s)


@router.post("/spaces")
def create_space(data: SpaceIn, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    uid = get_current_user_id(authorization)
    u = db.get(User, UUID(uid))
    if not u:
        raise HTTPException(404, "User not found")
    if u.role not in ("SPACE_OWNER", "ADMIN"):
        raise HTTPException(403, "Solo space owners pueden crear espacios")
    s = Space(owner_id=u.id, **data.model_dump())
    db.add(s)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "Slug ya existe")
    db.refresh(s)
    return space_out(s)


@router.put("/spaces/{id}")
def update_space(id: UUID, data: SpaceIn, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    uid = get_current_user_id(authorization)
    s = db.get(Space, id)
    if not s:
        raise HTTPException(404, "Space not found")
    u = db.get(User, UUID(uid))
    if not u or (s.owner_id != u.id and u.role not in ("owner", "admin")):
        raise HTTPException(403, "No tienes permiso")
    for k, v in data.model_dump().items():
        setattr(s, k, v)
    db.commit()
    return space_out(s)


# ============ SPACE AVAILABILITY ============
class SpaceAvailIn(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: str
    end_time: str


@router.get("/spaces/{id}/availability")
def get_space_availability(id: UUID, db: Session = Depends(get_db)):
    if not db.get(Space, id):
        raise HTTPException(404, "Space not found")
    rows = db.scalars(select(SpaceAvailability).where(SpaceAvailability.space_id == id).order_by(SpaceAvailability.day_of_week)).all()
    return [
        {"id": str(a.id), "day_of_week": a.day_of_week, "start_time": str(a.start_time), "end_time": str(a.end_time)}
        for a in rows
    ]


@router.post("/spaces/{id}/availability")
def add_space_availability(id: UUID, data: SpaceAvailIn, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    s = db.get(Space, id)
    if not s:
        raise HTTPException(404, "Space not found")
    uid = get_current_user_id(authorization)
    u = db.get(User, UUID(uid))
    if not u or (s.owner_id != u.id and u.role not in ("owner", "admin")):
        raise HTTPException(403, "No tienes permiso")
    try:
        st = time.fromisoformat(data.start_time)
        et = time.fromisoformat(data.end_time)
    except ValueError:
        raise HTTPException(422, "Formato de hora inválido (HH:MM)")
    a = SpaceAvailability(space_id=id, day_of_week=data.day_of_week, start_time=st, end_time=et)
    db.add(a)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "Slot ya existe")
    return {"id": a.id}


# ============ SPACE BOOKINGS ============
class SpaceBookingIn(BaseModel):
    space_id: UUID
    experience_id: UUID | None = None
    start_at: str
    end_at: str


@router.post("/space-bookings")
def create_space_booking(data: SpaceBookingIn, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    uid = get_current_user_id(authorization)
    u = db.get(User, UUID(uid))
    if not u:
        raise HTTPException(404, "User not found")
    try:
        start = datetime.fromisoformat(data.start_at)
        end = datetime.fromisoformat(data.end_at)
    except ValueError:
        raise HTTPException(422, "Formato datetime inválido (ISO)")
    if end <= start:
        raise HTTPException(422, "end_at debe ser posterior a start_at")
    b = SpaceBooking(space_id=data.space_id, experience_id=data.experience_id, start_at=start, end_at=end)
    db.add(b)
    db.commit()
    return {"id": b.id, "status": b.status}


@router.get("/space-bookings", dependencies=[Depends(require_admin())])
def list_space_bookings(db: Session = Depends(get_db)):
    return [
        {"id": str(b.id), "space_id": str(b.space_id), "experience_id": str(b.experience_id) if b.experience_id else None,
         "start_at": b.start_at.isoformat(), "end_at": b.end_at.isoformat(), "status": b.status}
        for b in db.scalars(select(SpaceBooking).order_by(SpaceBooking.start_at.desc())).all()
    ]


# ============ COUPONS ============
class CouponIn(BaseModel):
    code: str = Field(min_length=3, max_length=50)
    discount_percent: Decimal = Field(ge=0, le=100)
    expires_at: str


@router.post("/coupons")
def create_coupon(data: CouponIn, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    uid = get_current_user_id(authorization)
    u = db.get(User, UUID(uid))
    if not u:
        raise HTTPException(404, "User not found")
    if u.role not in ("ORGANIZER", "ADMIN"):
        raise HTTPException(403, "Solo organizadores pueden crear cupones")
    try:
        exp = datetime.fromisoformat(data.expires_at)
    except ValueError:
        raise HTTPException(422, "Formato datetime inválido (ISO)")
    c = Coupon(code=data.code.upper(), discount_percent=data.discount_percent, expires_at=exp, organizer_id=u.id)
    db.add(c)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "Código ya existe")
    return {"id": c.id, "code": c.code}


@router.get("/coupons")
def list_coupons(valid: bool | None = None, db: Session = Depends(get_db)):
    q = select(Coupon)
    if valid:
        q = q.where(Coupon.expires_at > datetime.now(timezone.utc))
    return [
        {"id": str(c.id), "code": c.code, "discount_percent": float(c.discount_percent),
         "expires_at": c.expires_at.isoformat(), "organizer_id": str(c.organizer_id) if c.organizer_id else None}
        for c in db.scalars(q.order_by(Coupon.created_at.desc())).all()
    ]


# ============ AI AGENT DECISIONS ============
class AiDecisionIn(BaseModel):
    agent_role: str
    target_id: UUID
    decision_type: str
    reasoning: str | None = None


@router.post("/ai-decisions", dependencies=[Depends(require_admin())])
def create_ai_decision(data: AiDecisionIn, db: Session = Depends(get_db)):
    d = AiAgentDecision(**data.model_dump())
    db.add(d)
    db.commit()
    return {"id": d.id}


@router.get("/ai-decisions", dependencies=[Depends(require_admin())])
def list_ai_decisions(agent_role: str | None = None, db: Session = Depends(get_db)):
    q = select(AiAgentDecision)
    if agent_role:
        q = q.where(AiAgentDecision.agent_role == agent_role)
    return [
        {"id": str(d.id), "agent_role": d.agent_role, "target_id": str(d.target_id),
         "decision_type": d.decision_type, "reasoning": d.reasoning, "created_at": d.created_at.isoformat()}
        for d in db.scalars(q.order_by(AiAgentDecision.created_at.desc())).all()
    ]


# ============ EVENT EVIDENCE (KYC) ============
class EvidenceIn(BaseModel):
    experience_id: UUID
    photo_url: str
    exif_lat: Decimal | None = None
    exif_lng: Decimal | None = None
    exif_timestamp: str | None = None


@router.post("/evidence", dependencies=[Depends(require_admin())])
def create_evidence(data: EvidenceIn, db: Session = Depends(get_db)):
    if not db.get(Product, data.experience_id):
        raise HTTPException(404, "Experience not found")
    ts = None
    if data.exif_timestamp:
        try:
            ts = datetime.fromisoformat(data.exif_timestamp)
        except ValueError:
            raise HTTPException(422, "exif_timestamp inválido")
    e = EventEvidence(experience_id=data.experience_id, photo_url=data.photo_url,
                      exif_lat=data.exif_lat, exif_lng=data.exif_lng, exif_timestamp=ts)
    db.add(e)
    db.commit()
    return {"id": e.id}


@router.get("/evidence", dependencies=[Depends(require_admin())])
def list_evidence(experience_id: UUID | None = None, db: Session = Depends(get_db)):
    q = select(EventEvidence)
    if experience_id:
        q = q.where(EventEvidence.experience_id == experience_id)
    return [
        {"id": str(e.id), "experience_id": str(e.experience_id), "photo_url": e.photo_url,
         "is_verified": e.is_verified, "created_at": e.created_at.isoformat()}
        for e in db.scalars(q.order_by(EventEvidence.created_at.desc())).all()
    ]
