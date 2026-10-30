"""Offline French parser for counter talk.

Works with no network and no API key, so the assistant degrades gracefully
on 2G or when the LLM is unavailable. Examples it understands:

    "2 pains et un sucre"         -> cart: 2 x Pain, 1 x Sucre (catalog prices)
    "3 cafés à 100, savon"        -> cart with explicit unit price
    "riz 2 kg 1000"               -> bare number = line total
    "crédit Moussa 2000 riz"      -> ardoise for Moussa
    "Awa me doit 1500"            -> ardoise for Awa
    "ventes d'aujourd'hui ?"      -> summary
    "c'est quoi Lightning ?"      -> explanation
"""

from __future__ import annotations

import re
import unicodedata

from .types import Draft, DraftItem, Product

NUMBER_WORDS = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6,
    "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12,
    "quinze": 15, "vingt": 20, "trente": 30,
}
SUMMARY_RE = re.compile(r"\b(ventes?|vendu|resume|bilan|recette|chiffre|aujourd ?hui|journee)\b")
CREDIT_RE = re.compile(r"\b(credit|ardoise|doit|dette|devoir)\b")
EXPLAIN_RE = re.compile(r"\b(c ?est quoi|qu ?est ?ce|comment|pourquoi|explique)\b|\b(lightning|bitcoin|sats?|satoshis?)\b.*\?")
PRICE_RE = re.compile(r"(?:\ba\s+)?(\d[\d\s]{0,9})\s*(?:f|fr|francs?|fcfa|cfa)?\b")
SPLIT_RE = re.compile(r",|;|\+|\bet\b|\bpuis\b|\bavec\b")
STOP = {"de", "du", "des", "le", "la", "les", "l", "d", "pour", "a", "au", "kg", "kilo", "kilos",
        "litre", "litres", "l'unite", "unite", "chacun", "chacune", "piece", "pieces", "sachet",
        "sachets", "f", "fr", "franc", "francs", "fcfa", "cfa", "me", "il", "elle", "doit",
        "credit", "ardoise", "dette", "total"}

EXPLAIN_TEXT = (
    "Lightning, c'est de l'argent numérique (bitcoin) qui arrive en 2 secondes, "
    "sans monnaie à rendre et presque sans frais. Le client scanne le QR avec son "
    "portefeuille, vous voyez « Payé ✓ ». Les prix restent en FCFA : Boutik fait la conversion."
)
HELP_TEXT = (
    "Dites par exemple : « 2 pains et un sucre », « crédit Moussa 2000 », "
    "ou « ventes d'aujourd'hui ? »."
)


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("’", "'").replace("'", " ")
    return re.sub(r"\s+", " ", t).strip()


def _singular(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith(("s", "x")) else word


def _product_keys(p: Product) -> set[str]:
    words = [w for w in norm(p.name).split() if w.isalpha() and w not in STOP]
    return {_singular(w) for w in words[:1]} | ({" ".join(words)} if len(words) > 1 else set())


def _match_product(segment_words: list[str], catalog: list[Product]) -> Product | None:
    sing = {_singular(w) for w in segment_words}
    joined = " ".join(_singular(w) for w in segment_words)
    best = None
    for p in catalog:
        for key in _product_keys(p):
            if key in sing or (" " in key and key in joined):
                if best is None or len(key) > len(best[1]):
                    best = (p, key)
    return best[0] if best else None


def _to_int(s: str) -> int:
    return int(re.sub(r"\s", "", s))


def _parse_segment(seg: str, catalog: list[Product]) -> DraftItem | None:
    seg = seg.strip()
    if not seg:
        return None
    words = seg.split()
    qty = 1
    if words and (words[0].isdigit() or words[0] in NUMBER_WORDS):
        candidate = int(words[0]) if words[0].isdigit() else NUMBER_WORDS[words[0]]
        rest = " ".join(words[1:])
        # "2 pains" -> qty; "1500" alone -> a price, handled below.
        if rest and not rest.split()[0].isdigit() and candidate < 100:
            qty = candidate
            words = words[1:]
    rest_text = " ".join(words)
    unit_price = None
    line_total = None
    explicit_unit = re.search(r"\ba\s+(\d[\d\s]{0,9})", rest_text) or re.search(
        r"(\d[\d\s]{0,9})\s*(?:f|fr|francs?|fcfa)?\s*(?:l unite|chacun|chacune|piece)", rest_text
    )
    if explicit_unit:
        unit_price = _to_int(explicit_unit.group(1))
    else:
        nums = [int(n) for n in re.findall(r"\b\d{2,7}\b", rest_text)]
        big = [n for n in nums if n >= 25]
        if big:
            line_total = big[-1]
    name_words = [w for w in re.sub(r"\d+", " ", rest_text).split() if w not in STOP and w.isalpha()]
    product = _match_product(name_words, catalog)
    if product:
        name = product.name
        if unit_price is None:
            unit_price = round(line_total / qty) if line_total else product.price_xof
    else:
        if unit_price is None and line_total is None:
            return None
        name = " ".join(name_words).capitalize() or "Montant libre"
        if unit_price is None:
            unit_price = round(line_total / qty)
    if unit_price <= 0:
        return None
    return DraftItem(name=name[:40], qty=qty, unit_xof=unit_price)


def parse(text: str, catalog: list[Product]) -> Draft:
    t = norm(text)
    if not t:
        return Draft(intent="unknown", reply=HELP_TEXT)
    if EXPLAIN_RE.search(t) and not CREDIT_RE.search(t):
        return Draft(intent="explain", reply=EXPLAIN_TEXT)
    if CREDIT_RE.search(t):
        amounts = [_to_int(m) for m in re.findall(r"\b\d[\d ]{1,8}\d\b|\b\d{2,}\b", t)]
        amounts = [a for a in amounts if a >= 25]
        # Customer = first capitalised-looking word in the original text that is not a keyword.
        raw_words = re.findall(r"[A-Za-zÀ-ÿ'-]+", text)
        customer = next(
            (w for w in raw_words if w[:1].isupper() and norm(w) not in STOP and norm(w) not in
             {"credit", "ardoise", "pour", "il", "elle"}),
            "",
        )
        if not customer:
            words = [w for w in t.split() if w.isalpha() and w not in STOP]
            customer = words[0].capitalize() if words else ""
        if amounts and customer:
            note_words = [w for w in t.split() if w.isalpha() and w not in STOP and norm(customer) != w]
            return Draft(
                intent="credit",
                customer=customer[:30],
                amount_xof=amounts[0],
                note=" ".join(note_words)[:60],
                reply=f"Ardoise pour {customer} : {amounts[0]} FCFA. Confirmer ?",
            )
        return Draft(intent="unknown", reply="Pour une ardoise, dites : « crédit Moussa 2000 ».")
    if SUMMARY_RE.search(t) and not re.search(r"\d", t):
        return Draft(intent="summary")
    items = [i for i in (_parse_segment(s, catalog) for s in SPLIT_RE.split(t)) if i]
    if items:
        return Draft(intent="cart", items=items, reply="Panier prêt. Vérifiez puis encaissez.")
    return Draft(intent="unknown", reply=HELP_TEXT)
