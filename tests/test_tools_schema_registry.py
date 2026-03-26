"""Tests for ToolDefinition, ToolRegistry, and schema helpers."""

from __future__ import annotations

import pytest

from harness0.tools.registry import ToolRegistry
from harness0.tools.schema import ParameterSchema, RiskLevel, ToolDefinition


def test_risk_level_str_enum() -> None:
    assert RiskLevel.READ == "read"
    assert RiskLevel("execute") == RiskLevel.EXECUTE


def test_tool_definition_validate_arguments() -> None:
    tool = ToolDefinition(
        name="add",
        description="add two numbers",
        parameters=[
            ParameterSchema(name="a", type="integer", description="first"),
            ParameterSchema(name="b", type="integer", description="second"),
        ],
        risk_level=RiskLevel.READ,
    )
    assert tool.validate_arguments({"a": 1, "b": 2}) == []
    errs = tool.validate_arguments({"a": 1})
    assert any("b" in e for e in errs)


def test_tool_definition_to_openai_schema() -> None:
    tool = ToolDefinition(
        name="greet",
        description="Say hi",
        parameters=[
            ParameterSchema(
                name="name",
                type="string",
                description="Who",
                required=False,
                default="world",
            ),
        ],
    )
    schema = tool.to_openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "greet"
    props = schema["function"]["parameters"]["properties"]
    assert "name" in props
    assert props["name"].get("default") == "world"
    assert "name" not in schema["function"]["parameters"]["required"]


def test_tool_definition_from_function_sync() -> None:
    def sync_tool(x: int, y: str = "ok") -> str:
        """Does something."""
        return str(x)

    td = ToolDefinition.from_function(sync_tool, risk_level=RiskLevel.WRITE)
    assert td.name == "sync_tool"
    assert td.handler is sync_tool
    assert td.risk_level == RiskLevel.WRITE
    names = {p.name for p in td.parameters}
    assert names == {"x", "y"}


@pytest.mark.asyncio
async def test_tool_definition_from_function_async() -> None:
    async def async_tool(q: str) -> str:
        return q

    td = ToolDefinition.from_function(async_tool)
    assert td.name == "async_tool"


def test_registry_register_get_require() -> None:
    reg = ToolRegistry()
    t = ToolDefinition(name="t1", description="d", parameters=[])
    reg.register(t)
    assert reg.get("t1") is t
    assert reg.require("t1") is t
    with pytest.raises(KeyError, match="not registered"):
        reg.require("missing")


def test_registry_openai_schemas_and_names() -> None:
    reg = ToolRegistry()
    reg.register(ToolDefinition(name="a", description="da", parameters=[]))
    reg.register(ToolDefinition(name="b", description="db", parameters=[]))
    schemas = reg.openai_schemas()
    assert len(schemas) == 2
    assert set(reg.names()) == {"a", "b"}
    assert "a" in reg
    assert len(reg) == 2


def test_registry_has_duplicates() -> None:
    reg = ToolRegistry()
    reg.register(ToolDefinition(name="x", description="Same", parameters=[]))
    reg.register(ToolDefinition(name="y", description="same ", parameters=[]))
    dups = reg.has_duplicates()
    assert dups
    assert ("x", "y") in dups or ("y", "x") in dups
