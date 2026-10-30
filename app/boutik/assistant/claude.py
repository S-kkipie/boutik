"""Claude-backed parser. Only drafts; the result is re-validated by Pydantic
and the server recomputes every total before anything reaches LND."""

from __future__ import annotations

import json
import logging

import anthropic

from .types import Draft, Product

log = logging.getLogger("boutik.assistant")

SYSTEM = """Tu es l'assistant de caisse d'une boutique de quartier au Sénégal.
Le commerçant te parle en français (parfois avec des mots wolof). Les prix sont en FCFA.
Transforme sa phrase en une intention JSON:
- "cart": il vend des articles. Remplis items (name, qty, unit_xof). Utilise le nom et le prix
  du catalogue quand l'article y est; sinon prends le prix dit par le commerçant.
  Un nombre seul après l'article est le total de la ligne: divise par qty pour unit_xof.
- "credit": un client prend à crédit (ardoise). Remplis customer (prénom), amount_xof, note.
- "summary": il demande ses ventes, son bilan ou sa recette.
- "explain": il pose une question sur Bitcoin/Lightning. Réponds dans reply en 2 ou 3 phrases
  simples, sans jargon, en français.
- "unknown": sinon; mets dans reply un exemple de phrase à dire.
reply: une phrase courte en français pour le commerçant.
Tu ne peux ni payer ni envoyer d'argent: tu proposes seulement un brouillon."""

SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["cart", "credit", "summary", "explain", "unknown"]},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "qty": {"type": "integer"},
                    "unit_xof": {"type": "integer"},
                },
                "required": ["name", "qty", "unit_xof"],
                "additionalProperties": False,
            },
        },
        "customer": {"type": "string"},
        "amount_xof": {"type": "integer"},
        "note": {"type": "string"},
        "reply": {"type": "string"},
    },
    "required": ["intent", "items", "customer", "amount_xof", "note", "reply"],
    "additionalProperties": False,
}


class ClaudeParser:
    def __init__(self, api_key: str, model: str):
        self.model = model
        self.client = anthropic.AsyncAnthropic(api_key=api_key, timeout=12.0, max_retries=1)

    async def parse(self, text: str, catalog: list[Product]) -> Draft:
        menu = "\n".join(f"- {p.name}: {p.price_xof} FCFA" for p in catalog)
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=SYSTEM,
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            messages=[
                {
                    "role": "user",
                    "content": f"Catalogue:\n{menu}\n\nPhrase du commerçant:\n{text}",
                }
            ],
        )
        if response.stop_reason in ("refusal", "max_tokens"):
            raise ValueError(f"assistant stopped: {response.stop_reason}")
        raw = next(b.text for b in response.content if b.type == "text")
        data = json.loads(raw)
        data["engine"] = "claude"
        return Draft.model_validate(data)
