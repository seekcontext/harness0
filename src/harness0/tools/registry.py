"""ToolRegistry — the central catalog of all governed tools."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .schema import ToolDefinition

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central catalog of all registered tools available to the agent.

    Tools are registered either via the @engine.tool decorator or by calling
    register() directly. The registry provides the OpenAI-format schema list
    for LLM calls and lookup by name for execution.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            logger.warning(
                "Tool %r is already registered — overwriting with new definition.",
                definition.name,
            )
        self._tools[definition.name] = definition
        logger.debug("Registered tool: %r (risk=%s)", definition.name, definition.risk_level)

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def require(self, name: str) -> ToolDefinition:
        tool = self._tools.get(name)
        if tool is None:
            available = ", ".join(self._tools.keys()) or "(none)"
            raise KeyError(
                f"Tool `{name}` is not registered. Available tools: {available}"
            )
        return tool

    def all_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def openai_schemas(self) -> list[dict[str, Any]]:
        """Return all tool schemas in OpenAI function-calling format."""
        return [t.to_openai_schema() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def has_duplicates(self) -> list[tuple[str, str]]:
        """
        Detect tools with identical descriptions (golden rule enforcement).
        Returns list of (name_a, name_b) pairs that share the same description.
        """
        seen: dict[str, str] = {}
        duplicates: list[tuple[str, str]] = []
        for name, tool in self._tools.items():
            key = tool.description.strip().lower()
            if key in seen:
                duplicates.append((seen[key], name))
            else:
                seen[key] = name
        return duplicates

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
