import hashlib
import time

import httpx
import pytest

from boutik.assistant import Assistant
from boutik.config import Settings
from boutik.db import DB
from boutik.lnd import DecodedInvoice, Invoice, InvoiceState, PaymentResult
from boutik.main import build_ctx, create_app
from boutik.rates import RateService

H = {"x-boutik": "1"}


class FakeLnd:
    """Stands in for both the POS (invoice) and wallet macaroon clients."""

    def __init__(self):
        self.invoices: dict[str, dict] = {}
        self.paid: list[str] = []

    async def add_invoice(self, sats, memo, expiry_s):
        r = hashlib.sha256(f"{len(self.invoices)}{memo}".encode()).hexdigest()
        bolt11 = f"lnbcrt{sats}n1fake{r[:20]}"
        self.invoices[r] = {"sats": sats, "memo": memo, "state": "OPEN", "bolt11": bolt11}
        return Invoice(r_hash=r, payment_request=bolt11)

    async def lookup_invoice(self, r_hash):
        i = self.invoices[r_hash]
        return InvoiceState(state=i["state"], amt_paid_sat=i["sats"] if i["state"] == "SETTLED" else 0,
                            settle_date=int(time.time()))

    def settle(self, bolt11):
        for i in self.invoices.values():
            if i["bolt11"] == bolt11:
                i["state"] = "SETTLED"

    async def decode_payreq(self, bolt11):
        sats = int(bolt11.removeprefix("lnbcrt").split("n")[0] or 0)
        return DecodedInvoice("02" * 33, "ab" * 32, sats, int(time.time()), 3600, "test")

    async def pay(self, bolt11, fee_limit_sat, timeout_s=30):
        self.paid.append(bolt11)
        return PaymentResult("SUCCEEDED", "ab" * 32, 1, "")

    async def balances(self):
        return {"lightning_sats": 300_000, "inbound_sats": 9_000_000, "onchain_sats": 200_000,
                "onchain_unconfirmed_sats": 0}

    async def new_address(self):
        return "bcrt1ptestaddress"


@pytest.fixture
def lnd():
    return FakeLnd()


@pytest.fixture
async def client(lnd):
    settings = Settings(demo_mode=True, pin="1234", cookie_secure=False, rate_source="fixed",
                        fallback_eur_per_btc=100_000.0, public_url="http://test")
    ctx = build_ctx(settings, db=DB(":memory:"), rates=RateService("fixed", 100_000.0),
                    assistant=Assistant(""), pos=lnd, wallet=lnd, customer=lnd)
    app = create_app(ctx)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        c.ctx = ctx
        yield c


async def login(c, pin="1234"):
    return await c.post("/api/login", json={"pin": pin}, headers=H)


async def test_security_headers_and_auth_required(client):
    r = await client.get("/api/summary")
    assert r.status_code == 401
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"


async def test_csrf_header_required(client):
    r = await client.post("/api/login", json={"pin": "1234"})
    assert r.status_code == 403


async def test_lockout_after_five_bad_pins(client):
    for _ in range(5):
        assert (await login(client, "0000")).status_code == 401
    r = await login(client, "1234")
    assert r.status_code == 401 and r.json()["locked_for"] > 0


async def test_sale_happy_path(client, lnd):
    assert (await login(client)).status_code == 200
    r = await client.post("/api/sales", json={"items": [{"name": "Pain", "qty": 2, "unit_xof": 150}]}, headers=H)
    assert r.status_code == 200, r.text
    sale = r.json()
    assert sale["amount_xof"] == 300 and sale["status"] == "open"
    # 300 FCFA at 100k EUR/BTC = 300 / 65_595_700 BTC -> 458 sats, rounded up
    assert sale["amount_sats"] == 458
    assert sale["bolt11"].startswith("lnbcrt")
    qr = await client.get(f"/api/pay/{sale['token']}/qr.svg")
    assert qr.status_code == 200 and qr.text.startswith("<svg")
    lnd.settle(sale["bolt11"])
    r = await client.get(f"/api/payments/{sale['token']}")
    assert r.json()["status"] == "paid" and r.json()["method"] == "lightning"
    s = (await client.get("/api/summary")).json()
    assert s["lightning_xof"] == 300 and s["sales_count"] == 1
    assert s["top_items"][0] == {"name": "Pain", "qty": 2}


async def test_amount_bounds_enforced(client):
    await login(client)
    r = await client.post("/api/sales", json={"amount_xof": 10}, headers=H)
    assert r.status_code == 400 and r.json()["error"] == "amount_out_of_range"
    r = await client.post("/api/sales", json={"amount_xof": 99_999_999}, headers=H)
    assert r.status_code == 422


