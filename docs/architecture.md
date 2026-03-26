# Harness0 — Technical Architecture

## Overview

harness0 implements the 5-layer Harness model as composable, framework-agnostic Python components. Each layer can be used independently or wired together via the `HarnessEngine` facade.

```
HarnessEngine (facade — wires all 5 layers together)
    ├── L1 ContextAssembler    ← independently importable
    ├── L2 ToolInterceptor     ← independently importable
    ├── L3 SecurityGuard       ← independently importable
    ├── L4 FeedbackTranslator  ← independently importable
    └── L5 EntropyManager      ← independently importable
```

## System Architecture

```
                    ┌─────────────────────────┐
                    │      User / CLI / SDK    │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │     HarnessEngine        │
                    │   (facade, entry point)   │
                    └────────────┬─────────────┘
                                 │
               ┌─────────────────▼─────────────────┐
               │           AgentLoop               │
               │   assemble → call LLM → handle    │
               │   tool calls → collect feedback   │
               │   → check entropy → repeat        │
               └──┬──────┬──────┬──────┬──────┬────┘
                  │      │      │      │      │
            ┌─────▼┐ ┌──▼───┐ ┌▼────┐ ┌▼────┐ ┌▼─────┐
            │  L1  │ │  L2  │ │ L3  │ │ L4  │ │  L5  │
            │Contxt│ │Tools │ │Secur│ │Feedb│ │Entro │
            │Assem.│ │Govnc.│ │Guard│ │Loop │ │Mgmt. │
            └──────┘ └──────┘ └──────┘ └─────┘ └──────┘
                  │      │      │      │      │
            ┌─────▼──────▼──────▼──────▼──────▼────┐
            │           LLM Provider               │
            │   (OpenAI / Anthropic / DeepSeek)     │
            └──────────────────────────────────────┘
```

## Cross-Layer Coordination

The 5 layers are not independent pipelines — they form a coordinated system:

```
L3 SecurityGuard blocks "rm -rf /"
        │
        ▼
L4 FeedbackTranslator generates signal:
   "Command rejected by security policy. Suggestion: use targeted delete."
        │
        ▼
L1 ContextAssembler injects signal into next turn's context
        │
        ▼
LLM receives actionable feedback → adjusts behavior
        │
        ▼
L5 EntropyManager detects accumulated old feedback signals
        │
        ▼
L1 ContextAssembler removes stale signals on next assembly
```

## Project Structure

```
harness0/
├── src/harness0/
│   ├── __init__.py              # Version, top-level exports
│   ├── engine.py                # HarnessEngine facade
│   ├── core/
│   │   ├── loop.py              # AgentLoop runner
│   │   ├── state.py             # AgentState, checkpoint/restore
│   │   └── config.py            # HarnessConfig (Pydantic)
│   ├── context/                 # L1: Context Assembly
│   │   ├── assembler.py         # ContextAssembler
│   │   ├── layers.py            # ContextLayer, priority, freshness
│   │   └── sources.py           # File/Dir/Callable/Inline sources
│   ├── tools/                   # L2: Tool Governance
│   │   ├── registry.py          # ToolRegistry
│   │   ├── governance.py        # RiskLevel, approval rules
│   │   ├── schema.py            # ToolDefinition DSL
│   │   └── interceptor.py       # ToolInterceptor pipeline
│   ├── security/                # L3: Security Guard
│   │   ├── sandbox.py           # ProcessSandbox
│   │   ├── command_guard.py     # CommandGuard
│   │   └── approval.py          # ApprovalManager
│   ├── feedback/                # L4: Feedback Loop
│   │   ├── translator.py        # FeedbackTranslator
│   │   ├── hints.py             # SystemHint builder
│   │   └── signals.py           # FeedbackSignal types
│   ├── entropy/                 # L5: Entropy Management
│   │   ├── manager.py           # EntropyManager orchestrator
│   │   ├── compressor.py        # Context window compression
│   │   └── decay.py             # Rule/memory expiry detection
│   ├── llm/
│   │   ├── base.py              # LLMProvider ABC
│   │   ├── openai.py            # OpenAI adapter
│   │   └── anthropic.py         # Anthropic adapter
│   ├── integrations/            # Framework adapters (optional install)
│   │   ├── __init__.py
│   │   ├── langchain.py         # pip install harness0[langchain]
│   │   ├── openai_sdk.py        # pip install harness0[openai]
│   │   ├── pydantic_ai.py       # pip install harness0[pydantic-ai]
│   │   └── crewai.py            # pip install harness0[crewai]
│   └── plugins/
│       ├── base.py              # ToolPlugin ABC
│       └── builtin/
│           ├── file_tools.py    # read_file, write_file, list_dir
│           ├── shell_tools.py   # run_command (sandboxed)
│           └── search_tools.py  # grep, glob
├── examples/
│   └── simple_agent.py          # Minimal working example
├── tests/
├── pyproject.toml
├── README.md
└── LICENSE
```

