from typing import Literal

from pydantic import BaseModel, Field


class Product(BaseModel):
    id: int = 0
    name: str
    emoji: str = ""
    price_xof: int


class DraftItem(BaseModel):
    name: str = Field(max_length=40)
    qty: int = Field(ge=1, le=999)
    unit_xof: int = Field(ge=1, le=2_000_000)


class Draft(BaseModel):
    """What the assistant proposes. Never executed without the merchant tapping Confirm."""

    intent: Literal["cart", "credit", "summary", "explain", "unknown"]
    items: list[DraftItem] = Field(default_factory=list, max_length=30)
    customer: str = Field("", max_length=30)
    amount_xof: int = Field(0, ge=0, le=2_000_000)
    note: str = Field("", max_length=60)
    reply: str = Field("", max_length=600)
    engine: Literal["claude", "local"] = "local"

    @property
    def total_xof(self) -> int:
        return sum(i.qty * i.unit_xof for i in self.items)
