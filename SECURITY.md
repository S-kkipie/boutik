# Security policy

## Test networks only

Boutik is a hackathon MVP. It runs on **regtest** by default, and the configuration only accepts `regtest`, `signet` or `testnet`.

- Never use it with mainnet funds.
- Never import real seeds, keys or macaroons from a mainnet node.
- The demo PIN (`1234`) and the bitcoind RPC password in `docker-compose.yml` are public demo values. Change them for any shared deployment.

See [THREAT_MODEL.md](THREAT_MODEL.md) for what the design protects against and what it does not.

## Reporting a vulnerability

- **Preferred:** open a private security advisory on this GitHub repository (Security tab → "Report a vulnerability").
- **Low-impact issues** (hardening ideas, documentation gaps): a regular GitHub issue is fine.

Please include the affected file or endpoint, steps to reproduce, and the impact you expect. We aim to answer within 7 days during the hackathon period.

## Scope

In scope: the application code in `app/`, `docker-compose.yml`, `scripts/` and the bootstrap process.

Out of scope: vulnerabilities in LND, Bitcoin Core, Docker or the browser themselves (report those upstream), attacks that require control of the Docker host, and anything on the public demo that only affects zero-value regtest coins.