## Layer Details

### L1: Context Assembly

The core insight: prompts are not documents, they are assembly systems.

**Key types:**

```python
class DisclosureLevel(str, Enum):
    INDEX = "index"    # Always injected — brief, pointer-based, < 200 tokens
    DETAIL = "detail"  # Loaded selectively based on task relevance

class ContextLayer(BaseModel):
    name: str                              # e.g. "base", "soul", "agents", "skills"
    priority: int                          # Higher = loaded later = higher override
    source: ContextSource                  # File, directory, callable, or inline
    freshness: Freshness                   # static / per_session / per_turn
    max_tokens: int | None                 # Per-layer token budget
    disclosure_level: DisclosureLevel      # Index (always) vs Detail (selective)

class ContextAssembler:
    async def assemble(self, turn_context: TurnContext) -> list[Message]:
        """
        1. Load all INDEX layers unconditionally.
        2. Load DETAIL layers only when task keywords match.
        3. Sort by priority → apply token budgets → return messages.
        """
```

**Source types:**
- `FileSource` — Load from `.md` / `.yaml` files (maps to AGENTS.md, SOUL.md)
- `DirectorySource` — Auto-scan all files in a directory (maps to skills/)
- `CallableSource` — Runtime-dynamic generation (e.g. inject current state summary)
- `InlineSource` — Direct string content

**Freshness model:**
- `static` — Load once at initialization
- `per_session` — Reload at session start
- `per_turn` — Reload every turn (for dynamic state)

**Progressive disclosure flow:**
```
Turn N arrives
  → All INDEX layers always injected (AGENTS.md index, system rules summary)
  → DETAIL layers checked: does task mention "security"? → inject security.md
  → Token budget applied across all selected layers
  → Messages assembled by priority order
```

### L2: Tool Governance

The core insight: tools are not "a list of functions," they are "governed runtime capabilities."

**Risk levels:**

```python
class RiskLevel(str, Enum):
    READ = "read"           # No side effects (e.g. read_file, search)
    WRITE = "write"         # Modifies state (e.g. write_file)
    EXECUTE = "execute"     # Runs code/commands (e.g. shell)
    CRITICAL = "critical"   # Irreversible or dangerous
```

**Interception pipeline:**

```
ToolCall
  → Schema Validation (check params against JSON Schema)
  → Risk Assessment (classify by RiskLevel)
  → Approval Check (if EXECUTE/CRITICAL: request approval)
  → Execute (run the handler)
  → Output Truncation (enforce max_output_tokens)
  → Audit Log (record call, result, timing)
  → ToolResult
```

**Declarative tool definition via decorator:**

```python
@engine.tool(risk_level=RiskLevel.EXECUTE, requires_approval=True, timeout=30)
async def run_command(command: str) -> str:
    """Execute a shell command in the sandbox."""
    ...
```

