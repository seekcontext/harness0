"""harness0 — Layer 0 of agent reliability.

    Agent = Loop(Model + Harness)
    You provide the Model. harness0 provides the Harness.

Five composable layers, independently importable:

    from harness0 import HarnessEngine                    # all 5 layers
    from harness0.context import ContextAssembler         # L1 only
    from harness0.tools import ToolInterceptor            # L2 only
    from harness0.security import CommandGuard            # L3 only
    from harness0.feedback import FeedbackTranslator      # L4 only
    from harness0.entropy import EntropyManager           # L5 only
"""

__version__ = "0.0.4"

from harness0.context import (
    CallableSource,
    ContextAssembler,
    ContextLayer,
    DirectorySource,
    DisclosureLevel,
    FileSource,
    Freshness,
    InlineSource,
)
from harness0.core import (
    AgentState,
    EntropyConfig,
    FeedbackConfig,
    GoldenRule,
    HarnessConfig,
    LLMConfig,
    Message,
    SecurityConfig,
    ToolCall,
    ToolGovernanceConfig,
    ToolResult,
    TurnContext,
)
from harness0.engine import HarnessEngine, RunResult
from harness0.entropy import EntropyGardener, EntropyManager, GardenAction
from harness0.feedback import FeedbackSignal, FeedbackTranslator, SignalBundle, SignalType
from harness0.security import (
    ApprovalManager,
    AutoApproveBackend,
    AutoDenyBackend,
    CommandGuard,
    ProcessSandbox,
    StdinApprovalBackend,
)
from harness0.tools import AuditRecord, RiskLevel, ToolDefinition, ToolInterceptor, ToolRegistry

__all__ = [
    # Engine
    "HarnessEngine",
    "RunResult",
    # Config
    "HarnessConfig",
    "LLMConfig",
    "SecurityConfig",
    "FeedbackConfig",
    "EntropyConfig",
    "ToolGovernanceConfig",
    "GoldenRule",
    # Core types
    "Message",
    "ToolCall",
    "ToolResult",
    "TurnContext",
    "AgentState",
    # L1
    "ContextAssembler",
    "ContextLayer",
    "Freshness",
    "DisclosureLevel",
    "FileSource",
    "DirectorySource",
    "InlineSource",
    "CallableSource",
    # L2
    "RiskLevel",
    "ToolDefinition",
    "ToolRegistry",
    "ToolInterceptor",
    "AuditRecord",
    # L3
    "CommandGuard",
    "ProcessSandbox",
    "ApprovalManager",
    "StdinApprovalBackend",
    "AutoDenyBackend",
    "AutoApproveBackend",
    # L4
    "FeedbackSignal",
    "SignalType",
    "SignalBundle",
    "FeedbackTranslator",
    # L5
    "EntropyManager",
    "EntropyGardener",
    "GardenAction",
]
