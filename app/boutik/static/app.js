import { h, api, fcfa, sats, errText, toast, chime, copy, poll } from "./ui.js";

const T = {
  fr: {
    tab_pos: "Caisse", tab_credit: "Ardoises", tab_sales: "Journal", tab_wallet: "Portefeuille",
    pin_title: "Entrez votre code", pin_new: "Créez votre code (4 à 6 chiffres)", pin_confirm: "Confirmez le code",
    pin_demo: "Démo : code 1234", pin_mismatch: "Les deux codes ne correspondent pas. Recommencez.", shop_name: "Nom de la boutique", locked: "Trop d'essais. Réessayez dans {s} s.",
    ask_ph: "Ex : 2 pains et un sucre", ask_go: "Envoyer", mic: "Parler", ask_hint: "Dites ou tapez la vente",
    use_draft: "Au panier", rate: "1 000 F ≈ {n} sats",
    free_amount: "Montant", cart_empty: "Touchez un article ou tapez un montant",
    charge: "Encaisser", clear: "Vider", add_product: "Article",
    pay_title: "Le client scanne pour payer", waiting: "En attente du paiement…", expired: "QR expiré",
    new_qr: "Nouveau QR", copy_inv: "Copier la facture", copied: "Copié", cash: "Payé en espèces", cancel: "Annuler",
    demo_pay: "Simuler le client (démo)", paid: "Payé", next_sale: "Nouvelle vente", close: "Fermer",
    credits_title: "Ardoises", credits_open: "{n} ouverte(s) · {t}", new_credit: "Nouvelle ardoise",
    customer: "Prénom ou surnom du client", amount: "Montant (FCFA)", note: "Note (facultatif)", save: "Enregistrer", save_share: "Enregistrer et envoyer",
    share: "Envoyer le lien", share_other: "Autre application…", copy_link: "Copier le lien", open_client: "Voir la page du client", no_credits: "Aucune ardoise. Notez ici ce que les clients doivent.",
    share_msg: "Bonjour {c}, votre ardoise chez {s} : {a}. Payez en Lightning ici : {u}",
    sales_title: "Aujourd'hui", total: "Total", lightning: "Lightning", cash_short: "Espèces", open_credits: "Ardoises ouvertes",
    no_sales: "Pas encore de vente aujourd'hui.", sale: "Vente",
    wallet_title: "Portefeuille", balance: "Solde Lightning", onchain: "Solde on-chain", inbound: "Capacité de réception",
    receive_onchain: "Recevoir on-chain", send: "Envoyer un paiement", paste_inv: "Collez la facture Lightning (lnbcrt…)",
    check: "Vérifier", confirm_send: "Confirmer avec le code", sent: "Envoyé", limit: "Envoyé aujourd'hui : {s} / {l}",
    demo_wallet: "Client démo", demo_invoice: "Créer une facture client démo de 1 000 F",
    demo_explain: "Réseau de test regtest : ces bitcoins n'ont aucune valeur.",
    logout: "Se déconnecter", ln_starting: "Lightning démarre…", lang: "English", engine_claude: "IA Claude", engine_local: "Assistant hors ligne",
    product_name: "Nom de l'article", price: "Prix (FCFA)", emoji: "Emoji (facultatif)", remove: "Retirer",
  },
  en: {
    tab_pos: "Till", tab_credit: "Tabs", tab_sales: "Sales", tab_wallet: "Wallet",
    pin_title: "Enter your PIN", pin_new: "Create your PIN (4 to 6 digits)", pin_confirm: "Confirm PIN",
    pin_demo: "Demo: PIN 1234", pin_mismatch: "PINs do not match. Start again.", shop_name: "Shop name", locked: "Too many attempts. Retry in {s}s.",
    ask_ph: "e.g. 2 pains et un sucre", ask_go: "Send", mic: "Speak", ask_hint: "Say or type the sale",
    use_draft: "To cart", rate: "1,000 F ≈ {n} sats",
    free_amount: "Amount", cart_empty: "Tap an item or type an amount",
    charge: "Charge", clear: "Clear", add_product: "Item",
    pay_title: "Customer scans to pay", waiting: "Waiting for payment…", expired: "QR expired",
    new_qr: "New QR", copy_inv: "Copy invoice", copied: "Copied", cash: "Paid in cash", cancel: "Cancel",
    demo_pay: "Simulate customer (demo)", paid: "Paid", next_sale: "Next sale", close: "Close",
    credits_title: "Tabs", credits_open: "{n} open · {t}", new_credit: "New tab",
    customer: "Customer first name or nickname", amount: "Amount (FCFA)", note: "Note (optional)", save: "Save", save_share: "Save and send",
    share: "Send link", share_other: "Other app…", copy_link: "Copy link", open_client: "Open customer page", no_credits: "No tabs yet. Record here what customers owe.",
    share_msg: "Hello {c}, your tab at {s}: {a}. Pay with Lightning here: {u}",
    sales_title: "Today", total: "Total", lightning: "Lightning", cash_short: "Cash", open_credits: "Open tabs",
    no_sales: "No sales yet today.", sale: "Sale",
    wallet_title: "Wallet", balance: "Lightning balance", onchain: "On-chain balance", inbound: "Can receive",
    receive_onchain: "Receive on-chain", send: "Send a payment", paste_inv: "Paste the Lightning invoice (lnbcrt…)",
    check: "Check", confirm_send: "Confirm with PIN", sent: "Sent", limit: "Sent today: {s} / {l}",
    demo_wallet: "Demo customer", demo_invoice: "Create a 1,000 F demo customer invoice",
    demo_explain: "Regtest test network: these bitcoins have no value.",
    logout: "Log out", ln_starting: "Lightning starting…", lang: "Français", engine_claude: "Claude AI", engine_local: "Offline assistant",
    product_name: "Item name", price: "Price (FCFA)", emoji: "Emoji (optional)", remove: "Remove",
  },
};