### L3: Security Guard

The core insight: security must be enforced at runtime, not in prompts.

**Three lines of defense:**

1. **ProcessSandbox** — Subprocess pool management
   - Max concurrent processes (default: 5)
   - Output cap (default: 100KB)
   - Timeout enforcement (default: 30s)
   - Automatic cleanup on session end

2. **CommandGuard** — Command parsing and blocklist
   - Regex-based command pattern matching
   - Configurable blocklist (`rm -rf`, `sudo`, `> /dev/sda`, etc.)
   - Returns structured `GuardResult` with rejection reason

3. **ApprovalManager** — Risk-based approval workflows
   - Three modes: `always` / `risky_only` / `never`
   - SHA-256 fingerprint cache (approve once, skip same action next time)
   - Pluggable approval backend (default: stdin prompt)

### L4: Feedback Loop

The core insight: translate system events into model-consumable feedback language.

**FeedbackSignal structure:**

```python
class FeedbackSignal(BaseModel):
    type: SignalType           # "error" | "warning" | "info" | "constraint"
    source: str                # Which subsystem generated this
    message: str               # Human/model-readable explanation
    actionable: bool           # Can the model do something about it?
    suggestion: str | None     # Recommended next step (brief)
    fix_instructions: str | None  # Step-by-step agent-consumable repair guidance
    
    def to_xml_hint(self) -> str:
        """Render as XML-tagged hint for injection into agent context."""
```

The `fix_instructions` field is the key difference from a simple error message. It contains complete, actionable steps the agent can execute immediately — modeled on OpenAI's linter error messages that embed fix guidance directly into agent context.

**Translation examples:**

| System Event | Raw Output | Translated Signal |
|---|---|---|
| Command blocked | `PermissionError` | "Command 'rm -rf /' blocked by security policy. Suggestion: use targeted delete on specific files." |
| Output truncated | Silently cut off | "Tool output was truncated from 50K to 5K tokens. Consider narrowing your search scope." |
| Subprocess timeout | `TimeoutError` | "Command exceeded 30s timeout. Consider breaking into smaller steps or increasing timeout." |
| Approval denied | Empty response | "Action 'deploy to production' was denied by approval policy. This action requires explicit user confirmation." |

**SystemHint injection:** Translated signals are rendered as XML-tagged hints and injected into the next turn's context via L1 ContextAssembler.

### L5: Entropy Management

The core insight: agent systems decay over time. Active maintenance is required.

**EntropyManager capabilities:**

1. **Degradation detection** (what LangChain does NOT do):
   - Rule conflict detection: identify contradictory instructions in context
   - Temporal staleness: flag documents/rules older than threshold
   - Information density scoring: detect low-value, high-token-count content
   - Repetition detection: find duplicate or near-duplicate content

2. **Context compression** (comparable to LangChain Summarization):
   - Summarize old tool results
   - Collapse repeated patterns
   - Trim low-value conversation history

3. **Targeted cleanup** (based on detection results):
   - Remove expired rules rather than compressing them
   - Resolve conflicts by prioritizing newer/higher-priority sources
   - Replace verbose content with structured summaries

4. **EntropyGardener** (NEW — proactive background GC):

```python
class GardenAction(BaseModel):
    action_type: Literal["remove", "update", "flag"]
    target: str            # Layer name or content identifier
    reason: str            # Human-readable explanation
    fix_instructions: str | None  # What to do to fix it

class EntropyGardener:
    """
    Background GC for context quality. Runs every N turns proactively.
    Inspired by OpenAI's doc-gardening agent pattern.
    
    Checks golden rules declared in harness.yaml:
      entropy:
        golden_rules:
          - id: no_stale_layers
            description: "All FileSource layers must be fresher than staleness_threshold_hours"
            severity: warning
          - id: no_duplicate_tools
            description: "No two registered tools may have identical descriptions"
            severity: error
    """
    async def maybe_garden(self, context: list[ContextLayer]) -> list[GardenAction]: ...
    async def garden(self, context: list[ContextLayer]) -> list[GardenAction]: ...
```

