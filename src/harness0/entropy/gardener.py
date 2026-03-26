"""EntropyGardener — proactive background GC for context quality.

Inspired by OpenAI's "doc-gardening" agent pattern: rather than waiting for token
budget exhaustion, the gardener runs on a fixed interval, applies mechanically
verifiable golden rules, and emits targeted GardenActions instead of blunt compression.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from harness0.feedback.signals import FeedbackSignal
from harness0.feedback.translator import FeedbackTranslator

if TYPE_CHECKING:
    from harness0.context.layers import ContextLayer
    from harness0.core.config import EntropyConfig, GoldenRule
    from harness0.feedback.signals import FeedbackSignal
    from harness0.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class GardenAction(BaseModel):
    """A targeted repair action produced by the gardener."""

    action_type: Literal["remove", "update", "flag"]
    target: str
    reason: str
    severity: Literal["error", "warning", "info"] = "warning"
    fix_instructions: str | None = None
    signal: FeedbackSignal | None = None

    model_config = {"arbitrary_types_allowed": True}


GardenAction.model_rebuild()


class EntropyGardener:
    """
    Proactive context quality enforcer.

    Runs every `gardener_interval_turns` turns via `maybe_garden()`. Each pass:
      1. Checks all context layers for temporal staleness.
      2. Verifies golden rules declared in harness.yaml.
      3. (Optionally) checks the tool registry for duplicate descriptions.

    Returns a list of GardenAction describing what needs attention.
    Each action carries a FeedbackSignal for L4 injection and fix_instructions
    for the agent to act on directly.
    """

    def __init__(
        self,
        config: EntropyConfig,
        translator: FeedbackTranslator | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.config = config
        self.translator = translator
        self.tool_registry = tool_registry
        self._turn_counter = 0

    async def maybe_garden(
        self, layers: list[ContextLayer]
    ) -> list[GardenAction]:
        """Run a gardening pass if the interval has elapsed, otherwise skip."""
        if not self.config.gardener_enabled:
            return []
        self._turn_counter += 1
        if self._turn_counter % self.config.gardener_interval_turns != 0:
            return []
        return await self.garden(layers)

    async def garden(self, layers: list[ContextLayer]) -> list[GardenAction]:
        """Full gardening pass. Returns all detected issues as GardenActions."""
        actions: list[GardenAction] = []
        actions.extend(self._check_staleness(layers))
        actions.extend(self._check_golden_rules(layers))
        if self.tool_registry:
            actions.extend(self._check_tool_duplicates())

        if self.translator:
            for action in actions:
                if action.signal:
                    await self.translator.add(action.signal)

        if actions:
            logger.info(
                "EntropyGardener: %d issue(s) detected at turn %d",
                len(actions), self._turn_counter,
            )

        return actions

    # ── Checkers ──────────────────────────────────────────────────────────────

    def _check_staleness(self, layers: list[ContextLayer]) -> list[GardenAction]:
        actions: list[GardenAction] = []
        threshold_hours = self.config.staleness_threshold_hours

        for layer in layers:
            if layer.is_stale(threshold_hours):
                modified = layer.source.last_modified
                age_hours = (time.time() - modified) / 3600
                signal = FeedbackTranslator.context_stale(layer.name, age_hours)
                actions.append(
                    GardenAction(
                        action_type="flag",
                        target=layer.name,
                        reason=f"Layer is {age_hours:.1f}h old (threshold: {threshold_hours}h)",
                        severity="warning",
                        fix_instructions=signal.fix_instructions,
                        signal=signal,
                    )
                )
        return actions

    def _check_golden_rules(self, layers: list[ContextLayer]) -> list[GardenAction]:
        actions: list[GardenAction] = []

        for rule in self.config.golden_rules:
            checker = _RULE_CHECKERS.get(rule.id)
            if checker is None:
                logger.debug("No built-in checker for golden rule %r — skipping.", rule.id)
                continue
            violations = checker(rule, layers, self.tool_registry)
            actions.extend(violations)

        return actions

    def _check_tool_duplicates(self) -> list[GardenAction]:
        if not self.tool_registry:
            return []
        duplicates = self.tool_registry.has_duplicates()
        actions: list[GardenAction] = []
        for name_a, name_b in duplicates:
            signal = FeedbackTranslator.golden_rule_violated(
                rule_id="no_duplicate_tools",
                description="No two tools may share the same description",
                details=f"Tools `{name_a}` and `{name_b}` have identical descriptions.",
            )
            actions.append(
                GardenAction(
                    action_type="flag",
                    target=f"{name_a},{name_b}",
                    reason="Duplicate tool descriptions make tool selection ambiguous.",
                    severity="error",
                    fix_instructions=(
                        f"1. Tools `{name_a}` and `{name_b}` share the same description.\n"
                        "2. Update one or both descriptions to be distinct and specific.\n"
                        "3. Clear descriptions improve the model's tool selection accuracy."
                    ),
                    signal=signal,
                )
            )
        return actions


# ── Built-in golden rule checkers ─────────────────────────────────────────────

def _check_no_stale_layers(
    rule: GoldenRule,
    layers: list[ContextLayer],
    registry: ToolRegistry | None,
) -> list[GardenAction]:
    """Handled by _check_staleness; this is a no-op when called from golden rules."""
    return []


def _check_no_duplicate_tools(
    rule: GoldenRule,
    layers: list[ContextLayer],
    registry: ToolRegistry | None,
) -> list[GardenAction]:
    """Duplicate tool check is handled separately via _check_tool_duplicates."""
    return []


def _check_no_conflicting_instructions(
    rule: GoldenRule,
    layers: list[ContextLayer],
    registry: ToolRegistry | None,
) -> list[GardenAction]:
    """
    Simple heuristic conflict detector: look for layers that contain opposite directives.
    E.g. one layer says "always use X", another says "never use X".
    """
    actions: list[GardenAction] = []
    negation_pairs = [
        ("always use", "never use"),
        ("must use", "do not use"),
        ("required:", "forbidden:"),
    ]

    layer_contents: list[tuple[str, str]] = []
    for layer in layers:
        if layer._content_cache:
            layer_contents.append((layer.name, layer._content_cache.lower()))

    for i, (name_a, content_a) in enumerate(layer_contents):
        for name_b, content_b in layer_contents[i + 1:]:
            for positive, negative in negation_pairs:
                shared_subjects = _find_shared_subjects(content_a, content_b, positive, negative)
                if shared_subjects:
                    details = f"Conflicting directives about: {', '.join(shared_subjects[:3])}"
                    signal = FeedbackTranslator.golden_rule_violated(
                        rule_id=rule.id,
                        description=rule.description,
                        details=f"Layers `{name_a}` and `{name_b}`: {details}",
                    )
                    actions.append(
                        GardenAction(
                            action_type="flag",
                            target=f"{name_a},{name_b}",
                            reason=details,
                            severity=rule.severity,
                            fix_instructions=(
                                f"1. Layers `{name_a}` and `{name_b}` contain conflicting "
                                f"instructions.\n2. Conflict: {details}\n"
                                "3. Reconcile by editing the lower-priority layer.\n"
                                "4. Ensure only one authoritative source defines each rule."
                            ),
                            signal=signal,
                        )
                    )
    return actions


def _find_shared_subjects(
    content_a: str, content_b: str, positive: str, negative: str
) -> list[str]:
    import re
    pattern = re.compile(rf"{re.escape(positive)}\s+(\w+)")
    subjects_a = {m.group(1) for m in pattern.finditer(content_a)}
    neg_pattern = re.compile(rf"{re.escape(negative)}\s+(\w+)")
    subjects_b = {m.group(1) for m in neg_pattern.finditer(content_b)}
    return list(subjects_a & subjects_b)


_RULE_CHECKERS = {
    "no_stale_layers": _check_no_stale_layers,
    "no_duplicate_tools": _check_no_duplicate_tools,
    "no_conflicting_instructions": _check_no_conflicting_instructions,
}
