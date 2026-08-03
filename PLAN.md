# Multi-Hub — Hub Universal de Experiencias y Productos

## Visión
Sistema booking-style que conecta con cualquier plataforma ecommerce (Prestashop, Shopify, WooCommerce, WordPress) **O** funciona como panel propio para crear y gestionar productos desde cero (hoteles, restaurantes, tours, servicios).

## Arquitectura

```
multi-hub/
├── core/                        # Modelo de datos unificado
│   ├── models.py                # Product, Variant, Category, Availability, Image, Connector
│   ├── database.py              # SQLAlchemy engine + session
│   └── schema.sql               # DDL completo
├── connectors/                  # Adaptadores por plataforma
│   ├── base.py                  # Interfaz abstracta BaseConnector
│   ├── prestashop.py            # Reusar del multi-presta actual
│   ├── shopify.py               # Shopify Admin API
│   ├── woocommerce.py           # WooCommerce REST API
│   └── native.py                # Sin plataforma — usa DB local directamente
├── api/                         # FastAPI unificado
│   ├── main.py                  # App + middleware + startup
│   ├── routes/
│   │   ├── products.py          # CRUD productos (nativos + sincronizados)
│   │   ├── categories.py        # CRUD categorías
│   │   ├── availability.py      # Disponibilidad / stock
│   │   ├── connectors.py        # Gestión de conectores (alta, sync, status)
│   │   ├── orders.py            # Pedidos / reservas
│   │   ├── dashboard.py         # Stats, métricas, KPIs del dashboard
│   │   └── media.py             # Upload de imágenes
│   ├── middleware.py             # Rate limit, request context, auth
│   ├── security.py              # HMAC, tokens, API keys
│   ├── requirements.txt
│   └── Dockerfile
├── dashboard/                   # Panel de administración (HTML/JS/CSS)
│   ├── index.html               # SPA dashboard — gestión completa
│   ├── products.html            # CRUD productos
│   ├── connectors.html          # Gestión de conexiones
│   └── styles.css
├── frontend/                    # UI pública (booking/search)
│   ├── index.html               # Home con buscador
│   ├── results.html             # Resultados de búsqueda
│   ├── product.html             # Detalle de producto/experiencia
│   ├── checkout.html            # Checkout / reserva
│   ├── hub_engine.js            # Motor de búsqueda
│   ├── styles.css
│   └── Dockerfile
├── worker/                      # Background tasks
│   ├── tasks.py                 # Celery tasks (sync, retry, reconcile)
│   ├── database.py
│   ├── requirements.txt
│   └── Dockerfile
├── infra/
│   ├── docker/
│   │   ├── docker-compose.yml
│   │   └── nginx/
│   │       └── hub.conf
│   └── db/
│       └── schema.sql
├── scripts/
│   ├── bootstrap.sh
│   └── seed_demo.sh
├── Makefile
├── .env.example
├── .gitignore
└── README.md
```

## Modelo de Datos Unificado

### Tabla: products
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | UUID PK | Identificador único |
| name | TEXT NOT NULL | Nombre del producto/experiencia |
| slug | TEXT UNIQUE | URL-friendly identifier |
| description | TEXT | Descripción completa |
| description_short | TEXT | Descripción corta |
| category_id | UUID FK → categories | Categoría |
| base_price | NUMERIC(12,2) | Precio base |
| currency | VARCHAR(8) | Moneda (USD, EUR, CRC) |
| product_type | TEXT | hotel, restaurant, tour, service, custom |
| status | TEXT | draft, active, archived |
| images | JSONB | Array de URLs de imágenes |
| metadata | JSONB | Campo flexible (amenities, schedule, etc.) |
| source_connector_id | UUID FK → connectors | NULL si es nativo |
| external_id | TEXT | ID en plataforma externa |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### Tabla: categories
| Campo | Tipo |
|-------|------|
| id | UUID PK |
| name | TEXT NOT NULL |
| slug | TEXT UNIQUE |
| parent_id | UUID FK → categories (self-ref) |
| icon | TEXT |
| sort_order | INTEGER |

### Tabla: availability
| Campo | Tipo |
|-------|------|
| id | UUID PK |
| product_id | UUID FK → products |
| date | DATE NOT NULL |
| slots_total | INTEGER |
| slots_available | INTEGER |
| price_override | NUMERIC(12,2) NULL |
| metadata | JSONB |

### Tabla: connectors
| Campo | Tipo |
|-------|------|
| id | UUID PK |
| name | TEXT NOT NULL |
| platform | TEXT NOT NULL (prestashop, shopify, woocommerce, native) |
| config | JSONB (url, api_key encrypted, etc.) |
| status | TEXT (active, error, disabled) |
| last_sync_at | TIMESTAMPTZ |
| sync_interval_minutes | INTEGER |
| created_at | TIMESTAMPTZ |

