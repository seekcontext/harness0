"""Tests for L1 context assembly and sources."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from harness0.context.assembler import ContextAssembler
from harness0.context.layers import ContextLayer, DisclosureLevel
from harness0.context.sources import InlineSource, make_source
from harness0.core.config import ContextConfig, ContextLayerConfig
from harness0.core.types import TurnContext

if TYPE_CHECKING:
    from pathlib import Path


def test_make_source_inline_and_file(tmp_path: Path) -> None:
    from harness0.context.sources import FileSource, InlineSource

    f = tmp_path / "a.md"
    f.write_text("file content", encoding="utf-8")
    assert isinstance(make_source(str(f)), FileSource)
    assert isinstance(make_source("inline:hello"), InlineSource)


@pytest.mark.asyncio
async def test_context_layer_detail_keywords() -> None:
    layer = ContextLayer(
        name="api",
        source=InlineSource("API docs"),
        disclosure_level=DisclosureLevel.DETAIL,
        keywords=["api", "rest"],
    )
    assert layer.is_relevant_for_task("call the API") is True
    assert layer.is_relevant_for_task("unrelated task") is False


@pytest.mark.asyncio
async def test_context_assembler_assemble_index_only() -> None:
    layer = ContextLayer(
        name="base",
        source=InlineSource("You are helpful."),
        priority=0,
        disclosure_level=DisclosureLevel.INDEX,
    )
    asm = ContextAssembler([layer], total_token_budget=2000)
    msgs = await asm.assemble(TurnContext(task="anything", session_id="s1"))
    assert len(msgs) == 1
    assert msgs[0].role == "system"
    assert "helpful" in msgs[0].content


@pytest.mark.asyncio
async def test_context_assembler_from_config(tmp_path: Path) -> None:
    cfg = ContextConfig(
        layers=[
            ContextLayerConfig(
                name="L",
                source="inline:Configured layer.",
                priority=1,
                disclosure_level="index",
            )
        ],
        total_token_budget=1000,
    )
    asm = ContextAssembler.from_config(cfg)
    msgs = await asm.assemble(TurnContext(task="t", session_id="sid"))
    assert msgs and "Configured" in msgs[0].content


def test_context_assembler_remove_layer() -> None:
    a = ContextLayer(name="a", source=InlineSource("a"), priority=0)
    b = ContextLayer(name="b", source=InlineSource("b"), priority=1)
    asm = ContextAssembler([a, b])
    assert asm.remove_layer("a") is True
    assert len(asm.layers) == 1
    assert asm.layers[0].name == "b"
