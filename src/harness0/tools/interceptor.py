"""ToolInterceptor — L2 pipeline: validate → risk-assess → approve → execute → audit."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

import tiktoken

from harness0.core.types import ToolCall, ToolResult
from harness0.feedback.signals import FeedbackSignal, SignalType
from harness0.feedback.translator import FeedbackTranslator

from .schema import RiskLevel

if TYPE_CHECKING:
    from harness0.core.config import ToolGovernanceConfig
    from harness0.security.approval import ApprovalManager
    from harness0.security.command_guard import CommandGuard
    from harness0.security.sandbox import ProcessSandbox

    from .registry import ToolRegistry

logger = logging.getLogger(__name__)

_ENCODING = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def _truncate_output(text: str, max_tokens: int) -> tuple[str, bool]:
    tokens = _ENCODING.encode(text)
    if len(tokens) <= max_tokens:
        return text, False
    truncated = _ENCODING.decode(tokens[:max_tokens])
    return truncated + f"\n[...output truncated: {len(tokens)} → {max_tokens} tokens]", True


class AuditRecord:
    """Immutable record of a single tool execution."""

    __slots__ = ("call_id", "tool_name", "arguments", "risk_level", "approved",
                 "output_tokens", "truncated", "error", "duration_ms", "timestamp")

    def __init__(
        self,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        risk_level: RiskLevel,
        approved: bool,
        output_tokens: int,
        truncated: bool,
        error: str | None,
        duration_ms: float,
        timestamp: float,
    ) -> None:
        for k, v in locals().items():
            if k != "self":
                object.__setattr__(self, k, v)


class ToolInterceptor:
    """
    L2 interception pipeline for every tool call.

    Pipeline:
      ToolCall
        → Schema Validation   (check args against ToolDefinition)
        → Risk Assessment     (classify, check if approval is needed)
        → Command Guard       (for execute-risk tools: check blocklist)
        → Approval Check      (if EXECUTE/CRITICAL: request approval)
        → Execute             (call the handler or sandbox)
        → Output Truncation   (enforce max_output_tokens)
        → Audit Log           (record call, result, timing)
        → ToolResult

    On any failure: emits a FeedbackSignal and returns a ToolResult with error
    rather than raising. The agent always gets a structured response.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        config: ToolGovernanceConfig,
        translator: FeedbackTranslator,
        approval_manager: ApprovalManager | None = None,
        command_guard: CommandGuard | None = None,
        sandbox: ProcessSandbox | None = None,
    ) -> None:
        self.registry = registry
        self.config = config
        self.translator = translator
        self.approval_manager = approval_manager
        self.command_guard = command_guard
        self.sandbox = sandbox
        self._audit_log: list[AuditRecord] = []

    async def execute(self, call: ToolCall) -> ToolResult:
        start = time.monotonic()

        # ── 1. Lookup ────────────────────────────────────────────────────────
        tool = self.registry.get(call.name)
        if tool is None:
            signal = FeedbackSignal(
                type=SignalType.ERROR,
                source="tools.interceptor",
                message=f"Tool `{call.name}` is not registered.",
                actionable=True,
                fix_instructions=(
                    f"1. Tool `{call.name}` does not exist in the registry.\n"
                    f"2. Available tools: {', '.join(self.registry.names()) or '(none)'}.\n"
                    "3. Choose from the available tools or ask the user to register a new one."
                ),
            )
            await self.translator.add(signal)
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                output="",
                error=signal.message,
            )

        # ── 2. Schema validation ─────────────────────────────────────────────
        errors = tool.validate_arguments(call.arguments)
        if errors:
            signal = FeedbackTranslator.tool_schema_invalid(call.name, "; ".join(errors))
            await self.translator.add(signal)
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                output="",
                error=signal.message,
            )

        # ── 3. Command guard (for shell-like tools) ──────────────────────────
        if self.command_guard and tool.risk_level in (RiskLevel.EXECUTE, RiskLevel.CRITICAL):
            command_arg = call.arguments.get("command", "")
            if command_arg:
                result = self.command_guard.check(command_arg)
                if not result.allowed and result.signal:
                    await self.translator.add(result.signal)
                    return ToolResult(
                        tool_call_id=call.id,
                        name=call.name,
                        output="",
                        error=result.signal.message,
                    )

        # ── 4. Approval ──────────────────────────────────────────────────────
        needs_approval = tool.requires_approval or tool.risk_level == RiskLevel.CRITICAL
        if self.approval_manager and needs_approval:
            approved = await self.approval_manager.request(
                action=f"{call.name}({call.arguments})",
                risk_level=tool.risk_level.value,
                context=f"Tool: {tool.description}",
                translator=self.translator,
            )
            if not approved:
                duration_ms = (time.monotonic() - start) * 1000
                self._record_audit(call, tool.risk_level, approved=False,
                                   output_tokens=0, truncated=False,
                                   error="denied", duration_ms=duration_ms)
                return ToolResult(
                    tool_call_id=call.id,
                    name=call.name,
                    output="",
                    error=f"Action `{call.name}` was denied by approval policy.",
                )

        # ── 5. Execute ───────────────────────────────────────────────────────
        try:
            timeout = tool.timeout
            if timeout and tool.handler:
                raw_output = await asyncio.wait_for(
                    _invoke(tool.handler, call.arguments), timeout=timeout
                )
            elif tool.handler:
                raw_output = await _invoke(tool.handler, call.arguments)
            else:
                raw_output = f"(Tool `{call.name}` has no handler registered)"

            output = str(raw_output)

        except TimeoutError:
            signal = FeedbackTranslator.subprocess_timeout(call.name, tool.timeout or 30)
            await self.translator.add(signal)
            duration_ms = (time.monotonic() - start) * 1000
            self._record_audit(call, tool.risk_level, approved=True,
                               output_tokens=0, truncated=False,
                               error="timeout", duration_ms=duration_ms)
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                output="",
                error=signal.message,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            signal = FeedbackTranslator.from_exception(exc, f"tools.{call.name}")
            await self.translator.add(signal)
            duration_ms = (time.monotonic() - start) * 1000
            self._record_audit(call, tool.risk_level, approved=True,
                               output_tokens=0, truncated=False,
                               error=str(exc), duration_ms=duration_ms)
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                output="",
                error=signal.message,
                duration_ms=duration_ms,
            )

        # ── 6. Output truncation ─────────────────────────────────────────────
        max_tokens = tool.max_output_tokens or self.config.max_output_tokens
        output_tokens = _count_tokens(output)
        truncated = False
        if output_tokens > max_tokens:
            output, truncated = _truncate_output(output, max_tokens)
            signal = FeedbackTranslator.output_truncated(call.name, output_tokens, max_tokens)
            await self.translator.add(signal)

        # ── 7. Audit ─────────────────────────────────────────────────────────
        duration_ms = (time.monotonic() - start) * 1000
        self._record_audit(call, tool.risk_level, approved=True,
                           output_tokens=_count_tokens(output),
                           truncated=truncated, error=None, duration_ms=duration_ms)

        logger.debug(
            "Tool %r executed in %.1fms (risk=%s, tokens=%d, truncated=%s)",
            call.name, duration_ms, tool.risk_level, _count_tokens(output), truncated,
        )

        return ToolResult(
            tool_call_id=call.id,
            name=call.name,
            output=output,
            truncated=truncated,
            duration_ms=duration_ms,
        )

    def _record_audit(
        self,
        call: ToolCall,
        risk_level: RiskLevel,
        approved: bool,
        output_tokens: int,
        truncated: bool,
        error: str | None,
        duration_ms: float,
    ) -> None:
        if not self.config.audit_enabled:
            return
        self._audit_log.append(
            AuditRecord(
                call_id=call.id,
                tool_name=call.name,
                arguments=call.arguments,
                risk_level=risk_level,
                approved=approved,
                output_tokens=output_tokens,
                truncated=truncated,
                error=error,
                duration_ms=duration_ms,
                timestamp=time.time(),
            )
        )

    def audit_log(self) -> list[AuditRecord]:
        return list(self._audit_log)


async def _invoke(handler: Any, arguments: dict[str, Any]) -> Any:
    """Call a sync or async handler with the given keyword arguments."""
    if asyncio.iscoroutinefunction(handler):
        return await handler(**arguments)
    return await asyncio.to_thread(handler, **arguments)
