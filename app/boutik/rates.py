"""BTC/EUR reference rate with caching and an offline fallback.

The app must keep selling when the price API is down or the shop is offline,
so every failure degrades to the last good value, then to a fixed fallback.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from .money import SATS_PER_BTC, xof_per_btc

log = logging.getLogger("boutik.rates")

SOURCES = (
    ("mempool.space", "https://mempool.space/api/v1/prices", lambda d: d["EUR"]),
    (
        "coingecko",
        "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=eur",
        lambda d: d["bitcoin"]["eur"],
    ),
)
TTL_S = 600


@dataclass(frozen=True)
class Rate:
    eur_per_btc: float
    source: str
    fetched_at: int

    def as_dict(self) -> dict:
        xpb = xof_per_btc(self.eur_per_btc)
        return {
            "eur_per_btc": round(self.eur_per_btc, 2),
            "xof_per_btc": round(xpb),
            "sats_per_1000_xof": round(1000 * SATS_PER_BTC / xpb),
            "source": self.source,
            "fetched_at": self.fetched_at,
        }


class RateService:
    def __init__(self, mode: str, fallback_eur_per_btc: float):
        self.mode = mode
        self._fallback = Rate(fallback_eur_per_btc, "fallback", int(time.time()))
        self._cached: Rate | None = None

    async def get(self) -> Rate:
        if self.mode == "fixed":
            return self._fallback
        now = time.time()
        if self._cached and now - self._cached.fetched_at < TTL_S:
            return self._cached
        async with httpx.AsyncClient(timeout=4) as client:
            for name, url, pick in SOURCES:
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    value = float(pick(r.json()))
                    if 1_000 < value < 10_000_000:  # sanity bounds
                        self._cached = Rate(value, name, int(now))
                        return self._cached
                except (httpx.HTTPError, KeyError, ValueError, TypeError):
                    log.warning("rate source %s unavailable", name)
        return self._cached or self._fallback
