"""Shared pytest fixtures for harness0."""

from __future__ import annotations

import pytest

from harness0.core.config import FeedbackConfig, SecurityConfig, ToolGovernanceConfig
from harness0.feedback.translator import FeedbackTranslator
from harness0.security.approval import ApprovalManager, AutoApproveBackend
from harness0.security.command_guard import CommandGuard
from harness0.security.sandbox import ProcessSandbox
from harness0.tools.interceptor import ToolInterceptor
from harness0.tools.registry import ToolRegistry


@pytest.fixture
def feedback_config() -> FeedbackConfig:
    return FeedbackConfig(inject_hints=True, max_signals_per_turn=50)


@pytest.fixture
def translator(feedback_config: FeedbackConfig) -> FeedbackTranslator:
    return FeedbackTranslator(feedback_config)


@pytest.fixture
def security_config() -> SecurityConfig:
    return SecurityConfig(
        sandbox_enabled=True,
        max_processes=5,
        max_output_bytes=100_000,
        default_timeout=30,
        blocked_commands=["rm -rf", "sudo"],
        approval_mode="never",
    )


@pytest.fixture
def tool_governance_config() -> ToolGovernanceConfig:
    return ToolGovernanceConfig(max_output_tokens=5000, audit_enabled=True)


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry()


@pytest.fixture
def interceptor(
    registry: ToolRegistry,
    tool_governance_config: ToolGovernanceConfig,
    translator: FeedbackTranslator,
    security_config: SecurityConfig,
) -> ToolInterceptor:
    cg = CommandGuard(security_config)
    sandbox = ProcessSandbox(security_config)
    am = ApprovalManager(security_config, backend=AutoApproveBackend())
    return ToolInterceptor(
        registry=registry,
        config=tool_governance_config,
        translator=translator,
        approval_manager=am,
        command_guard=cg,
        sandbox=sandbox,
    )
