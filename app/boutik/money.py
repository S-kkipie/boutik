"""FCFA <-> sats conversion.

The West African CFA franc (XOF) is pegged to the euro at a fixed parity,
so BTC/XOF is derived from BTC/EUR without a second price feed.
"""

import math

XOF_PER_EUR = 655.957
SATS_PER_BTC = 100_000_000


def xof_per_btc(eur_per_btc: float) -> float:
    return eur_per_btc * XOF_PER_EUR


def xof_to_sats(amount_xof: int, eur_per_btc: float) -> int:
    """Round up so the merchant never receives less than the FCFA price."""
    if amount_xof <= 0:
        raise ValueError("amount must be positive")
    return max(1, math.ceil(amount_xof * SATS_PER_BTC / xof_per_btc(eur_per_btc)))


def sats_to_xof(sats: int, eur_per_btc: float) -> int:
    return round(sats * xof_per_btc(eur_per_btc) / SATS_PER_BTC)


def format_xof(amount: int) -> str:
    """French grouping with narrow no-break spaces: 12 500 FCFA."""
    return f"{amount:,}".replace(",", " ") + " FCFA"
