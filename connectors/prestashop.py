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
        def _name(p):
            n = p.get("name")
            if isinstance(n, list) and n:
                return n[0].get("value", "Product")
            return n or "Product"
        return [ProductData(name=_name(p), slug=str(p["id"]), price=float(p.get("price", 0)), external_id=str(p["id"])) for p in r.json().get("products", [])]
    async def create_order(self, order_data: OrderData):
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
  <order>
    <id_customer>1</id_customer>
    <id_address_delivery>1</id_address_delivery>
    <id_address_invoice>1</id_address_invoice>
    <payment>bankwire</payment>
    <module>bankwire</module>
    <associations>
      <order_rows>
        <order_row>
          <product_id>{int(order_data.product_id)}</product_id>
          <product_quantity>{order_data.quantity}</product_quantity>
        </order_row>
      </order_rows>
    </associations>
  </order>
</prestashop>"""
        async with self._client() as c:
            r = await c.post("/api/orders", content=xml.encode(), headers={"Content-Type": "application/xml"})
            if not r.is_success:
                return {"ok": False, "status": r.status_code, "error": r.text[:200]}
            d = r.json().get("order", {})
            return {"ok": True, "external_order_id": str(d.get("id")), "status": d.get("current_state")}
    async def sync_catalog(self): return SyncResult(errors=["Use worker sync; catalog mapping is platform-specific"])
