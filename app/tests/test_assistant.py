import json
from types import SimpleNamespace

import pytest

from boutik.assistant import Assistant
from boutik.assistant.types import Product

CATALOG = [Product(id=1, name="Pain", emoji="🥖", price_xof=150)]


def fake_response(payload, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=json.dumps(payload))],
    )


@pytest.fixture
def assistant():
    return Assistant(api_key="test-key", model="claude-opus-5-5")


async def test_claude_draft_is_validated_and_tagged(assistant, monkeypatch):
    seen = {}

    async def create(**kw):
        seen.update(kw)
        return fake_response({"intent": "cart", "items": [{"name": "Pain", "qty": 2, "unit_xof": 150}],
                              "customer": "", "amount_xof": 0, "note": "", "reply": "Panier prêt."})

    monkeypatch.setattr(assistant._claude.client.messages, "create", create)
    d = await assistant.parse("deux pains", CATALOG)
    assert d.engine == "claude" and d.total_xof == 300
    assert seen["output_config"]["format"]["type"] == "json_schema"
    assert "Pain: 150 FCFA" in seen["messages"][0]["content"]


async def test_out_of_bounds_llm_output_falls_back_to_local(assistant, monkeypatch):
    async def create(**kw):
        return fake_response({"intent": "cart", "items": [{"name": "Pain", "qty": 5000, "unit_xof": 150}],
                              "customer": "", "amount_xof": 0, "note": "", "reply": ""})

    monkeypatch.setattr(assistant._claude.client.messages, "create", create)
    d = await assistant.parse("2 pains", CATALOG)
    assert d.engine == "local" and d.items[0].qty == 2


async def test_api_failure_falls_back_to_local(assistant, monkeypatch):
    async def create(**kw):
        raise ConnectionError("offline")

    monkeypatch.setattr(assistant._claude.client.messages, "create", create)
    d = await assistant.parse("2 pains", CATALOG)
    assert d.engine == "local" and d.intent == "cart"


async def test_refusal_falls_back_to_local(assistant, monkeypatch):
    async def create(**kw):
        return fake_response({}, stop_reason="refusal")

    monkeypatch.setattr(assistant._claude.client.messages, "create", create)
    assert (await assistant.parse("2 pains", CATALOG)).engine == "local"
