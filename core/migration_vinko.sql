-- ============================================================
-- VINKO + Multi-Hub Unified Schema Migration
-- Fusiona el modelo multi-rol de VINKO (organizadores, locales,
-- tiers, comisiones) sobre el Postgres de Multi-Hub.
-- Idempotente: seguro de re-ejecutar.
-- Aplicar: psql -U hub -d multihub -f core/migration_vinko.sql
-- ============================================================

-- 1. COUNTRIES (seed LatAm)
CREATE TABLE IF NOT EXISTS countries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    iso_code CHAR(2) UNIQUE NOT NULL,
    currency_code CHAR(3) NOT NULL,
    timezone TEXT NOT NULL,
    tax_id_label TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO countries (iso_code, currency_code, timezone, tax_id_label) VALUES
('AR', 'ARS', 'America/Argentina/Buenos_Aires', 'CUIL'),
('BR', 'BRL', 'America/Sao_Paulo', 'CPF'),
('MX', 'MXN', 'America/Mexico_City', 'RFC'),
('CO', 'COP', 'America/Bogota', 'NIT'),
('CL', 'CLP', 'America/Santiago', 'RUT'),
('PE', 'PEN', 'America/Lima', 'RUC')
ON CONFLICT (iso_code) DO NOTHING;

-- 2. ORGANIZER TIERS (18 niveles, comision por GMV mensual)
CREATE TABLE IF NOT EXISTS organizer_tiers (
    level INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    commission_rate DECIMAL(5,2) NOT NULL,
    min_gmv DECIMAL(15,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO organizer_tiers (level, name, commission_rate, min_gmv) VALUES
(1, 'Nuevo I', 15.00, 0.00),
(2, 'Nuevo II', 14.50, 200000.00),
(3, 'Nuevo III', 14.00, 400000.00),
(4, 'Bronce I', 13.00, 600000.00),
(5, 'Bronce II', 12.00, 750000.00),
(6, 'Bronce III', 11.00, 900000.00),
(7, 'Plata I', 10.00, 1000000.00),
(8, 'Plata II', 9.50, 1400000.00),
(9, 'Plata III', 9.00, 2000000.00),
(10, 'Oro I', 8.50, 3000000.00),
(11, 'Oro II', 8.00, 4500000.00),
(12, 'Oro III', 7.50, 6000000.00),
(13, 'Platinum I', 7.00, 8000000.00),
(14, 'Platinum II', 6.50, 10000000.00),
(15, 'Platinum III', 6.00, 15000000.00),
(16, 'Diamante I', 5.00, 20000000.00),
(17, 'Diamante II', 4.50, 30000000.00),
(18, 'Diamante III', 4.00, 50000000.00)
ON CONFLICT (level) DO NOTHING;

-- 3. EXTEND USERS (Multi-Hub) -> roles multi-tenant + tier + GMV
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(16) NOT NULL DEFAULT 'CLIENT'
    CHECK (role IN ('CLIENT','ORGANIZER','SPACE_OWNER','ADMIN'));
ALTER TABLE users ADD COLUMN IF NOT EXISTS tier_id INTEGER REFERENCES organizer_tiers(level) DEFAULT 1;
ALTER TABLE users ADD COLUMN IF NOT EXISTS gmv_total NUMERIC(15,2) NOT NULL DEFAULT 0.00;
ALTER TABLE users ADD COLUMN IF NOT EXISTS current_month_gmv NUMERIC(15,2) NOT NULL DEFAULT 0.00;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_transaction_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_saas_subscriber BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS kyc_status VARCHAR(20) NOT NULL DEFAULT 'PENDING';
ALTER TABLE users ADD COLUMN IF NOT EXISTS country_id UUID REFERENCES countries(id);
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_language CHAR(2) NOT NULL DEFAULT 'es';
ALTER TABLE users ADD COLUMN IF NOT EXISTS slug TEXT UNIQUE;

-- 4. EXTEND PRODUCTS (Multi-Hub) -> experiences con ubicacion
ALTER TABLE products ADD COLUMN IF NOT EXISTS organizer_id UUID REFERENCES users(id);
ALTER TABLE products ADD COLUMN IF NOT EXISTS location_type VARCHAR(20) NOT NULL DEFAULT 'private_space'
    CHECK (location_type IN ('public_space','private_space'));
ALTER TABLE products ADD COLUMN IF NOT EXISTS location_lat DECIMAL(9,6);
ALTER TABLE products ADD COLUMN IF NOT EXISTS location_lng DECIMAL(9,6);
ALTER TABLE products ADD COLUMN IF NOT EXISTS location_description TEXT;

-- 5. PROFILES (link-in-bio por organizador)
CREATE TABLE IF NOT EXISTS profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    slug TEXT UNIQUE NOT NULL,
    bio JSONB NOT NULL DEFAULT '{}'::jsonb,
    avatar_url TEXT,
    rating_average DECIMAL(3,2) NOT NULL DEFAULT 0.0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. SPACES (locales de los space owners)
CREATE TABLE IF NOT EXISTS spaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID REFERENCES users(id) ON DELETE CASCADE,
    country_id UUID REFERENCES countries(id),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description JSONB NOT NULL DEFAULT '{}'::jsonb,
    capacity INTEGER NOT NULL,
    equipment JSONB NOT NULL DEFAULT '[]'::jsonb,
    address TEXT NOT NULL,
    pricing_model TEXT CHECK (pricing_model IN ('FIXED','PERCENTAGE')),
    price_per_hour DECIMAL(12,2),
    percentage_fee DECIMAL(5,2),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. SPACE AVAILABILITY (horarios recurrentes)
CREATE TABLE IF NOT EXISTS space_availability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    day_of_week INTEGER CHECK (day_of_week BETWEEN 0 AND 6),
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    UNIQUE(space_id, day_of_week, start_time, end_time)
);

-- 8. SPACE BOOKINGS (experiencia <-> espacio)
CREATE TABLE IF NOT EXISTS space_bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id UUID REFERENCES spaces(id),
    experience_id UUID REFERENCES products(id),
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'CONFIRMED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 9. COUPONS (descuentos AI / manuales)
CREATE TABLE IF NOT EXISTS coupons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    discount_percent DECIMAL(5,2) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    organizer_id UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 10. AI AGENT DECISIONS (growth engine: churn, dead hours, validacion)
CREATE TABLE IF NOT EXISTS ai_agent_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_role VARCHAR(20) NOT NULL,
    target_id UUID NOT NULL,
    decision_type VARCHAR(20) NOT NULL,
    reasoning TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 11. EVENT EVIDENCE (KYC forense: fotos con EXIF)
CREATE TABLE IF NOT EXISTS event_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experience_id UUID REFERENCES products(id) ON DELETE CASCADE,
    photo_url TEXT NOT NULL,
    exif_lat DECIMAL(10,8),
    exif_lng DECIMAL(11,8),
    exif_timestamp TIMESTAMPTZ,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 12. INDICES
CREATE INDEX IF NOT EXISTS products_organizer_idx ON products(organizer_id);
CREATE INDEX IF NOT EXISTS spaces_owner_idx ON spaces(owner_id);
CREATE INDEX IF NOT EXISTS space_bookings_space_idx ON space_bookings(space_id);
CREATE INDEX IF NOT EXISTS space_bookings_experience_idx ON space_bookings(experience_id);
CREATE INDEX IF NOT EXISTS ai_agent_decisions_target_idx ON ai_agent_decisions(target_id);
