# Boutik threat model

Scope: the code in this repository as deployed by `docker-compose.yml` (regtest). Every mitigation below points at the file that implements it. Where something is not covered, we say so.

## Assets

| Asset | Where it lives | Why it matters |
|---|---|---|
| Merchant funds (Lightning + on-chain) | `lnd-merchant` volume | Theft = direct loss for the shop |
| `admin.macaroon` (merchant and customer nodes) | LND data volumes | Full control of a node |
| Baked macaroons `pos`, `wallet`, `customer` + TLS certs | `creds` volume, mode 0400, owned by uid 10001 | `wallet` can spend; `pos` can only invoice |
| Merchant PIN | `settings.pin_hash` in SQLite (scrypt) | Gates login and every outgoing payment |
| Session tokens | Cookie `boutik_s`; SHA-256 hash in SQLite | Session hijack = merchant access (minus spending without PIN) |
| Sales and ardoise records, incl. customer nicknames and notes | SQLite `/data/boutik.sqlite3` | Commercial and personal data |
| Pay-link tokens (`/p/<token>`) | SQLite, shared over WhatsApp | Bearer capability to see and pay one debt |
| `ANTHROPIC_API_KEY` (optional) | App environment | Billing abuse if leaked |
| bitcoind RPC credentials | Compose environment | Control of the regtest chain |

## Trust boundaries

1. **Phone ↔ app**: the internet (or LAN). Untrusted network, untrusted browsers, including anyone who receives a pay link.
2. **App ↔ LND**: Docker `internal` network, TLS pinned to each node's own certificate, one macaroon per client.
3. **Bootstrap ↔ LND / bitcoind**: the only process with admin rights; runs once and exits.
4. **App ↔ external APIs**: Claude API and price APIs over HTTPS; their responses are treated as untrusted input.
5. **Host ↔ containers**: whoever controls the Docker host controls everything (out of scope, see residual risks).

## STRIDE by component

### PWA (merchant phone)

| Threat | Mitigation | Where |
|---|---|---|
| **S** Someone picks up the phone and uses the till | PIN login; sessions expire after 12 h; logout button | `security.py` `Auth`, `main.py` `/api/login` |
| **T** XSS via product names, customer nicknames or notes | DOM built with `textContent` only (no `innerHTML`); labels reject `< > " \` { } \\`; strict CSP `script-src 'self'` with no inline script | `static/ui.js` `h()`, `main.py` `CLEAN`, `security.py` `CSP` |
| **T** Clickjacking of the till | `X-Frame-Options: DENY`, CSP `frame-ancestors 'none'` | `security.py` `SECURITY_HEADERS` |
| **I** Stale money state from cache | Service worker never caches `/api/*`; API responses carry `Cache-Control: no-store` | `static/sw.js`, `main.py` `guard` |
| **I** Referrer leaking pay-link tokens | `Referrer-Policy: no-referrer` | `security.py` |

### Public pay link (`/p/<token>`, `/api/pay/<token>*`)

| Threat | Mitigation | Where |
|---|---|---|
| **S/I** Guessing other customers' links | 128-bit random token (`secrets.token_urlsafe(16)`) | `service.py` `create_payment` |
| **I** Link reveals the customer's identity or the shop's records | Public view drops `id`, `note`, `created_at`; customer name reduced to its initial (`M…`); invoice memo is `<shop> #<id>`, never the customer's name | `main.py` `public_view`, `db.py` `payment_dict(public=True)`, `service.py` `ensure_invoice` |
| **T** Paying a stale price after FCFA/BTC moves | Debt stored in FCFA; invoice issued at the current rate when the link is opened and re-issued when less than 60 s remain | `service.py` `ensure_invoice`, `REISSUE_MARGIN_S` |
| **T** Missing a payment made just before re-issue | The current invoice is looked up (`refresh`) before a new one replaces it; a replacement is issued only in the invoice's last 60 s, and the replaced invoice's hash is kept (`prev_r_hash`) and reconciled too, so paying the old QR in that window still settles the ardoise | `service.py` `ensure_invoice`, `refresh`; test `test_payment_to_replaced_invoice_still_counts` |
| **D** Invoice spam through a shared link | 20 invoice requests/min per IP and 6/min per token; 120 views/min per IP | `main.py` `pay_invoice`, `pay_view`, `pay_qr` |
| **R** Customer claims they paid | Settlement is read from LND (`SETTLED`, `amt_paid_sat`, `settle_date`), not from the client | `service.py` `refresh` |

### App API (FastAPI)

