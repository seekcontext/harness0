"""EntropyManager — L5 orchestrator: detect degradation, compress, and garden."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import tiktoken

from .gardener import EntropyGardener, GardenAction

if TYPE_CHECKING:
    from harness0.context.layers import ContextLayer
    from harness0.core.config import EntropyConfig
    from harness0.core.types import Message, TurnContext
    from harness0.feedback.translator import FeedbackTranslator
    from harness0.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_ENCODING = tiktoken.get_encoding("cl100k_base")


def _count_tokens(messages: list[Message]) -> int:
    return sum(len(_ENCODING.encode(m.content)) for m in messages)


class EntropyManager:
    """
    L5: Active context quality maintenance.

    Responsibilities:
      1. Compression — trim bloated conversation history when approaching budget.
      2. Decay detection — flag stale rules / tool results in the message history.
      3. Gardening — delegate periodic quality checks to EntropyGardener.

    Unlike LangChain's summarization (triggered only at token limit, blunt),
    harness0 detects and repairs multiple degradation types proactively.
    """

    def __init__(
        self,
        config: EntropyConfig,
        translator: FeedbackTranslator,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.config = config
        self.translator = translator
        self.gardener = EntropyGardener(
            config=config,
            translator=translator,
            tool_registry=tool_registry,
        )

    async def process(
        self,
        messages: list[Message],
        turn_context: TurnContext,
        context_layers: list[ContextLayer] | None = None,
    ) -> tuple[list[Message], list[GardenAction]]:
        """
        Run the full L5 pipeline on the current message history.

        Returns:
          - Cleaned/compressed message list
          - GardenActions produced this turn (may be empty if gardener didn't fire)
        """
        messages = self._detect_and_remove_stale_signals(messages)
        messages = self._deduplicate_tool_results(messages)
        messages = self._compress_if_needed(messages)

        garden_actions: list[GardenAction] = []
        if context_layers is not None:
            garden_actions = await self.gardener.maybe_garden(context_layers)

        return messages, garden_actions

    # ── Degradation detection ─────────────────────────────────────────────────

    def _detect_and_remove_stale_signals(self, messages: list[Message]) -> list[Message]:
        """
        Remove harness:signal blocks that are older than decay_check_interval turns.
        Stale signals clutter context and cause the agent to over-index on old constraints.
        """
        cleaned: list[Message] = []
        signal_count = 0
        for msg in messages:
            if "<harness:signals>" in msg.content and msg.role == "system":
                signal_count += 1
                if signal_count > self.config.decay_check_interval:
                    logger.debug("Removing stale harness:signal block from message history.")
                    continue
            cleaned.append(msg)
        return cleaned

    def _deduplicate_tool_results(self, messages: list[Message]) -> list[Message]:
        """
        Remove duplicate consecutive tool result messages (same tool, identical output).
        Repetition wastes tokens and anchors the model on redundant information.
        """
        cleaned: list[Message] = []
        seen_tool_outputs: set[str] = set()

        for msg in messages:
            if msg.role == "tool":
                key = f"{msg.name}::{msg.content[:200]}"
                if key in seen_tool_outputs:
                    logger.debug("Deduplicating repeated tool result: %s", msg.name)
                    continue
                seen_tool_outputs.add(key)
            cleaned.append(msg)

        return cleaned

    # ── Compression ───────────────────────────────────────────────────────────

    def _compress_if_needed(self, messages: list[Message]) -> list[Message]:
        """
        If total message tokens exceed the compression threshold, trim the oldest
        non-system, non-first-user messages. Preserves the first user message
        (the task) and all system messages.
        """
        total = _count_tokens(messages)
        if total <= self.config.compression_threshold:
            return messages

        logger.info(
            "Context compression triggered: %d tokens > threshold %d",
            total, self.config.compression_threshold,
        )

        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        if not non_system:
            return messages

        first_user = next((m for m in non_system if m.role == "user"), None)
        rest = [m for m in non_system if m is not first_user]

        # Drop oldest messages from rest until under threshold
        keep = [first_user] if first_user else []
        while rest and _count_tokens(system_msgs + keep + rest) > self.config.compression_threshold:
            dropped = rest.pop(0)
            logger.debug(
                "Compression: dropped %s message (%d chars)", dropped.role, len(dropped.content)
            )

        rebuilt = system_msgs + keep + rest
        new_total = _count_tokens(rebuilt)
        logger.info("Compression complete: %d → %d tokens", total, new_total)
        return rebuilt

    # ── Conflict detection ────────────────────────────────────────────────────

    def detect_conflicts(self, messages: list[Message]) -> list[str]:
        """
        Heuristic scan for contradictory instructions across system messages.
        Returns a list of human-readable conflict descriptions.
        """
        if not self.config.detect_conflicts:
            return []

        system_contents = [m.content.lower() for m in messages if m.role == "system"]
        conflicts: list[str] = []

        import re

        pairs = [
            ("always ", "never "),
            ("must ", "must not "),
            ("required: ", "forbidden: "),
        ]

        for i, content_a in enumerate(system_contents):
            for content_b in system_contents[i + 1:]:
                for pos, neg in pairs:
                    pos_subjects = {
                        m.group(1) for m in re.finditer(rf"{re.escape(pos)}(\w+)", content_a)
                    }
                    neg_subjects = {
                        m.group(1) for m in re.finditer(rf"{re.escape(neg)}(\w+)", content_b)
                    }
                    overlap = pos_subjects & neg_subjects
                    if overlap:
                        conflicts.append(
                            f"Conflict: system messages disagree about: {', '.join(overlap)}"
                        )

        return conflicts
