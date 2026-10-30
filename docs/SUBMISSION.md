# Devpost submission text (ready to paste)

Replace `VIDEO_URL` before submitting.

---

## Project name

Boutik

## Tagline (under 200 characters)

A Lightning till and credit notebook for Dakar's corner shops: priced in FCFA, ~15 KB on a mid-range phone, with an assistant that drafts sales and can never spend.

## Inspiration

Every Dakar neighbourhood has a *boutique* that sells bread, rice, sugar and Café Touba all day, in small amounts and almost always in cash. Two everyday problems stood out: there is never enough change, and regular customers buy on credit that is written in a paper *cahier de crédit*. That notebook gets lost or disputed, and a relative abroad who wants to settle the family's tab has no way to pay the shop directly. Lightning payments settle in seconds with no change to give, but most wallets speak in sats and jargon, while the shopkeeper thinks in FCFA. We wanted a tool that fits the counter as it is.

## What it does

- **Till (Caisse)**: tap products or type an amount in FCFA, show a Lightning QR, get a full-screen "Payé ✓" with a chime when it settles. Sats are computed server-side, rounded up so the shop never receives less than the FCFA price. Cash sales are one tap too.
- **Credit notebook (Ardoises)**: record a debt in FCFA with a customer nickname and send a WhatsApp pay link. The link creates a fresh invoice at the current rate when opened, so the debt stays in FCFA. The customer, or a relative abroad, pays from any Lightning wallet and the ardoise closes itself.
- **Assistant**: "2 pains, 3 cafés Touba et un sucre" becomes a draft cart; "crédit Moussa 2500" becomes a draft ardoise; "ventes du jour ?" returns the day's summary. Claude when an API key is configured, an offline French parser otherwise. It only drafts; the merchant confirms.
- **Journal**: today's total, Lightning vs cash, top items, money still owed.
- **Wallet**: balances in FCFA, receive on-chain, send a Lightning payment behind PIN re-entry and a daily limit.
- **Demo customer**: a second real LND node pays invoices from a button, so anyone can test the full flow without a wallet.

## How we built it

- **Lightning**: two real LND v0.21.5 nodes on a Bitcoin Core 29.5 regtest backend, all in Docker Compose. A one-shot bootstrap container mines blocks, opens a 10M sat channel, and bakes least-privilege macaroons: the till's macaroon can only create and read invoices; the spending macaroon is used only behind PIN re-entry, a network-prefix check, a daily limit and a fee cap. The app never sees `admin.macaroon`.
- **Backend**: Python, FastAPI, SQLite, httpx against the LND REST API, server-side SVG QR codes with segno, BTC/EUR from mempool.space or CoinGecko with cache and fallback, converted at the fixed 655.957 XOF/EUR peg.
- **AI**: Claude (`claude-opus-5-5`) with a strict JSON schema and low effort, re-validated with Pydantic; an offline rule-based French parser as fallback when there is no key or no network.
- **Frontend**: a PWA in vanilla JavaScript with no framework and no build step. About 15 KB gzipped on first load, system fonts, emoji as product pictures, service worker with network-first and offline fallback, French first with English.
- **Quality**: 27 pytest tests (parser, API, security) and an end-to-end script that runs the whole flow against the real nodes, including a check that the till's macaroon is refused by LND when it tries to pay.

## Challenges we ran into

- Making the debt stay in FCFA while Lightning invoices are in sats and expire: we store FCFA and issue a new invoice at the current rate each time the link is opened.
- Least privilege with LND: getting the bootstrap to be the only holder of admin macaroons, and proving from inside the app container that the till cannot spend.
- Keeping capabilities out of logs: pay links are bearer tokens, so we disabled the default access log, log route templates instead, and silenced HTTP client logs that would have printed invoices.
- Old Android phones: newer emoji render as empty boxes on Android versions still common in the region, so we kept to older emoji.
- Building for 3G: no framework, QR codes rendered on the server, and a service worker that still opens the till offline.

## Accomplishments that we're proud of

- A complete, working flow on real Lightning nodes with one command: `docker compose up --build`.
- A till that cannot spend money, even if the app is compromised.
- About 15 KB to load the whole merchant app.
- An assistant that understands counter French ("deux pains et un sucre", "Awa me doit 1 500") and still works offline.

## What we learned

- The hardest part of a payment tool for small shops is not Lightning, it is fitting the existing habits: FCFA, credit, WhatsApp, cash.
- Macaroons make least privilege practical; baking them per role is cheap and worth it.
- An LLM is useful at the counter only if it is optional, bounded, and never in the money path.

## What's next for Boutik

1. Signet / mutinynet deployment.
2. A phone-only, non-custodial wallet for the shop through an LSP (Breez SDK or LDK Node).
3. A mobile-money off-ramp through a licensed partner.
4. Wolof voice and interface, built with native speakers.
5. Nostr Wallet Connect, multi-shop support for cooperatives (GIE), and nostr receipts.
6. Tests with real boutiques in Dakar to measure time-to-paid, Lightning share and ardoise repayment.

## Built with

`bitcoin` · `lightning-network` · `lnd` · `bitcoin-core` · `python` · `fastapi` · `sqlite` · `httpx` · `javascript` · `pwa` · `service-worker` · `docker` · `docker-compose` · `claude` · `anthropic` · `segno`

## Try it out

- Code: https://github.com/S-kkipie/boutik
- Live demo: https://boutik-demo.santiago-918.workers.dev (PIN `1234`, regtest, zero-value coins)
- Video: VIDEO_URL

---

## Résumé en français

**Boutik** est une caisse Lightning et un cahier de crédit pour les boutiques de quartier à Dakar. Les prix restent en FCFA ; Boutik convertit en sats. Le boutiquier encaisse avec un QR et voit « Payé ✓ » en quelques secondes, sans monnaie à rendre. Les ardoises sont notées en FCFA et le client, ou un parent à l'étranger, les règle par un lien WhatsApp. Un assistant comprend le français du comptoir (« 2 pains et un sucre ») et prépare la vente, sans jamais pouvoir dépenser. L'application pèse environ 15 Ko, fonctionne sur un Android de milieu de gamme et en 3G, et tourne sur de vrais nœuds LND (regtest) avec une seule commande : `docker compose up --build`. Code ouvert sous licence MIT.
