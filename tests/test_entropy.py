"""Tests for EntropyManager and EntropyGardener."""

from __future__ import annotations

import pytest

from harness0.context.layers import ContextLayer, DisclosureLevel, Freshness
from harness0.context.sources import InlineSource
from harness0.core.config import EntropyConfig, FeedbackConfig, GoldenRule
from harness0.core.types import Message, TurnContext
from harness0.entropy.gardener import EntropyGardener
from harness0.entropy.manager import EntropyManager
from harness0.feedback.translator import FeedbackTranslator
from harness0.tools.registry import ToolRegistry


@pytest.fixture
def entropy_translator() -> FeedbackTranslator:
    return FeedbackTranslator(FeedbackConfig(max_signals_per_turn=50))


@pytest.mark.asyncio
async def test_entropy_deduplicates_tool_results(entropy_translator: FeedbackTranslator) -> None:
    cfg = EntropyConfig(compression_threshold=1_000_000, gardener_enabled=False)
    em = EntropyManager(cfg, translator=entropy_translator)
    messages = [
        Message(role="tool", content="same output here", name="t", tool_call_id="1"),
        Message(role="tool", content="same output here", name="t", tool_call_id="2"),
    ]
    cleaned, actions = await em.process(messages, TurnContext(task="t"), context_layers=None)
    assert len(cleaned) == 1
    assert actions == []


@pytest.mark.asyncio
async def test_entropy_removes_stale_harness_signals(
    entropy_translator: FeedbackTranslator,
) -> None:
    cfg = EntropyConfig(
        compression_threshold=1_000_000,
        decay_check_interval=2,
        gardener_enabled=False,
    )
    em = EntropyManager(cfg, translator=entropy_translator)
    sig = "<harness:signals>\n<x/>\n</harness:signals>"
    messages = [
        Message(role="system", content=sig),
        Message(role="system", content=sig),
        Message(role="system", content=sig),
    ]
    cleaned, _ = await em.process(messages, TurnContext(task="t"), context_layers=None)
    assert len(cleaned) < len(messages)


@pytest.mark.asyncio
async def test_entropy_compression_drops_old_messages(
    entropy_translator: FeedbackTranslator,
) -> None:
    cfg = EntropyConfig(compression_threshold=50, gardener_enabled=False)
    em = EntropyManager(cfg, translator=entropy_translator)
    long_content = "token " * 200
    messages = [
        Message(role="user", content="keep me — task"),
        Message(role="assistant", content="filler"),
        Message(role="user", content=long_content),
    ]
    cleaned, _ = await em.process(messages, TurnContext(task="t"), context_layers=None)
    assert any("keep me" in m.content for m in cleaned if m.role == "user")


def test_detect_conflicts_disabled(entropy_translator: FeedbackTranslator) -> None:
    cfg = EntropyConfig(detect_conflicts=False)
    em = EntropyManager(cfg, translator=entropy_translator)
    msgs = [
        Message(role="system", content="always foo"),
        Message(role="system", content="never foo"),
    ]
    assert em.detect_conflicts(msgs) == []


def test_detect_conflicts_finds_overlap(entropy_translator: FeedbackTranslator) -> None:
    cfg = EntropyConfig(detect_conflicts=True)
    em = EntropyManager(cfg, translator=entropy_translator)
    msgs = [
        Message(role="system", content="always use python"),
        Message(role="system", content="never use python"),
    ]
    conflicts = em.detect_conflicts(msgs)
    assert conflicts


@pytest.mark.asyncio
async def test_gardener_skips_when_disabled(entropy_translator: FeedbackTranslator) -> None:
    cfg = EntropyConfig(gardener_enabled=False, gardener_interval_turns=1)
    g = EntropyGardener(config=cfg, translator=entropy_translator)
    layer = ContextLayer(
        name="L",
        source=InlineSource("x"),
        freshness=Freshness.STATIC,
    )
    actions = await g.maybe_garden([layer])
    assert actions == []


@pytest.mark.asyncio
async def test_gardener_runs_on_interval(entropy_translator: FeedbackTranslator) -> None:
    cfg = EntropyConfig(
        gardener_enabled=True,
        gardener_interval_turns=2,
        staleness_threshold_hours=0,
        golden_rules=[],
    )
    g = EntropyGardener(config=cfg, translator=entropy_translator)
    layer = ContextLayer(
        name="L",
        source=InlineSource("always use X in layer A"),
        disclosure_level=DisclosureLevel.INDEX,
    )
    layer2 = ContextLayer(
        name="L2",
        source=InlineSource("never use X in layer B"),
        disclosure_level=DisclosureLevel.INDEX,
    )
    await layer.get_content(session_id="s")
    await layer2.get_content(session_id="s")
    assert await g.maybe_garden([layer, layer2]) == []
    actions = await g.maybe_garden([layer, layer2])
    assert isinstance(actions, list)


@pytest.mark.asyncio
async def test_gardener_duplicate_tools_flag(entropy_translator: FeedbackTranslator) -> None:
    cfg = EntropyConfig(gardener_enabled=True, gardener_interval_turns=1, golden_rules=[])
    reg = ToolRegistry()
    from harness0.tools.schema import ToolDefinition

    reg.register(ToolDefinition(name="a", description="DupDesc", parameters=[]))
    reg.register(ToolDefinition(name="b", description="dupdesc", parameters=[]))
    g = EntropyGardener(config=cfg, translator=entropy_translator, tool_registry=reg)
    layer = ContextLayer(name="L", source=InlineSource("z"))
    actions = await g.garden([layer])
    assert any(
        "duplicate" in a.reason.lower()
        or "Duplicate" in (a.signal.message if a.signal else "")
        for a in actions
    )


@pytest.mark.asyncio
async def test_gardener_golden_rule_conflicting_instructions(
    entropy_translator: FeedbackTranslator,
) -> None:
    cfg = EntropyConfig(
        gardener_enabled=True,
        gardener_interval_turns=1,
        golden_rules=[
            GoldenRule(
                id="no_conflicting_instructions",
                description="No conflicts",
                severity="warning",
            )
        ],
    )
    g = EntropyGardener(config=cfg, translator=entropy_translator)
    layer_a = ContextLayer(
        name="A",
        source=InlineSource("always use foobar for deploys"),
        disclosure_level=DisclosureLevel.INDEX,
    )
    layer_b = ContextLayer(
        name="B",
        source=InlineSource("never use foobar for deploys"),
        disclosure_level=DisclosureLevel.INDEX,
    )
    await layer_a.get_content(session_id="s")
    await layer_b.get_content(session_id="s")
    actions = await g.garden([layer_a, layer_b])
    assert any(a.action_type == "flag" for a in actions)
