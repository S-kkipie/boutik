"""Assistant: Claude when configured, offline French parser otherwise."""

from __future__ import annotations

import logging

from pydantic import ValidationError

from . import rules
from .types import Draft, DraftItem, Product

log = logging.getLogger("boutik.assistant")

__all__ = ["Assistant", "Draft", "DraftItem", "Product"]


class Assistant:
    def __init__(self, api_key: str = "", model: str = "claude-opus-5-5"):
        self._claude = None
        if api_key:
            from .claude import ClaudeParser

            self._claude = ClaudeParser(api_key, model)

    @property
    def engine(self) -> str:
        return "claude" if self._claude else "local"

    async def parse(self, text: str, catalog: list[Product]) -> Draft:
        if self._claude:
            try:
                return await self._claude.parse(text, catalog)
            except (ValidationError, ValueError, StopIteration) as e:
                log.warning("assistant: invalid LLM output (%s), using local parser", type(e).__name__)
            except Exception as e:  # network, auth, rate limit: never block the counter
                log.warning("assistant: LLM unavailable (%s), using local parser", type(e).__name__)
        return rules.parse(text, catalog)
