// Shared helpers. DOM is built with textContent only: user data never becomes HTML.

export function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

const nf = new Intl.NumberFormat("fr-FR");
export const fcfa = (n) => `${nf.format(Math.round(n || 0))} FCFA`;
export const sats = (n) => `${nf.format(n || 0)} sats`;

export class ApiError extends Error {
  constructor(status, code, data) {
    super(code);
    this.status = status;
    this.code = code;
    this.data = data;
  }
}

export async function api(path, { method = "GET", body } = {}) {
  const opt = { method, headers: {}, credentials: "same-origin", cache: "no-store" };
  if (method !== "GET") opt.headers["X-Boutik"] = "1"; // CSRF guard, see server middleware
  if (body !== undefined) {
    opt.headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(body);
  }
  let r;
  try {
    r = await fetch(path, opt);
  } catch {
    throw new ApiError(0, "network");
  }
  let data = null;
  try { data = await r.json(); } catch { /* empty body */ }
  if (!r.ok) {
    const code = data?.error || (r.status === 422 ? "invalid_input" : "server");
    throw new ApiError(r.status, code, data);
  }
  return data;
}

export const ERRORS = {
  fr: {
    network: "Pas de connexion. Vérifiez le réseau et réessayez.",
    server: "Le serveur ne répond pas. Réessayez dans un instant.",
    invalid_input: "Vérifiez les champs : montant ou nom invalide.",
    amount_out_of_range: "Le montant doit être entre 25 et 2 000 000 FCFA.",
    lightning_unavailable: "Lightning indisponible pour le moment. Encaissez en espèces.",
    bad_pin: "Code PIN incorrect.",
    too_many_requests: "Trop de demandes. Patientez une minute.",
    daily_limit: "Limite d'envoi du jour atteinte.",
    wrong_network: "Cette facture n'est pas pour ce réseau.",
    invalid_invoice: "Facture illisible. Recopiez-la en entier.",
    invoice_expired: "Cette facture a expiré. Demandez-en une nouvelle.",
    amount_required: "Facture sans montant : demandez une facture avec montant.",
    payment_failed: "Paiement échoué. Aucun argent n'est parti.",
    not_open: "Ce paiement est déjà réglé ou annulé.",
    not_found: "Lien introuvable.",
    demo_disabled: "Mode démo désactivé.",
    unauthorized: "Session expirée. Entrez votre code.",
    csrf: "Requête refusée.",
  },
  en: {
    network: "No connection. Check the network and retry.",
    server: "Server not responding. Try again shortly.",
    invalid_input: "Check the fields: invalid amount or name.",
    amount_out_of_range: "Amount must be between 25 and 2,000,000 FCFA.",
    lightning_unavailable: "Lightning unavailable right now. Take cash.",
    bad_pin: "Wrong PIN.",
    too_many_requests: "Too many requests. Wait a minute.",
    daily_limit: "Daily sending limit reached.",
    wrong_network: "This invoice is for another network.",
    invalid_invoice: "Unreadable invoice. Paste it in full.",
    invoice_expired: "This invoice expired. Ask for a new one.",
    amount_required: "Invoice has no amount: ask for one with an amount.",
    payment_failed: "Payment failed. No money left your wallet.",
    not_open: "Already settled or cancelled.",
    not_found: "Link not found.",
    demo_disabled: "Demo mode is off.",
    unauthorized: "Session expired. Enter your PIN.",
    csrf: "Request refused.",
  },
};

export function errText(e, lang = "fr") {
  const t = ERRORS[lang] || ERRORS.fr;
  return t[e?.code] || t.server;
}

let toastTimer;
export function toast(msg) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 3200);
}

export function chime() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [880, 1320].forEach((f, i) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.frequency.value = f;
      g.gain.setValueAtTime(0.18, ctx.currentTime + i * 0.16);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.16 + 0.15);
      o.connect(g).connect(ctx.destination);
      o.start(ctx.currentTime + i * 0.16);
      o.stop(ctx.currentTime + i * 0.16 + 0.16);
    });
  } catch { /* audio is a bonus */ }
  navigator.vibrate?.([80, 60, 160]);
}

export async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

// Poll with backoff: 2s while healthy, up to 10s while the network is flaky.
export function poll(fn, { every = 2000, max = 10000 } = {}) {
  let stopped = false;
  let delay = every;
  const tick = async () => {
    if (stopped) return;
    try {
      const done = await fn();
      delay = every;
      if (done) return;
    } catch {
      delay = Math.min(max, delay * 1.6);
    }
    if (!stopped) setTimeout(tick, document.hidden ? Math.max(delay, 5000) : delay);
  };
  setTimeout(tick, every);
  return () => (stopped = true);
}
