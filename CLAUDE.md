# Multi-Hub — Rediseño Frontend

## Proyecto
Marketplace de experiencias (hoteles, tours, restaurantes, spa, eventos). Backend FastAPI + Postgres. Frontend estático servido por FastAPI StaticFiles desde /app/frontend.

## API (NO MODIFICAR)
- GET /api/v1/products?status=active&search={q} → array [{id,name,slug,description,description_short,category_id,base_price,currency,product_type,status,images[],metadata{venue,starts_at}}]
- GET /api/v1/products/{id} → producto individual
- GET /api/v1/categories → [{id,name,slug,icon,parent_id,sort_order}]
- POST /api/v1/orders → {customer_name,customer_email,date_from,quantity,product_id,total_amount,currency,metadata}
- 40 productos activos reales. product_type: event|tour|service|restaurant|hotel. Categorías: Hoteles, Restaurantes, Tours y Aventura, Spa y Bienestar, Eventos.

## Alcance del rediseño
SOLO frontend/: index.html, product.html, results.html, checkout.html, como-funciona.html, styles.css, hub_engine.js. NO tocar api/, core/, dashboard/, worker/, connectors/.

## Requisitos de diseño
- Estética empresarial premium y moderna: marketplace de experiencias de lujo accesible
- Dark theme sofisticado (no negro plano): gradientes profundos, glassmorphism sutil, acentos vibrantes (violeta/cian/dorado)
- Tipografía premium: Google Fonts (ej. "Sora" o "Space Grotesk" para display, "Inter" para body)
- Hero impactante con búsqueda, categorías con iconos, tarjetas de producto premium con hover effects, micro-interacciones y animaciones suaves (CSS + IntersectionObserver, sin librerías pesadas)
- Responsive total (mobile-first)
- SEO: meta tags, Open Graph, favicon
- CERO métricas falsas: no inventar números, stats, testimonios ni reviews. Usar copy descriptivo genérico.
- Mantener funcionalidad: búsqueda, detalle, reserva (checkout), página "cómo funciona"
- Mejorar hub_engine.js: card() con diseño premium, manejo de imágenes fallback con gradientes SVG, categorías con iconos
- Imágenes: usar las Unsplash URLs de los productos; fallback = gradiente + emoji/icono
- Añadir: navbar sticky con blur, footer completo con links, CTA WhatsApp (wa.me/50600000000 placeholder), sección categorías, sección "experiencias destacadas", sección "cómo funciona" resumida en home, newsletter (form no funcional, solo UI con mensaje "Próximamente")
- checkout.html: mejorar UX, validación, resumen de reserva con datos del producto, mensaje honesto (sin prometer email que no existe — usar "Solicitud recibida, te contactaremos")

## Estándares
- HTML semántico, CSS custom (no Tailwind CDN), JS vanilla sin dependencias
- Archivos autocontenidos, sin build step
- Código limpio, comentado en español

## Admin Auth (2026-08-30)
- Login: https://hub.zabreuit.com/dashboard/login.html
- Usuarios demo: demo_owner/demo-owner-2026 (owner), demo_admin/demo-admin-2026 (admin), demo_viewer/demo-viewer-2026 (viewer, solo lectura)
- ⚠️ CAMBIAR passwords demo antes de compartir: docker exec multi-hub-api-1 python scripts/seed_admin.py (usa env DEMO_*_PASS)
- Endpoints admin protegidos con JWT (require_admin en api/security.py). Mutaciones exigen owner/admin. Checkout público (POST /orders) y GET products/categories siguen abiertos.