const S = {
  lang: (() => { try { return localStorage.getItem("lang") || "fr"; } catch { return "fr"; } })(),
  status: null,
  rate: null,
  products: [],
  cart: new Map(), // key -> {name, qty, unit_xof, emoji}
  stopPoll: null,
};
const t = (k, vars = {}) => (T[S.lang][k] || T.fr[k] || k).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? "");
const $app = document.getElementById("app");
const $tabs = document.getElementById("tabs");
const $sheet = document.getElementById("sheet");
const fail = (e) => {
  if (e?.code === "unauthorized") return boot();
  toast(errText(e, S.lang));
};

function render(...nodes) {
  $app.replaceChildren(...nodes);
}

// ---------------- boot & auth ----------------

async function boot() {
  try {
    S.status = await api("/api/status");
  } catch (e) {
    render(h("p", { class: "boot" }, errText(e, S.lang)), h("button", { class: "block", onclick: boot }, "↻"));
    return;
  }
  document.documentElement.lang = S.lang;
  if (!S.status.has_pin) return pinScreen("setup");
  if (!S.status.authenticated) return pinScreen("login");
  S.rate = await api("/api/rate").catch(() => null);
  S.products = await api("/api/products").catch(() => []);
  $tabs.hidden = false;
  for (const b of $tabs.querySelectorAll("[data-i18n]")) b.textContent = t(b.dataset.i18n);
  route();
  if (!S.status.lightning) waitForLightning();
}

// Single-container demo: nodes may still be starting. Re-check until Lightning is up.
function waitForLightning() {
  const stop = poll(async () => {
    const st = await api("/api/status");
    if (!st.lightning) return false;
    S.status = st;
    if ($sheet.hidden) route();
    return true;
  }, { every: 4000, max: 8000 });
  return stop;
}

