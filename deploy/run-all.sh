#!/bin/bash
# Supervisor for the single-container demo. Same trust split as docker compose:
# root runs bitcoind/LND/bootstrap; the web app runs as uid 10001 and only gets
# the baked least-privilege macaroons (LND dirs are 0700 root).
set -euo pipefail
D=/data
RPCUSER=boutik
RPCPASS="$(head -c 18 /dev/urandom | base64 | tr -dc A-Za-z0-9)"   # fresh per boot, never leaves the box
mkdir -p "$D/bitcoin" "$D/merchant" "$D/customer" "$D/creds" "$D/app"
chmod 700 "$D/bitcoin" "$D/merchant" "$D/customer"
chown boutik:boutik "$D/app"

bitcoind -regtest -server -txindex -fallbackfee=0.0002 -datadir="$D/bitcoin" \
  -rpcbind=127.0.0.1 -rpcallowip=127.0.0.1 -rpcuser="$RPCUSER" -rpcpassword="$RPCPASS" \
  -zmqpubrawblock=tcp://127.0.0.1:28332 -zmqpubrawtx=tcp://127.0.0.1:28333 \
  -maxtipage=2000000000 -listen=0 -printtoconsole=0 &
PIDS=($!)

lnd_node() { # name rpc rest p2p
  lnd --lnddir="$D/$1" --noseedbackup --bitcoin.regtest --bitcoin.node=bitcoind \
    --bitcoind.rpchost=127.0.0.1:18443 --bitcoind.rpcuser="$RPCUSER" --bitcoind.rpcpass="$RPCPASS" \
    --bitcoind.zmqpubrawblock=tcp://127.0.0.1:28332 --bitcoind.zmqpubrawtx=tcp://127.0.0.1:28333 \
    --rpclisten=127.0.0.1:"$2" --restlisten=127.0.0.1:"$3" --listen=127.0.0.1:"$4" \
    --alias="boutik-$1" --trickledelay=500 --debuglevel=warn >"$D/$1.log" 2>&1 &
  PIDS+=($!)
}
sleep 2
lnd_node merchant 10009 8080 9735
lnd_node customer 10010 8081 9736

# App first, so the page answers while the nodes fund themselves (~20 s).
# Proxy headers trusted from anywhere: only the Cloudflare Worker can reach this port,
# and it overwrites X-Forwarded-For with CF-Connecting-IP.
su-exec boutik env \
  BOUTIK_DATA_DIR="$D/app" BOUTIK_CREDS_DIR="$D/creds" \
  BOUTIK_LND_MERCHANT_URL=https://localhost:8080 BOUTIK_LND_CUSTOMER_URL=https://localhost:8081 \
  FORWARDED_ALLOW_IPS='*' uvicorn boutik.main:app --host 0.0.0.0 --port 8000 --proxy-headers --no-access-log &
PIDS+=($!)

BITCOIN_RPC_URL=http://127.0.0.1:18443 BITCOIN_RPC_USER="$RPCUSER" BITCOIN_RPC_PASSWORD="$RPCPASS" \
LND_MERCHANT_DIR="$D/merchant" LND_CUSTOMER_DIR="$D/customer" \
LND_MERCHANT_REST=https://localhost:8080 LND_CUSTOMER_REST=https://localhost:8081 \
LND_MERCHANT_P2P=127.0.0.1:9735 LND_CUSTOMER_P2P=127.0.0.1:9736 \
CREDS_DIR="$D/creds" python3 -m boutik.bootstrap || echo "bootstrap failed; Lightning stays disabled" >&2 &

# If a long-running process dies, exit so the platform restarts a clean instance.
wait -n "${PIDS[@]}"
echo "a long-running process exited; stopping" >&2
exit 1
