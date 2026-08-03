from .base import BaseConnector, OrderData, ProductData, SyncResult


class NativeConnector(BaseConnector):
    async def healthcheck(self): return {"ok": True, "platform": "native"}
    async def fetch_products(self): return []
    async def create_order(self, order_data: OrderData): return {"external_order_id": None}
    async def sync_catalog(self): return SyncResult()