### Tabla: orders
| Campo | Tipo |
|-------|------|
| id | UUID PK |
| product_id | UUID FK → products |
| customer_name | TEXT |
| customer_email | TEXT |
| customer_phone | TEXT |
| date_from | DATE |
| date_to | DATE |
| quantity | INTEGER |
| total_amount | NUMERIC(12,2) |
| currency | VARCHAR(8) |
| status | TEXT (pending, confirmed, cancelled, completed) |
| payment_status | TEXT (unpaid, paid, refunded) |
| connector_id | UUID FK → connectors NULL |
| external_order_id | TEXT NULL |
| metadata | JSONB |
| created_at | TIMESTAMPTZ |

### Tabla: admin_users
| Campo | Tipo |
|-------|------|
| id | UUID PK |
| username | TEXT UNIQUE |
| password_hash | TEXT |
| totp_secret | TEXT NULL |
| is_active | BOOLEAN |
| created_at | TIMESTAMPTZ |

## API Endpoints

### Products
- `GET /api/v1/products` — Listar (filtros: category, type, status, search)
- `GET /api/v1/products/{id}` — Detalle
- `POST /api/v1/products` — Crear (nativo)
- `PUT /api/v1/products/{id}` — Actualizar
- `DELETE /api/v1/products/{id}` — Archivar
- `POST /api/v1/products/{id}/availability` — Setear disponibilidad
- `GET /api/v1/products/{id}/availability?from=&to=` — Consultar disponibilidad

### Categories
- `GET /api/v1/categories`
- `POST /api/v1/categories`
- `PUT /api/v1/categories/{id}`
- `DELETE /api/v1/categories/{id}`

### Connectors
- `GET /api/v1/connectors` — Listar
- `POST /api/v1/connectors` — Crear (alta de tienda)
- `POST /api/v1/connectors/{id}/sync` — Trigger sync manual
- `GET /api/v1/connectors/{id}/status` — Estado del conector
- `DELETE /api/v1/connectors/{id}` — Desactivar

### Orders
- `POST /api/v1/orders` — Crear reserva/pedido
- `GET /api/v1/orders` — Listar
- `GET /api/v1/orders/{id}` — Detalle
- `PATCH /api/v1/orders/{id}` — Update status

### Dashboard
- `GET /api/v1/dashboard/stats` — KPIs (ventas, productos activos, reservas hoy)
- `GET /api/v1/dashboard/charts` — Datos para gráficos

### Media
- `POST /api/v1/media/upload` — Subir imagen
- `GET /api/v1/media/{filename}` — Servir imagen

## Dashboard UI (Panel Admin)

Página principal: `dashboard/index.html`
- **Sidebar**: Productos, Categorías, Conectores, Órdenes, Config
- **Vista Productos**: Tabla con búsqueda, filtros, acciones CRUD
- **Vista Conectores**: Cards con estado, botón sync, último sync
- **Vista Órdenes**: Timeline de pedidos con filtros por estado
- **Vista Dashboard**: KPIs cards + charts (ventas diarias, productos por tipo)

Estilo: dark theme glassmorphism (consistente con el frontend actual de multi-presta)

## Conectores — Interfaz Base

```python
class BaseConnector(ABC):
    @abstractmethod
    async def healthcheck(self) -> dict: ...
    
    @abstractmethod
    async def fetch_products(self) -> list[ProductData]: ...
    
    @abstractmethod
    async def create_order(self, order_data: OrderData) -> dict: ...
    
    @abstractmethod
    async def sync_catalog(self) -> SyncResult: ...
```

Cada conector traduce entre el modelo unificado y la API de la plataforma.

## Frontend Público

Estilo Booking/Despegar con buscador:
- **Home**: Hero + buscador (destino, fechas, personas) + categorías + featured
- **Results**: Grid de cards con filtros (precio, tipo, categoría)
- **Product Detail**: Galería, descripción, disponibilidad, precio, botón reservar
- **Checkout**: Formulario de reserva + confirmación

## Fase 1 — MVP (Este sprint)

1. ✅ Core models + schema SQL
2. ✅ API CRUD productos nativos
3. ✅ Dashboard admin (productos + categorías)
4. ✅ Frontend público (home + results + product detail)
5. ✅ Worker para sync background
6. ✅ Docker compose (PG + Redis + API + Worker)
7. ⏳ Conector Prestashop (reusar del actual)
8. ⏳ Conector nativo (CRUD directo)

## Stack Técnico

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2
- **DB**: PostgreSQL 16
- **Cache**: Redis 7
- **Worker**: Celery + Redis broker
- **Frontend**: HTML5 + Tailwind CSS + vanilla JS (sin framework)
- **Auth**: API keys + HMAC + optional2FA
- **Deploy**: Docker Compose (dev) → Docker Swarm/K8s (prod)
