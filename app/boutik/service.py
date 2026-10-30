"""Payment logic shared by the merchant API and the public pay page."""

from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any

from .assistant import Assistant
from .config import Settings
from .db import DB, now
from .lnd import InvoiceBackend, LndError, WalletBackend
from .money import format_xof, sats_to_xof, xof_to_sats
from .rates import RateService
from .security import Auth, RateLimiter

log = logging.getLogger("boutik.service")

# Re-issue an invoice when less than this many seconds remain, so a customer
# never scans a QR that expires while their wallet is opening.
REISSUE_MARGIN_S = 60


class PaymentError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass
class Ctx:
    settings: Settings
    db: DB
    auth: Auth
    limiter: RateLimiter
    rates: RateService
    assistant: Assistant
    pos: InvoiceBackend | None = None
    wallet: WalletBackend | None = None
    customer: Any | None = None  # demo-only LndRest for the simulated customer


def day_bounds(ts: int | None = None) -> tuple[int, int]:
    """Dakar runs on UTC all year (no DST), so a UTC day is a shop day."""
    t = ts or now()
    start = t - t % 86400
    return start, start + 86400


def create_payment(
    ctx: Ctx, kind: str, amount_xof: int, items: list[dict] | None = None, customer: str = "", note: str = ""
) -> dict:
    s = ctx.settings
    if not (s.min_invoice_xof <= amount_xof <= s.max_invoice_xof):
        raise PaymentError("amount_out_of_range")
    token = secrets.token_urlsafe(16)
    ctx.db.exec(
        "INSERT INTO payments(token, kind, amount_xof, items, customer, note, created_at) VALUES(?,?,?,?,?,?,?)",
        (token, kind, amount_xof, json.dumps(items or [], ensure_ascii=False), customer, note, now()),
    )
    return get_payment(ctx, token)


def get_payment(ctx: Ctx, token: str):
    row = ctx.db.one("SELECT * FROM payments WHERE token=?", (token,))
    if not row:
        raise PaymentError("not_found", 404)
    return row


async def refresh(ctx: Ctx, row) -> Any:
    """Ask LND whether the current invoice settled. Cheap; called on poll and by the reconciler."""
    if row["status"] != "open" or not row["r_hash"] or ctx.pos is None:
        return row
    # The previous invoice may still be paid in the minute after it was replaced.
    for r_hash in filter(None, (row["r_hash"], row["prev_r_hash"])):
        try:
            st = await ctx.pos.lookup_invoice(r_hash)
        except LndError:
            continue
        if st.state == "SETTLED":
            break
    else:
        return row
    if st.state == "SETTLED":
        ctx.db.exec(
            "UPDATE payments SET status='paid', method='lightning', paid_at=?, amount_sats=? "
            "WHERE id=? AND status='open'",
            (st.settle_date or now(), st.amt_paid_sat or row["amount_sats"], row["id"]),
        )
        log.info("payment settled kind=%s id=%s", row["kind"], row["id"])
        return get_payment(ctx, row["token"])
    return row


async def ensure_invoice(ctx: Ctx, token: str):
    """Return the payment with a payable invoice, issuing a fresh one at today's
    rate when there is none or it is about to expire. Debts stay in FCFA."""
    row = await refresh(ctx, get_payment(ctx, token))
    if row["status"] != "open":
        return row
    if row["r_hash"] and (row["invoice_expires_at"] or 0) - now() > REISSUE_MARGIN_S:
        return row
    if ctx.pos is None:
        raise PaymentError("lightning_unavailable", 503)
    rate = await ctx.rates.get()
    sats = xof_to_sats(row["amount_xof"], rate.eur_per_btc)
    expiry = ctx.settings.sale_invoice_expiry_s
    memo = f"{ctx.settings.shop_name} #{row['id']}"[:60]  # never the customer's name
    try:
        inv = await ctx.pos.add_invoice(sats, memo, expiry)
    except LndError as e:
        log.warning("add_invoice failed: %s", e)
        raise PaymentError("lightning_unavailable", 503) from e
    ctx.db.exec(
        "UPDATE payments SET prev_r_hash=r_hash, r_hash=?, bolt11=?, amount_sats=?, invoice_expires_at=? WHERE id=?",
        (inv.r_hash, inv.payment_request, sats, now() + expiry, row["id"]),
    )
    return get_payment(ctx, token)


def mark_cash(ctx: Ctx, token: str):
    row = get_payment(ctx, token)
    if row["status"] != "open":
        raise PaymentError("not_open", 409)
    ctx.db.exec(
        "UPDATE payments SET status='paid', method='cash', paid_at=?, bolt11=NULL WHERE id=?",
        (now(), row["id"]),
    )
    return get_payment(ctx, token)


