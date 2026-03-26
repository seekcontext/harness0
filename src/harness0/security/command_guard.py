"""CommandGuard — L3 first line of defense: pattern-based command validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from harness0.feedback.signals import FeedbackSignal, SignalType

if TYPE_CHECKING:
    from harness0.core.config import SecurityConfig


@dataclass
class GuardResult:
    allowed: bool
    command: str
    matched_pattern: str | None = None
    signal: FeedbackSignal | None = None


class CommandGuard:
    """
    Pattern-based command blocklist enforcer.

    Every rejection produces a FeedbackSignal with agent-readable fix_instructions,
    not a bare exception. This follows the principle that system constraints must
    be expressed in language the agent can act on.
    """

    _SAFE_ALTERNATIVES: dict[str, list[str]] = {
        "rm -rf": ["rm -r <specific_path>", "shutil.rmtree(<path>) in Python"],
        "sudo": ["run the specific command without sudo", "use a pre-approved privileged tool"],
        "> /dev/sda": ["write to a specific file path instead"],
        "dd if=": ["use cp or rsync for file copying"],
        "chmod 777": ["chmod 755 <path> or chmod 644 <path>"],
        "curl.*sh": ["download the script first, inspect it, then run it explicitly"],
    }

    def __init__(self, config: SecurityConfig) -> None:
        self.config = config
        self._patterns: list[re.Pattern[str]] = [
            re.compile(re.escape(cmd), re.IGNORECASE)
            for cmd in config.blocked_commands
        ]

    def check(self, command: str) -> GuardResult:
        """Check a command against the blocklist. Returns GuardResult immediately."""
        for pattern, raw in zip(self._patterns, self.config.blocked_commands, strict=False):
            if pattern.search(command):
                alternatives = self._SAFE_ALTERNATIVES.get(raw, [])
                signal = self._make_signal(command, raw, alternatives)
                return GuardResult(
                    allowed=False,
                    command=command,
                    matched_pattern=raw,
                    signal=signal,
                )
        return GuardResult(allowed=True, command=command)

    def _make_signal(
        self,
        command: str,
        matched: str,
        alternatives: list[str],
    ) -> FeedbackSignal:
        alt_text = ""
        if alternatives:
            listed = "\n".join(f"   • {a}" for a in alternatives)
            alt_text = f"\n3. Consider these safer alternatives:\n{listed}"

        return FeedbackSignal(
            type=SignalType.CONSTRAINT,
            source="security.command_guard",
            message=(
                f"Command blocked: `{command[:120]}` "
                f"matches blocked pattern `{matched}`."
            ),
            actionable=True,
            fix_instructions=(
                f"1. Do NOT retry `{command[:80]}` — it matches the security blocklist.\n"
                f"2. Reason: the pattern `{matched}` is blocked because it can cause "
                f"irreversible or dangerous side effects.{alt_text}\n"
                "4. If this operation is truly required, request explicit approval from the user."
            ),
            metadata={"matched_pattern": matched, "command_preview": command[:200]},
        )

    def add_pattern(self, pattern: str) -> None:
        """Dynamically add a blocked command pattern at runtime."""
        self.config.blocked_commands.append(pattern)
        self._patterns.append(re.compile(re.escape(pattern), re.IGNORECASE))
