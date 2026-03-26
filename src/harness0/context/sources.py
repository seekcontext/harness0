"""ContextSource implementations — the pluggable data providers for L1."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class ContextSource(ABC):
    """Base class for all context sources."""

    @abstractmethod
    async def load(self) -> str:
        """Load and return the source content as a string."""

    @property
    def last_modified(self) -> float:
        """Return the last modification timestamp (epoch seconds). 0 = unknown."""
        return 0.0


class InlineSource(ContextSource):
    """Static string content, defined directly in code or config."""

    def __init__(self, content: str) -> None:
        self._content = content
        self._loaded_at = time.time()

    async def load(self) -> str:
        return self._content

    @property
    def last_modified(self) -> float:
        return self._loaded_at


class FileSource(ContextSource):
    """Load content from a single file on disk."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    async def load(self) -> str:
        if not self.path.exists():
            raise FileNotFoundError(f"Context file not found: {self.path}")
        return await asyncio.to_thread(self.path.read_text, encoding="utf-8")

    @property
    def last_modified(self) -> float:
        try:
            return self.path.stat().st_mtime
        except OSError:
            return 0.0


class DirectorySource(ContextSource):
    """Load and concatenate all matching files in a directory."""

    def __init__(
        self,
        directory: str | Path,
        glob: str = "**/*.md",
        separator: str = "\n\n---\n\n",
    ) -> None:
        self.directory = Path(directory)
        self.glob = glob
        self.separator = separator

    async def load(self) -> str:
        if not self.directory.is_dir():
            raise NotADirectoryError(f"Context directory not found: {self.directory}")
        files = sorted(self.directory.glob(self.glob))
        if not files:
            return ""
        contents = await asyncio.gather(
            *[asyncio.to_thread(f.read_text, encoding="utf-8") for f in files]
        )
        return self.separator.join(
            f"### {f.name}\n{content}" for f, content in zip(files, contents, strict=False)
        )

    @property
    def last_modified(self) -> float:
        try:
            return max(
                (f.stat().st_mtime for f in self.directory.glob(self.glob)), default=0.0
            )
        except OSError:
            return 0.0


class CallableSource(ContextSource):
    """Dynamic source backed by an async or sync callable."""

    def __init__(self, fn: Callable[[], Any]) -> None:
        self._fn = fn
        self._loaded_at: float = 0.0

    async def load(self) -> str:
        if asyncio.iscoroutinefunction(self._fn):
            result = await self._fn()
        else:
            result = await asyncio.to_thread(self._fn)
        self._loaded_at = time.time()
        return str(result)

    @property
    def last_modified(self) -> float:
        return self._loaded_at


def make_source(spec: str | ContextSource) -> ContextSource:
    """
    Parse a source spec string from harness.yaml into a ContextSource instance.

    Supported formats:
      "path/to/file.md"            → FileSource
      "dir:path/to/dir"            → DirectorySource
      "inline:some text here"      → InlineSource
    """
    if isinstance(spec, ContextSource):
        return spec
    if spec.startswith("dir:"):
        return DirectorySource(spec[4:])
    if spec.startswith("inline:"):
        return InlineSource(spec[7:])
    return FileSource(spec)
