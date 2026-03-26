"""ContextLayer — the unit of assembly in L1."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .sources import ContextSource, make_source


class Freshness(StrEnum):
    STATIC = "static"        # Load once at init, cache forever
    PER_SESSION = "per_session"  # Reload once per session start
    PER_TURN = "per_turn"    # Reload on every turn


class DisclosureLevel(StrEnum):
    INDEX = "index"    # Always injected — brief, pointer-based (the "map")
    DETAIL = "detail"  # Loaded selectively — only when task keywords match


class ContextLayer(BaseModel):
    """
    A single named unit of context with its source, priority, freshness, and
    disclosure level.

    Progressive disclosure: INDEX layers are always present in every turn's
    context window. DETAIL layers are only loaded when the current task contains
    any of the declared keywords, keeping the total token footprint small.
    """

    name: str
    source: ContextSource
    priority: int = 0
    freshness: Freshness = Freshness.STATIC
    max_tokens: int | None = None
    disclosure_level: DisclosureLevel = DisclosureLevel.INDEX
    keywords: list[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _content_cache: str | None = None
    _cached_at: float = 0.0
    _cached_session: str = ""

    def is_relevant_for_task(self, task: str) -> bool:
        """Return True if this DETAIL layer should be loaded for the given task."""
        if self.disclosure_level == DisclosureLevel.INDEX:
            return True
        if not self.keywords:
            return True
        task_lower = task.lower()
        return any(kw.lower() in task_lower for kw in self.keywords)

    def is_stale(self, staleness_threshold_hours: float) -> bool:
        """Return True if the underlying source file is older than the threshold."""
        threshold_seconds = staleness_threshold_hours * 3600
        modified = self.source.last_modified
        if modified == 0.0:
            return False
        return (time.time() - modified) > threshold_seconds

    async def get_content(
        self, session_id: str = "", force_reload: bool = False
    ) -> str:
        """Load content with freshness-aware caching."""
        should_reload = force_reload or self._content_cache is None

        if not should_reload:
            match self.freshness:
                case Freshness.PER_TURN:
                    should_reload = True
                case Freshness.PER_SESSION:
                    should_reload = session_id != self._cached_session
                case Freshness.STATIC:
                    should_reload = False

        if should_reload:
            self._content_cache = await self.source.load()
            self._cached_at = time.time()
            self._cached_session = session_id

        return self._content_cache or ""

    @classmethod
    def from_config(cls, cfg: Any) -> ContextLayer:
        """Build a ContextLayer from a ContextLayerConfig pydantic model."""
        return cls(
            name=cfg.name,
            source=make_source(cfg.source),
            priority=cfg.priority,
            freshness=Freshness(cfg.freshness),
            max_tokens=cfg.max_tokens,
            disclosure_level=DisclosureLevel(cfg.disclosure_level),
            keywords=cfg.keywords,
        )
