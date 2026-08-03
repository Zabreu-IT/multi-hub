# Multi-Hub

Hub de productos, reservas y experiencias con catálogo nativo o sincronizado desde PrestaShop, Shopify y WooCommerce.

## Inicio

```bash
cp .env.example .env
make up
make seed
```

Abre `http://localhost:8080`; el panel está en `/dashboard/` y la API en `/docs`.

## Seguridad

En producción define `API_KEY` para mutaciones administrativas. Si defines también `HMAC_SECRET`, cada petición protegida debe incluir `X-Hub-Signature`: HMAC-SHA256 del cuerpo crudo. La creación pública de reservas permanece abierta por diseño.

## Conectores

Alta un conector mediante `POST /api/v1/connectors`; `config` usa `url` + `api_key` (PrestaShop), `url` + `access_token` (Shopify), o `url` + `consumer_key`/`consumer_secret` (WooCommerce). Las plataformas requieren esas credenciales y el mapeo de pedidos depende de sus datos de cliente/dirección; el catálogo se sincroniza en Celery.
