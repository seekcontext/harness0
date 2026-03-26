"""ToolDefinition — declarative schema for governed tools."""

from __future__ import annotations

import inspect
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Callable


class RiskLevel(StrEnum):
    READ = "read"          # No side effects (read_file, search, list)
    WRITE = "write"        # Modifies persistent state (write_file, create_dir)
    EXECUTE = "execute"    # Runs code or shell commands
    CRITICAL = "critical"  # Irreversible or dangerous (deploy, delete, network calls)


class ParameterSchema(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


class ToolDefinition(BaseModel):
    """Complete specification of a governed tool."""

    name: str
    description: str
    parameters: list[ParameterSchema]
    risk_level: RiskLevel = RiskLevel.READ
    requires_approval: bool = False
    timeout: int | None = None
    max_output_tokens: int | None = None
    handler: Any = None  # The actual callable; excluded from serialisation

    model_config = {"arbitrary_types_allowed": True}

    def to_openai_schema(self) -> dict[str, Any]:
        """Emit an OpenAI-compatible tool schema for the LLM call."""
        properties: dict[str, Any] = {}
        required: list[str] = []
        for p in self.parameters:
            properties[p.name] = {"type": p.type, "description": p.description}
            if p.default is not None:
                properties[p.name]["default"] = p.default
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def validate_arguments(self, arguments: dict[str, Any]) -> list[str]:
        """Return a list of validation error strings (empty = valid)."""
        errors: list[str] = []
        for param in self.parameters:
            if param.required and param.name not in arguments:
                errors.append(f"Missing required parameter: `{param.name}`")
        return errors

    @classmethod
    def from_function(
        cls,
        fn: Callable[..., Any],
        risk_level: RiskLevel = RiskLevel.READ,
        requires_approval: bool = False,
        timeout: int | None = None,
        max_output_tokens: int | None = None,
        description: str | None = None,
    ) -> ToolDefinition:
        """
        Introspect a Python function and build a ToolDefinition from its
        signature and docstring. Used by the @engine.tool decorator.
        """
        sig = inspect.signature(fn)
        doc = inspect.getdoc(fn) or ""
        params: list[ParameterSchema] = []

        for name, param in sig.parameters.items():
            if name in ("self", "ctx", "context"):
                continue
            annotation = param.annotation
            type_str = _annotation_to_json_type(annotation)
            params.append(
                ParameterSchema(
                    name=name,
                    type=type_str,
                    description=f"Parameter `{name}`",
                    required=param.default is inspect.Parameter.empty,
                    default=None if param.default is inspect.Parameter.empty else param.default,
                )
            )

        return cls(
            name=fn.__name__,
            description=description or doc or fn.__name__,
            parameters=params,
            risk_level=risk_level,
            requires_approval=requires_approval,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
            handler=fn,
        )


def _annotation_to_json_type(annotation: Any) -> str:

    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    if annotation in type_map:
        return type_map[annotation]
    origin = getattr(annotation, "__origin__", None)
    if origin is list:
        return "array"
    if origin is dict:
        return "object"
    return "string"
