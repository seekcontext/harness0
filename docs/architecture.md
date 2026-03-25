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
class ContextLayer(BaseModel):
    name: str                    # e.g. "base", "soul", "agents", "skills"
    priority: int                # Higher = loaded later = higher override
    source: ContextSource        # File, directory, callable, or inline
    freshness: Freshness         # static / per_session / per_turn
    max_tokens: int | None       # Per-layer token budget

class ContextAssembler:
    async def assemble(self, turn_context: TurnContext) -> list[Message]:
        """Load all layers → sort by priority → apply token budgets → return messages."""
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
    type: SignalType      # "error" | "warning" | "info" | "constraint"
    source: str           # Which subsystem generated this
    message: str          # Human/model-readable explanation
    actionable: bool      # Can the model do something about it?
    suggestion: str | None  # Recommended next step
```

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

max_iterations: 50
checkpoint_enabled: true
```

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