function pinScreen(mode) {
  $tabs.hidden = true;
  let pin = "";
  let first = null;
  const dots = h("div", { class: "dots", "aria-hidden": "true" });
  const err = h("p", { class: "err", role: "alert" });
  const title = h("h1", {}, mode === "setup" ? t("pin_new") : t("pin_title"));
  const shop = mode === "setup" ? h("input", { placeholder: t("shop_name"), maxlength: 60, autocomplete: "organization" }) : null;
  const maxLen = mode === "setup" ? 6 : 8;
  const draw = () => dots.replaceChildren(...Array.from({ length: Math.max(4, pin.length) }, (_, i) => h("i", { class: i < pin.length ? "f" : "" })));
  const submit = async () => {
    if (pin.length < 4) return;
    try {
      if (mode === "setup") {
        if (!first) { first = pin; pin = ""; title.textContent = t("pin_confirm"); return draw(); }
        if (first !== pin) { first = null; pin = ""; title.textContent = t("pin_new"); err.textContent = t("pin_mismatch"); return draw(); }
        await api("/api/setup", { method: "POST", body: { pin, shop_name: shop.value.trim() } });
      } else {
        await api("/api/login", { method: "POST", body: { pin } });
      }
      boot();
    } catch (e) {
      pin = "";
      draw();
      err.textContent = e.data?.locked_for ? t("locked", { s: e.data.locked_for }) : errText(e, S.lang);
    }
  };
  const press = (k) => {
    err.textContent = "";
    if (k === "⌫") pin = pin.slice(0, -1);
    else if (k === "OK") return submit();
    else if (pin.length < maxLen) pin += k;
    draw();
    if (mode === "login" && pin.length === 4 && S.status.demo_pin_hint) submit();
  };
  const keys = h("div", { class: "keys" }, ..."123456789".split("").map((k) => h("button", { onclick: () => press(k) }, k)),
    h("button", { onclick: () => press("⌫"), "aria-label": "Effacer" }, "⌫"),
    h("button", { onclick: () => press("0") }, "0"),
    h("button", { class: "primary", onclick: () => press("OK") }, "OK"));
  draw();
  render(h("section", { class: "pin" },
    h("div", { class: "logo", "aria-hidden": "true" }, "⚡🏪"),
    h("p", { class: "muted" }, S.status.shop_name || "Boutik"),
    title, shop, dots, err, keys,
    S.status.demo_pin_hint ? h("p", { class: "muted small" }, t("pin_demo")) : null,
    S.status.locked_for ? h("p", { class: "err" }, t("locked", { s: S.status.locked_for })) : null,
    h("button", { class: "ghost small", onclick: toggleLang }, t("lang"))));
}

function toggleLang() {
  S.lang = S.lang === "fr" ? "en" : "fr";
  try { localStorage.setItem("lang", S.lang); } catch { /* private mode */ }
  boot();
}

// ---------------- routing ----------------

const ROUTES = { caisse: posScreen, ardoises: creditsScreen, journal: salesScreen, portefeuille: walletScreen };

