"""ProcessSandbox — L3 subprocess pool with resource limits."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from harness0.core.types import ToolResult
from harness0.feedback.translator import FeedbackTranslator

if TYPE_CHECKING:
    from harness0.core.config import SecurityConfig

logger = logging.getLogger(__name__)


class ProcessSandbox:
    """
    Manages subprocess execution with:
      - Concurrency limits (semaphore)
      - Per-process output cap (bytes)
      - Wall-clock timeout enforcement
      - Automatic cleanup on session end

    All resource violations produce FeedbackSignals via FeedbackTranslator,
    not raw exceptions, so the agent receives actionable remediation steps.
    """

    def __init__(self, config: SecurityConfig) -> None:
        self.config = config
        self._semaphore = asyncio.Semaphore(config.max_processes)
        self._active_processes: list[asyncio.subprocess.Process] = []

    async def run(
        self,
        command: str,
        tool_call_id: str,
        translator: FeedbackTranslator | None = None,
        timeout: int | None = None,
        cwd: str | None = None,
    ) -> ToolResult:
        """
        Execute a shell command in the sandbox and return a ToolResult.

        On timeout or output overflow, emits a FeedbackSignal and returns a
        partial result rather than raising an exception.
        """
        effective_timeout = timeout or self.config.default_timeout
        start = time.monotonic()

        async with self._semaphore:
            try:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=cwd,
                )
                self._active_processes.append(proc)

                try:
                    raw_output, _ = await asyncio.wait_for(
                        proc.communicate(), timeout=effective_timeout
                    )
                except TimeoutError:
                    proc.kill()
                    await proc.communicate()
                    duration_ms = (time.monotonic() - start) * 1000
                    signal = FeedbackTranslator.subprocess_timeout(command, effective_timeout)
                    if translator:
                        await translator.add(signal)
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        name="run_command",
                        output="",
                        error=signal.message,
                        duration_ms=duration_ms,
                    )
                finally:
                    if proc in self._active_processes:
                        self._active_processes.remove(proc)

                duration_ms = (time.monotonic() - start) * 1000
                output = raw_output.decode("utf-8", errors="replace")

                truncated = False
                if len(raw_output) > self.config.max_output_bytes:
                    output = output[: self.config.max_output_bytes].decode(
                        "utf-8", errors="replace"
                    ) if isinstance(output, bytes) else output[: self.config.max_output_bytes]
                    output += f"\n[...output truncated at {self.config.max_output_bytes} bytes]"
                    truncated = True

                return ToolResult(
                    tool_call_id=tool_call_id,
                    name="run_command",
                    output=output,
                    error=None if proc.returncode == 0 else f"Exit code {proc.returncode}",
                    truncated=truncated,
                    duration_ms=duration_ms,
                )

            except Exception as exc:
                logger.exception("Sandbox error running command: %s", command[:100])
                signal = FeedbackTranslator.from_exception(exc, "security.sandbox")
                if translator:
                    await translator.add(signal)
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name="run_command",
                    output="",
                    error=signal.message,
                    duration_ms=(time.monotonic() - start) * 1000,
                )

    async def cleanup(self) -> None:
        """Kill all active processes. Call on session end."""
        for proc in list(self._active_processes):
            try:
                proc.kill()
                await proc.communicate()
            except Exception:
                pass
        self._active_processes.clear()