| Threat | Mitigation | Where |
|---|---|---|
| **S** PIN brute force | scrypt (N=2^14, r=8, p=1) with random salt; constant-time compare; global lockout 5 min after 5 failures in 5 min; login limited to 10/min per IP | `security.py` `hash_pin`, `verify_pin`, `Auth.check_pin`; `main.py` `login` |
| **S** Session theft | Random 256-bit token, stored as SHA-256 only; cookie `HttpOnly`, `SameSite=Strict`, `Secure` (default `true`, `false` only in the local compose demo) | `security.py` `Auth.new_session`, `main.py` `set_cookie` |
| **T** CSRF on state-changing calls | Every non-GET `/api/` request must carry `X-Boutik: 1`; a cross-site form cannot set it and a cross-site fetch would need CORS, which the app never grants | `main.py` `guard` |
| **T** Tampered amounts (negative, huge, mismatched totals) | Pydantic bounds on every field (`qty` 1–999, amounts 1–2 000 000, ≤30 items, label lengths); server recomputes the total from items; `min/max_invoice_xof` enforced; SQLite `CHECK` constraints | `main.py` request models, `service.py` `create_payment`, `db.py` `SCHEMA` |
| **E** Spending with a stolen session | Outgoing payments require the PIN again on every call; wrong PINs count towards the lockout | `main.py` `pay` |
| **T/E** Paying a malicious invoice | Network prefix check (`lnbcrt` on regtest); length ≤ 2000, ASCII, no whitespace; LND decode required; zero-amount and expired invoices refused; daily limit (100 000 FCFA by default) on successful sends; fee limit `max(10, 1%)` sats | `service.py` `pay_invoice`, `main.py` `Bolt11In` |
| **I** Secrets or capabilities in logs | uvicorn access log disabled; own log line prints the route template, with token-like path segments replaced by `*` as fallback; `httpx` logger set to WARNING so LND URLs with payment hashes and invoices are not logged; assistant text never logged; settlement log has kind and id only | `Dockerfile` `--no-access-log`, `main.py` `guard`, `TOKENISH`, logging setup, `service.py` |
| **I** Fingerprinting / API discovery | OpenAPI, `/docs` and `/redoc` disabled | `main.py` `create_app` |
| **D** Request floods | Sliding-window limits per endpoint (sales and credits 60/min, assistant 20/min, wallet pay 10/min, address 10/min, setup 5/min, demo 20/min per IP); limiter memory bounded | `security.py` `RateLimiter`, `main.py` `limit` |
| **E** Container breakout impact | Non-root uid 10001, read-only root FS, `tmpfs /tmp`, `cap_drop: [ALL]`, `no-new-privileges` | `app/Dockerfile`, `docker-compose.yml` |

### Assistant / LLM

| Threat | Mitigation | Where |
|---|---|---|
| **E** Prompt injection makes the model move money | The assistant has no tools and no macaroon; it only returns a draft. Nothing executes until the merchant taps Confirm, which calls the normal validated endpoints | `assistant/__init__.py`, `assistant/claude.py`, `static/app.js` `draftView` |
| **T** Model returns wrong totals or out-of-range values | Strict JSON schema on the API call, Pydantic re-validation (`DraftItem` bounds), total recomputed from items; server recomputes again when the sale is created | `assistant/claude.py` `SCHEMA`, `assistant/types.py`, `main.py` `new_sale` |
| **D** LLM outage or slow network blocks the counter | 12 s timeout, 1 retry, then the offline French parser | `assistant/__init__.py` `Assistant.parse` |
| **I** Sending customer data to a third party | Only the merchant's sentence and the product catalogue are sent; no records, no history. Claude mode is opt-in (`ANTHROPIC_API_KEY`) | `assistant/claude.py` |
| **D/$** Cost abuse of the API key | Assistant requires a merchant session; 20 calls/min; `max_tokens` 2048 | `main.py` `assistant` |

### LND nodes

| Threat | Mitigation | Where |
|---|---|---|
| **E** App compromise drains or reconfigures the node | App never sees `admin.macaroon` (LND volumes are not mounted in `app`). `pos.macaroon` = `invoices:read/write`, `info:read` only; `wallet.macaroon` cannot open/close channels, bake macaroons or sign messages | `bootstrap.py` `PERMS`, `docker-compose.yml` volumes |
| **S/I** Network attacker on the LND API | LND ports not published; `internal: true` network; TLS verified against each node's own cert | `docker-compose.yml`, `lnd.py` `LndRest` |
| **I** Lightning metadata in invoices | Memo is the shop name and an internal number only | `service.py` `ensure_invoice` |

### Bootstrap