function route() {
  if (!S.status?.authenticated) return;
  if (!$sheet.hidden) closeSheet();
  const tab = location.hash.slice(1) || "caisse";
  for (const a of $tabs.querySelectorAll("a")) {
    const on = a.dataset.tab === tab;
    a.classList.toggle("on", on);
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  (ROUTES[tab] || posScreen)();
}
window.addEventListener("hashchange", route);

function header(title) {
  const chips = h("div", { class: "row" });
  if (S.rate) chips.append(h("span", { class: "chip", title: `source: ${S.rate.source}` }, "⚡ ", t("rate", { n: new Intl.NumberFormat("fr-FR").format(S.rate.sats_per_1000_xof) })));
  if (S.status.network !== "mainnet") chips.append(h("span", { class: "chip demo" }, S.status.network));
  if (!S.status.lightning) chips.append(h("span", { class: "chip", role: "status" }, "⏳ ", t("ln_starting")));
  return h("header", { class: "top" }, h("h1", {}, title), chips);
}

// ---------------- POS ----------------

function cartTotal() {
  let n = 0;
  for (const i of S.cart.values()) n += i.qty * i.unit_xof;
  return n;
}

function addToCart(item, qty = 1) {
  const key = item.id ? `p${item.id}` : `c${item.name}${item.unit_xof}`;
  const cur = S.cart.get(key) || { name: item.name, emoji: item.emoji || "", unit_xof: item.unit_xof ?? item.price_xof, qty: 0 };
  cur.qty = Math.min(999, cur.qty + qty);
  S.cart.set(key, cur);
}

function posScreen() {
  const reply = h("div");
  const input = h("input", { placeholder: t("ask_ph"), maxlength: 300, enterkeyhint: "send", "aria-label": t("ask_ph") });
  const ask = async (text) => {
    if (!text.trim()) return;
    reply.replaceChildren(h("p", { class: "reply muted" }, "…"));
    try {
      const d = await api("/api/assistant", { method: "POST", body: { text } });
      reply.replaceChildren(draftView(d));
    } catch (e) {
      reply.replaceChildren();
      fail(e);
    }
  };
  const form = h("form", { class: "ask", onsubmit: (e) => { e.preventDefault(); ask(input.value); } }, input);
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SR) {
    const mic = h("button", { type: "button", class: "mic", "aria-label": t("mic"), title: t("mic") }, "🎙️");
    mic.addEventListener("click", () => {
      const rec = new SR();
      rec.lang = S.lang === "fr" ? "fr-FR" : "en-US";
      rec.interimResults = false;
      mic.classList.add("on");
      rec.onresult = (ev) => { input.value = ev.results[0][0].transcript; ask(input.value); };
      rec.onend = () => mic.classList.remove("on");
      rec.onerror = () => mic.classList.remove("on");
      rec.start();
    });
    form.append(mic);
  }
  form.append(h("button", { type: "submit", "aria-label": t("ask_go") }, "➤"));

  const grid = h("div", { class: "grid" });
  const bar = h("div", { class: "cartbar" });
  const draw = () => {
    grid.replaceChildren(
      ...S.products.map((p) => {
        const q = S.cart.get(`p${p.id}`)?.qty;
        return h("button", { class: "prod", onclick: () => { addToCart(p); draw(); }, "aria-label": `${p.name}, ${fcfa(p.price_xof)}` },
          q ? h("span", { class: "q" }, q) : null,
          h("span", { class: "e", "aria-hidden": "true" }, p.emoji || "🛒"),
          h("span", { class: "n" }, p.name), h("span", { class: "p" }, fcfa(p.price_xof)));
      }),
      h("button", { class: "prod add", onclick: keypadSheet }, h("span", { class: "e" }, "🔢"), h("span", { class: "n" }, t("free_amount"))),
      h("button", { class: "prod add", onclick: productSheet }, h("span", { class: "e" }, "＋"), h("span", { class: "n" }, t("add_product"))),
    );
    const total = cartTotal();
    const count = [...S.cart.values()].reduce((a, i) => a + i.qty, 0);
    bar.replaceChildren(h("div", { class: "inner" },
      total ? h("button", { class: "ghost", onclick: () => { S.cart.clear(); draw(); }, "aria-label": t("clear") }, "✕") : null,
      h("div", { class: "btn total" }, h("span", {}, fcfa(total)), h("small", {}, total ? `${count} article(s)` : t("cart_empty"))),
      h("button", { class: "primary big", disabled: !total, onclick: () => charge() }, "⚡ ", t("charge"))));
  };
  draw();
  posScreen.redraw = draw;
  render(header(S.status.shop_name), form,
    h("p", { class: "small muted" }, "🎙️ ", t("ask_hint"), " · ", S.status.assistant_engine === "claude" ? t("engine_claude") : t("engine_local")),
    reply, h("div", { class: "spacer" }), grid, h("div", { class: "spacer" }), bar);
}

function draftView(d) {
  const box = h("div", { class: "reply stack" });
  if (d.reply) box.append(h("p", {}, d.reply));
  if (d.intent === "cart" && d.items.length) {
    box.append(h("ul", { class: "list" }, ...d.items.map((i) => h("li", {}, h("span", { class: "grow" }, `${i.qty} × ${i.name}`), h("span", { class: "amt" }, fcfa(i.qty * i.unit_xof))))));
    box.append(h("div", { class: "row" }, h("strong", { class: "grow" }, t("total")), h("strong", { class: "amt" }, fcfa(d.total_xof))));
    box.append(h("div", { class: "row" },
      h("button", { class: "grow", onclick: () => { d.items.forEach((i) => addToCart(matchProduct(i), i.qty)); posScreen.redraw?.(); box.remove(); } }, "＋ ", t("use_draft")),
      h("button", { class: "primary grow", onclick: () => { S.cart.clear(); d.items.forEach((i) => addToCart(matchProduct(i), i.qty)); charge(); } }, "⚡ ", t("charge"))));
  }
  if (d.intent === "credit") {
    box.append(h("button", { class: "primary block", onclick: () => creditSheet({ customer: d.customer, amount_xof: d.amount_xof, note: d.note }) }, "📒 ", t("new_credit")));
  }
  return box;
}

function matchProduct(item) {
  const p = S.products.find((p) => p.name === item.name && p.price_xof === item.unit_xof);
  return p || { name: item.name, unit_xof: item.unit_xof };
}

