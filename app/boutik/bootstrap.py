"""Regtest bootstrap (one-shot container).

Funds both LND nodes, opens a customer -> merchant channel, then bakes
least-privilege macaroons into /creds. This is the only process that reads
admin.macaroon; the app container never sees it. Safe to re-run: it skips
whatever is already done.
"""

from __future__ import annotations

import base64
import os
import shutil
import sys
import time
from pathlib import Path

import httpx

RPC_URL = os.environ.get("BITCOIN_RPC_URL", "http://bitcoind:18443")
RPC_AUTH = (
    os.environ.get("BITCOIN_RPC_USER", "boutik"),
    os.environ.get("BITCOIN_RPC_PASSWORD", "regtest-only-not-a-secret"),
)
CREDS = Path(os.environ.get("CREDS_DIR", "/creds"))
APP_UID = int(os.environ.get("APP_UID", "10001"))

CHANNEL_SATS = 10_000_000
PUSH_SATS = 300_000  # gives the merchant spendable Lightning funds for the "send" demo
MERCHANT_ONCHAIN_SATS = 200_000

# Permissions per baked macaroon. Nothing here can create more macaroons,
# open/close channels, or sign arbitrary messages.
PERMS = {
    "pos": [("invoices", "read"), ("invoices", "write"), ("info", "read")],
    "wallet": [
        ("offchain", "read"),
        ("offchain", "write"),
        ("onchain", "read"),
        ("address", "read"),
        ("address", "write"),
        ("info", "read"),
    ],
    "customer": [
        ("offchain", "read"),
        ("offchain", "write"),
        ("onchain", "read"),
        ("invoices", "read"),
        ("invoices", "write"),
        ("info", "read"),
    ],
}


def log(msg: str) -> None:
    print(f"[bootstrap] {msg}", flush=True)


def rpc(method: str, *params):
    r = httpx.post(
        RPC_URL,
        auth=RPC_AUTH,
        json={"jsonrpc": "1.0", "id": "boutik", "method": method, "params": list(params)},
        timeout=30,
    )
    body = r.json()
    if body.get("error"):
        raise RuntimeError(f"bitcoind {method}: {body['error']}")
    return body["result"]


class Node:
    def __init__(self, name: str, rest_url: str, p2p: str):
        self.name = name
        self.rest_url = rest_url
        self.p2p = p2p
        base = Path(os.environ.get(f"LND_{name.upper()}_DIR", f"/lnd/{name}"))
        self.tls = base / "tls.cert"
        self.admin = base / "data/chain/bitcoin/regtest/admin.macaroon"
        self._http: httpx.Client | None = None

    def wait_ready(self, timeout: int = 180) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.tls.exists() and self.admin.exists():
                try:
                    self._http = httpx.Client(
                        base_url=self.rest_url,
                        verify=str(self.tls),
                        headers={"Grpc-Metadata-macaroon": self.admin.read_bytes().hex()},
                        timeout=60,
                    )
                    self.get("/v1/getinfo")
                    return
                except (httpx.HTTPError, RuntimeError):
                    pass
            time.sleep(2)
        raise SystemExit(f"{self.name}: LND not ready after {timeout}s")

    def get(self, path: str, **kw):
        assert self._http
        r = self._http.get(path, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"{self.name} GET {path}: {r.text[:200]}")
        return r.json()

    def post(self, path: str, body: dict):
        assert self._http
        r = self._http.post(path, json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"{self.name} POST {path}: {r.text[:200]}")
        return r.json()

    def wait_synced(self, height: int, timeout: int = 120) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            info = self.get("/v1/getinfo")
            if info.get("synced_to_chain") and int(info.get("block_height", 0)) >= height:
                return
            time.sleep(1)
        raise SystemExit(f"{self.name}: not synced to height {height}")

    def address(self) -> str:
        return self.get("/v1/newaddress", params={"type": 4})["address"]

    def bake(self, perms: list[tuple[str, str]]) -> str:
        body = {"permissions": [{"entity": e, "action": a} for e, a in perms]}
        return self.post("/v1/macaroon", body)["macaroon"]


