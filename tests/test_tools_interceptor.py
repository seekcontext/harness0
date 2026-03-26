"""Tests for ToolInterceptor (L2)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from harness0.core.config import SecurityConfig, ToolGovernanceConfig
from harness0.core.types import ToolCall
from harness0.security.approval import ApprovalManager, AutoDenyBackend
from harness0.security.command_guard import CommandGuard
from harness0.tools.interceptor import ToolInterceptor
from harness0.tools.schema import ParameterSchema, RiskLevel, ToolDefinition

if TYPE_CHECKING:
    from harness0.feedback.translator import FeedbackTranslator
    from harness0.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_execute_unknown_tool_emits_signal(
    translator: FeedbackTranslator,
    registry: ToolRegistry,
) -> None:
    cfg = ToolGovernanceConfig(audit_enabled=False)
    intr = ToolInterceptor(
        registry=registry,
        config=cfg,
        translator=translator,
        approval_manager=None,
        command_guard=None,
        sandbox=None,
    )
    res = await intr.execute(ToolCall(name="nope", arguments={}))
    assert res.error
    assert "not registered" in res.error
    bundle = await translator.flush()
    assert bundle.signals


@pytest.mark.asyncio
async def test_execute_schema_validation_failure(
    translator: FeedbackTranslator,
    registry: ToolRegistry,
) -> None:
    registry.register(
        ToolDefinition(
            name="need_x",
            description="needs x",
            parameters=[
                ParameterSchema(name="x", type="string", description="required", required=True),
            ],
            handler=lambda x: x,
        )
    )
    intr = ToolInterceptor(
        registry=registry,
        config=ToolGovernanceConfig(audit_enabled=False),
        translator=translator,
        approval_manager=None,
        command_guard=None,
        sandbox=None,
    )
    res = await intr.execute(ToolCall(name="need_x", arguments={}))
    assert res.error
    assert "validation" in res.error.lower() or "Missing" in res.error


@pytest.mark.asyncio
async def test_execute_sync_handler_via_thread(
    translator: FeedbackTranslator, registry: ToolRegistry
) -> None:
    def echo(msg: str) -> str:
        return f"got:{msg}"

    registry.register(
        ToolDefinition(
            name="echo",
            description="echo",
            parameters=[ParameterSchema(name="msg", type="string", description="m", required=True)],
            handler=echo,
            risk_level=RiskLevel.READ,
        )
    )
    intr = ToolInterceptor(
        registry=registry,
        config=ToolGovernanceConfig(audit_enabled=True),
        translator=translator,
        approval_manager=None,
        command_guard=None,
        sandbox=None,
    )
    res = await intr.execute(ToolCall(name="echo", arguments={"msg": "hi"}))
    assert res.error is None
    assert res.output == "got:hi"
    assert intr.audit_log()


@pytest.mark.asyncio
async def test_execute_async_handler(
    translator: FeedbackTranslator,
    registry: ToolRegistry,
) -> None:
    async def slow_ok() -> str:
        await asyncio.sleep(0.01)
        return "async-ok"

    registry.register(
        ToolDefinition(
            name="slow_ok",
            description="async tool",
            parameters=[],
            handler=slow_ok,
        )
    )
    intr = ToolInterceptor(
        registry=registry,
        config=ToolGovernanceConfig(audit_enabled=False),
        translator=translator,
        approval_manager=None,
        command_guard=None,
        sandbox=None,
    )
    res = await intr.execute(ToolCall(name="slow_ok", arguments={}))
    assert res.output == "async-ok"


@pytest.mark.asyncio
async def test_command_guard_blocks_execute_risk(
    translator: FeedbackTranslator, registry: ToolRegistry
) -> None:
    sec = SecurityConfig(approval_mode="never", blocked_commands=["rm -rf"])
    cg = CommandGuard(sec)
    registry.register(
        ToolDefinition(
            name="run_cmd",
            description="run shell",
            parameters=[
                ParameterSchema(
                    name="command",
                    type="string",
                    description="cmd",
                    required=True,
                ),
            ],
            handler=lambda command: command,
            risk_level=RiskLevel.EXECUTE,
        )
    )
    intr = ToolInterceptor(
        registry=registry,
        config=ToolGovernanceConfig(audit_enabled=False),
        translator=translator,
        approval_manager=None,
        command_guard=cg,
        sandbox=None,
    )
    res = await intr.execute(
        ToolCall(name="run_cmd", arguments={"command": "rm -rf /tmp/x"})
    )
    assert res.error
    assert "blocked" in res.error.lower() or "Command" in res.error


@pytest.mark.asyncio
async def test_approval_denied_returns_error(
    translator: FeedbackTranslator, registry: ToolRegistry
) -> None:
    sec = SecurityConfig(approval_mode="always")
    am = ApprovalManager(sec, backend=AutoDenyBackend())
    registry.register(
        ToolDefinition(
            name="risky",
            description="risky op",
            parameters=[],
            handler=lambda: "should not run",
            risk_level=RiskLevel.READ,
            requires_approval=True,
        )
    )
    intr = ToolInterceptor(
        registry=registry,
        config=ToolGovernanceConfig(audit_enabled=False),
        translator=translator,
        approval_manager=am,
        command_guard=None,
        sandbox=None,
    )
    res = await intr.execute(ToolCall(name="risky", arguments={}))
    assert res.error
    assert "denied" in res.error.lower()


@pytest.mark.asyncio
async def test_handler_timeout(translator: FeedbackTranslator, registry: ToolRegistry) -> None:
    async def hang() -> str:
        await asyncio.sleep(10)
        return "no"

    registry.register(
        ToolDefinition(
            name="hang",
            description="hangs",
            parameters=[],
            handler=hang,
            timeout=1,
        )
    )
    intr = ToolInterceptor(
        registry=registry,
        config=ToolGovernanceConfig(audit_enabled=False),
        translator=translator,
        approval_manager=None,
        command_guard=None,
        sandbox=None,
    )
    res = await intr.execute(ToolCall(name="hang", arguments={}))
    assert res.error
    assert "timeout" in res.error.lower() or "exceeded" in res.error.lower()


@pytest.mark.asyncio
async def test_output_truncation_emits_warning(
    translator: FeedbackTranslator, registry: ToolRegistry
) -> None:
    huge = "word " * 5000

    def big_out() -> str:
        return huge

    registry.register(
        ToolDefinition(
            name="big",
            description="big output",
            parameters=[],
            handler=big_out,
            max_output_tokens=20,
        )
    )
    intr = ToolInterceptor(
        registry=registry,
        config=ToolGovernanceConfig(max_output_tokens=5000, audit_enabled=False),
        translator=translator,
        approval_manager=None,
        command_guard=None,
        sandbox=None,
    )
    res = await intr.execute(ToolCall(name="big", arguments={}))
    assert res.truncated or "truncat" in res.output.lower()
    bundle = await translator.flush()
    assert any("truncat" in (s.message.lower()) for s in bundle.signals) or res.truncated
