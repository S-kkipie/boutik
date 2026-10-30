# Boutik — design spec (2026-10-30)

Hackathon: Dakar Bitcoin Hack by BTrust (Devpost, deadline 2026-11-20 20:00 UTC).
Decisions taken autonomously (the user asked for no confirmation round-trips).

## Problem

Senegalese corner shops ("boutiques") run on cash and a paper credit notebook
("cahier de crédit"). Change (monnaie) is scarce, the notebook gets lost or
disputed, and mobile-money fees eat thin margins. Diaspora relatives cannot
settle a family member's shop tab directly.

## Primary user

The boutiquier: one person behind the counter, mid-range Android phone,
intermittent 3G, French as working language, thinks in FCFA, not in sats.

## Solution (MVP scope)

1. **Caisse** — tap products or type an amount in FCFA, show a Lightning QR,
   get a loud "Payé ✓" when it settles. Sats are computed server-side.
2. **Ardoises (credit notebook)** — record a debt in FCFA with a customer
   nickname, share a payment link by WhatsApp. The link creates a fresh invoice
   at the current rate when opened, so the debt stays in FCFA. Cash repayment
   can be recorded too.
3. **Assistant** — "2 pains et un sucre" → draft cart; "crédit Moussa 2000" →
   draft ardoise; "ventes du jour ?" → summary. Claude when a key is configured,
   deterministic French parser otherwise. It only drafts; the merchant confirms.
   It has no spending capability.
4. **Portefeuille** — balances in FCFA + sats, receive on-chain, send a
   Lightning payment behind PIN re-entry and a daily limit.
5. **Demo customer wallet** (regtest only) — a second LND node that can pay any
   Boutik invoice from a button, so judges can run the happy path without a wallet.

## Architecture

- `bitcoind` (regtest) ← `lnd-merchant`, `lnd-customer` (LND v0.21.5).
- `bootstrap` one-shot (admin macaroons): mines, funds, opens channel
  customer→merchant with a push, bakes least-privilege macaroons into a shared
  volume, then exits.
- `app` (FastAPI, SQLite) only sees baked macaroons:
  - `pos.macaroon`: invoices read/write, info read.
  - `wallet.macaroon`: offchain read/write, onchain read, address read/write, info read.
  - `customer.macaroon` (demo only): offchain read/write, invoices read, info read.
- PWA: vanilla JS modules, no build step, system fonts, server-rendered SVG QR,
  service worker caching the shell.
- Only the app port is published; bitcoind/LND stay on the internal network.

## Network choice

Default is regtest: one command, deterministic, no faucet, zero-value coins.
Signet/mutinynet is the documented next step (config is network-aware;
invoices are checked against the expected network prefix).

## Security

PIN (scrypt) + HttpOnly SameSite=Strict session cookie; lockout after 5 failures;
CSRF via custom header requirement; strict CSP (no inline script); Pydantic bounds
on every amount; BOLT11 decoded and checked (network, amount > 0, expiry, limit)
before paying; no PII or memo text in logs; LLM output validated and recomputed
server-side; rate limits on invoice creation, public pay links and the assistant.

## Testing

pytest with a fake LND client for unit/API tests; `scripts/e2e.sh` runs the
happy path against the real compose stack; GitHub Actions runs both.

## Out of scope (next iteration)

Mobile-money off-ramp partner, signet/mutinynet, LSP-backed non-custodial mobile
wallet (Breez SDK / LDK), NWC, Wolof voice (needs native speakers), multi-shop.