function keypadSheet() {
  let v = "";
  const out = h("div", { class: "amount", "aria-live": "polite" });
  const draw = () => out.replaceChildren(v ? new Intl.NumberFormat("fr-FR").format(+v) : "0", " ", h("small", {}, "FCFA"));
  const press = (k) => {
    if (k === "⌫") v = v.slice(0, -1);
    else if (k === "000") v = v ? (v + "000").slice(0, 7) : v;
    else if (v.length < 7) v = (v + k).replace(/^0+/, "");
    draw();
  };
  draw();
  openSheet(h("h2", {}, t("free_amount")), out,
    h("div", { class: "keys" }, ..."123456789".split("").map((k) => h("button", { onclick: () => press(k) }, k)),
      h("button", { onclick: () => press("000") }, "000"), h("button", { onclick: () => press("0") }, "0"),
      h("button", { onclick: () => press("⌫"), "aria-label": "Effacer" }, "⌫")),
    h("div", { class: "spacer" }),
    h("button", { class: "primary big block", onclick: () => { if (+v) { closeSheet(); charge(+v); } } }, "⚡ ", t("charge")),
    h("button", { class: "ghost block", onclick: closeSheet }, t("close")));
}

function productSheet() {
  const name = h("input", { maxlength: 40, required: true });
  const price = h("input", { inputmode: "numeric", pattern: "[0-9]*", maxlength: 7, required: true });
  const emoji = h("input", { maxlength: 8 });
  const err = h("p", { class: "err", role: "alert" });
  const list = h("ul", { class: "list" }, ...S.products.map((p) => h("li", {},
    h("span", { class: "grow" }, `${p.emoji} ${p.name} · ${fcfa(p.price_xof)}`),
    h("button", { class: "danger", onclick: async () => { await api(`/api/products/${p.id}`, { method: "DELETE" }).catch(fail); S.products = await api("/api/products"); closeSheet(); posScreen(); } }, t("remove")))));
  openSheet(h("h2", {}, t("add_product")),
    h("form", { onsubmit: async (e) => {
      e.preventDefault();
      try {
        await api("/api/products", { method: "POST", body: { name: name.value.trim(), price_xof: +price.value, emoji: emoji.value.trim() } });
        S.products = await api("/api/products");
        closeSheet(); posScreen();
      } catch (er) { err.textContent = errText(er, S.lang); }
    } },
    h("label", {}, t("product_name"), name), h("label", {}, t("price"), price), h("label", {}, t("emoji"), emoji), err,
    h("button", { class: "primary block" }, t("save"))),
    h("div", { class: "spacer" }), list,
    h("button", { class: "ghost block", onclick: closeSheet }, t("close")));
}

async function charge(amount) {
  const body = amount ? { amount_xof: amount } : { items: [...S.cart.values()].map(({ name, qty, unit_xof }) => ({ name, qty, unit_xof })) };
  try {
    const p = await api("/api/sales", { method: "POST", body });
    paySheet(p, () => { S.cart.clear(); });
  } catch (e) {
    fail(e);
  }
}

// ---------------- payment sheet ----------------

