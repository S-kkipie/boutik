"""HTTP API + static PWA."""

from __future__ import annotations

import asyncio
import contextlib
import re
import json
import logging
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field, field_validator

from . import service
from .assistant import Assistant, Product
from .config import Settings, get_settings
from .db import DB, payment_dict
from .lnd import LndError, LndRest
from .money import sats_to_xof
from .qr import bolt11_svg
from .rates import RateService
from .security import SECURITY_HEADERS, Auth, RateLimiter
from .service import Ctx, PaymentError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("boutik")
# httpx logs full URLs at INFO, which would put invoices and payment hashes in the logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

STATIC = Path(__file__).parent / "static"
COOKIE = "boutik_s"
TOKENISH = re.compile(r"/[A-Za-z0-9_-]{16,}")
CLEAN = r"^[^<>\"`{}\\]*$"  # labels are plain text; rejects markup characters outright


# ---------- request models (every amount is bounded) ----------


class PinIn(BaseModel):
    pin: str = Field(pattern=r"^\d{4,8}$")


class SetupIn(PinIn):
    shop_name: str = Field("", max_length=60, pattern=CLEAN)


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=40, pattern=CLEAN)
    qty: int = Field(ge=1, le=999)
    unit_xof: int = Field(ge=1, le=2_000_000)


class SaleIn(BaseModel):
    items: list[ItemIn] = Field(default_factory=list, max_length=30)
    amount_xof: int | None = Field(None, ge=1, le=2_000_000)


class CreditIn(BaseModel):
    customer: str = Field(min_length=1, max_length=30, pattern=CLEAN)
    amount_xof: int = Field(ge=1, le=2_000_000)
    note: str = Field("", max_length=60, pattern=CLEAN)


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=40, pattern=CLEAN)
    emoji: str = Field("", max_length=8, pattern=CLEAN)
    price_xof: int = Field(ge=1, le=2_000_000)


class AssistantIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class Bolt11In(BaseModel):
    bolt11: str = Field(min_length=10, max_length=2000)

    @field_validator("bolt11")
    @classmethod
    def _ascii(cls, v: str) -> str:
        v = v.strip()
        if not v.isascii() or any(c.isspace() for c in v):
            raise ValueError("invalid invoice")
        return v


class PayIn(Bolt11In):
    pin: str = Field(pattern=r"^\d{4,8}$")


class DemoInvoiceIn(BaseModel):
    amount_xof: int = Field(ge=25, le=50_000)


# ---------- app factory ----------


def _load_lnd(settings: Settings, quiet: bool = False) -> tuple[LndRest | None, LndRest | None, LndRest | None]:
    c = settings.creds_dir

    def mk(url: str, mac: str, cert: str) -> LndRest | None:
        if (c / mac).exists() and (c / cert).exists():
            return LndRest.from_files(url, c / mac, c / cert)
        if not quiet:
            log.warning("credentials %s not there yet: Lightning disabled until bootstrap finishes", mac)
        return None

    pos = mk(settings.lnd_merchant_url, "pos.macaroon", "merchant-tls.cert")
    wallet = mk(settings.lnd_merchant_url, "wallet.macaroon", "merchant-tls.cert")
    customer = None
    if settings.demo_mode and settings.network == "regtest":
        customer = mk(settings.lnd_customer_url, "customer.macaroon", "customer-tls.cert")
    return pos, wallet, customer


async def _connect_lnd(ctx: Ctx) -> None:
    """Pick up credentials as soon as bootstrap writes them (single-container deploys
    start the app before the nodes are funded)."""
    while ctx.pos is None or ctx.wallet is None:
        await asyncio.sleep(3)
        pos, wallet, customer = _load_lnd(ctx.settings, quiet=True)
        if pos and wallet:
            ctx.pos, ctx.wallet, ctx.customer = pos, wallet, customer
            log.info("Lightning credentials loaded")


