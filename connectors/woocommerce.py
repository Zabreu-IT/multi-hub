import httpx
from .base import BaseConnector, OrderData, ProductData, SyncResult


class WooCommerceConnector(BaseConnector):
    def _auth(self): return (self.config["consumer_key"], self.config["consumer_secret"])
    def _url(self): return self.config["url"].rstrip("/") + "/wp-json/wc/v3"
    async def healthcheck(self):
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.get(self._url() + "/products", auth=self._auth(), params={"per_page": 1}); return {"ok": r.is_success, "status": r.status_code}
    async def fetch_products(self):
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.get(self._url() + "/products", auth=self._auth(), params={"per_page": 100}); r.raise_for_status()
        return [ProductData(p["name"], p["slug"], float(p.get("price") or 0), str(p["id"]), p.get("description")) for p in r.json()]
    async def create_order(self, order_data: OrderData): raise NotImplementedError("WooCommerce orders require line-item mapping")
    async def sync_catalog(self): return SyncResult(errors=["Use worker sync; catalog mapping is platform-specific"])