function paySheet(p, onPaid) {
  const qr = h("div", { class: "qr" });
  const status = h("div", { class: "wait" });
  const actions = h("div", { class: "stack" });
  let current = p;
  let timer;

  const drawQr = () => {
    qr.replaceChildren(h("img", { src: `/api/pay/${current.token}/qr.svg?h=${current.invoice_expires_at}`, alt: "QR Lightning", width: 300, height: 300 }));
    clearInterval(timer);
    const tickExp = () => {
      const left = (current.invoice_expires_at || 0) - Math.floor(Date.now() / 1000);
      if (left <= 0) {
        clearInterval(timer);
        status.replaceChildren(h("span", {}, t("expired")), h("button", { onclick: reissue }, "↻ ", t("new_qr")));
      } else {
        status.replaceChildren(h("span", { class: "dot", "aria-hidden": "true" }), h("span", {}, t("waiting")), h("span", { class: "muted small" }, `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`));
      }
    };
    tickExp();
    timer = setInterval(tickExp, 1000);
  };
  const reissue = async () => {
    try { current = await api(`/api/payments/${current.token}/invoice`, { method: "POST" }); drawQr(); } catch (e) { fail(e); }
  };
  const done = (row) => {
    stop();
    clearInterval(timer);
    onPaid?.();
    chime();
    const paid = h("div", { class: "paid", role: "alert" }, h("div", {},
      h("div", { class: "tick", "aria-hidden": "true" }, "✓"),
      h("h1", {}, t("paid"), row.method === "cash" ? ` · ${t("cash_short")}` : " · Lightning ⚡"),
      h("div", { class: "amt" }, fcfa(row.amount_xof)),
      h("button", { class: "big", onclick: () => { closeSheet(); route(); } }, t("next_sale"))));
    $sheet.replaceChildren(paid);
    paid.querySelector("button").focus();
  };
  const stop = poll(async () => {
    const row = await api(`/api/payments/${current.token}`);
    if (row.status === "paid") { done(row); return true; }
    if (row.status === "cancelled") { closeSheet(); return true; }
    return false;
  });
  S.stopPoll = () => { stop(); clearInterval(timer); };

  actions.append(
    h("button", { class: "block", onclick: async () => toast((await copy(current.bolt11)) ? t("copied") : current.bolt11) }, "📋 ", t("copy_inv")),
    h("button", { class: "block", onclick: async () => { try { done(await api(`/api/payments/${current.token}/cash`, { method: "POST" })); } catch (e) { fail(e); } } }, "💵 ", t("cash")),
  );
  if (S.status.demo_mode) {
    actions.prepend(h("button", { class: "bolt block", onclick: async (ev) => {
      ev.currentTarget.disabled = true;
      try { await api(`/api/demo/pay/${current.token}`, { method: "POST" }); } catch (e) { fail(e); ev.currentTarget.disabled = false; }
    } }, "📱 ", t("demo_pay")));
  }
  actions.append(h("button", { class: "ghost danger block", onclick: async () => { await api(`/api/payments/${current.token}/cancel`, { method: "POST" }).catch(() => {}); closeSheet(); } }, t("cancel")));

  openSheet(h("p", { class: "muted" }, t("pay_title")),
    h("div", { class: "amount" }, fcfa(p.amount_xof)),
    h("p", { class: "muted small" }, `≈ ${sats(p.amount_sats)}`),
    qr, status, actions);
  drawQr();
}

function openSheet(...kids) {
  $sheet.replaceChildren(h("div", { class: "inner stack" }, ...kids));
  $sheet.hidden = false;
  document.body.style.overflow = "hidden";
  $sheet.querySelector("button, input")?.focus();
}

function closeSheet() {
  S.stopPoll?.();
  S.stopPoll = null;
  $sheet.hidden = true;
  $sheet.replaceChildren();
  document.body.style.overflow = "";
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$sheet.hidden) closeSheet(); });

// ---------------- ardoises ----------------

async function creditsScreen() {
  render(header(t("credits_title")), h("p", { class: "muted" }, "…"));
  let rows;
  try { rows = await api("/api/payments?kind=credit"); } catch (e) { return fail(e); }
  const open = rows.filter((r) => r.status === "open");
  const totalOpen = open.reduce((a, r) => a + r.amount_xof, 0);
  render(header(t("credits_title")),
    h("p", { class: "muted" }, t("credits_open", { n: open.length, t: fcfa(totalOpen) })),
    h("button", { class: "primary block big", onclick: () => creditSheet() }, "＋ ", t("new_credit")),
    h("div", { class: "spacer" }),
    rows.length ? h("ul", { class: "list card" }, ...rows.map(creditRow)) : h("p", { class: "empty card" }, t("no_credits")));
}

function creditRow(r) {
  const age = Math.max(0, Math.floor((Date.now() / 1000 - r.created_at) / 86400));
  const li = h("li", {},
    h("div", { class: "grow" },
      h("div", { class: "who" }, r.customer),
      h("div", { class: "small muted" }, [r.note, age ? `${age} j` : ""].filter(Boolean).join(" · "))),
    h("div", { class: "amt" }, fcfa(r.amount_xof)));
  if (r.status === "open") {
    li.append(h("button", { "aria-label": `${t("share")} ${r.customer}`, onclick: () => shareCredit(r) }, "📤"));
    li.append(h("button", { "aria-label": `${t("cash")} ${r.customer}`, onclick: async () => {
      try { await api(`/api/payments/${r.token}/cash`, { method: "POST" }); toast(`${r.customer} · ${t("paid")}`); creditsScreen(); } catch (e) { fail(e); }
    } }, "💵"));
  } else {
    li.append(h("span", { class: `tag ${r.method === "lightning" ? "ln" : ""}` }, r.method === "lightning" ? "⚡" : "💵", " ", t("paid")));
  }
  return li;
}