def build_ctx(settings: Settings, **overrides) -> Ctx:
    db = overrides.pop("db", None) or DB(settings.db_path)
    if settings.demo_mode:
        db.seed_products()
    auth = Auth(db, settings.session_ttl_s)
    if settings.pin and not auth.has_pin():
        auth.set_pin(settings.pin)
    if not db.get_setting("shop_name"):
        db.set_setting("shop_name", settings.shop_name)
    ctx = Ctx(
        settings=settings,
        db=db,
        auth=auth,
        limiter=RateLimiter(),
        rates=overrides.pop("rates", None) or RateService(settings.rate_source, settings.fallback_eur_per_btc),
        assistant=overrides.pop("assistant", None)
        or Assistant(settings.anthropic_api_key, settings.assistant_model),
    )
    for k, v in overrides.items():
        setattr(ctx, k, v)
    return ctx


def create_app(ctx: Ctx | None = None) -> FastAPI:
    owns_lnd = ctx is None

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal ctx
        if ctx is None:
            settings = get_settings()
            pos, wallet, customer = _load_lnd(settings)
            ctx = build_ctx(settings, pos=pos, wallet=wallet, customer=customer)
        app.state.ctx = ctx
        tasks = [asyncio.create_task(_reconciler(ctx))]
        if owns_lnd:
            tasks.append(asyncio.create_task(_connect_lnd(ctx)))
        yield
        for task in tasks:
            task.cancel()
        if owns_lnd:
            for c in (ctx.pos, ctx.wallet, ctx.customer):
                if c is not None:
                    await c.aclose()

    app = FastAPI(title="Boutik", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    if ctx is not None:
        app.state.ctx = ctx
    app.add_middleware(GZipMiddleware, minimum_size=800)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        start = time.perf_counter()
        path = request.url.path
        # CSRF: state-changing API calls must carry a custom header, which a
        # cross-site form cannot set and cross-site fetch cannot send without CORS.
        if path.startswith("/api/") and request.method not in ("GET", "HEAD") and request.headers.get(
            "x-boutik"
        ) != "1":
            response: Response = JSONResponse({"error": "csrf"}, status_code=403)
        else:
            response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        if request.app.state.ctx.settings.cookie_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        # Access log without tokens or query strings: pay links are capabilities.
        route = request.scope.get("route")
        template = getattr(route, "path", None) or TOKENISH.sub("/*", path)
        log.info("%s %s %s %.0fms", request.method, template, response.status_code, (time.perf_counter() - start) * 1000)
        return response

    @app.exception_handler(PaymentError)
    async def _perr(_: Request, e: PaymentError):
        return JSONResponse({"error": e.code}, status_code=e.status)

    def C(request: Request) -> Ctx:
        return request.app.state.ctx

    def ip(request: Request) -> str:
        return request.client.host if request.client else "?"

    def limit(ctx: Ctx, key: str, n: int, window: int = 60) -> None:
        if not ctx.limiter.allow(key, n, window):
            raise PaymentError("too_many_requests", 429)

    def authed(request: Request) -> Ctx:
        ctx = C(request)
        if not ctx.auth.valid_session(request.cookies.get(COOKIE)):
            raise PaymentError("unauthorized", 401)
        return ctx

    def set_cookie(resp: Response, ctx: Ctx, token: str) -> None:
        resp.set_cookie(
            COOKIE, token, max_age=ctx.settings.session_ttl_s, httponly=True,
            secure=ctx.settings.cookie_secure, samesite="strict", path="/",
        )

    def catalog(ctx: Ctx) -> list[Product]:
        return [
            Product(id=r["id"], name=r["name"], emoji=r["emoji"], price_xof=r["price_xof"])
            for r in ctx.db.q("SELECT * FROM products WHERE active=1 ORDER BY id")
        ]

    def pay_url(ctx: Ctx, request: Request, token: str) -> str:
        base = ctx.settings.public_url or str(request.base_url)
        return f"{base.rstrip('/')}/p/{token}"

    # ---------- health / status / auth ----------

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    @app.get("/api/status")
    async def status(request: Request):
        ctx = C(request)
        return {
            "shop_name": ctx.db.get_setting("shop_name"),
            "has_pin": ctx.auth.has_pin(),
            "authenticated": ctx.auth.valid_session(request.cookies.get(COOKIE)),
            "demo_mode": ctx.settings.demo_mode,
            "demo_pin_hint": "1234" if ctx.settings.demo_mode and ctx.settings.pin == "1234" else None,
            "network": ctx.settings.network,
            "lightning": ctx.pos is not None,
            "assistant_engine": ctx.assistant.engine,
            "locked_for": ctx.auth.locked_for(),
        }

    @app.post("/api/setup")
    async def setup(body: SetupIn, request: Request, response: Response):
        ctx = C(request)
        limit(ctx, f"setup:{ip(request)}", 5)
        if ctx.auth.has_pin():
            raise PaymentError("already_setup", 409)
        ctx.auth.set_pin(body.pin)
        if body.shop_name.strip():
            ctx.db.set_setting("shop_name", body.shop_name.strip())
        set_cookie(response, ctx, ctx.auth.new_session())
        return {"ok": True}

    @app.post("/api/login")
    async def login(body: PinIn, request: Request, response: Response):
        ctx = C(request)
        limit(ctx, f"login:{ip(request)}", 10)
        if not ctx.auth.check_pin(body.pin):
            return JSONResponse({"error": "bad_pin", "locked_for": ctx.auth.locked_for()}, status_code=401)
        set_cookie(response, ctx, ctx.auth.new_session())
        return {"ok": True}

    @app.post("/api/logout")
    async def logout(request: Request, response: Response):
        C(request).auth.end_session(request.cookies.get(COOKIE))
        response.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    @app.get("/api/rate")
    async def rate(request: Request):
        return (await C(request).rates.get()).as_dict()

    # ---------- catalog ----------

    @app.get("/api/products")
    async def products(ctx: Ctx = Depends(authed)):
        return [p.model_dump() for p in catalog(ctx)]

    @app.post("/api/products")
    async def add_product(body: ProductIn, ctx: Ctx = Depends(authed)):
        if ctx.db.one("SELECT COUNT(*) n FROM products WHERE active=1")["n"] >= 60:
            raise PaymentError("too_many_products")
        pid = ctx.db.exec(
            "INSERT INTO products(name, emoji, price_xof) VALUES(?,?,?)", (body.name.strip(), body.emoji, body.price_xof)
        )
        return {"id": pid}

    @app.delete("/api/products/{pid}")
    async def del_product(pid: int, ctx: Ctx = Depends(authed)):
        ctx.db.exec("UPDATE products SET active=0 WHERE id=?", (pid,))
        return {"ok": True}

    # ---------- sales & ardoises ----------

    @app.post("/api/sales")
    async def new_sale(body: SaleIn, request: Request, ctx: Ctx = Depends(authed)):
        limit(ctx, "sales", 60)
        items = [i.model_dump() for i in body.items]
        total = sum(i["qty"] * i["unit_xof"] for i in items) if items else (body.amount_xof or 0)
        if not items and body.amount_xof:
            items = [{"name": "Montant libre", "qty": 1, "unit_xof": body.amount_xof}]
        row = service.create_payment(ctx, "sale", total, items)
        row = await service.ensure_invoice(ctx, row["token"])
        return payment_dict(row)

    @app.post("/api/credits")
    async def new_credit(body: CreditIn, request: Request, ctx: Ctx = Depends(authed)):
        limit(ctx, "credits", 60)
        row = service.create_payment(ctx, "credit", body.amount_xof, [], body.customer.strip(), body.note.strip())
        d = payment_dict(row)
        d["pay_url"] = pay_url(ctx, request, row["token"])
        return d

    @app.get("/api/payments")
    async def list_payments(request: Request, kind: str = "sale", status: str = "", ctx: Ctx = Depends(authed)):
        if kind not in ("sale", "credit") or status not in ("", "open", "paid", "cancelled"):
            raise PaymentError("bad_filter")
        if kind == "sale":
            rows = ctx.db.q(
                "SELECT * FROM payments WHERE kind='sale' AND status=? ORDER BY id DESC LIMIT 100",
                (status or "paid",),
            )
        elif status:
            rows = ctx.db.q(
                "SELECT * FROM payments WHERE kind='credit' AND status=? ORDER BY id DESC LIMIT 100", (status,)
            )
        else:
            rows = ctx.db.q(
                "SELECT * FROM payments WHERE kind='credit' AND status!='cancelled' "
                "ORDER BY status='open' DESC, id DESC LIMIT 100"
            )
        out = []
        for r in rows:
            d = payment_dict(r)
            if r["kind"] == "credit":
                d["pay_url"] = pay_url(ctx, request, r["token"])
            out.append(d)
        return out

    @app.get("/api/payments/{token}")
    async def get_payment(token: str, ctx: Ctx = Depends(authed)):
        row = await service.refresh(ctx, service.get_payment(ctx, token))
        return payment_dict(row)

    @app.post("/api/payments/{token}/invoice")
    async def reissue(token: str, ctx: Ctx = Depends(authed)):
        return payment_dict(await service.ensure_invoice(ctx, token))

    @app.post("/api/payments/{token}/cash")
    async def cash(token: str, ctx: Ctx = Depends(authed)):
        return payment_dict(service.mark_cash(ctx, token))

    @app.post("/api/payments/{token}/cancel")
    async def cancel(token: str, ctx: Ctx = Depends(authed)):
        return payment_dict(service.cancel(ctx, token))

    @app.get("/api/summary")
    async def summary(ctx: Ctx = Depends(authed)):
        s = service.summary(ctx)
        s["text"] = service.summary_text(s)
        return s

    # ---------- public pay link (customer side) ----------

    @app.get("/p/{token}")
    async def pay_page(token: str):
        return FileResponse(STATIC / "pay.html")

    def public_view(ctx: Ctx, row) -> dict:
        d = payment_dict(row, public=True)
        d["shop_name"] = ctx.db.get_setting("shop_name")
        d["customer"] = row["customer"][:1] + "…" if row["customer"] else ""  # initial only
        d["demo_mode"] = ctx.settings.demo_mode
        return d

    @app.get("/api/pay/{token}")
    async def pay_view(token: str, request: Request):
        ctx = C(request)
        limit(ctx, f"pay:{ip(request)}", 120)
        row = await service.refresh(ctx, service.get_payment(ctx, token))
        return public_view(ctx, row)

    @app.post("/api/pay/{token}/invoice")
    async def pay_invoice(token: str, request: Request):
        ctx = C(request)
        limit(ctx, f"payinv:{ip(request)}", 20)
        limit(ctx, f"payinv:{token}", 6)
        return public_view(ctx, await service.ensure_invoice(ctx, token))

    @app.get("/api/pay/{token}/qr.svg")
    async def pay_qr(token: str, request: Request):
        ctx = C(request)
        limit(ctx, f"qr:{ip(request)}", 120)
        row = service.get_payment(ctx, token)
        if row["status"] != "open" or not row["bolt11"]:
            raise PaymentError("no_invoice", 404)
        return Response(bolt11_svg(row["bolt11"]), media_type="image/svg+xml",
                        headers={"Cache-Control": "private, max-age=600"})

    # ---------- wallet ----------

    @app.get("/api/wallet")
    async def wallet(ctx: Ctx = Depends(authed)):
        if ctx.wallet is None:
            raise PaymentError("lightning_unavailable", 503)
        try:
            b = await ctx.wallet.balances()
        except LndError as e:
            raise PaymentError("lightning_unavailable", 503) from e
        r = await ctx.rates.get()
        return {
            **b,
            "lightning_xof": sats_to_xof(b["lightning_sats"], r.eur_per_btc),
            "onchain_xof": sats_to_xof(b["onchain_sats"], r.eur_per_btc),
            "sent_today_xof": service.sent_today_xof(ctx),
            "daily_limit_xof": ctx.settings.daily_send_limit_xof,
            "network": ctx.settings.network,
        }

    @app.post("/api/wallet/address")
    async def address(ctx: Ctx = Depends(authed)):
        if ctx.wallet is None:
            raise PaymentError("lightning_unavailable", 503)
        limit(ctx, "address", 10)
        return {"address": await ctx.wallet.new_address()}

    @app.post("/api/wallet/decode")
    async def decode(body: Bolt11In, ctx: Ctx = Depends(authed)):
        if ctx.wallet is None:
            raise PaymentError("lightning_unavailable", 503)
        b = body.bolt11.lower().removeprefix("lightning:")
        if not b.startswith(ctx.settings.invoice_prefix):
            raise PaymentError("wrong_network")
        try:
            d = await ctx.wallet.decode_payreq(b)
        except LndError as e:
            raise PaymentError("invalid_invoice") from e
        r = await ctx.rates.get()
        return {
            "amount_sats": d.num_satoshis,
            "amount_xof": sats_to_xof(d.num_satoshis, r.eur_per_btc),
            "description": d.description[:120],
            "expired": d.timestamp + d.expiry < time.time(),
        }

    @app.post("/api/wallet/pay")
    async def pay(body: PayIn, request: Request, ctx: Ctx = Depends(authed)):
        limit(ctx, "wallet-pay", 10)
        # Spending needs the PIN again, even with a valid session.
        if not ctx.auth.check_pin(body.pin):
            return JSONResponse({"error": "bad_pin", "locked_for": ctx.auth.locked_for()}, status_code=401)
        return await service.pay_invoice(ctx, body.bolt11)

    # ---------- assistant ----------

    @app.post("/api/assistant")
    async def assistant(body: AssistantIn, ctx: Ctx = Depends(authed)):
        limit(ctx, "assistant", 20)
        draft = await ctx.assistant.parse(body.text, catalog(ctx))
        out = draft.model_dump()
        out["total_xof"] = draft.total_xof
        if draft.intent == "summary":
            out["reply"] = service.summary_text(service.summary(ctx))
        return out

    # ---------- demo customer (regtest only) ----------

    def demo(ctx: Ctx):
        if not (ctx.settings.demo_mode and ctx.settings.network == "regtest" and ctx.customer):
            raise PaymentError("demo_disabled", 404)
        return ctx.customer

    @app.post("/api/demo/pay/{token}")
    async def demo_pay(token: str, request: Request):
        ctx = C(request)
        cust = demo(ctx)
        limit(ctx, f"demo:{ip(request)}", 20)
        row = service.get_payment(ctx, token)
        if row["status"] != "open" or not row["bolt11"]:
            raise PaymentError("not_open", 409)
        try:
            res = await cust.pay(row["bolt11"], fee_limit_sat=100)
        except LndError as e:
            raise PaymentError("payment_failed", 502) from e
        row = await service.refresh(ctx, service.get_payment(ctx, token))
        return {"status": res.status, "payment_status": row["status"]}

    @app.get("/api/demo/wallet")
    async def demo_wallet(request: Request):
        ctx = C(request)
        b = await demo(ctx).balances()
        r = await ctx.rates.get()
        return {**b, "lightning_xof": sats_to_xof(b["lightning_sats"], r.eur_per_btc)}

    @app.post("/api/demo/invoice")
    async def demo_invoice(body: DemoInvoiceIn, request: Request):
        ctx = C(request)
        cust = demo(ctx)
        limit(ctx, f"demoinv:{ip(request)}", 10)
        r = await ctx.rates.get()
        from .money import xof_to_sats

        inv = await cust.add_invoice(xof_to_sats(body.amount_xof, r.eur_per_btc), "Client démo", 900)
        return {"bolt11": inv.payment_request}

    # ---------- static PWA ----------

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/sw.js")
    async def sw():
        return FileResponse(STATIC / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @app.get("/manifest.webmanifest")
    async def manifest():
        return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


async def _reconciler(ctx: Ctx) -> None:
    """Marks ardoises paid even when nobody is watching the screen."""
    while True:
        try:
            await service.reconcile_once(ctx)
        except Exception as e:  # keep the loop alive; one bad poll must not stop settlement tracking
            log.warning("reconciler: %s", type(e).__name__)
        await asyncio.sleep(10)


app = create_app()
