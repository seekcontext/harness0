"""ApprovalManager — L3 risk-based approval workflows."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from harness0.feedback.translator import FeedbackTranslator

if TYPE_CHECKING:
    from harness0.core.config import SecurityConfig

logger = logging.getLogger(__name__)


class ApprovalBackend(ABC):
    """Pluggable approval UI. Default is stdin; swap for Slack, web, etc."""

    @abstractmethod
    async def request(self, action: str, context: str) -> bool:
        """Prompt for approval. Return True if approved, False if denied."""


class StdinApprovalBackend(ApprovalBackend):
    """Default backend: prompt the user on stdin. Blocks the event loop briefly."""

    async def request(self, action: str, context: str) -> bool:
        prompt = (
            f"\n[harness0] Approval required\n"
            f"Action : {action}\n"
            f"Context: {context}\n"
            f"Allow? [y/N] "
        )
        answer = await asyncio.to_thread(input, prompt)
        return answer.strip().lower() in {"y", "yes"}


class AutoDenyBackend(ApprovalBackend):
    """Non-interactive backend: always deny. Useful for testing."""

    async def request(self, action: str, context: str) -> bool:
        logger.info("AutoDeny: denied action %r", action)
        return False


class AutoApproveBackend(ApprovalBackend):
    """Non-interactive backend: always approve. Use only in trusted environments."""

    async def request(self, action: str, context: str) -> bool:
        logger.info("AutoApprove: approved action %r", action)
        return True


class ApprovalManager:
    """
    Manages risk-based approval workflows with a fingerprint cache.

    Three modes (configured via harness.yaml):
      always      — every action requires approval
      risky_only  — only EXECUTE and CRITICAL risk levels require approval
      never       — approvals are skipped (use only in sandboxed/trusted environments)

    SHA-256 fingerprint cache: once an action is approved, the same action
    fingerprint is auto-approved for the remainder of the session.
    """

    def __init__(
        self,
        config: SecurityConfig,
        backend: ApprovalBackend | None = None,
    ) -> None:
        self.config = config
        self.backend = backend or StdinApprovalBackend()
        self._approved_fingerprints: set[str] = set()

    @staticmethod
    def _fingerprint(action: str) -> str:
        return hashlib.sha256(action.encode()).hexdigest()

    async def request(
        self,
        action: str,
        risk_level: str,
        context: str = "",
        translator: FeedbackTranslator | None = None,
    ) -> bool:
        """
        Request approval for an action. Returns True if approved.

        Emits a FeedbackSignal on denial so the agent understands why and
        what it can do instead.
        """
        mode = self.config.approval_mode

        if mode == "never":
            return True

        if mode == "risky_only" and risk_level not in ("execute", "critical"):
            return True

        fp = self._fingerprint(action)
        if fp in self._approved_fingerprints:
            logger.debug("Action approved via fingerprint cache: %s", action[:60])
            return True

        approved = await self.backend.request(action, context)

        if approved:
            self._approved_fingerprints.add(fp)
            logger.info("Approved: %s", action[:80])
        else:
            logger.info("Denied: %s", action[:80])
            signal = FeedbackTranslator.approval_denied(action)
            if translator:
                await translator.add(signal)

        return approved

    def clear_cache(self) -> None:
        """Clear the fingerprint cache (e.g. when session ends)."""
        self._approved_fingerprints.clear()