function shareCredit(r) {
  const text = t("share_msg", { c: r.customer, s: S.status.shop_name, a: fcfa(r.amount_xof), u: r.pay_url });
  openSheet(h("h2", {}, "📤 ", t("share"), " · ", r.customer),
    h("p", { class: "reply" }, text),
    h("a", { class: "btn primary big block", href: `https://wa.me/?text=${encodeURIComponent(text)}`, target: "_blank", rel: "noopener" }, "WhatsApp"),
    navigator.share ? h("button", { class: "block", onclick: () => navigator.share({ text }).catch(() => {}) }, t("share_other")) : null,
    h("button", { class: "block", onclick: async () => toast((await copy(r.pay_url)) ? t("copied") : r.pay_url) }, "📋 ", t("copy_link")),
    h("a", { class: "btn block", href: r.pay_url, target: "_blank", rel: "noopener" }, "👁 ", t("open_client")),
    h("button", { class: "ghost block", onclick: closeSheet }, t("close")));
}

function creditSheet(prefill = {}) {
  const customer = h("input", { maxlength: 30, required: true, value: prefill.customer || "", autocomplete: "off" });
  const amount = h("input", { inputmode: "numeric", pattern: "[0-9]*", maxlength: 7, required: true, value: prefill.amount_xof || "" });
  const note = h("input", { maxlength: 60, value: prefill.note || "" });
  const err = h("p", { class: "err", role: "alert" });
  openSheet(h("h2", {}, t("new_credit")),
    h("form", { onsubmit: async (e) => {
      e.preventDefault();
      try {
        const r = await api("/api/credits", { method: "POST", body: { customer: customer.value.trim(), amount_xof: +amount.value, note: note.value.trim() } });
        history.replaceState(null, "", "#ardoises"); // no hashchange: keep the share sheet open
        route();
        shareCredit(r);
      } catch (er) { err.textContent = errText(er, S.lang); }
    } },
    h("label", {}, t("customer"), customer), h("label", {}, t("amount"), amount), h("label", {}, t("note"), note), err,
    h("button", { class: "primary block big" }, t("save_share"))),
    h("button", { class: "ghost block", onclick: closeSheet }, t("close")));
}

// ---------------- journal ----------------

async function salesScreen() {
  render(header(t("sales_title")), h("p", { class: "muted" }, "…"));
  let s, rows;
  try { [s, rows] = await Promise.all([api("/api/summary"), api("/api/payments?kind=sale")]); } catch (e) { return fail(e); }
  const start = s.day_start;
  const today = rows.filter((r) => r.paid_at >= start);
  const stat = (label, value, sub) => h("div", { class: "card stat" }, h("span", { class: "small muted" }, label), h("b", {}, value), sub ? h("span", { class: "small muted" }, sub) : null);
  render(header(t("sales_title")),
    h("p", { class: "reply" }, s.text),
    h("div", { class: "stats" },
      stat(t("total"), fcfa(s.total_xof), `${s.sales_count} ${t("sale").toLowerCase()}(s)`),
      stat(t("lightning"), fcfa(s.lightning_xof), sats(s.lightning_sats)),
      stat(t("cash_short"), fcfa(s.cash_xof)),
      stat(t("open_credits"), fcfa(s.open_credits_xof), String(s.open_credits))),
    h("div", { class: "spacer" }),
    today.length ? h("ul", { class: "list card" }, ...today.map((r) => h("li", {},
      h("div", { class: "grow" },
        h("div", {}, r.items.map((i) => `${i.qty}× ${i.name}`).join(", ") || t("sale")),
        h("div", { class: "small muted" }, new Date(r.paid_at * 1000).toLocaleTimeString(S.lang === "fr" ? "fr-FR" : "en-GB", { hour: "2-digit", minute: "2-digit" }))),
      h("span", { class: `tag ${r.method === "lightning" ? "ln" : ""}` }, r.method === "lightning" ? "⚡" : "💵"),
      h("span", { class: "amt" }, fcfa(r.amount_xof))))) : h("p", { class: "empty card" }, t("no_sales")));
}

