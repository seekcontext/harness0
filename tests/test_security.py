"""Tests for L3 security components."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from harness0.core.config import SecurityConfig
from harness0.security.approval import ApprovalManager, AutoApproveBackend, AutoDenyBackend
from harness0.security.command_guard import CommandGuard
from harness0.security.sandbox import ProcessSandbox

if TYPE_CHECKING:
    from harness0.feedback.translator import FeedbackTranslator


def test_command_guard_allows_safe_command() -> None:
    cfg = SecurityConfig(blocked_commands=["sudo"])
    g = CommandGuard(cfg)
    r = g.check("echo hello")
    assert r.allowed is True
    assert r.signal is None


def test_command_guard_blocks_configured_pattern() -> None:
    cfg = SecurityConfig(blocked_commands=["rm -rf", "sudo"])
    g = CommandGuard(cfg)
    r = g.check("please sudo ls")
    assert r.allowed is False
    assert r.signal is not None
    assert r.matched_pattern == "sudo"


def test_command_guard_case_insensitive() -> None:
    cfg = SecurityConfig(blocked_commands=["RM -RF"])
    g = CommandGuard(cfg)
    r = g.check("rm -rf /")
    assert r.allowed is False


def test_command_guard_add_pattern_runtime() -> None:
    cfg = SecurityConfig(blocked_commands=[])
    g = CommandGuard(cfg)
    assert g.check("danger").allowed is True
    g.add_pattern("danger")
    assert g.check("danger").allowed is False


@pytest.mark.asyncio
async def test_approval_manager_never_skips_prompt() -> None:
    cfg = SecurityConfig(approval_mode="never")
    am = ApprovalManager(cfg, backend=AutoDenyBackend())
    ok = await am.request("any", risk_level="critical")
    assert ok is True


@pytest.mark.asyncio
async def test_approval_manager_risky_only_allows_read() -> None:
    cfg = SecurityConfig(approval_mode="risky_only")
    am = ApprovalManager(cfg, backend=AutoDenyBackend())
    assert await am.request("x", risk_level="read") is True
    assert await am.request("x", risk_level="execute") is False


@pytest.mark.asyncio
async def test_approval_fingerprint_cache(
    translator: FeedbackTranslator,
) -> None:
    cfg = SecurityConfig(approval_mode="always")
    am = ApprovalManager(cfg, backend=AutoApproveBackend())
    assert await am.request("same_action", risk_level="read", translator=translator) is True
    assert await am.request("same_action", risk_level="read", translator=translator) is True
    am.clear_cache()
    assert await am.request("same_action", risk_level="read", translator=translator) is True


@pytest.mark.asyncio
async def test_process_sandbox_echo(
    translator: FeedbackTranslator,
    security_config: SecurityConfig,
) -> None:
    sandbox = ProcessSandbox(security_config)
    res = await sandbox.run(
        "echo harness_test_ok",
        tool_call_id="tc1",
        translator=translator,
        timeout=5,
    )
    assert "harness_test_ok" in res.output
    assert res.error is None or res.error == ""
    await sandbox.cleanup()


@pytest.mark.asyncio
async def test_process_sandbox_timeout(
    translator: FeedbackTranslator,
    security_config: SecurityConfig,
) -> None:
    sandbox = ProcessSandbox(security_config)
    res = await sandbox.run(
        "sleep 60",
        tool_call_id="tc2",
        translator=translator,
        timeout=1,
    )
    assert res.error
    assert "timeout" in res.error.lower() or "exceeded" in res.error.lower()
    await sandbox.cleanup()
