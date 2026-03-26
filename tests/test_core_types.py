"""Tests for harness0.core.types."""

from __future__ import annotations

from harness0.core.types import AgentState, Message, ToolCall, ToolResult, TurnContext


def test_message_roles_and_optional_fields() -> None:
    m = Message(role="user", content="hello")
    assert m.name is None
    assert m.tool_call_id is None

    t = Message(role="tool", content="ok", name="my_tool", tool_call_id="tc1")
    assert t.name == "my_tool"
    assert t.tool_call_id == "tc1"


def test_tool_call_default_id() -> None:
    a = ToolCall(name="echo", arguments={"x": 1})
    b = ToolCall(name="echo", arguments={"x": 1})
    assert a.id.startswith("call_")
    assert b.id.startswith("call_")
    assert a.id != b.id


def test_turn_context_first_turn() -> None:
    ctx = TurnContext(turn_number=0, task="t")
    assert ctx.is_first_turn is True
    ctx.turn_number = 1
    assert ctx.is_first_turn is False


def test_agent_state_to_turn_context_roundtrip() -> None:
    state = AgentState(task="do thing", turn_number=2)
    state.messages.append(Message(role="user", content="do thing"))
    state.tool_results.append(
        ToolResult(tool_call_id="c1", name="t", output="out", error=None)
    )
    state.metadata["k"] = "v"

    tc = state.to_turn_context()
    assert tc.session_id == state.session_id
    assert tc.turn_number == 2
    assert tc.task == "do thing"
    assert tc.history == state.messages
    assert tc.tool_results == state.tool_results
    assert tc.metadata == {"k": "v"}