// ---------------- wallet ----------------

async function walletScreen() {
  render(header(t("wallet_title")), h("p", { class: "muted" }, "…"));
  let w;
  try { w = await api("/api/wallet"); } catch (e) { return fail(e); }
  const addr = h("div");
  const send = h("div", { class: "stack" });
  const inv = h("input", { placeholder: t("paste_inv"), autocomplete: "off", autocapitalize: "off", spellcheck: "false" });
  const err = h("p", { class: "err", role: "alert" });

  const check = async () => {
    err.textContent = "";
    try {
      const d = await api("/api/wallet/decode", { method: "POST", body: { bolt11: inv.value.trim() } });
      if (d.expired) { err.textContent = errText({ code: "invoice_expired" }, S.lang); return; }
      const pin = h("input", { type: "password", inputmode: "numeric", pattern: "[0-9]*", maxlength: 8, autocomplete: "off", "aria-label": "PIN" });
      send.replaceChildren(h("div", { class: "card stack" },
        h("div", { class: "amount" }, fcfa(d.amount_xof)), h("p", { class: "muted small" }, `${sats(d.amount_sats)} · ${d.description || "—"}`),
        h("label", {}, t("confirm_send"), pin),
        h("button", { class: "primary block", onclick: async (ev) => {
          ev.currentTarget.disabled = true;
          try {
            const r = await api("/api/wallet/pay", { method: "POST", body: { bolt11: inv.value.trim(), pin: pin.value } });
            chime(); toast(`${t("sent")} · ${fcfa(r.amount_xof)}`); walletScreen();
          } catch (e) {
            ev.currentTarget.disabled = false;
            err.textContent = e.data?.locked_for ? t("locked", { s: e.data.locked_for }) : errText(e, S.lang);
          }
        } }, t("send")), err));
      pin.focus();
    } catch (e) { err.textContent = errText(e, S.lang); }
  };

  const demoBox = S.status.demo_mode ? h("section", { class: "card stack" },
    h("h2", {}, "📱 ", t("demo_wallet")), h("p", { class: "small muted" }, t("demo_explain")),
    h("button", { class: "block", onclick: async () => {
      try { const r = await api("/api/demo/invoice", { method: "POST", body: { amount_xof: 1000 } }); inv.value = r.bolt11; check(); } catch (e) { fail(e); }
    } }, t("demo_invoice"))) : null;

  render(header(t("wallet_title")),
    h("section", { class: "card" },
      h("span", { class: "small muted" }, t("balance")), h("div", { class: "amount" }, fcfa(w.lightning_xof)),
      h("p", { class: "muted small" }, `${sats(w.lightning_sats)} · ${t("inbound")} ${sats(w.inbound_sats)}`),
      h("p", { class: "small" }, `${t("onchain")} : ${fcfa(w.onchain_xof)} (${sats(w.onchain_sats)})`),
      h("p", { class: "small muted" }, t("limit", { s: fcfa(w.sent_today_xof), l: fcfa(w.daily_limit_xof) }))),
    h("div", { class: "spacer" }),
    h("section", { class: "card stack" }, h("h2", {}, t("send")), inv, h("button", { class: "block", onclick: check }, t("check")), send, err),
    h("div", { class: "spacer" }),
    demoBox, demoBox ? h("div", { class: "spacer" }) : null,
    h("section", { class: "card stack" },
      h("button", { class: "block", onclick: async () => {
        try { const r = await api("/api/wallet/address", { method: "POST" }); addr.replaceChildren(h("p", { class: "mono" }, r.address), h("button", { class: "block", onclick: async () => toast((await copy(r.address)) ? t("copied") : r.address) }, "📋")); } catch (e) { fail(e); }
      } }, "⛓️ ", t("receive_onchain")), addr),
    h("div", { class: "spacer" }),
    h("div", { class: "row" },
      h("button", { class: "grow", onclick: toggleLang }, t("lang")),
      h("button", { class: "grow danger", onclick: async () => { await api("/api/logout", { method: "POST" }).catch(() => {}); boot(); } }, t("logout"))));
}

// ---------------- offline + service worker ----------------

const $off = document.getElementById("offline");
const net = () => ($off.hidden = navigator.onLine);
addEventListener("online", net);
addEventListener("offline", net);
net();
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});

boot();
