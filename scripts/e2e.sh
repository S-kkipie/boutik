#!/usr/bin/env bash
# End-to-end happy path against the running docker compose stack (real LND, regtest).
# Usage: ./scripts/e2e.sh [base_url]
set -euo pipefail
BASE="${1:-http://localhost:8000}"
JAR="$(mktemp)"; trap 'rm -f "$JAR"' EXIT
H=(-H "X-Boutik: 1" -H "Content-Type: application/json")
pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
die()  { printf '  \033[31m✗ %s\033[0m\n' "$1"; exit 1; }
j()    { python3 -c "import sys,json; d=json.load(sys.stdin); print(eval(sys.argv[1], {}, {'d': d}))" "$1"; }
get()  { curl -fsS -b "$JAR" -c "$JAR" "$BASE$1"; }
post() { curl -fsS -b "$JAR" -c "$JAR" "${H[@]}" -X POST "$BASE$1" -d "${2:-{\}}"; }

echo "Boutik e2e → $BASE"
for i in $(seq 1 60); do curl -fsS "$BASE/healthz" >/dev/null 2>&1 && break; sleep 2; done
get /api/status | j 'd["lightning"]' | grep -q True || die "Lightning not connected"
pass "app up, Lightning connected"

post /api/login '{"pin":"1234"}' >/dev/null && pass "login with demo PIN"

SALE=$(post /api/sales '{"items":[{"name":"Pain","qty":2,"unit_xof":150},{"name":"Sucre 1 kg","qty":1,"unit_xof":700}]}')
TOKEN=$(echo "$SALE" | j 'd["token"]')
echo "$SALE" | j 'd["bolt11"]' | grep -q '^lnbcrt' || die "no regtest invoice"
pass "sale 1000 FCFA → $(echo "$SALE" | j 'd["amount_sats"]') sats invoice"

post "/api/demo/pay/$TOKEN" | j 'd["payment_status"]' | grep -q paid || die "demo customer payment failed"
get "/api/payments/$TOKEN" | j 'd["status"]+"/"+d["method"]' | grep -q 'paid/lightning' || die "sale not settled"
pass "customer node paid over Lightning, sale settled"

CREDIT=$(post /api/credits '{"customer":"Moussa","amount_xof":2000,"note":"riz"}')
CT=$(echo "$CREDIT" | j 'd["token"]')
PUB=$(curl -fsS "${H[@]}" -X POST "$BASE/api/pay/$CT/invoice")
echo "$PUB" | j 'd["customer"]' | grep -q '^M…$' || die "public link leaks customer name"
curl -fsS "${H[@]}" -X POST "$BASE/api/demo/pay/$CT" >/dev/null
curl -fsS "$BASE/api/pay/$CT" | j 'd["status"]' | grep -q paid || die "ardoise not settled"
pass "ardoise link: fresh invoice, name masked, paid by customer"

INV=$(post /api/demo/invoice '{"amount_xof":1000}' | j 'd["bolt11"]')
code=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR" "${H[@]}" -X POST "$BASE/api/wallet/pay" -d "{\"bolt11\":\"$INV\",\"pin\":\"0000\"}")
[ "$code" = 401 ] || die "wallet pay accepted a wrong PIN ($code)"
post /api/wallet/pay "{\"bolt11\":\"$INV\",\"pin\":\"1234\"}" | j 'd["status"]' | grep -q SUCCEEDED || die "merchant send failed"
pass "merchant send: wrong PIN refused, right PIN paid"

S=$(get /api/summary)
pass "summary: $(echo "$S" | j 'd["text"]')"

if [ -z "${E2E_SKIP_DOCKER:-}" ] && command -v docker >/dev/null && docker compose ps app >/dev/null 2>&1; then
  OUT=$(docker compose exec -T app python - <<'PY'
import asyncio
from pathlib import Path
from boutik.lnd import LndRest, LndError
async def main():
    pos = LndRest.from_files("https://lnd-merchant:8080", Path("/creds/pos.macaroon"), Path("/creds/merchant-tls.cert"))
    try:
        await pos.pay("lnbcrt1u1invalid", fee_limit_sat=1)
        print("SPENT")
    except LndError as e:
        print("DENIED" if "permission" in str(e).lower() or "denied" in str(e).lower() or "403" in str(e) else f"OTHER {e}")
    print("ADMIN_VISIBLE" if Path("/creds/admin.macaroon").exists() else "NO_ADMIN")
asyncio.run(main())
PY
)
  echo "$OUT" | grep -q DENIED || die "POS macaroon could spend: $OUT"
  echo "$OUT" | grep -q NO_ADMIN || die "admin macaroon visible to app"
  pass "least privilege: POS macaroon cannot spend; app never sees admin.macaroon"
fi
echo "All checks passed."
