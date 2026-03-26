"""HarnessConfig — single source of truth for all 5 layers, loaded from harness.yaml."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import yaml
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pathlib import Path


class ContextLayerConfig(BaseModel):
    name: str
    source: str
    priority: int = 0
    freshness: Literal["static", "per_session", "per_turn"] = "static"
    max_tokens: int | None = None
    disclosure_level: Literal["index", "detail"] = "index"
    keywords: list[str] = Field(default_factory=list)


class ContextConfig(BaseModel):
    layers: list[ContextLayerConfig] = Field(default_factory=list)
    total_token_budget: int = 8000


class ToolGovernanceConfig(BaseModel):
    default_risk: Literal["read", "write", "execute", "critical"] = "read"
    max_output_tokens: int = 5000
    audit_enabled: bool = True


class GoldenRule(BaseModel):
    """A mechanically verifiable invariant for EntropyGardener to enforce."""

    id: str
    description: str
    severity: Literal["error", "warning", "info"] = "warning"


class SecurityConfig(BaseModel):
    sandbox_enabled: bool = True
    max_processes: int = 5
    max_output_bytes: int = 100_000
    default_timeout: int = 30
    blocked_commands: list[str] = Field(
        default_factory=lambda: ["rm -rf", "sudo", "> /dev/sda", ":(){ :|:& };:"]
    )
    approval_mode: Literal["always", "risky_only", "never"] = "risky_only"


class FeedbackConfig(BaseModel):
    inject_hints: bool = True
    signal_format: Literal["xml", "json", "markdown"] = "xml"
    max_signals_per_turn: int = 10


class EntropyConfig(BaseModel):
    compression_threshold: int = 6000
    decay_check_interval: int = 10
    detect_conflicts: bool = True
    staleness_threshold_hours: int = 24
    gardener_enabled: bool = True
    gardener_interval_turns: int = 5
    golden_rules: list[GoldenRule] = Field(default_factory=list)


class LLMConfig(BaseModel):
    provider: Literal["openai", "anthropic", "compatible"] = "openai"
    model: str = "gpt-4o"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.0
    max_tokens: int = 4096


class HarnessConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    tools: ToolGovernanceConfig = Field(default_factory=ToolGovernanceConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
    entropy: EntropyConfig = Field(default_factory=EntropyConfig)
    max_iterations: int = 50
    checkpoint_enabled: bool = True

    @classmethod
    def from_yaml(cls, path: str | Path) -> HarnessConfig:
        """Load config from a harness.yaml file."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls.model_validate(data)

    @classmethod
    def default(cls) -> HarnessConfig:
        """Return a sensible default config for quick start."""
        return cls()
