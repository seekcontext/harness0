"""Tests for HarnessEngine facade and LLM adapter."""

from __future__ import annotations

from typing import Any

import pytest

from harness0.core.types import Message
from harness0.engine import HarnessEngine, RunResult, _call_llm
from harness0.tools.registry import ToolRegistry
from harness0.tools.schema import RiskLevel


def test_run_result_repr() -> None:
    from harness0.core.types import AgentState

    state = AgentState(task="t", output="hello world " * 10, status="done", turn_number=3)
    rr = RunResult(state=state, signals=[])
    text = repr(rr)
    assert "done" in text
    assert "turns=3" in text


@pytest.mark.asyncio
async def test_engine_run_without_llm_completes() -> None:
    engine = HarnessEngine.default()
    result = await engine.run("my task", llm_client=None, max_iterations=3)
    assert result.status == "done"
    assert "No LLM client" in result.output
    assert isinstance(result.signals, list)


@pytest.mark.asyncio
async def test_engine_execute_tool_registered() -> None:
    engine = HarnessEngine.default()

    @engine.tool(risk_level=RiskLevel.READ)
    def add(a: int, b: int) -> int:
        return a + b

    res = await engine.execute_tool("add", a=2, b=3)
    assert res.error is None
    assert res.output == "5"


@pytest.mark.asyncio
async def test_engine_max_iterations_failure() -> None:
    engine = HarnessEngine.default()
    engine.config.max_iterations = 2

    class LoopClient:
        async def chat_completions_create(self) -> dict[str, Any]:
            return {
                "content": "",
                "finish_reason": "tool_calls",
                "tool_calls": [
                    {
                        "id": "c1",
                        "function": {"name": "noop", "arguments": {}},
                    }
                ],
            }

    @engine.tool()
    def noop() -> str:
        return "ok"

    client = LoopClient()

    async def llm_adapter(**kwargs: Any) -> dict[str, Any]:
        return await client.chat_completions_create()

    result = await engine.run("task", llm_client=llm_adapter, max_iterations=2)
    assert result.status == "failed"
    assert "max_iterations" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_call_llm_openai_style_mock() -> None:
    reg = ToolRegistry()

    class Fn:
        name = "echo"
        arguments = "{}"

    class Msg:
        content = "hi"
        tool_calls = [type("TC", (), {"id": "1", "function": Fn()})()]

    class Choice:
        message = Msg()
        finish_reason = "tool_calls"

    class Resp:
        choices = [Choice()]

    class Completions:
        async def create(self, **kwargs: Any) -> Resp:
            return Resp()

    class Chat:
        completions = Completions()

    client = type("C", (), {"chat": Chat()})()
    out = await _call_llm(
        client,
        [Message(role="user", content="u")],
        reg,
    )
    assert out["finish_reason"] == "tool_calls"
    assert out["tool_calls"]


@pytest.mark.asyncio
async def test_call_llm_async_callable_fallback() -> None:
    reg = ToolRegistry()

    async def client(**kwargs: Any) -> dict[str, Any]:
        return {"content": "done", "finish_reason": "stop", "tool_calls": []}

    out = await _call_llm(client, [Message(role="user", content="x")], reg)
    assert out["content"] == "done"
    assert out["finish_reason"] == "stop"