| Threat | Mitigation | Where |
|---|---|---|
| **E** Long-lived admin access | One-shot container (`restart: "no"`), mounts LND volumes read-only, exits after writing baked macaroons | `docker-compose.yml`, `bootstrap.py` |
| **T** Partial or racing writes of credentials | Each file written to `.tmp`, chowned to the app uid, chmod 0400, then atomically renamed | `bootstrap.py` `write_secret` |
| **T** Re-running corrupts state | Idempotent: skips mining, peering and channel opening that already happened | `bootstrap.py` `main` |

### Rates API (mempool.space, CoinGecko)

| Threat | Mitigation | Where |
|---|---|---|
| **T** Poisoned or absurd price | Sanity bounds (1 000 < EUR/BTC < 10 000 000); FCFA derived from the fixed 655.957 XOF/EUR peg; sats rounded up so the shop never receives less than the FCFA price | `rates.py`, `money.py` |
| **D** API down or shop offline | 4 s timeout, second source, last good value cached 10 min, then fixed fallback; `BOUTIK_RATE_SOURCE=fixed` disables egress | `rates.py` `RateService` |

### Host

| Threat | Mitigation | Where |
|---|---|---|
| **I** Database or credentials read from disk | Out of scope for the MVP: whoever controls the Docker host controls the shop. Volumes are local Docker volumes | — |

## Residual risks and what is not covered

- **`--noseedbackup`**: LND wallets are created without a seed backup and unlocked automatically. Acceptable on regtest only. A real deployment must create the wallet with a seed, store the seed offline, and unlock through a secure mechanism.
- **Default credentials**: the demo PIN `1234` and the bitcoind RPC password in `docker-compose.yml` are demo values. Set `BOUTIK_PIN` empty (the app then asks for a new PIN) and change `BITCOIN_RPC_PASSWORD` for anything shared.
- **Single PIN, single operator**: no per-employee accounts, no roles.
- **In-memory rate limiter and lockout**: reset on restart; one process per shop is assumed.
- **No TLS termination in the app**: run it behind a reverse proxy with HTTPS and set `BOUTIK_COOKIE_SECURE=true`.
- **Demo endpoints are unauthenticated** (`/api/demo/*`): they exist only when `BOUTIK_DEMO_MODE=true` and the network is regtest, are rate-limited, and move only zero-value regtest coins. A public demo visitor can still make the demo customer pay demo invoices.
- **Browser speech recognition** may send audio to the browser vendor's servers. It is optional and only triggered by the mic button.
- **Pay links are bearer capabilities**: anyone who has the link can see the amount, shop name and initial, and can pay it. They cannot change it.
- **No encryption at rest** for SQLite; customer nicknames and notes are stored in clear on the host.
- **No audit log** of merchant actions beyond the sales and sends tables.
- **Supply chain**: images are pinned by tag (`lnd:v0.21.5-beta`, `bitcoin:29.5-alpine`), not by digest; Python dependencies use version ranges.

## How we verified

Unit and API tests (`cd app && pytest`, 31 tests, fake LND) include these security checks in `app/tests/test_api.py`:

- `test_security_headers_and_auth_required`: CSP and `X-Frame-Options` present; API returns 401 without a session.
- `test_csrf_header_required`: a POST without `X-Boutik: 1` is refused with 403.
- `test_lockout_after_five_bad_pins`: after 5 wrong PINs the right PIN is refused and `locked_for > 0`.
- `test_amount_bounds_enforced`: 10 FCFA → `amount_out_of_range`; 99 999 999 → 422.
- `test_markup_rejected_in_labels`: `<script>` as a customer name → 422.
- `test_credit_link_issues_fresh_invoice_and_hides_name`: the public view shows `M…` and no `note`.
- `test_wallet_pay_requires_pin_and_network`: wrong PIN → 401; mainnet invoice → `wrong_network`.
- `test_wallet_daily_limit`: payment over the limit → `daily_limit`.
- `test_zero_amount_invoice_refused`: zero-amount invoice → `amount_required`.

End-to-end against the real stack (`./scripts/e2e.sh`, real LND v0.21.5 on regtest):

- Wrong PIN on a real outgoing payment → HTTP 401; right PIN → `SUCCEEDED`.
- Inside the app container, a payment attempted with `pos.macaroon` is refused by LND with `permission denied`.
- `/creds/admin.macaroon` does not exist inside the app container.
- The public ardoise view returns the masked name `M…`.

We also checked the app logs after a full run: they show route templates such as `POST /api/demo/pay/{token} 200`, with no tokens, invoices or payment hashes.