**GoldenRule config** in `harness.yaml`:
```yaml
entropy:
  gardener_enabled: true
  gardener_interval_turns: 5
  golden_rules:
    - id: no_stale_layers
      description: "All FileSource layers must be newer than staleness_threshold_hours"
      severity: warning
    - id: no_duplicate_tools
      description: "No two tools may share the same description"
      severity: error
    - id: no_conflicting_instructions
      description: "Detect contradictory rules across context layers"
      severity: error
```

**Difference from LangChain Summarization:**

| | LangChain Summarization | harness0 Entropy Management |
|---|---|---|
| Trigger | Token count near limit | Every N turns proactively |
| Method | LLM summarization of old messages | Detection + classification + targeted cleanup |
| Detects rule conflicts? | No | Yes |
| Detects stale information? | No | Yes |
| Detects repetition patterns? | No | Yes |
| Nature | Passive space reclamation | Active quality maintenance |

## Integration Architecture

Each layer can be used standalone or plugged into existing frameworks via adapters:

### LangChain Integration

Maps harness0 layers to LangChain middleware hooks:

| harness0 Layer | LangChain Hook | Behavior |
|---|---|---|
| L1 ContextAssembler | `before_model` | Assemble context before each LLM call |
| L2 ToolInterceptor | `wrap_tool_call` | Wrap every tool call with validation/risk/audit |
| L3 SecurityGuard | `wrap_tool_call` | Security check before tool execution |
| L4 FeedbackTranslator | `after_model` + `wrap_tool_call` | Collect events and inject feedback signals |
| L5 EntropyManager | `before_model` | Detect and clean context degradation |

```python
from harness0.integrations.langchain import HarnessMiddleware

agent = create_deep_agent(
    model="gpt-4o",
    middleware=[HarnessMiddleware.from_config("harness.yaml")],
)
```

### OpenAI Agents SDK Integration

Maps to guardrails:

```python
from harness0.integrations.openai_sdk import HarnessInputGuardrail, HarnessToolGuardrail

agent = Agent(
    name="coding-agent",
    input_guardrails=[HarnessInputGuardrail(config)],
    tool_guardrails=[HarnessToolGuardrail(config)],
)
```

### PydanticAI Integration

Maps to dependency injection:

```python
from harness0.integrations.pydantic_ai import HarnessDeps

agent = Agent("openai:gpt-4o", deps_type=HarnessDeps)

@agent.tool
async def run_command(ctx: RunContext[HarnessDeps], command: str) -> str:
    return await ctx.deps.execute_tool("run_command", command=command)
```

### CrewAI Integration

Maps to tool wrappers:

```python
from harness0.integrations.crewai import harness_tool

@harness_tool(risk_level="execute", config=harness_config)
def run_shell(command: str) -> str:
    ...
```

## Configuration

All 5 layers are configurable via a single `harness.yaml`:

```yaml
llm:
  provider: openai
  model: gpt-4o

context:
  layers:
    - name: base
      source: prompts/base.md
      priority: 0
    - name: project
      source: AGENTS.md
      priority: 10
      freshness: per_session
    - name: state
      source: callable:get_current_state
      priority: 20
      freshness: per_turn
  total_token_budget: 8000

tools:
  default_risk: read
  max_output_tokens: 5000

security:
  sandbox_enabled: true
  max_processes: 5
  max_output_bytes: 100000
  default_timeout: 30
  blocked_commands:
    - "rm -rf"
    - "sudo"
    - "> /dev/sda"
  approval_mode: risky_only

feedback:
  inject_hints: true
  signal_format: xml

entropy:
  compression_threshold: 6000
  decay_check_interval: 10
  detect_conflicts: true
  staleness_threshold_hours: 24
  gardener_enabled: true
  gardener_interval_turns: 5
  golden_rules:
    - id: no_stale_layers
      description: "All FileSource layers must be newer than staleness_threshold_hours"
      severity: warning
    - id: no_duplicate_tools
      description: "No two tools may share the same description"
      severity: error

max_iterations: 50
checkpoint_enabled: true
```

