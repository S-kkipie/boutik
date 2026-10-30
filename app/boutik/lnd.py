"""Minimal async client for the LND REST API.

Each instance is bound to one macaroon, so a client built from the POS
macaroon cannot move funds even if the code calling it is buggy.
"""

from __future__ import annotations

import base64
import json
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx


class LndError(RuntimeError):
    """LND answered with an error or could not be reached."""


@dataclass(frozen=True)
class Invoice:
    r_hash: str  # hex
    payment_request: str


@dataclass(frozen=True)
class InvoiceState:
    state: str  # OPEN | SETTLED | CANCELED | ACCEPTED
    amt_paid_sat: int
    settle_date: int


@dataclass(frozen=True)
class DecodedInvoice:
    destination: str
    payment_hash: str
    num_satoshis: int
    timestamp: int
    expiry: int
    description: str


@dataclass(frozen=True)
class PaymentResult:
    status: str  # SUCCEEDED | FAILED
    payment_hash: str
    fee_sat: int
    failure_reason: str


class InvoiceBackend(Protocol):
    async def add_invoice(self, sats: int, memo: str, expiry_s: int) -> Invoice: ...
    async def lookup_invoice(self, r_hash_hex: str) -> InvoiceState: ...


class WalletBackend(Protocol):
    async def decode_payreq(self, bolt11: str) -> DecodedInvoice: ...
    async def pay(self, bolt11: str, fee_limit_sat: int, timeout_s: int = 30) -> PaymentResult: ...
    async def balances(self) -> dict[str, int]: ...
    async def new_address(self) -> str: ...


def _int(v: Any) -> int:
    return int(v or 0)


class LndRest:
    def __init__(self, base_url: str, macaroon_hex: str, tls_cert: Path | str, timeout: float = 15.0):
        ctx = ssl.create_default_context(cafile=str(tls_cert))
        self._http = httpx.AsyncClient(
            base_url=base_url,
            verify=ctx,
            headers={"Grpc-Metadata-macaroon": macaroon_hex},
            timeout=timeout,
        )

    @classmethod
    def from_files(cls, base_url: str, macaroon: Path, tls_cert: Path) -> "LndRest":
        return cls(base_url, macaroon.read_text().strip(), tls_cert)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _req(self, method: str, path: str, **kw: Any) -> dict[str, Any]:
        try:
            r = await self._http.request(method, path, **kw)
        except httpx.HTTPError as e:
            raise LndError(f"lnd unreachable: {type(e).__name__}") from e
        if r.status_code >= 400:
            try:
                msg = r.json().get("message", "")
            except ValueError:
                msg = ""
            raise LndError(msg or f"lnd http {r.status_code}")
        return r.json()

    async def get_info(self) -> dict[str, Any]:
        return await self._req("GET", "/v1/getinfo")

    async def add_invoice(self, sats: int, memo: str, expiry_s: int) -> Invoice:
        d = await self._req(
            "POST", "/v1/invoices", json={"value": str(sats), "memo": memo, "expiry": str(expiry_s)}
        )
        return Invoice(
            r_hash=base64.b64decode(d["r_hash"]).hex(),
            payment_request=d["payment_request"],
        )

    async def lookup_invoice(self, r_hash_hex: str) -> InvoiceState:
        d = await self._req("GET", f"/v1/invoice/{r_hash_hex}")
        return InvoiceState(
            state=d.get("state", "OPEN"),
            amt_paid_sat=_int(d.get("amt_paid_sat")),
            settle_date=_int(d.get("settle_date")),
        )

    async def decode_payreq(self, bolt11: str) -> DecodedInvoice:
        d = await self._req("GET", f"/v1/payreq/{bolt11}")
        return DecodedInvoice(
            destination=d.get("destination", ""),
            payment_hash=d.get("payment_hash", ""),
            num_satoshis=_int(d.get("num_satoshis")),
            timestamp=_int(d.get("timestamp")),
            expiry=_int(d.get("expiry")) or 3600,
            description=d.get("description", ""),
        )

    async def pay(self, bolt11: str, fee_limit_sat: int, timeout_s: int = 30) -> PaymentResult:
        """Router SendPaymentV2. The REST gateway streams JSON objects; keep the last final one."""
        body = {
            "payment_request": bolt11,
            "timeout_seconds": timeout_s,
            "fee_limit_sat": str(fee_limit_sat),
            "no_inflight_updates": True,
        }
        last: dict[str, Any] = {}
        try:
            async with self._http.stream(
                "POST", "/v2/router/send", json=body, timeout=timeout_s + 10
            ) as r:
                if r.status_code >= 400:
                    body = await r.aread()
                    try:
                        msg = json.loads(body).get("error", {}).get("message", "")
                    except ValueError:
                        msg = ""
                    raise LndError(msg or f"lnd http {r.status_code}")
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    if "error" in msg:
                        raise LndError(msg["error"].get("message", "payment error"))
                    res = msg.get("result", msg)
                    last = res
                    if res.get("status") in ("SUCCEEDED", "FAILED"):
                        break
        except httpx.HTTPError as e:
            raise LndError(f"lnd unreachable: {type(e).__name__}") from e
        return PaymentResult(
            status=last.get("status", "FAILED"),
            payment_hash=last.get("payment_hash", ""),
            fee_sat=_int(last.get("fee_sat")),
            failure_reason=last.get("failure_reason", "") if last.get("status") != "SUCCEEDED" else "",
        )

    async def balances(self) -> dict[str, int]:
        ch = await self._req("GET", "/v1/balance/channels")
        oc = await self._req("GET", "/v1/balance/blockchain")
        return {
            "lightning_sats": _int((ch.get("local_balance") or {}).get("sat")),
            "inbound_sats": _int((ch.get("remote_balance") or {}).get("sat")),
            "onchain_sats": _int(oc.get("confirmed_balance")),
            "onchain_unconfirmed_sats": _int(oc.get("unconfirmed_balance")),
        }

    async def new_address(self) -> str:
        # TAPROOT_PUBKEY = 4
        d = await self._req("GET", "/v1/newaddress", params={"type": 4})
        return d["address"]
