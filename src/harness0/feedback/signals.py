"""FeedbackSignal — structured, agent-consumable system events."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SignalType(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    CONSTRAINT = "constraint"


class FeedbackSignal(BaseModel):
    """
    A structured representation of a system event, translated for agent consumption.

    The key principle (from OpenAI Harness Engineering): every system failure must
    be expressed in language the agent can act on — not just "what went wrong" but
    "what to do next." The fix_instructions field carries that step-by-step guidance,
    formatted as a numbered list the agent can execute directly.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    type: SignalType
    source: str
    message: str
    actionable: bool = True
    suggestion: str | None = None
    fix_instructions: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)

    def to_xml_hint(self) -> str:
        """Render as an XML-tagged hint for injection into agent context via L1."""
        lines = [
            f'<harness:signal id="{self.id}" type="{self.type.value}" source="{self.source}">'
        ]
        lines.append(f"  <message>{self.message}</message>")
        if self.fix_instructions:
            lines.append(f"  <fix_instructions>{self.fix_instructions}</fix_instructions>")
        elif self.suggestion:
            lines.append(f"  <suggestion>{self.suggestion}</suggestion>")
        lines.append("</harness:signal>")
        return "\n".join(lines)

    def to_markdown_hint(self) -> str:
        """Render as a markdown block for injection into agent context."""
        icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️", "constraint": "🔒"}.get(
            self.type, "•"
        )
        lines = [f"{icon} **[{self.source}]** {self.message}"]
        if self.fix_instructions:
            lines.append(f"\n**How to fix:**\n{self.fix_instructions}")
        elif self.suggestion:
            lines.append(f"\n*Suggestion: {self.suggestion}*")
        return "\n".join(lines)

    def to_json_hint(self) -> dict[str, Any]:
        return {
            "harness_signal": {
                "id": self.id,
                "type": self.type,
                "source": self.source,
                "message": self.message,
                "fix_instructions": self.fix_instructions,
                "suggestion": self.suggestion,
            }
        }


class SignalBundle(BaseModel):
    """A collection of signals for a single turn."""

    signals: list[FeedbackSignal] = Field(default_factory=list)

    def has_errors(self) -> bool:
        return any(s.type == SignalType.ERROR for s in self.signals)

    def has_actionable(self) -> bool:
        return any(s.actionable for s in self.signals)

    def render(self, fmt: str = "xml") -> str:
        """Render all signals into a single string for context injection."""
        if not self.signals:
            return ""
        rendered = [
            s.to_xml_hint() if fmt == "xml"
            else s.to_markdown_hint() if fmt == "markdown"
            else str(s.to_json_hint())
            for s in self.signals
        ]
        if fmt == "xml":
            return "<harness:signals>\n" + "\n".join(rendered) + "\n</harness:signals>"
        return "\n\n".join(rendered)
