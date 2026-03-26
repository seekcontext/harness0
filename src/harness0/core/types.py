"""Core shared types used across all 5 layers."""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single message in the conversation."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None


class ToolCall(BaseModel):
    """A tool invocation requested by the model."""

    id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:8]}")
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """The outcome of executing a tool call."""

    tool_call_id: str
    name: str
    output: str
    error: str | None = None
    truncated: bool = False
    duration_ms: float = 0.0


class TurnContext(BaseModel):
    """Context passed to each layer during a single agent turn."""

    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    turn_number: int = 0
    task: str = ""
    history: list[Message] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_first_turn(self) -> bool:
        return self.turn_number == 0


class AgentState(BaseModel):
    """Full state of a running agent session, checkpointable."""

    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    task: str
    turn_number: int = 0
    messages: list[Message] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    status: Literal["running", "done", "failed", "waiting_approval"] = "running"
    output: str | None = None
    error: str | None = None
    started_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_turn_context(self) -> TurnContext:
        return TurnContext(
            session_id=self.session_id,
            turn_number=self.turn_number,
            task=self.task,
            history=self.messages,
            tool_results=self.tool_results,
            metadata=self.metadata,
        )
