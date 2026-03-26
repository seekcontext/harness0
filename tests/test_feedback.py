"""Tests for FeedbackSignal, SignalBundle, and FeedbackTranslator."""

from __future__ import annotations

import pytest

from harness0.core.config import FeedbackConfig
from harness0.feedback.signals import FeedbackSignal, SignalBundle, SignalType
from harness0.feedback.translator import FeedbackTranslator


def test_feedback_signal_xml_hint_contains_tags() -> None:
    s = FeedbackSignal(
        type=SignalType.ERROR,
        source="test",
        message="oops",
        fix_instructions="1. Fix it",
    )
    xml = s.to_xml_hint()
    assert "harness:signal" in xml
    assert "oops" in xml
    assert "fix_instructions" in xml


def test_signal_bundle_render_xml_wraps() -> None:
    b = SignalBundle(
        signals=[
            FeedbackSignal(type=SignalType.INFO, source="a", message="m1"),
        ]
    )
    out = b.render("xml")
    assert "<harness:signals>" in out


def test_signal_bundle_has_errors() -> None:
    b = SignalBundle(
        signals=[
            FeedbackSignal(type=SignalType.WARNING, source="w", message="w"),
            FeedbackSignal(type=SignalType.ERROR, source="e", message="e"),
        ]
    )
    assert b.has_errors() is True
    assert b.has_actionable() is True


@pytest.mark.asyncio
async def test_translator_flush_clears_bundle() -> None:
    tr = FeedbackTranslator(FeedbackConfig())
    await tr.add(
        FeedbackSignal(type=SignalType.INFO, source="s", message="hello")
    )
    b1 = await tr.flush()
    assert len(b1.signals) == 1
    b2 = await tr.flush()
    assert b2.signals == []


@pytest.mark.asyncio
async def test_translator_respects_max_signals_per_turn() -> None:
    tr = FeedbackTranslator(FeedbackConfig(max_signals_per_turn=2))
    for i in range(5):
        await tr.add(
            FeedbackSignal(type=SignalType.INFO, source="s", message=str(i))
        )
    b = await tr.flush()
    assert len(b.signals) == 2


def test_render_bundle_inject_hints_disabled() -> None:
    tr = FeedbackTranslator(FeedbackConfig(inject_hints=False))
    b = SignalBundle(
        signals=[FeedbackSignal(type=SignalType.INFO, source="s", message="x")]
    )
    assert tr.render_bundle(b) == ""


def test_static_factory_methods() -> None:
    s1 = FeedbackTranslator.output_truncated("t", 100, 10)
    assert s1.type == SignalType.WARNING
    s2 = FeedbackTranslator.approval_denied("action")
    assert "denied" in s2.message.lower()
    s3 = FeedbackTranslator.tool_schema_invalid("tool", "bad args")
    assert "schema" in s3.message.lower()