## Design Principles (Informed by OpenAI Harness Engineering)

These principles are derived from OpenAI's production experience building a 1M-LOC fully agent-generated codebase. They shape every layer of harness0.

### 1. Progressive Disclosure (L1)

> "Give Codex a map, not a 1,000-page manual."

Context is a scarce resource. Injecting everything upfront crowds out the task itself. Instead:

- **Index layers** (`disclosure_level: "index"`) are always injected — brief, < 200 tokens, pointer-based.
- **Detail layers** (`disclosure_level: "detail"`) are loaded selectively when task relevance is detected.

This maps to the `DisclosureLevel` enum on `ContextLayer` and controls the assembly strategy in `ContextAssembler`.

### 2. Agent-Readable Error Messages (L3 → L4)

> "We write error messages with fix instructions injected into agent context."

Raw errors are useless to models. Every rejection, timeout, or constraint violation must be translated into an **actionable, structured signal** that the agent can reason about and act on directly.

`FeedbackSignal` carries a `fix_instructions` field — step-by-step repair guidance formatted for agent consumption, not human reading. `CommandGuard` and all L3 components produce `FeedbackSignal` directly rather than raising bare exceptions.

### 3. Active Entropy Gardening (L5)

> "We started encoding golden principles directly into the repo and built a continuous cleanup loop."
> "Technical debt is like a high-interest loan: pay it down in small amounts continuously."

Passive cleanup (triggered only when token budget is exceeded) is insufficient. harness0 introduces `EntropyGardener` — a background GC process that runs every N turns:

- Scans for staleness, conflicts, and pattern drift
- Applies **golden rules** (mechanically verifiable invariants declared in `harness.yaml`)
- Produces targeted `GardenAction` fixes rather than blunt compression

### 4. Agent-Readable Design (Cross-Cutting)

> "Anything the agent cannot access in context at runtime does not exist."

All harness0 outputs — config, error messages, audit logs, feedback signals — are designed as **agent-consumable artifacts** first. This means:

- Structured, not prose: every output has a predictable schema
- Self-describing: includes `source`, `type`, and `fix_instructions` fields
- Version-controlled: `harness.yaml` config is the single source of truth, readable by both humans and agents

---

## Tech Stack

- **Python 3.11+**, asyncio-based
- **Pydantic v2** — Data models, config validation
- **httpx** — Async HTTP for LLM API calls
- **PyYAML** — YAML config loading
- **tiktoken** — Token counting for context budgets
- **Build**: hatchling via pyproject.toml
- **Test**: pytest + pytest-asyncio
- **Lint**: ruff

## API Surface (Minimal Usage)

```python
from harness0 import HarnessEngine

engine = HarnessEngine.from_config("harness.yaml")

@engine.tool(risk_level="read")
async def read_file(path: str) -> str:
    return open(path).read()

@engine.tool(risk_level="execute", requires_approval=True)
async def run_command(command: str) -> str:
    ...

result = await engine.run("Create a hello world Python script")
print(result.output)
```

## API Surface (Individual Layer Usage)

```python
# Use just L1
from harness0.context import ContextAssembler, ContextLayer, FileSource
assembler = ContextAssembler(layers=[...])
messages = await assembler.assemble(turn_context)

# Use just L2
from harness0.tools import ToolRegistry, ToolInterceptor
interceptor = ToolInterceptor(registry)
result = await interceptor.execute(tool_call)

# Use just L5
from harness0.entropy import EntropyManager
manager = EntropyManager(compression_threshold=6000)
cleaned = await manager.process(bloated_messages)
```
