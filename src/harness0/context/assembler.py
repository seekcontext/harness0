"""ContextAssembler — L1, the heart of multi-layer context assembly."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import tiktoken

from harness0.core.types import Message, TurnContext

from .layers import ContextLayer, DisclosureLevel

if TYPE_CHECKING:
    from harness0.core.config import ContextConfig

logger = logging.getLogger(__name__)

_ENCODING = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def _truncate_to_budget(text: str, max_tokens: int) -> str:
    tokens = _ENCODING.encode(text)
    if len(tokens) <= max_tokens:
        return text
    truncated = _ENCODING.decode(tokens[:max_tokens])
    return truncated + f"\n\n[...truncated to {max_tokens} tokens]"


class ContextAssembler:
    """
    L1: Assembles the system prompt from multiple ContextLayers each turn.

    Assembly strategy:
      1. Select layers: always include INDEX layers; include DETAIL layers only
         when the task contains their declared keywords.
      2. Load content with freshness-aware caching.
      3. Sort selected layers by priority (ascending — lower priority first, so
         higher-priority content appears later and is closer to the LLM call).
      4. Apply per-layer and total token budgets, dropping lowest-priority
         layers that exceed the budget.
      5. Emit a single system Message containing all assembled content.
    """

    def __init__(
        self,
        layers: list[ContextLayer],
        total_token_budget: int = 8000,
    ) -> None:
        self.layers = sorted(layers, key=lambda layer: layer.priority)
        self.total_token_budget = total_token_budget

    @classmethod
    def from_config(cls, config: ContextConfig) -> ContextAssembler:
        layers = [ContextLayer.from_config(lc) for lc in config.layers]
        return cls(layers=layers, total_token_budget=config.total_token_budget)

    async def assemble(self, turn_context: TurnContext) -> list[Message]:
        """
        Build the list of messages to prepend to the LLM call for this turn.
        Returns a list containing a single system message with all assembled context.
        """
        selected = self._select_layers(turn_context.task)
        if not selected:
            return []

        loaded: list[tuple[ContextLayer, str]] = []
        for layer in selected:
            try:
                content = await layer.get_content(session_id=turn_context.session_id)
                loaded.append((layer, content))
            except Exception as exc:
                logger.warning("Failed to load context layer %r: %s", layer.name, exc)

        assembled = self._apply_budgets(loaded)
        if not assembled:
            return []

        system_content = "\n\n".join(assembled)
        return [Message(role="system", content=system_content)]

    def _select_layers(self, task: str) -> list[ContextLayer]:
        """Apply progressive disclosure: always include INDEX, selectively include DETAIL."""
        selected = []
        for layer in self.layers:
            if layer.disclosure_level == DisclosureLevel.INDEX:
                selected.append(layer)
            elif layer.is_relevant_for_task(task):
                selected.append(layer)
                logger.debug(
                    "DETAIL layer %r selected for task (keyword match)", layer.name
                )
            else:
                logger.debug(
                    "DETAIL layer %r skipped (no keyword match for task)", layer.name
                )
        return selected

    def _apply_budgets(self, loaded: list[tuple[ContextLayer, str]]) -> list[str]:
        """
        Apply per-layer and total token budgets.
        Drops layers that exceed the total budget, starting from lowest priority.
        """
        result_parts: list[tuple[int, str]] = []
        remaining = self.total_token_budget

        for layer, content in loaded:
            if layer.max_tokens:
                content = _truncate_to_budget(content, layer.max_tokens)

            token_count = _count_tokens(content)
            if token_count > remaining:
                if layer.disclosure_level == DisclosureLevel.INDEX:
                    # INDEX layers get truncated rather than dropped
                    content = _truncate_to_budget(content, max(remaining - 50, 100))
                    token_count = _count_tokens(content)
                    logger.warning(
                        "INDEX layer %r truncated to fit token budget", layer.name
                    )
                else:
                    logger.warning(
                        "DETAIL layer %r dropped: exceeds remaining token budget "
                        "(%d tokens needed, %d remaining)",
                        layer.name,
                        token_count,
                        remaining,
                    )
                    continue

            result_parts.append((layer.priority, content))
            remaining -= token_count

        result_parts.sort(key=lambda x: x[0])
        return [content for _, content in result_parts]

    def add_layer(self, layer: ContextLayer) -> None:
        """Dynamically add a layer at runtime."""
        self.layers.append(layer)
        self.layers.sort(key=lambda layer: layer.priority)

    def remove_layer(self, name: str) -> bool:
        """Remove a layer by name. Returns True if found and removed."""
        before = len(self.layers)
        self.layers = [layer for layer in self.layers if layer.name != name]
        return len(self.layers) < before
