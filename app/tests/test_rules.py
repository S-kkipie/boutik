import pytest

from boutik.assistant import rules
from boutik.assistant.types import Product
from boutik.db import DEMO_PRODUCTS

CATALOG = [Product(id=i, name=n, emoji=e, price_xof=p) for i, (n, e, p) in enumerate(DEMO_PRODUCTS, 1)]


def cart(text):
    d = rules.parse(text, CATALOG)
    assert d.intent == "cart", d
    return [(i.name, i.qty, i.unit_xof) for i in d.items]


def test_catalog_items_with_number_words():
    assert cart("2 pains et un sucre") == [("Pain", 2, 150), ("Sucre 1 kg", 1, 700)]


def test_plural_and_accents():
    assert cart("trois cafés Touba, savon") == [("Café Touba", 3, 100), ("Savon", 1, 300)]


def test_explicit_unit_price_overrides_catalog():
    assert cart("3 pains à 175") == [("Pain", 3, 175)]


def test_bare_number_is_line_total():
    assert cart("2 riz 1100") == [("Riz 1 kg", 2, 550)]


def test_unknown_item_with_price():
    assert cart("piles 500 f") == [("Piles", 1, 500)]


def test_amount_only():
    assert cart("5000") == [("Montant libre", 1, 5000)]


def test_credit_named_customer():
    d = rules.parse("crédit Moussa 2000 pour riz", CATALOG)
    assert (d.intent, d.customer, d.amount_xof) == ("credit", "Moussa", 2000)


def test_credit_doit_phrase():
    d = rules.parse("Awa me doit 1 500", CATALOG)
    assert (d.intent, d.customer, d.amount_xof) == ("credit", "Awa", 1500)


@pytest.mark.parametrize("text", ["ventes d'aujourd'hui ?", "Bilan de la journée", "combien j'ai vendu"])
def test_summary(text):
    assert rules.parse(text, CATALOG).intent == "summary"


def test_explain():
    d = rules.parse("C'est quoi Lightning ?", CATALOG)
    assert d.intent == "explain" and "FCFA" in d.reply


def test_gibberish_is_unknown():
    assert rules.parse("bonjour", CATALOG).intent == "unknown"
