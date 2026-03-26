"""Tests for HarnessConfig and nested models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml
from pydantic import ValidationError

from harness0.core.config import (
    ContextLayerConfig,
    GoldenRule,
    HarnessConfig,
    LLMConfig,
    SecurityConfig,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_harness_config_defaults() -> None:
    cfg = HarnessConfig.default()
    assert cfg.max_iterations == 50
    assert cfg.llm.provider == "openai"
    assert cfg.context.total_token_budget == 8000
    assert "rm -rf" in cfg.security.blocked_commands


def test_harness_config_from_yaml_roundtrip(tmp_path: Path) -> None:
    data = {
        "max_iterations": 12,
        "llm": {"model": "gpt-4o-mini", "temperature": 0.2},
        "context": {
            "total_token_budget": 4000,
            "layers": [
                {
                    "name": "rules",
                    "source": "inline:Be concise.",
                    "priority": 0,
                    "freshness": "static",
                    "disclosure_level": "index",
                }
            ],
        },
        "entropy": {
            "golden_rules": [
                {
                    "id": "no_conflicting_instructions",
                    "description": "No conflicts",
                    "severity": "warning",
                }
            ]
        },
    }
    path = tmp_path / "harness.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    cfg = HarnessConfig.from_yaml(path)
    assert cfg.max_iterations == 12
    assert cfg.llm.model == "gpt-4o-mini"
    assert cfg.llm.temperature == 0.2
    assert cfg.context.total_token_budget == 4000
    assert len(cfg.context.layers) == 1
    assert cfg.context.layers[0].name == "rules"
    assert len(cfg.entropy.golden_rules) == 1
    assert cfg.entropy.golden_rules[0].id == "no_conflicting_instructions"


def test_harness_config_from_empty_yaml_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    cfg = HarnessConfig.from_yaml(path)
    assert isinstance(cfg, HarnessConfig)


def test_security_config_approval_mode_literal() -> None:
    s = SecurityConfig(approval_mode="never")
    assert s.approval_mode == "never"


def test_llm_config_optional_api_key() -> None:
    llm = LLMConfig(api_key=None, base_url=None)
    assert llm.api_key is None


def test_context_layer_config_keywords_default() -> None:
    cl = ContextLayerConfig(name="n", source="inline:x")
    assert cl.keywords == []


def test_golden_rule_severity() -> None:
    r = GoldenRule(id="r1", description="d", severity="error")
    assert r.severity == "error"


def test_invalid_yaml_structure_rejected() -> None:
    with pytest.raises(ValidationError):
        HarnessConfig.model_validate({"max_iterations": "not_an_int"})
