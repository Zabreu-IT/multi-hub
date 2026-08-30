import httpx
from .base import BaseConnector, OrderData, ProductData, SyncResult


class ShopifyConnector(BaseConnector):
    def _headers(self): return {"X-Shopify-Access-Token": self.config["access_token"]}
    def _url(self): return self.config["url"].rstrip("/") + "/admin/api/2024-10"
    async def healthcheck(self):
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(self._url() + "/shop.json", headers=self._headers()); return {"ok": r.is_success, "status": r.status_code}
    async def fetch_products(self):
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(self._url() + "/products.json", headers=self._headers()); r.raise_for_status()
        return [ProductData(p["title"], p["handle"], float((p.get("variants") or [{"price": 0}])[0]["price"]), str(p["id"]), p.get("body_html")) for p in r.json().get("products", [])]
    async def create_order(self, order_data: OrderData):
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(self._url() + "/orders.json", headers=self._headers(), json={
                "order": {
                    "email": order_data.customer_email,
                    "line_items": [{"variant_id": int(order_data.product_id), "quantity": order_data.quantity}],
                    "currency": order_data.currency,
                }
            })
            if not r.is_success:
                return {"ok": False, "status": r.status_code, "error": r.text[:200]}
            d = r.json().get("order", {})
            return {"ok": True, "external_order_id": str(d.get("id")), "status": d.get("financial_status")}
    async def sync_catalog(self): return SyncResult(errors=["Use worker sync; catalog mapping is platform-specific"])
