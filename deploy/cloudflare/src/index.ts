import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  BOUTIK: DurableObjectNamespace<BoutikDemo>;
}

export class BoutikDemo extends Container<Env> {
  defaultPort = 8000;
  sleepAfter = "30m";
  envVars = {
    BOUTIK_DEMO_MODE: "true",
    BOUTIK_PIN: "1234",
    BOUTIK_SHOP_NAME: "Boutique Keur Daba",
    BOUTIK_COOKIE_SECURE: "true",
    BOUTIK_RATE_SOURCE: "auto",
  };
}

const STARTING = `<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="5">
<title>Boutik · démarrage</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;
background:#f7f3ea;color:#17171c;font:18px/1.4 system-ui,sans-serif;text-align:center;padding:16px}
@media(prefers-color-scheme:dark){body{background:#111214;color:#f2efe8}}</style></head>
<body><div><p style="font-size:2.5rem;margin:0">⚡🏪</p><h1>Boutik démarre…</h1>
<p>Le nœud Lightning de démo se réveille (≈ 30 s).<br>The demo Lightning node is waking up.</p></div></body></html>`;

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // The app trusts proxy headers only because this Worker is its sole caller:
    // overwrite them so clients cannot spoof their IP past the app's rate limits.
    const headers = new Headers(request.headers);
    headers.set("x-forwarded-for", request.headers.get("cf-connecting-ip") ?? "0.0.0.0");
    headers.set("x-forwarded-proto", "https");
    const forwarded = new Request(request, { headers });
    try {
      return await getContainer(env.BOUTIK, "demo").fetch(forwarded);
    } catch {
      const url = new URL(request.url);
      if (url.pathname.startsWith("/api/")) {
        return Response.json({ error: "lightning_unavailable" }, { status: 503, headers: { "retry-after": "5" } });
      }
      return new Response(STARTING, {
        status: 503,
        headers: { "content-type": "text/html; charset=utf-8", "retry-after": "5", "cache-control": "no-store" },
      });
    }
  },
};