def cancel(ctx: Ctx, token: str):
    row = get_payment(ctx, token)
    if row["status"] != "open":
        raise PaymentError("not_open", 409)
    ctx.db.exec("UPDATE payments SET status='cancelled', bolt11=NULL WHERE id=?", (row["id"],))
    return get_payment(ctx, token)


def summary(ctx: Ctx, ts: int | None = None) -> dict:
    start, end = day_bounds(ts)
    rows = ctx.db.q(
        "SELECT * FROM payments WHERE status='paid' AND paid_at>=? AND paid_at<?", (start, end)
    )
    ln = sum(r["amount_xof"] for r in rows if r["method"] == "lightning")
    cash = sum(r["amount_xof"] for r in rows if r["method"] == "cash")
    sats = sum(r["amount_sats"] or 0 for r in rows if r["method"] == "lightning")
    counts: dict[str, int] = {}
    for r in rows:
        for it in json.loads(r["items"]):
            counts[it["name"]] = counts.get(it["name"], 0) + int(it.get("qty", 1))
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
    open_credit = ctx.db.one(
        "SELECT COUNT(*) n, COALESCE(SUM(amount_xof),0) total FROM payments WHERE kind='credit' AND status='open'"
    )
    return {
        "day_start": start,
        "sales_count": sum(1 for r in rows if r["kind"] == "sale"),
        "credits_repaid": sum(1 for r in rows if r["kind"] == "credit"),
        "total_xof": ln + cash,
        "lightning_xof": ln,
        "cash_xof": cash,
        "lightning_sats": sats,
        "top_items": [{"name": n, "qty": q} for n, q in top],
        "open_credits": open_credit["n"],
        "open_credits_xof": open_credit["total"],
    }


def summary_text(s: dict) -> str:
    repaid = f" + {s['credits_repaid']} ardoise(s) réglée(s)" if s["credits_repaid"] else ""
    parts = [
        f"Aujourd'hui : {s['sales_count']} vente(s){repaid}, {format_xof(s['total_xof'])} encaissés "
        f"(Lightning {format_xof(s['lightning_xof'])} · espèces {format_xof(s['cash_xof'])})."
    ]
    if s["top_items"]:
        parts.append("Top : " + ", ".join(f"{t['name']} ×{t['qty']}" for t in s["top_items"]) + ".")
    if s["open_credits"]:
        parts.append(f"Ardoises ouvertes : {s['open_credits']} pour {format_xof(s['open_credits_xof'])}.")
    else:
        parts.append("Aucune ardoise ouverte.")
    return " ".join(parts)


def sent_today_xof(ctx: Ctx) -> int:
    start, _ = day_bounds()
    row = ctx.db.one(
        "SELECT COALESCE(SUM(amount_xof),0) t FROM sends WHERE status='SUCCEEDED' AND created_at>=?",
        (start,),
    )
    return int(row["t"])


async def pay_invoice(ctx: Ctx, bolt11: str) -> dict:
    """Outgoing payment. Caller has already re-checked the PIN."""
    if ctx.wallet is None:
        raise PaymentError("lightning_unavailable", 503)
    bolt11 = bolt11.strip().lower().removeprefix("lightning:")
    if not bolt11.startswith(ctx.settings.invoice_prefix) or len(bolt11) > 2000:
        raise PaymentError("wrong_network")
    try:
        dec = await ctx.wallet.decode_payreq(bolt11)
    except LndError as e:
        raise PaymentError("invalid_invoice") from e
    if dec.num_satoshis <= 0:
        raise PaymentError("amount_required")
    if dec.timestamp + dec.expiry < time.time():
        raise PaymentError("invoice_expired")
    rate = await ctx.rates.get()
    amount_xof = sats_to_xof(dec.num_satoshis, rate.eur_per_btc)
    if sent_today_xof(ctx) + amount_xof > ctx.settings.daily_send_limit_xof:
        raise PaymentError("daily_limit")
    fee_limit = max(10, dec.num_satoshis // 100)
    try:
        res = await ctx.wallet.pay(bolt11, fee_limit_sat=fee_limit)
    except LndError as e:
        log.warning("payment failed: %s", e)
        raise PaymentError("payment_failed", 502) from e
    ctx.db.exec(
        "INSERT INTO sends(amount_sats, amount_xof, fee_sat, status, created_at) VALUES(?,?,?,?,?)",
        (dec.num_satoshis, amount_xof, res.fee_sat, res.status, now()),
    )
    if res.status != "SUCCEEDED":
        raise PaymentError("payment_failed", 502)
    return {"status": res.status, "amount_sats": dec.num_satoshis, "amount_xof": amount_xof, "fee_sat": res.fee_sat}


async def reconcile_once(ctx: Ctx) -> None:
    rows = ctx.db.q(
        "SELECT * FROM payments WHERE status='open' AND r_hash IS NOT NULL AND invoice_expires_at>?",
        (now() - 3600,),
    )
    for row in rows:
        await refresh(ctx, row)
