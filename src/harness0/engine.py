"""HarnessEngine — the top-level facade that wires all 5 layers together."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from harness0.context.assembler import ContextAssembler
from harness0.core.config import HarnessConfig
from harness0.core.types import AgentState, Message, ToolCall, ToolResult
from harness0.entropy.manager import EntropyManager
from harness0.feedback.translator import FeedbackTranslator
from harness0.security.approval import ApprovalManager
from harness0.security.command_guard import CommandGuard
from harness0.security.sandbox import ProcessSandbox
from harness0.tools.interceptor import ToolInterceptor
from harness0.tools.registry import ToolRegistry
from harness0.tools.schema import RiskLevel, ToolDefinition

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from harness0.context.layers import ContextLayer
    from harness0.feedback.signals import SignalBundle

logger = logging.getLogger(__name__)


class RunResult:
    """The output of a completed agent run."""

    def __init__(self, state: AgentState, signals: list[SignalBundle]) -> None:
        self.output = state.output or ""
        self.status = state.status
        self.error = state.error
        self.turn_count = state.turn_number
        self.signals = signals
        self._state = state

    def __repr__(self) -> str:
        preview = self.output[:80]
        return f"RunResult(status={self.status!r}, turns={self.turn_count}, output={preview!r})"


class HarnessEngine:
    """
    The single entry point for harness0.

    Wires all 5 layers into a coherent agent loop:
      L1 ContextAssembler  → build system prompt each turn
      L2 ToolInterceptor   → govern every tool call
      L3 SecurityGuard     → block dangerous commands, require approvals
      L4 FeedbackTranslator → convert events to agent-readable signals
      L5 EntropyManager    → maintain context quality turn-over-turn

    Usage (minimal):
        engine = HarnessEngine.from_config("harness.yaml")

        @engine.tool(risk_level="read")
        async def read_file(path: str) -> str:
            return open(path).read()

        result = await engine.run("Summarise README.md")
        print(result.output)
    """

    def __init__(self, config: HarnessConfig) -> None:
        self.config = config

        # L4 — init first; other layers reference it
        self.translator = FeedbackTranslator(config.feedback)

        # L2
        self.registry = ToolRegistry()

        # L3
        self.command_guard = CommandGuard(config.security)
        self.sandbox = ProcessSandbox(config.security)
        self.approval_manager = ApprovalManager(config.security)

        # L2 interceptor (depends on L3 + L4)
        self.interceptor = ToolInterceptor(
            registry=self.registry,
            config=config.tools,
            translator=self.translator,
            approval_manager=self.approval_manager,
            command_guard=self.command_guard,
            sandbox=self.sandbox,
        )

        # L1 — layers added later via context_layers list or from_config
        self._context_layers: list[ContextLayer] = []
        self.assembler: ContextAssembler | None = None
        if config.context.layers:
            self.assembler = ContextAssembler.from_config(config.context)
            self._context_layers = self.assembler.layers

        # L5
        self.entropy_manager = EntropyManager(
            config=config.entropy,
            translator=self.translator,
            tool_registry=self.registry,
        )

        self._signal_history: list[SignalBundle] = []

    # ── Constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, path: str | Path) -> HarnessEngine:
        config = HarnessConfig.from_yaml(path)
        return cls(config)

    @classmethod
    def default(cls) -> HarnessEngine:
        """Create an engine with sensible defaults — no config file needed."""
        return cls(HarnessConfig.default())

    # ── @tool decorator ───────────────────────────────────────────────────────

    def tool(
        self,
        fn: Callable[..., Any] | None = None,
        *,
        risk_level: RiskLevel | str = RiskLevel.READ,
        requires_approval: bool = False,
        timeout: int | None = None,
        max_output_tokens: int | None = None,
        description: str | None = None,
    ) -> Any:
        """
        Decorator to register a function as a governed tool.

        Usage:
            @engine.tool(risk_level="execute", requires_approval=True)
            async def run_command(command: str) -> str:
                ...
        """
        if isinstance(risk_level, str):
            risk_level = RiskLevel(risk_level)

        def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            definition = ToolDefinition.from_function(
                fn=f,
                risk_level=risk_level,
                requires_approval=requires_approval,
                timeout=timeout,
                max_output_tokens=max_output_tokens,
                description=description,
            )
            self.registry.register(definition)
            return f

        if fn is not None:
            return decorator(fn)
        return decorator

    # ── Context layer management ──────────────────────────────────────────────

    def add_context_layer(self, layer: ContextLayer) -> None:
        """Add a context layer to the engine at runtime."""
        self._context_layers.append(layer)
        if self.assembler:
            self.assembler.add_layer(layer)
        else:
            self.assembler = ContextAssembler(
                layers=self._context_layers,
                total_token_budget=self.config.context.total_token_budget,
            )

    # ── Main run loop ─────────────────────────────────────────────────────────

    async def run(
        self,
        task: str,
        llm_client: Any | None = None,
        max_iterations: int | None = None,
    ) -> RunResult:
        """
        Run the agent loop for the given task.

        The loop:
          1. Assemble context (L1)
          2. Clean entropy (L5)
          3. Call LLM
          4. Handle tool calls through interceptor (L2 + L3 + L4)
          5. Inject feedback signals back into context (L4 → L1)
          6. Repeat until done or max_iterations reached

        Args:
            task: The natural language task to accomplish.
            llm_client: An LLM provider client. If None, uses a stub (for testing).
            max_iterations: Override config.max_iterations.
        """
        max_iter = max_iterations or self.config.max_iterations
        state = AgentState(task=task)
        state.messages.append(Message(role="user", content=task))

        for iteration in range(max_iter):
            state.turn_number = iteration
            turn_ctx = state.to_turn_context()

            # L5: entropy maintenance
            state.messages, garden_actions = await self.entropy_manager.process(
                messages=state.messages,
                turn_context=turn_ctx,
                context_layers=self._context_layers,
            )

            # L1: context assembly
            system_messages: list[Message] = []
            if self.assembler:
                system_messages = await self.assembler.assemble(turn_ctx)

            # L4: inject pending feedback signals from previous turn
            bundle = await self.translator.flush()
            self._signal_history.append(bundle)
            if bundle.signals:
                hint_text = self.translator.render_bundle(bundle)
                if hint_text:
                    system_messages.append(Message(role="system", content=hint_text))

            # LLM call
            full_messages = system_messages + state.messages
            if llm_client is None:
                # Stub: no LLM configured — return immediately
                state.output = f"(No LLM client configured. Task: {task})"
                state.status = "done"
                break

            response = await _call_llm(llm_client, full_messages, self.registry)

            if response.get("finish_reason") == "stop":
                state.output = response.get("content", "")
                state.status = "done"
                break

            # Handle tool calls
            tool_calls_data = response.get("tool_calls", [])
            if not tool_calls_data:
                state.output = response.get("content", "")
                state.status = "done"
                break

            state.messages.append(
                Message(role="assistant", content=response.get("content", ""))
            )

            tool_results: list[ToolResult] = await asyncio.gather(*[
                self.interceptor.execute(
                    ToolCall(
                        id=tc.get("id", ""),
                        name=tc["function"]["name"],
                        arguments=tc["function"].get("arguments", {}),
                    )
                )
                for tc in tool_calls_data
            ])

            for result in tool_results:
                state.messages.append(
                    Message(
                        role="tool",
                        content=result.output or result.error or "",
                        name=result.name,
                        tool_call_id=result.tool_call_id,
                    )
                )
                state.tool_results.append(result)
        else:
            state.status = "failed"
            state.error = f"Reached max_iterations ({max_iter}) without completing the task."
            logger.warning(state.error)

        await self.sandbox.cleanup()
        return RunResult(state=state, signals=self._signal_history)

    # ── Convenience: execute a single tool call directly ─────────────────────

    async def execute_tool(self, tool_name: str, **arguments: Any) -> ToolResult:
        """Execute a single tool call outside the agent loop (useful for testing)."""
        call = ToolCall(name=tool_name, arguments=arguments)
        return await self.interceptor.execute(call)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _call_llm(
    client: Any,
    messages: list[Message],
    registry: ToolRegistry,
) -> dict[str, Any]:
    """
    Thin adapter: call the LLM client and normalise the response.
    Supports OpenAI-compatible clients (openai.AsyncOpenAI, etc.).
    """
    raw_messages = [{"role": m.role, "content": m.content} for m in messages]
    tools = registry.openai_schemas() if registry.names() else []

    kwargs: dict[str, Any] = {"messages": raw_messages}
    if tools:
        kwargs["tools"] = tools

    # Try OpenAI-style client
    if hasattr(client, "chat") and hasattr(client.chat, "completions"):
        resp = await client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        return {
            "content": choice.message.content or "",
            "finish_reason": choice.finish_reason,
            "tool_calls": [
                {
                    "id": tc.id,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in (choice.message.tool_calls or [])
            ],
        }

    # Fallback: assume client is a plain async callable
    return await client(messages=raw_messages, tools=tools)
