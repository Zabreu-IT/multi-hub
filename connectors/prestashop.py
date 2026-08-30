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
        # Flujo real PrestaShop: crear carrito -> crear pedido con id_cart
        async with self._client() as c:
            # 1. Crear carrito con el producto
            cart_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
  <cart>
    <id_currency>1</id_currency>
    <id_lang>1</id_lang>
    <id_customer>1</id_customer>
    <associations>
      <cart_rows>
        <cart_row>
          <id_product>{int(order_data.product_id)}</id_product>
          <id_product_attribute>0</id_product_attribute>
          <quantity>{order_data.quantity}</quantity>
        </cart_row>
      </cart_rows>
    </associations>
  </cart>
</prestashop>"""
            r = await c.post(
                "/api/carts",
                content=cart_xml.encode(),
                headers={"Content-Type": "application/xml"},
            )
            if r.status_code >= 400:
                raise RuntimeError(f"PrestaShop create_cart failed: {r.status_code} {r.text[:200]}")
            cart_id = r.json().get("cart", {}).get("id", "")
            if not cart_id:
                raise RuntimeError(f"PrestaShop no cart id: {r.text[:200]}")

            # 2. Crear pedido con id_cart
            order_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
  <order>
    <id_customer>1</id_customer>
    <id_address_delivery>1</id_address_delivery>
    <id_address_invoice>1</id_address_invoice>
    <payment>bankwire</payment>
    <module>bankwire</module>
    <id_cart>{cart_id}</id_cart>
  </order>
</prestashop>"""
            r2 = await c.post(
                "/api/orders",
                content=order_xml.encode(),
                headers={"Content-Type": "application/xml"},
            )
            if r2.status_code >= 400:
                raise RuntimeError(f"PrestaShop create_order failed: {r2.status_code} {r2.text[:200]}")
            return {"external_id": str(r2.json().get("order", {}).get("id", ""))}

    async def sync_catalog(self): return SyncResult(errors=["Use worker sync; catalog mapping is platform-specific"])
