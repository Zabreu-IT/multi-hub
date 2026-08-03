from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ProductData:
    name: str
    slug: str
    price: float = 0
    external_id: str | None = None
    description: str | None = None


@dataclass
class OrderData:
    product_id: str
    quantity: int
    total_amount: float
    customer_email: str


@dataclass
class SyncResult:
    created: int = 0
    updated: int = 0
    errors: list[str] | None = None


class BaseConnector(ABC):
    def __init__(self, config: dict[str, Any]): self.config = config

    @abstractmethod
    async def healthcheck(self) -> dict: ...
    @abstractmethod
    async def fetch_products(self) -> list[ProductData]: ...
    @abstractmethod
    async def create_order(self, order_data: OrderData) -> dict: ...
    @abstractmethod
    async def sync_catalog(self) -> SyncResult: ...
