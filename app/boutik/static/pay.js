// Customer-facing pay link. Shows only what is owed; never the shop's records.
import { h, api, fcfa, sats, errText, toast, chime, copy, poll } from "./ui.js";

const $app = document.getElementById("app");
const token = location.pathname.split("/").pop();

function view(...kids) {
  $app.replaceChildren(h("section", { class: "stack" }, ...kids));
}

function paid(d) {
  chime();
  view(h("div", { class: "card stack", role: "alert" },
    h("div", { class: "logo", "aria-hidden": "true" }, "✅"),
    h("h1", {}, "Merci ! Ardoise réglée."),
    h("p", { class: "amount" }, fcfa(d.amount_xof)),
    h("p", { class: "muted" }, d.shop_name)));
}

async function load() {
  let d;
  try {
    d = await api(`/api/pay/${encodeURIComponent(token)}`);
    if (d.status === "paid") return paid(d);
    if (d.status !== "open") return view(h("p", { class: "empty card" }, "Ce lien n'est plus actif."));
    d = await api(`/api/pay/${encodeURIComponent(token)}/invoice`, { method: "POST" });
  } catch (e) {
    return view(h("p", { class: "empty card" }, errText(e)), h("button", { class: "block", onclick: load }, "↻ Réessayer"));
  }
  if (d.status === "paid") return paid(d);

  const actions = h("div", { class: "stack" },
    h("a", { class: "btn primary big block", href: `lightning:${d.bolt11}` }, "⚡ Ouvrir mon portefeuille"),
    h("button", { class: "block", onclick: async () => toast((await copy(d.bolt11)) ? "Facture copiée" : d.bolt11) }, "📋 Copier la facture"));
  if (d.demo_mode) {
    actions.append(h("button", { class: "bolt block", onclick: async (ev) => {
      ev.currentTarget.disabled = true;
      try { await api(`/api/demo/pay/${encodeURIComponent(token)}`, { method: "POST" }); } catch (e) { toast(errText(e)); ev.currentTarget.disabled = false; }
    } }, "📱 Payer avec le portefeuille démo"));
  }
  view(
    h("header", { class: "top" }, h("h1", {}, d.shop_name), d.demo_mode ? h("span", { class: "chip demo" }, "démo") : null),
    h("p", { class: "muted" }, d.customer ? `Ardoise de ${d.customer}` : "Votre ardoise"),
    h("div", { class: "amount" }, fcfa(d.amount_xof)),
    h("p", { class: "muted small" }, `≈ ${sats(d.amount_sats)} · montant fixé en FCFA`),
    h("div", { class: "qr" }, h("img", { src: `/api/pay/${encodeURIComponent(token)}/qr.svg?h=${d.invoice_expires_at}`, alt: "QR Lightning", width: 300, height: 300 })),
    h("div", { class: "wait" }, h("span", { class: "dot", "aria-hidden": "true" }), h("span", {}, "En attente du paiement…")),
    actions,
    h("p", { class: "small muted" }, "Paiement Lightning : arrive en quelques secondes, sans monnaie à rendre."));

  poll(async () => {
    const s = await api(`/api/pay/${encodeURIComponent(token)}`);
    if (s.status === "paid") { paid(s); return true; }
    if ((d.invoice_expires_at || 0) * 1000 < Date.now()) { load(); return true; }
    return false;
  }, { every: 3000, max: 15000 });
}

load();
