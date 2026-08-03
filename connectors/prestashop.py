import httpx
from .base import BaseConnector, OrderData, ProductData, SyncResult


class PrestashopConnector(BaseConnector):
    def _client(self): return httpx.AsyncClient(base_url=self.config["url"].rstrip("/"), auth=(self.config["api_key"], ""), timeout=20)
    async def healthcheck(self):
        async with self._client() as c:
            r = await c.get("/api/products", params={"output_format": "JSON", "limit": 1}); return {"ok": r.is_success, "status": r.status_code}
    async def fetch_products(self):
        async with self._client() as c:
            r = await c.get("/api/products", params={"output_format": "JSON", "display": "full"}); r.raise_for_status()
        return [ProductData(name=p.get("name", "Product"), slug=str(p["id"]), price=float(p.get("price", 0)), external_id=str(p["id"])) for p in r.json().get("products", [])]
    async def create_order(self, order_data: OrderData): raise NotImplementedError("PrestaShop order creation needs address/customer mapping")
    async def sync_catalog(self): return SyncResult(errors=["Use worker sync; catalog mapping is platform-specific"])
