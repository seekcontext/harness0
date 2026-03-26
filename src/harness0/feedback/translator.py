"""FeedbackTranslator — converts raw system events into FeedbackSignals."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from .signals import FeedbackSignal, SignalBundle, SignalType

if TYPE_CHECKING:
    from harness0.core.config import FeedbackConfig

logger = logging.getLogger(__name__)


class FeedbackTranslator:
    """
    L4: Translates raw system events (exceptions, guard results, timeouts) into
    structured FeedbackSignals that the agent can reason about and act on.

    The design principle: raw exceptions are for humans; FeedbackSignals are for agents.
    Every L3 rejection, L2 truncation, and subprocess timeout flows through here
    before being injected back into the agent's context window via L1.
    """

    def __init__(self, config: FeedbackConfig) -> None:
        self.config = config
        self._current_bundle = SignalBundle()
        self._lock = asyncio.Lock()

    async def add(self, signal: FeedbackSignal) -> None:
        async with self._lock:
            if len(self._current_bundle.signals) >= self.config.max_signals_per_turn:
                logger.debug("Signal limit reached, dropping: %s", signal.id)
                return
            self._current_bundle.signals.append(signal)

    async def flush(self) -> SignalBundle:
        """Return and reset the current turn's signal bundle."""
        async with self._lock:
            bundle = self._current_bundle
            self._current_bundle = SignalBundle()
            return bundle

    def render_bundle(self, bundle: SignalBundle) -> str:
        """Render a bundle to a string for L1 context injection."""
        if not self.config.inject_hints or not bundle.signals:
            return ""
        return bundle.render(fmt=self.config.signal_format)

    # ── Convenience factory methods for common system events ──────────────

    @staticmethod
    def command_blocked(
        command: str,
        reason: str,
        allowed_alternatives: list[str] | None = None,
    ) -> FeedbackSignal:
        alternatives = ""
        if allowed_alternatives:
            alternatives = "\n3. Alternatives you may use: " + ", ".join(
                f"`{a}`" for a in allowed_alternatives
            )
        return FeedbackSignal(
            type=SignalType.CONSTRAINT,
            source="security.command_guard",
            message=f"Command blocked by security policy: `{command}`. Reason: {reason}",
            actionable=True,
            fix_instructions=(
                f"1. Do NOT retry the exact same command `{command}`.\n"
                f"2. Review the security policy reason: {reason}.{alternatives}\n"
                "4. If the operation is essential, request explicit user approval."
            ),
        )

    @staticmethod
    def output_truncated(tool_name: str, original_tokens: int, limit_tokens: int) -> FeedbackSignal:
        return FeedbackSignal(
            type=SignalType.WARNING,
            source=f"tools.interceptor.{tool_name}",
            message=(
                f"Tool `{tool_name}` output was truncated from ~{original_tokens} to "
                f"{limit_tokens} tokens to fit the context budget."
            ),
            actionable=True,
            fix_instructions=(
                "1. Narrow your query or search scope to reduce output size.\n"
                "2. Use more specific filters (e.g. file extension, directory, keyword).\n"
                "3. If you need the full output, ask the user to increase `max_output_tokens`."
            ),
        )

    @staticmethod
    def subprocess_timeout(command: str, timeout_seconds: int) -> FeedbackSignal:
        return FeedbackSignal(
            type=SignalType.ERROR,
            source="security.sandbox",
            message=f"Command `{command}` exceeded the {timeout_seconds}s timeout and was killed.",
            actionable=True,
            fix_instructions=(
                f"1. The command `{command}` took longer than {timeout_seconds}s.\n"
                "2. Break it into smaller steps that complete faster.\n"
                "3. Or use a more targeted variant (e.g. limit recursion depth, add `--timeout`).\n"
                "4. If this operation genuinely needs more time, "
                "ask the user to increase `default_timeout`."
            ),
        )

    @staticmethod
    def approval_denied(action: str, approver: str = "user") -> FeedbackSignal:
        return FeedbackSignal(
            type=SignalType.CONSTRAINT,
            source="security.approval",
            message=f"Action `{action}` was denied by {approver}.",
            actionable=True,
            fix_instructions=(
                f"1. The {approver} declined to approve `{action}`.\n"
                "2. Do not retry this action in the same session without re-confirmation.\n"
                "3. Explain to the user why this action is needed and ask for permission.\n"
                "4. Consider a safer alternative that does not require approval."
            ),
        )

    @staticmethod
    def tool_schema_invalid(tool_name: str, error: str) -> FeedbackSignal:
        return FeedbackSignal(
            type=SignalType.ERROR,
            source=f"tools.interceptor.{tool_name}",
            message=f"Tool call `{tool_name}` failed schema validation: {error}",
            actionable=True,
            fix_instructions=(
                f"1. The arguments you provided to `{tool_name}` do not match the tool's schema.\n"
                f"2. Validation error: {error}\n"
                "3. Check the tool's parameter definitions and retry with corrected arguments.\n"
                "4. If the tool signature is unclear, call `list_tools` to inspect the full schema."
            ),
        )

    @staticmethod
    def from_exception(exc: Exception, source: str) -> FeedbackSignal:
        """Generic fallback translator for unexpected exceptions."""
        return FeedbackSignal(
            type=SignalType.ERROR,
            source=source,
            message=f"Unexpected error in {source}: {type(exc).__name__}: {exc}",
            actionable=False,
            suggestion="Report this error to the system operator if it persists.",
            metadata={"exception_type": type(exc).__name__},
        )

    @staticmethod
    def context_stale(layer_name: str, age_hours: float) -> FeedbackSignal:
        return FeedbackSignal(
            type=SignalType.WARNING,
            source="entropy.gardener",
            message=(
                f"Context layer `{layer_name}` is {age_hours:.1f}h old and may be stale."
            ),
            actionable=True,
            fix_instructions=(
                f"1. The layer `{layer_name}` has not been updated in {age_hours:.1f} hours.\n"
                "2. Verify that its content still reflects the current system state.\n"
                "3. If outdated, update the source file or mark this layer as `per_turn` freshness."
            ),
        )

    @staticmethod
    def golden_rule_violated(rule_id: str, description: str, details: str) -> FeedbackSignal:
        return FeedbackSignal(
            type=SignalType.WARNING,
            source=f"entropy.gardener.rule.{rule_id}",
            message=f"Golden rule `{rule_id}` violated: {description}",
            actionable=True,
            fix_instructions=(
                f"1. Rule `{rule_id}`: {description}\n"
                f"2. Details: {details}\n"
                "3. Review and repair the violating content to restore harness invariants."
            ),
        )

    @staticmethod
    def custom(
        source: str,
        message: str,
        type: SignalType = SignalType.INFO,
        fix_instructions: str | None = None,
        **metadata: Any,
    ) -> FeedbackSignal:
        return FeedbackSignal(
            type=type,
            source=source,
            message=message,
            actionable=fix_instructions is not None,
            fix_instructions=fix_instructions,
            metadata=metadata,
        )