async def test_markup_rejected_in_labels(client):
    await login(client)
    r = await client.post("/api/credits", json={"customer": "<script>", "amount_xof": 500}, headers=H)
    assert r.status_code == 422


async def test_credit_link_issues_fresh_invoice_and_hides_name(client, lnd):
    await login(client)
    r = await client.post("/api/credits", json={"customer": "Moussa", "amount_xof": 2000, "note": "riz"}, headers=H)
    credit = r.json()
    assert credit["bolt11"] is None and credit["pay_url"].startswith("http://test/p/")
    token = credit["token"]
    anon = httpx.AsyncClient(transport=client._transport, base_url="http://test")
    v = (await anon.post(f"/api/pay/{token}/invoice", headers=H)).json()
    assert v["bolt11"] and v["customer"] == "M…" and "note" not in v
    lnd.settle(v["bolt11"])
    assert (await anon.get(f"/api/pay/{token}")).json()["status"] == "paid"


async def test_cash_repayment(client):
    await login(client)
    token = (await client.post("/api/credits", json={"customer": "Awa", "amount_xof": 700}, headers=H)).json()["token"]
    r = await client.post(f"/api/payments/{token}/cash", headers=H)
    assert r.json()["method"] == "cash"
    assert (await client.post(f"/api/payments/{token}/cash", headers=H)).status_code == 409


async def test_wallet_pay_requires_pin_and_network(client, lnd):
    await login(client)
    r = await client.post("/api/wallet/pay", json={"bolt11": "lnbcrt1000n1xyz", "pin": "9999"}, headers=H)
    assert r.status_code == 401
    r = await client.post("/api/wallet/pay", json={"bolt11": "lnbc1000n1mainnet", "pin": "1234"}, headers=H)
    assert r.json()["error"] == "wrong_network"
    r = await client.post("/api/wallet/pay", json={"bolt11": "lnbcrt1000n1xyz", "pin": "1234"}, headers=H)
    assert r.status_code == 200 and r.json()["status"] == "SUCCEEDED"


async def test_wallet_daily_limit(client):
    await login(client)
    client.ctx.settings.daily_send_limit_xof = 1000
    # 2000 sats at 100k EUR/BTC = ~1312 FCFA > 1000 limit
    r = await client.post("/api/wallet/pay", json={"bolt11": "lnbcrt2000n1xyz", "pin": "1234"}, headers=H)
    assert r.json()["error"] == "daily_limit"


async def test_zero_amount_invoice_refused(client):
    await login(client)
    r = await client.post("/api/wallet/pay", json={"bolt11": "lnbcrt0n1xyz", "pin": "1234"}, headers=H)
    assert r.json()["error"] == "amount_required"


async def test_assistant_local_cart_and_summary(client):
    await login(client)
    r = await client.post("/api/assistant", json={"text": "2 pains et un sucre"}, headers=H)
    d = r.json()
    assert d["intent"] == "cart" and d["total_xof"] == 1000 and d["engine"] == "local"
    r = await client.post("/api/assistant", json={"text": "ventes du jour ?"}, headers=H)
    assert r.json()["reply"].startswith("Aujourd'hui")


async def test_demo_pay_settles(client, lnd):
    await login(client)
    sale = (await client.post("/api/sales", json={"amount_xof": 500}, headers=H)).json()

    async def pay_and_settle(bolt11, fee_limit_sat, timeout_s=30):
        lnd.settle(bolt11)
        return PaymentResult("SUCCEEDED", "", 0, "")

    lnd.pay = pay_and_settle
    r = await client.post(f"/api/demo/pay/{sale['token']}", headers=H)
    assert r.json() == {"status": "SUCCEEDED", "payment_status": "paid"}


async def test_payment_to_replaced_invoice_still_counts(client, lnd):
    """A customer who scans the old QR in its last minute must still be credited."""
    await login(client)
    token = (await client.post("/api/credits", json={"customer": "Awa", "amount_xof": 900}, headers=H)).json()["token"]
    first = (await client.post(f"/api/payments/{token}/invoice", headers=H)).json()
    # Pretend the first invoice is about to expire so the next call re-issues.
    client.ctx.db.exec("UPDATE payments SET invoice_expires_at=? WHERE token=?", (int(time.time()) + 30, token))
    second = (await client.post(f"/api/payments/{token}/invoice", headers=H)).json()
    assert second["bolt11"] != first["bolt11"]
    lnd.settle(first["bolt11"])  # paid the old QR
    assert (await client.get(f"/api/payments/{token}")).json()["status"] == "paid"
