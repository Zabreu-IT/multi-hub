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
    async def create_order(self, order_data: OrderData):
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.post(self._url() + "/orders", auth=self._auth(), json={
                "payment_method": "bacs",
                "billing": {"first_name": order_data.customer_name.split(" ")[0], "last_name": " ".join(order_data.customer_name.split(" ")[1:]) or "-", "email": order_data.customer_email, "phone": order_data.customer_phone},
                "line_items": [{"product_id": int(order_data.product_id), "quantity": order_data.quantity}],
                "currency": order_data.currency,
            })
            if not r.is_success:
                return {"ok": False, "status": r.status_code, "error": r.text[:200]}
            d = r.json()
            return {"ok": True, "external_order_id": str(d.get("id")), "status": d.get("status")}
    async def sync_catalog(self): return SyncResult(errors=["Use worker sync; catalog mapping is platform-specific"])