def mine(n: int, addr: str) -> int:
    rpc("generatetoaddress", n, addr)
    return rpc("getblockcount")


def wait_bitcoind(timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            rpc("getblockchaininfo")
            return
        except (httpx.HTTPError, RuntimeError, ValueError):
            time.sleep(2)
    raise SystemExit("bitcoind not ready")


def active_channel(customer: Node, merchant_pub: str) -> bool:
    chans = customer.get("/v1/channels").get("channels", [])
    return any(c.get("remote_pubkey") == merchant_pub and c.get("active") for c in chans)


def write_secret(name: str, content: str | bytes) -> None:
    path = CREDS / name
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(content.encode() if isinstance(content, str) else content)
    os.chown(tmp, APP_UID, APP_UID)
    os.chmod(tmp, 0o400)
    tmp.replace(path)


def main() -> int:
    wait_bitcoind()
    merchant = Node(
        "merchant",
        os.environ.get("LND_MERCHANT_REST", "https://lnd-merchant:8080"),
        os.environ.get("LND_MERCHANT_P2P", "lnd-merchant:9735"),
    )
    customer = Node(
        "customer",
        os.environ.get("LND_CUSTOMER_REST", "https://lnd-customer:8080"),
        os.environ.get("LND_CUSTOMER_P2P", "lnd-customer:9735"),
    )
    merchant.wait_ready()
    customer.wait_ready()
    mpub = merchant.get("/v1/getinfo")["identity_pubkey"]
    log(f"merchant node {mpub[:16]}…")

    cust_addr = customer.address()
    height = rpc("getblockcount")
    if height < 101:
        log("mining 101 blocks to the demo customer (regtest coins, zero value)")
        height = mine(101, cust_addr)
    else:
        height = mine(1, cust_addr)  # refresh tip so LND does not think the chain is stale
    merchant.wait_synced(height)
    customer.wait_synced(height)

    if not active_channel(customer, mpub):
        pending = customer.get("/v1/channels/pending").get("pending_open_channels", [])
        if not pending:
            peers = customer.get("/v1/peers").get("peers", [])
            if not any(p.get("pub_key") == mpub for p in peers):
                customer.post("/v1/peers", {"addr": {"pubkey": mpub, "host": merchant.p2p}})
                time.sleep(2)
            log(f"opening {CHANNEL_SATS} sat channel customer -> merchant")
            customer.post(
                "/v1/channels",
                {
                    "node_pubkey": base64.b64encode(bytes.fromhex(mpub)).decode(),
                    "local_funding_amount": str(CHANNEL_SATS),
                    "push_sat": str(PUSH_SATS),
                    "sat_per_vbyte": "2",
                },
            )
            customer.post(
                "/v1/transactions",
                {"addr": merchant.address(), "amount": str(MERCHANT_ONCHAIN_SATS), "sat_per_vbyte": "2"},
            )
        height = mine(6, cust_addr)
        merchant.wait_synced(height)
        customer.wait_synced(height)
        deadline = time.time() + 90
        while not active_channel(customer, mpub):
            if time.time() > deadline:
                raise SystemExit("channel did not become active")
            time.sleep(1)
    log("channel active")

    CREDS.mkdir(parents=True, exist_ok=True)
    write_secret("pos.macaroon", merchant.bake(PERMS["pos"]))
    write_secret("wallet.macaroon", merchant.bake(PERMS["wallet"]))
    write_secret("customer.macaroon", customer.bake(PERMS["customer"]))
    for node in (merchant, customer):
        dst = CREDS / f"{node.name}-tls.cert"
        shutil.copyfile(node.tls, dst)
        os.chmod(dst, 0o444)
    log("least-privilege macaroons written; admin macaroons stay inside the LND volumes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
