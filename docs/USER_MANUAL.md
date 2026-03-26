# Harness0 — User Manual

> **Status**: v0.0.3 — Core layers (L1–L5) and `HarnessEngine` facade are implemented and functional.
> Sections marked **[PLANNED]** describe future capabilities not yet implemented.

---

## Table of Contents

- [1. Installation](#1-installation)
- [2. Core Concepts](#2-core-concepts)
- [3. Quick Start](#3-quick-start)
- [4. Configuration Reference](#4-configuration-reference)
- [5. L1: Context Assembly](#5-l1-context-assembly)
- [6. L2: Tool Governance](#6-l2-tool-governance)
- [7. L3: Security Guard](#7-l3-security-guard)
- [8. L4: Feedback Loop](#8-l4-feedback-loop)
- [9. L5: Entropy Management](#9-l5-entropy-management)
- [10. The Agent Loop](#10-the-agent-loop)
- [11. Using Individual Layers](#11-using-individual-layers)
- [12. Framework Integrations](#12-framework-integrations) [PLANNED]
- [13. Built-in Tool Plugins](#13-built-in-tool-plugins) [PLANNED]
- [14. LLM Providers](#14-llm-providers)
- [15. Advanced Topics](#15-advanced-topics)
- [16. Troubleshooting](#16-troubleshooting)

---

## 1. Installation

### Basic installation

```bash
pip install harness0
```

This installs the core library with all required dependencies:
`pydantic>=2.0`, `pyyaml>=6.0`, `tiktoken>=0.7`, `httpx>=0.27`, `aiofiles>=24.0`.

### With framework integration adapters [PLANNED]

```bash
pip install harness0[langchain]      # LangChain middleware
pip install harness0[openai]         # OpenAI Agents SDK guardrails
pip install harness0[pydantic-ai]    # PydanticAI dependency injection
pip install harness0[crewai]         # CrewAI tool wrappers
```

### From source (development)

```bash
git clone https://github.com/seekcontext/harness0.git
cd harness0
pip install -e ".[dev]"
```

The `[dev]` extra installs `pytest`, `pytest-asyncio`, and `ruff`.

### Requirements

- Python 3.11 or higher
- An LLM API key (OpenAI, Anthropic, or compatible provider)

---

## 2. Core Concepts

### The Harness Model

harness0 is built on one formula:

```
Agent = Loop(Model + Harness)
```

The **Model** is the LLM (GPT-4o, Claude, DeepSeek, etc.). The **Harness** is the engineering environment that makes the model work reliably. harness0 provides the Harness.

The **0** in the name means **Layer 0** — the foundational reliability substrate that sits beneath every orchestration framework. Ground zero of agent reliability.

### The 5 Layers

The Harness consists of 5 cooperating layers:

| Layer | Name | One-sentence summary |
|---|---|---|
| L1 | Context Assembly | Builds the prompt dynamically from multiple prioritized sources |
| L2 | Tool Governance | Validates, classifies, and audits every tool call |
| L3 | Security Guard | Enforces safety boundaries at runtime |
| L4 | Feedback Loop | Translates system events into actionable model feedback |
| L5 | Entropy Management | Detects and repairs context degradation over time |

### Two Usage Modes

1. **Full engine** — Use `HarnessEngine` to get all 5 layers wired together with an agent loop. Best for building agents from scratch.

2. **Individual layers** — Import and use any single layer independently. Best for enhancing an existing agent or framework.

### Configuration

All behavior is declared in a `harness.yaml` file. No runtime behavior is hidden — everything the harness does is visible in the configuration.

---

## 3. Quick Start

### 3.1 Minimal example (no config file)

```python
import asyncio
from harness0 import HarnessEngine, RiskLevel

# Zero-config engine with sensible defaults
engine = HarnessEngine.default()

@engine.tool(risk_level=RiskLevel.READ)
async def read_file(path: str) -> str:
    """Read a file and return its contents."""
    with open(path) as f:
        return f.read()

@engine.tool(risk_level=RiskLevel.WRITE)
async def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    with open(path, "w") as f:
        f.write(content)
    return f"Written {len(content)} chars to {path}"

@engine.tool(risk_level=RiskLevel.EXECUTE, requires_approval=True)
async def run_command(command: str) -> str:
    """Execute a shell command."""
    import subprocess
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout or result.stderr

async def main():
    from openai import AsyncOpenAI
    client = AsyncOpenAI()  # reads OPENAI_API_KEY from environment
    result = await engine.run("Create a Python script that prints hello world", llm_client=client)
    print(result.output)

asyncio.run(main())
```

### 3.2 With YAML configuration

**harness.yaml**:

```yaml
llm:
  provider: openai
  model: gpt-4o

context:
  layers:
    - name: base
      source: prompts/base.md
      priority: 0
      disclosure_level: index
    - name: security-guide
      source: prompts/security.md
      priority: 5
      disclosure_level: detail
      keywords: ["security", "permission", "auth"]
  total_token_budget: 8000

tools:
  default_risk: read
  max_output_tokens: 5000
  audit_enabled: true

security:
  sandbox_enabled: true
  blocked_commands: ["rm -rf", "sudo", "> /dev/sda"]
  approval_mode: risky_only
  default_timeout: 30

feedback:
  inject_hints: true
  signal_format: xml
  max_signals_per_turn: 10

entropy:
  compression_threshold: 6000
  decay_check_interval: 10
  detect_conflicts: true
  staleness_threshold_hours: 24
  gardener_enabled: true
  gardener_interval_turns: 5
  golden_rules:
    - id: no_stale_layers
      description: "All FileSource layers must be fresher than staleness_threshold_hours"
      severity: warning
    - id: no_duplicate_tools
      description: "No two tools may share the same description"
      severity: error

max_iterations: 50
checkpoint_enabled: true
```

**main.py**:

```python
import asyncio
from openai import AsyncOpenAI
from harness0 import HarnessEngine, RiskLevel

engine = HarnessEngine.from_config("harness.yaml")

@engine.tool(risk_level=RiskLevel.READ)
async def read_file(path: str) -> str:
    """Read a file and return its contents."""
    with open(path) as f:
        return f.read()

async def main():
    client = AsyncOpenAI()
    result = await engine.run("Summarise README.md", llm_client=client)
    print(result.output)
    print(f"Completed in {result.turn_count} turns, status: {result.status}")

asyncio.run(main())
```

### 3.3 What happens at runtime

When you call `engine.run(task, llm_client=client)`, the following sequence executes each turn:

```
Turn N:
  1. L5 EntropyManager.process()
     → Remove stale feedback signals from history
     → Deduplicate repeated tool results
     → Compress if token count exceeds threshold
     → EntropyGardener runs every N turns (checks golden rules)

  2. L1 ContextAssembler.assemble()
     → INDEX layers always injected (base prompt, system rules)
     → DETAIL layers injected only if task keywords match
     → Token budget enforced across all layers

  3. L4 FeedbackTranslator.flush()
     → Collect signals from previous turn (errors, blocks, truncations)
     → Render as XML/Markdown/JSON hint → inject into system messages

  4. LLM called with assembled context + history + tool schemas

  5. LLM returns tool calls:
     → L2 ToolInterceptor.execute() for each call:
        - Schema validation
        - CommandGuard check (for execute-risk tools)
        - ApprovalManager.request() (if requires_approval)
        - Handler invoked
        - Output truncated if over max_output_tokens
        - Audit record written
        - FeedbackSignal emitted on any failure

  6. Loop until LLM returns stop (no tool calls) or max_iterations reached
```

### 3.4 Programmatic configuration (no YAML)

```python
from harness0 import HarnessEngine
from harness0.core.config import (
    HarnessConfig,
    ContextConfig,
    ContextLayerConfig,
    ToolGovernanceConfig,
    SecurityConfig,
    FeedbackConfig,
    EntropyConfig,
    LLMConfig,
    GoldenRule,
)

config = HarnessConfig(
    llm=LLMConfig(provider="openai", model="gpt-4o"),
    context=ContextConfig(
        total_token_budget=8000,
        layers=[
            ContextLayerConfig(
                name="base",
                source="prompts/base.md",
                priority=0,
                disclosure_level="index",
            ),
        ],
    ),
    security=SecurityConfig(
        blocked_commands=["rm -rf", "sudo"],
        approval_mode="risky_only",
    ),
    entropy=EntropyConfig(
        gardener_enabled=True,
        gardener_interval_turns=5,
        golden_rules=[
            GoldenRule(id="no_duplicate_tools",
                       description="No two tools may share the same description",
                       severity="error"),
        ],
    ),
    max_iterations=50,
)

engine = HarnessEngine(config)
```

---

## 4. Configuration Reference

All fields and their defaults.

### 4.1 Top-level

| Field | Type | Default | Description |
|---|---|---|---|
| `llm` | `LLMConfig` | see below | LLM provider settings |
| `context` | `ContextConfig` | see below | L1 context assembly |
| `tools` | `ToolGovernanceConfig` | see below | L2 tool governance |
| `security` | `SecurityConfig` | see below | L3 security guard |
| `feedback` | `FeedbackConfig` | see below | L4 feedback loop |
| `entropy` | `EntropyConfig` | see below | L5 entropy management |
| `max_iterations` | `int` | `50` | Max agent loop turns before forced stop |
| `checkpoint_enabled` | `bool` | `True` | Reserved for future checkpoint persistence |

### 4.2 `llm`

| Field | Type | Default | Description |
|---|---|---|---|
| `provider` | `"openai" \| "anthropic" \| "compatible"` | `"openai"` | LLM provider |
| `model` | `str` | `"gpt-4o"` | Model name |
| `api_key` | `str \| None` | `None` | API key (falls back to env var) |
| `base_url` | `str \| None` | `None` | Override API endpoint |
| `temperature` | `float` | `0.0` | Sampling temperature |
| `max_tokens` | `int` | `4096` | Max tokens per LLM response |

### 4.3 `context`

| Field | Type | Default | Description |
|---|---|---|---|
| `layers` | `list[ContextLayerConfig]` | `[]` | Ordered list of context layers |
| `total_token_budget` | `int` | `8000` | Max tokens for assembled context |

**`ContextLayerConfig` fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | required | Unique layer identifier |
| `source` | `str` | required | Source spec (see §5.2) |
| `priority` | `int` | `0` | Load order; higher overrides lower |
| `freshness` | `"static" \| "per_session" \| "per_turn"` | `"static"` | Cache policy |
| `max_tokens` | `int \| None` | `None` | Per-layer token cap |
| `disclosure_level` | `"index" \| "detail"` | `"index"` | Always injected vs keyword-gated |
| `keywords` | `list[str]` | `[]` | Keywords that trigger DETAIL layers |

### 4.4 `tools`

| Field | Type | Default | Description |
|---|---|---|---|
| `default_risk` | `"read" \| "write" \| "execute" \| "critical"` | `"read"` | Default risk when not specified |
| `max_output_tokens` | `int` | `5000` | Truncate tool output beyond this |
| `audit_enabled` | `bool` | `True` | Write audit record for every call |

### 4.5 `security`

| Field | Type | Default | Description |
|---|---|---|---|
| `sandbox_enabled` | `bool` | `True` | Enable process sandbox |
| `max_processes` | `int` | `5` | Concurrent subprocess limit |
| `max_output_bytes` | `int` | `100000` | Per-process output cap (bytes) |
| `default_timeout` | `int` | `30` | Subprocess timeout (seconds) |
| `blocked_commands` | `list[str]` | `["rm -rf", "sudo", "> /dev/sda", ":(){ :\|:& };:"]` | Blocked command patterns |
| `approval_mode` | `"always" \| "risky_only" \| "never"` | `"risky_only"` | When to require approval |

### 4.6 `feedback`

| Field | Type | Default | Description |
|---|---|---|---|
| `inject_hints` | `bool` | `True` | Inject signals into next turn's context |
| `signal_format` | `"xml" \| "json" \| "markdown"` | `"xml"` | Signal rendering format |
| `max_signals_per_turn` | `int` | `10` | Cap signals collected per turn |

### 4.7 `entropy`

| Field | Type | Default | Description |
|---|---|---|---|
| `compression_threshold` | `int` | `6000` | Trigger compression above this token count |
| `decay_check_interval` | `int` | `10` | Signal staleness window (in turns) |
| `detect_conflicts` | `bool` | `True` | Scan for contradictory instructions |
| `staleness_threshold_hours` | `int` | `24` | Flag FileSource layers older than this |
| `gardener_enabled` | `bool` | `True` | Enable background quality GC |
| `gardener_interval_turns` | `int` | `5` | Run gardener every N turns |
| `golden_rules` | `list[GoldenRule]` | `[]` | Mechanically verifiable invariants |

**`GoldenRule` fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | required | Rule identifier (see built-in IDs below) |
| `description` | `str` | required | Human-readable rule description |
| `severity` | `"error" \| "warning" \| "info"` | `"warning"` | Violation severity |

**Built-in golden rule IDs:**

| ID | What it checks |
|---|---|
| `no_stale_layers` | All `FileSource` layers are newer than `staleness_threshold_hours` |
| `no_duplicate_tools` | No two registered tools share the same description |
| `no_conflicting_instructions` | No contradictory directives across context layers |

---

## 5. L1: Context Assembly

### 5.1 What it does

L1 assembles the system prompt from multiple `ContextLayer` objects each turn. The core insight: prompts are not static documents — they are assembly systems with priority, freshness, and progressive disclosure.

### 5.2 Source types

| Spec string | Source class | Description |
|---|---|---|
| `"path/to/file.md"` | `FileSource` | Single file from disk |
| `"dir:path/to/dir"` | `DirectorySource` | All `*.md` files in directory, concatenated |
| `"inline:some text"` | `InlineSource` | Literal string content |
| Python object | `CallableSource` | `async` or `sync` callable returning a string |

```python
from harness0.context import (
    ContextLayer, FileSource, DirectorySource, InlineSource, CallableSource,
    Freshness, DisclosureLevel,
)

# Load a single file
FileSource("prompts/base.md")

# Load all .md files in a directory
DirectorySource("docs/", glob="**/*.md")

# Inline content (useful for testing)
InlineSource("You are a helpful coding assistant.")

# Dynamic content from a callable
async def get_current_state() -> str:
    return f"Current directory: {os.getcwd()}"

CallableSource(get_current_state)
```

### 5.3 ContextLayer

```python
from harness0.context import ContextLayer, FileSource, Freshness, DisclosureLevel

layer = ContextLayer(
    name="base",
    source=FileSource("prompts/base.md"),
    priority=0,                           # Higher priority = injected later = takes precedence
    freshness=Freshness.STATIC,           # "static" | "per_session" | "per_turn"
    max_tokens=2000,                      # Optional per-layer token cap
    disclosure_level=DisclosureLevel.INDEX,  # "index" | "detail"
    keywords=[],                          # Keywords that activate DETAIL layers
)
```

**Freshness policies:**

| Policy | Behavior |
|---|---|
| `static` | Load once at initialization, cache forever |
| `per_session` | Reload at each new session start |
| `per_turn` | Reload on every turn (for dynamic state) |

### 5.4 Progressive Disclosure

The most important L1 design principle (from OpenAI Harness Engineering):

> "Give the agent a map, not a 1,000-page manual."

**INDEX layers** (`disclosure_level="index"`) are **always** injected. Use them for:
- Base system prompt
- Rules summary
- AGENTS.md index (short pointers to detailed docs)

**DETAIL layers** (`disclosure_level="detail"`) are injected **only when** the current task contains any of the declared `keywords`. Use them for:
- Domain-specific deep-dives (security guide, deployment runbook)
- Large reference docs that are only sometimes relevant

```python
# Always injected — acts as the "map"
ContextLayer(
    name="base",
    source=FileSource("AGENTS.md"),
    priority=0,
    disclosure_level=DisclosureLevel.INDEX,
)

# Only injected for security-related tasks
ContextLayer(
    name="security-detail",
    source=FileSource("docs/security.md"),
    priority=10,
    disclosure_level=DisclosureLevel.DETAIL,
    keywords=["security", "permission", "auth", "token", "credential"],
)
```

```python
layer.is_relevant_for_task("fix the authentication bug")  # True — matches "auth"
layer.is_relevant_for_task("write a sorting function")     # False — no keyword match
```

### 5.5 ContextAssembler

```python
from harness0.context import ContextAssembler, ContextLayer, FileSource, DisclosureLevel

assembler = ContextAssembler(
    layers=[
        ContextLayer(name="base", source=FileSource("base.md"),
                     disclosure_level=DisclosureLevel.INDEX),
        ContextLayer(name="detail", source=FileSource("detail.md"),
                     disclosure_level=DisclosureLevel.DETAIL, keywords=["db"]),
    ],
    total_token_budget=8000,
)

# Returns list[Message] to prepend to the LLM call
messages = await assembler.assemble(turn_context)

# Dynamic modification
assembler.add_layer(new_layer)
assembler.remove_layer("old-layer-name")  # Returns True if found
```

**Assembly algorithm:**
1. Select: always include INDEX layers; include DETAIL layers only when `keywords` match task
2. Load: content loaded with freshness-aware caching
3. Sort by priority (ascending)
4. Apply token budgets: per-layer cap first, then total budget
5. INDEX layers truncated if over budget (never dropped); DETAIL layers dropped if over budget
6. Return as a single `system` message

---

## 6. L2: Tool Governance

### 6.1 Risk levels

```python
from harness0.tools import RiskLevel

RiskLevel.READ      # No side effects (read_file, search, list)
RiskLevel.WRITE     # Modifies persistent state (write_file, create_dir)
RiskLevel.EXECUTE   # Runs code or shell commands
RiskLevel.CRITICAL  # Irreversible or dangerous (deploy, delete prod data)
```

### 6.2 Registering tools via decorator

```python
engine = HarnessEngine.default()

@engine.tool(risk_level=RiskLevel.READ)
async def read_file(path: str) -> str:
    """Read a file and return its contents."""
    with open(path) as f:
        return f.read()

@engine.tool(
    risk_level=RiskLevel.EXECUTE,
    requires_approval=True,
    timeout=60,
    max_output_tokens=2000,
    description="Execute a shell command in the project sandbox.",
)
async def run_command(command: str) -> str:
    import subprocess
    return subprocess.check_output(command, shell=True, text=True)
```

**Decorator parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `risk_level` | `RiskLevel \| str` | `RiskLevel.READ` | Risk classification |
| `requires_approval` | `bool` | `False` | Require human approval before execution |
| `timeout` | `int \| None` | `None` | Per-call timeout (seconds) |
| `max_output_tokens` | `int \| None` | `None` | Override global max_output_tokens |
| `description` | `str \| None` | `None` | Override docstring as tool description |

### 6.3 ToolDefinition

```python
from harness0.tools import ToolDefinition, RiskLevel, ParameterSchema

definition = ToolDefinition(
    name="search_files",
    description="Search for files matching a glob pattern.",
    parameters=[
        ParameterSchema(name="pattern", type="string",
                        description="Glob pattern to match", required=True),
        ParameterSchema(name="directory", type="string",
                        description="Root directory to search", required=False,
                        default="."),
    ],
    risk_level=RiskLevel.READ,
    handler=my_search_function,
)
engine.registry.register(definition)
```

### 6.4 ToolRegistry

```python
engine.registry.names()           # list[str] — all registered tool names
engine.registry.get("read_file")  # ToolDefinition | None
engine.registry.openai_schemas()  # list[dict] — OpenAI function-calling format
engine.registry.has_duplicates()  # list[(name_a, name_b)] — same-description pairs
len(engine.registry)              # int
"read_file" in engine.registry    # bool
```

### 6.5 Interception pipeline

Every tool call flows through this pipeline:

```
ToolCall
  → 1. Lookup         — verify tool is registered
  → 2. Validate       — check required args against ToolDefinition.parameters
  → 3. CommandGuard   — for EXECUTE/CRITICAL: check command against blocklist
  → 4. Approval       — if requires_approval or CRITICAL: request user approval
  → 5. Execute        — call handler (with optional timeout)
  → 6. Truncate       — cap output at max_output_tokens
  → 7. Audit          — write AuditRecord
  → ToolResult
```

On any failure at steps 1–4, execution is aborted and a `FeedbackSignal` is emitted.

### 6.6 ToolResult

```python
class ToolResult(BaseModel):
    tool_call_id: str
    name: str
    output: str         # Tool's return value as string
    error: str | None   # Set if tool failed at any step
    truncated: bool     # True if output was cut to max_output_tokens
    duration_ms: float  # Wall-clock execution time
```

### 6.7 Executing tools directly

```python
# Outside the agent loop — useful for testing
result = await engine.execute_tool("read_file", path="README.md")
print(result.output)
print(result.error)    # None if successful
print(result.truncated)
```

### 6.8 Audit log

```python
records = engine.interceptor.audit_log()

for r in records:
    print(r.tool_name, r.risk_level, r.duration_ms, r.error)
```

---

## 7. L3: Security Guard

### 7.1 Three lines of defense

| Component | Responsibility |
|---|---|
| `CommandGuard` | Pattern-based blocklist for shell commands |
| `ProcessSandbox` | Resource limits on subprocess execution |
| `ApprovalManager` | Risk-based human-in-the-loop approval |

### 7.2 CommandGuard

```python
from harness0.security import CommandGuard
from harness0.core.config import SecurityConfig

guard = CommandGuard(SecurityConfig(blocked_commands=["rm -rf", "sudo"]))

result = guard.check("sudo apt install nginx")
result.allowed          # False
result.matched_pattern  # "sudo"
result.signal           # FeedbackSignal with fix_instructions
result.signal.fix_instructions  # Step-by-step repair guidance for the agent

# Check a safe command
result = guard.check("ls -la")
result.allowed  # True

# Add patterns at runtime
guard.add_pattern("curl | bash")
```

**Key design**: every rejected command produces a `FeedbackSignal` with `fix_instructions` — specific, numbered steps the agent can follow. The agent never receives a bare exception.

```
Example fix_instructions for "sudo rm -rf /tmp":
  1. Do NOT retry this command — it matches the security blocklist.
  2. Reason: pattern `rm -rf` causes irreversible side effects.
  3. Consider these safer alternatives:
     • rm -r <specific_path>
     • shutil.rmtree(<path>) in Python
  4. If truly required, request explicit approval from the user.
```

### 7.3 ProcessSandbox

```python
from harness0.security import ProcessSandbox
from harness0.core.config import SecurityConfig

sandbox = ProcessSandbox(SecurityConfig(
    max_processes=5,
    max_output_bytes=100_000,
    default_timeout=30,
))

result = await sandbox.run(
    command="find . -name '*.py'",
    tool_call_id="call_abc123",
    timeout=15,       # Override default_timeout
    cwd="/project",
)

result.output      # Captured stdout+stderr
result.error       # None or error message
result.truncated   # True if output exceeded max_output_bytes
result.duration_ms

# Clean up all processes when session ends
await sandbox.cleanup()
```

### 7.4 ApprovalManager

```python
from harness0.security import ApprovalManager, StdinApprovalBackend, AutoApproveBackend, AutoDenyBackend

manager = ApprovalManager(
    config=SecurityConfig(approval_mode="risky_only"),
    backend=StdinApprovalBackend(),  # default: prompts on stdin
)

approved = await manager.request(
    action="deploy_to_production(env='prod')",
    risk_level="critical",
    context="Tool: Deploy the application to production",
)

# Custom approval backend
class SlackApprovalBackend(ApprovalBackend):
    async def request(self, action: str, context: str) -> bool:
        # Send to Slack, wait for ✅ reaction
        ...

manager = ApprovalManager(config=SecurityConfig(), backend=SlackApprovalBackend())
```

**Approval modes:**

| Mode | Behavior |
|---|---|
| `always` | Every tool call requires approval |
| `risky_only` | Only `EXECUTE` and `CRITICAL` require approval |
| `never` | Skip all approvals (use only in trusted environments) |

**Fingerprint cache**: Once approved, the same action (SHA-256 of `tool_name + arguments`) is auto-approved for the session.

```python
manager.clear_cache()  # Reset fingerprint cache
```

**Built-in backends:**

| Class | Behavior |
|---|---|
| `StdinApprovalBackend` | Default. Prompts user on stdin. |
| `AutoApproveBackend` | Always approves. For trusted/test environments. |
| `AutoDenyBackend` | Always denies. For testing denial flows. |

---

## 8. L4: Feedback Loop

### 8.1 What it does

L4 translates raw system events into structured `FeedbackSignal` objects that the model can understand and act on. Without this layer, the model sees cryptic errors. With it, the model sees the problem and what to do about it.

### 8.2 FeedbackSignal

```python
class FeedbackSignal(BaseModel):
    id: str                      # Auto-generated 8-char hex
    type: SignalType             # "error" | "warning" | "info" | "constraint"
    source: str                  # Subsystem (e.g. "security.command_guard")
    message: str                 # Human-readable explanation
    actionable: bool             # Can the agent do something about it?
    suggestion: str | None       # Brief recommended next action
    fix_instructions: str | None # Step-by-step agent-consumable repair guidance
    metadata: dict               # Extra structured data
    created_at: float            # Unix timestamp
```

The `fix_instructions` field is the key differentiator: it contains complete, numbered steps the agent can execute immediately — not just a description of what went wrong, but exactly what to do next.

### 8.3 Signal types

| Type | When used | Example message |
|---|---|---|
| `error` | Tool execution failed | "Tool `read_file` failed: FileNotFoundError: /no.txt" |
| `warning` | Something was degraded or limited | "Output truncated from 12K to 5K tokens." |
| `info` | Non-critical information | "Approval auto-granted via fingerprint cache." |
| `constraint` | Action blocked by policy | "Command `sudo ...` blocked by security policy." |

### 8.4 FeedbackTranslator

The `FeedbackTranslator` provides static factory methods for every common system event:

```python
from harness0.feedback import FeedbackTranslator

# Command blocked by L3
signal = FeedbackTranslator.command_blocked(
    command="sudo apt install",
    reason="contains 'sudo'",
    allowed_alternatives=["apt install (without sudo)"],
)

# Tool output truncated
signal = FeedbackTranslator.output_truncated(
    tool_name="grep_search",
    original_tokens=12000,
    limit_tokens=5000,
)

# Subprocess timed out
signal = FeedbackTranslator.subprocess_timeout(
    command="npm install",
    timeout_seconds=30,
)

# Approval denied
signal = FeedbackTranslator.approval_denied(
    action="deploy_to_production()",
    approver="user",
)

# Schema validation failed
signal = FeedbackTranslator.tool_schema_invalid(
    tool_name="write_file",
    error="Missing required parameter: `content`",
)

# Generic exception
signal = FeedbackTranslator.from_exception(exc, source="tools.my_tool")

# Context layer stale (from L5)
signal = FeedbackTranslator.context_stale(layer_name="base", age_hours=36.5)

# Golden rule violated (from L5)
signal = FeedbackTranslator.golden_rule_violated(
    rule_id="no_duplicate_tools",
    description="No two tools may share the same description",
    details="Tools `read_file` and `read_doc` have identical descriptions.",
)

# Custom signal
signal = FeedbackTranslator.custom(
    source="my_system.validator",
    message="Schema version mismatch detected.",
    type=SignalType.WARNING,
    fix_instructions="1. Run `migrate.py`\n2. Restart the service.",
)
```

### 8.5 Collecting and flushing signals

The `FeedbackTranslator` is stateful per turn. All signals are buffered and flushed at the start of the next turn:

```python
from harness0.feedback import FeedbackTranslator, SignalType

translator = FeedbackTranslator(config.feedback)

# Add a signal (typically called by L2/L3, not you directly)
await translator.add(my_signal)

# Flush signals for this turn (called by engine.run() automatically)
bundle = await translator.flush()  # returns SignalBundle, resets buffer

bundle.signals          # list[FeedbackSignal]
bundle.has_errors()     # bool
bundle.has_actionable() # bool
bundle.render("xml")    # str — formatted for injection into context
```

### 8.6 Signal rendering

```python
signal = FeedbackSignal(
    type=SignalType.CONSTRAINT,
    source="security.command_guard",
    message="Command `sudo rm -rf /tmp` blocked.",
    fix_instructions="1. Do NOT retry...\n2. Use rm -r instead.",
)

# XML (default)
print(signal.to_xml_hint())
```

```xml
<harness:signal id="a3f8c1d2" type="constraint" source="security.command_guard">
  <message>Command `sudo rm -rf /tmp` blocked.</message>
  <fix_instructions>1. Do NOT retry...
2. Use rm -r instead.</fix_instructions>
</harness:signal>
```

```python
# Markdown
print(signal.to_markdown_hint())
```

```markdown
🔒 **[security.command_guard]** Command `sudo rm -rf /tmp` blocked.

**How to fix:**
1. Do NOT retry...
2. Use rm -r instead.
```

```python
# JSON
signal.to_json_hint()  # dict with "harness_signal" key
```

A `SignalBundle` wraps multiple signals in a container tag:

```xml
<harness:signals>
  <harness:signal ...> ... </harness:signal>
  <harness:signal ...> ... </harness:signal>
</harness:signals>
```

### 8.7 Accessing signals programmatically

```python
result = await engine.run("Deploy the app", llm_client=client)

# All signal bundles accumulated across the run
for bundle in result.signals:
    for signal in bundle.signals:
        print(f"[{signal.type}] {signal.source}: {signal.message}")
```

---

## 9. L5: Entropy Management

### 9.1 What it does

L5 detects and repairs context degradation in long-running agent sessions. While other frameworks do passive compression (summarize when full), harness0 does active quality maintenance.

**Passive (other frameworks)**: Triggered only when token limit is reached. Method: LLM summarizes old messages. Blunt — treats all history the same.

**Active (harness0)**: Runs proactively every turn. Detects specific degradation types and applies targeted fixes. Includes a background GC (EntropyGardener).

### 9.2 EntropyManager

```python
from harness0.entropy import EntropyManager
from harness0.core.config import EntropyConfig

manager = EntropyManager(
    config=EntropyConfig(
        compression_threshold=6000,
        decay_check_interval=10,
        detect_conflicts=True,
        staleness_threshold_hours=24,
    ),
    translator=my_feedback_translator,
    tool_registry=my_tool_registry,
)

# In your agent loop each turn:
messages, garden_actions = await manager.process(
    messages=state.messages,
    turn_context=turn_ctx,
    context_layers=my_layers,  # Optional: pass for gardener to check
)
```

**What `process()` does each turn:**

1. **Remove stale signals** — Drops `<harness:signal>` blocks older than `decay_check_interval` turns (prevents signal noise accumulation)
2. **Deduplicate tool results** — Removes repeated consecutive tool calls with identical outputs
3. **Compress if over threshold** — Drops oldest non-system messages until under `compression_threshold` tokens
4. **Garden** — Runs `EntropyGardener.maybe_garden()` every `gardener_interval_turns` turns

### 9.3 Degradation detection

**Stale signals** — Old harness feedback blocks accumulate and crowd out fresh context:
```
Before: [system, signal_turn_1, signal_turn_2, ..., signal_turn_15, user_msg]
After:  [system, user_msg]  ← signals older than decay_check_interval removed
```

**Duplicate tool results** — Same tool called multiple times with identical output:
```
Before: [tool:grep("foo")="line 5", tool:grep("foo")="line 5", tool:grep("foo")="line 5"]
After:  [tool:grep("foo")="line 5"]
```

**Context overflow** — Total tokens exceed `compression_threshold`:
```
Before: 8,500 tokens (system + 20 turns of history)
After:  ~6,000 tokens (system + first user message + last N turns)
```

**Conflict detection** — Heuristic scan for contradictory instructions:
```python
conflicts = manager.detect_conflicts(messages)
# → ["Conflict: system messages disagree about: typescript"]
```

### 9.4 EntropyGardener

The gardener is a background GC that runs every `gardener_interval_turns` turns and enforces mechanically verifiable invariants (golden rules).

```python
from harness0.entropy import EntropyGardener, GardenAction
from harness0.core.config import EntropyConfig, GoldenRule

gardener = EntropyGardener(
    config=EntropyConfig(
        gardener_enabled=True,
        gardener_interval_turns=5,
        staleness_threshold_hours=24,
        golden_rules=[
            GoldenRule(
                id="no_duplicate_tools",
                description="No two tools may share the same description",
                severity="error",
            ),
            GoldenRule(
                id="no_conflicting_instructions",
                description="Detect contradictory directives across context layers",
                severity="warning",
            ),
        ],
    ),
    translator=my_translator,     # Optional: auto-emits FeedbackSignals on violations
    tool_registry=my_registry,    # Required for no_duplicate_tools check
)

# Force a full pass (used by EntropyManager internally)
actions: list[GardenAction] = await gardener.garden(my_layers)

# Or: run only if interval has elapsed
actions = await gardener.maybe_garden(my_layers)
```

**GardenAction** — what the gardener returns:

```python
class GardenAction(BaseModel):
    action_type: Literal["remove", "update", "flag"]
    target: str             # Layer name or "tool_a,tool_b"
    reason: str             # Human-readable description of the issue
    severity: str           # "error" | "warning" | "info"
    fix_instructions: str | None  # Agent-consumable repair steps
    signal: FeedbackSignal | None # Pre-built signal (auto-added to translator)
```

**Built-in golden rule checks:**

| Rule ID | What it checks | Requires |
|---|---|---|
| `no_stale_layers` | FileSource layers older than `staleness_threshold_hours` | `context_layers` |
| `no_duplicate_tools` | Two tools with identical descriptions | `tool_registry` |
| `no_conflicting_instructions` | Contradictory directives across loaded layer content | `context_layers` |

### 9.5 Using standalone

```python
from harness0.entropy import EntropyManager
from harness0.core.config import EntropyConfig
from harness0.feedback import FeedbackTranslator
from harness0.core.config import FeedbackConfig

translator = FeedbackTranslator(FeedbackConfig())
manager = EntropyManager(
    config=EntropyConfig(compression_threshold=6000),
    translator=translator,
)

# In your own agent loop:
messages, actions = await manager.process(messages=messages, turn_context=ctx)
```

---

## 10. The Agent Loop

### 10.1 engine.run()

```python
result = await engine.run(
    task="Create a Python script that prints hello world",
    llm_client=AsyncOpenAI(),     # Any OpenAI-compatible async client
    max_iterations=50,             # Override config.max_iterations
)
```

**LLM client compatibility:**
- `openai.AsyncOpenAI` — native support
- Any object with `client.chat.completions.create(**kwargs)` interface
- Any async callable `fn(messages=..., tools=...)` returning a dict

### 10.2 RunResult

```python
result.output      # str — final LLM text response
result.status      # "done" | "failed"
result.error       # str | None — set if status is "failed"
result.turn_count  # int — how many loop iterations ran
result.signals     # list[SignalBundle] — all signals from all turns
```

### 10.3 AgentState

The `AgentState` tracks everything about a running session:

```python
class AgentState(BaseModel):
    session_id: str
    task: str
    turn_number: int
    messages: list[Message]
    tool_results: list[ToolResult]
    status: Literal["running", "done", "failed", "waiting_approval"]
    output: str | None
    error: str | None
    started_at: float
    metadata: dict
```

### 10.4 Stop conditions

The loop stops when:
1. The LLM returns a final response with no tool calls (`finish_reason == "stop"`)
2. `max_iterations` is reached → `status = "failed"`
3. LLM client raises an unhandled exception

### 10.5 Accessing the raw state

```python
result._state            # AgentState — full internal state
result._state.messages   # Full conversation history
result._state.tool_results  # All tool calls and results

# All signals grouped by turn
for i, bundle in enumerate(result.signals):
    print(f"Turn {i}: {len(bundle.signals)} signals")
    for sig in bundle.signals:
        print(f"  [{sig.type}] {sig.message}")
```

---

## 11. Using Individual Layers

Every layer can be imported and used independently — no `HarnessEngine` required.

### 11.1 L1 only: Multi-layer prompt assembly

```python
from harness0.context import (
    ContextAssembler, ContextLayer, FileSource, InlineSource,
    Freshness, DisclosureLevel,
)
from harness0.core.types import TurnContext

assembler = ContextAssembler(
    layers=[
        ContextLayer(
            name="system",
            source=FileSource("system_prompt.md"),
            priority=0,
            disclosure_level=DisclosureLevel.INDEX,
        ),
        ContextLayer(
            name="project",
            source=FileSource("AGENTS.md"),
            priority=10,
            freshness=Freshness.PER_SESSION,
            disclosure_level=DisclosureLevel.INDEX,
        ),
        ContextLayer(
            name="db-detail",
            source=FileSource("docs/database.md"),
            priority=20,
            disclosure_level=DisclosureLevel.DETAIL,
            keywords=["database", "sql", "query", "migration"],
        ),
    ],
    total_token_budget=8000,
)

ctx = TurnContext(session_id="sess_1", turn_number=0, task="Fix the SQL migration")
messages = await assembler.assemble(ctx)
# Use `messages` with your own LLM call
```

### 11.2 L2 only: Governed tool execution

```python
from harness0.tools import ToolRegistry, ToolInterceptor, ToolDefinition, RiskLevel, ParameterSchema
from harness0.feedback import FeedbackTranslator
from harness0.core.config import ToolGovernanceConfig, FeedbackConfig

registry = ToolRegistry()
registry.register(ToolDefinition(
    name="write_file",
    description="Write content to a file.",
    parameters=[
        ParameterSchema(name="path", type="string", description="File path", required=True),
        ParameterSchema(name="content", type="string", description="Content to write", required=True),
    ],
    risk_level=RiskLevel.WRITE,
    handler=my_write_file_function,
))

translator = FeedbackTranslator(FeedbackConfig())
interceptor = ToolInterceptor(
    registry=registry,
    config=ToolGovernanceConfig(max_output_tokens=5000),
    translator=translator,
)

from harness0.core.types import ToolCall
result = await interceptor.execute(ToolCall(name="write_file", arguments={"path": "out.txt", "content": "hello"}))
print(result.output)
print(result.error)     # None if successful
print(result.truncated) # True if output was cut
```

### 11.3 L3 only: Security enforcement

```python
from harness0.security import CommandGuard, ProcessSandbox
from harness0.core.config import SecurityConfig

config = SecurityConfig(
    blocked_commands=["rm -rf", "sudo", "mkfs"],
    max_output_bytes=100_000,
    default_timeout=30,
)
guard = CommandGuard(config)
sandbox = ProcessSandbox(config)

# Check before executing
check = guard.check("ls -la /home/user")
if check.allowed:
    result = await sandbox.run(
        command="ls -la /home/user",
        tool_call_id="call_123",
    )
    print(result.output)
else:
    print("Blocked:", check.signal.message)
    print("Fix:", check.signal.fix_instructions)
```

### 11.4 L4 only: Better error messages for models

```python
from harness0.feedback import FeedbackTranslator, FeedbackSignal, SignalType
from harness0.core.config import FeedbackConfig

translator = FeedbackTranslator(FeedbackConfig())

# When a tool fails in your system:
try:
    result = run_command("npm install")
except TimeoutError as exc:
    signal = FeedbackTranslator.subprocess_timeout("npm install", timeout_seconds=30)
    await translator.add(signal)

# When the next LLM turn starts, flush signals and inject into context:
bundle = await translator.flush()
hint_text = translator.render_bundle(bundle)
# Add hint_text as a system message before your LLM call
```

### 11.5 L5 only: Context quality maintenance

```python
from harness0.entropy import EntropyManager, EntropyGardener
from harness0.core.config import EntropyConfig, GoldenRule
from harness0.feedback import FeedbackTranslator
from harness0.core.config import FeedbackConfig
from harness0.core.types import TurnContext

translator = FeedbackTranslator(FeedbackConfig())
manager = EntropyManager(
    config=EntropyConfig(
        compression_threshold=6000,
        detect_conflicts=True,
        gardener_enabled=True,
        gardener_interval_turns=5,
        golden_rules=[
            GoldenRule(id="no_duplicate_tools",
                       description="No duplicate descriptions",
                       severity="error"),
        ],
    ),
    translator=translator,
)

# In your agent loop each turn:
messages, garden_actions = await manager.process(
    messages=messages,
    turn_context=TurnContext(session_id="x", turn_number=turn_n, task=task),
    context_layers=my_layers,
)

# Inspect what the gardener flagged
for action in garden_actions:
    print(f"[{action.severity}] {action.target}: {action.reason}")
```

---

## 12. Framework Integrations [PLANNED]

Integration adapters map harness0's 5 layers to each framework's extension points. These are planned for a future release.

### 12.1 LangChain [PLANNED]

```python
# Future API
from harness0.integrations.langchain import HarnessMiddleware

agent = create_deep_agent(
    model="gpt-4o",
    middleware=[HarnessMiddleware.from_config("harness.yaml")],
)
```

### 12.2 OpenAI Agents SDK [PLANNED]

```python
# Future API
from harness0.integrations.openai_sdk import HarnessInputGuardrail, HarnessToolGuardrail

agent = Agent(
    name="coding-agent",
    input_guardrails=[HarnessInputGuardrail(config)],
    tool_guardrails=[HarnessToolGuardrail(config)],
)
```

### 12.3 PydanticAI [PLANNED]

```python
# Future API
from harness0.integrations.pydantic_ai import HarnessDeps

agent = Agent("openai:gpt-4o", deps_type=HarnessDeps)
```

### 12.4 CrewAI [PLANNED]

```python
# Future API
from harness0.integrations.crewai import harness_tool

@harness_tool(risk_level="execute", config=harness_config)
def run_shell(command: str) -> str:
    ...
```

---

## 13. Built-in Tool Plugins [PLANNED]

A set of pre-built tools with correct risk levels is planned for a future release.

### 13.1 File tools [PLANNED]

| Tool | Risk Level | Description |
|---|---|---|
| `read_file` | READ | Read file contents |
| `write_file` | WRITE | Write content to a file |
| `list_directory` | READ | List files and directories |

### 13.2 Shell tools [PLANNED]

| Tool | Risk Level | Description |
|---|---|---|
| `run_command` | EXECUTE | Execute a shell command through L3 SecurityGuard |

### 13.3 Search tools [PLANNED]

| Tool | Risk Level | Description |
|---|---|---|
| `grep_search` | READ | Search file contents by regex pattern |
| `glob_search` | READ | Find files by glob pattern |

Until these plugins are released, register your own tools using `@engine.tool`:

```python
import subprocess
from pathlib import Path

@engine.tool(risk_level=RiskLevel.READ)
async def read_file(path: str) -> str:
    """Read a file and return its contents."""
    return Path(path).read_text()

@engine.tool(risk_level=RiskLevel.WRITE)
async def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    Path(path).write_text(content)
    return f"Written {len(content)} chars to {path}"

@engine.tool(risk_level=RiskLevel.READ)
async def list_directory(path: str = ".") -> str:
    """List files and directories at a path."""
    return "\n".join(str(p) for p in Path(path).iterdir())

@engine.tool(risk_level=RiskLevel.EXECUTE, requires_approval=True, timeout=60)
async def run_command(command: str) -> str:
    """Execute a shell command."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr
```

---

## 14. LLM Providers

### 14.1 OpenAI (default)

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key="sk-...")  # or set OPENAI_API_KEY env var
result = await engine.run("Your task", llm_client=client)
```

### 14.2 Anthropic [PLANNED]

Direct Anthropic support via `llm/anthropic.py` is planned. Until then, use Anthropic's OpenAI-compatible endpoint if available, or implement a thin wrapper:

```python
import anthropic

class AnthropicAdapter:
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def __call__(self, messages: list, tools: list) -> dict:
        # Adapt Anthropic API response to harness0 format
        ...
```

### 14.3 OpenAI-compatible endpoints

Any API implementing the OpenAI chat completions interface works out of the box:

```python
from openai import AsyncOpenAI

# DeepSeek
client = AsyncOpenAI(
    api_key="your-deepseek-key",
    base_url="https://api.deepseek.com/v1",
)

# Ollama (local)
client = AsyncOpenAI(
    api_key="ollama",
    base_url="http://localhost:11434/v1",
)

# Together AI
client = AsyncOpenAI(
    api_key="your-together-key",
    base_url="https://api.together.xyz/v1",
)

result = await engine.run("Your task", llm_client=client)
```

### 14.4 Custom LLM adapter

Implement any async callable that accepts `messages` and `tools` and returns a dict:

```python
async def my_llm_client(messages: list[dict], tools: list[dict]) -> dict:
    # Call your LLM
    response = await my_api.call(messages=messages, tools=tools)
    return {
        "content": response.text,
        "finish_reason": "stop" if response.done else "tool_calls",
        "tool_calls": [
            {
                "id": tc.id,
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            for tc in response.tool_calls
        ],
    }

result = await engine.run("Your task", llm_client=my_llm_client)
```

---

## 15. Advanced Topics

### 15.1 Dynamic context layers at runtime

```python
from harness0.context import ContextLayer, InlineSource, DisclosureLevel

engine = HarnessEngine.default()

# Add context at runtime (e.g. based on user session)
user_context = ContextLayer(
    name="user-profile",
    source=InlineSource(f"User: {user.name}. Preferences: {user.prefs}"),
    priority=30,
    freshness=Freshness.PER_TURN,
    disclosure_level=DisclosureLevel.INDEX,
)
engine.add_context_layer(user_context)

# Remove a layer
engine.assembler.remove_layer("user-profile")
```

### 15.2 Custom golden rules

```python
from harness0.core.config import GoldenRule, EntropyConfig, HarnessConfig

config = HarnessConfig(
    entropy=EntropyConfig(
        golden_rules=[
            GoldenRule(
                id="no_stale_layers",
                description="All FileSource layers must be newer than 24h",
                severity="warning",
            ),
            GoldenRule(
                id="no_duplicate_tools",
                description="No two tools may share the same description",
                severity="error",
            ),
            GoldenRule(
                id="no_conflicting_instructions",
                description="Detect contradictory directives across context layers",
                severity="warning",
            ),
        ],
    ),
)
```

### 15.3 Custom approval backend

```python
from harness0.security import ApprovalBackend, ApprovalManager

class WebhookApprovalBackend(ApprovalBackend):
    async def request(self, action: str, context: str) -> bool:
        response = await httpx.post(
            "https://my-approval-service.com/approve",
            json={"action": action, "context": context},
        )
        return response.json()["approved"]

engine.approval_manager = ApprovalManager(
    config=engine.config.security,
    backend=WebhookApprovalBackend(),
)
```

### 15.4 Multi-format signal rendering

```python
# harness.yaml: feedback.signal_format controls the default

# Override per-bundle at runtime:
bundle = await translator.flush()
xml_hint = bundle.render("xml")       # <harness:signals>...</harness:signals>
md_hint = bundle.render("markdown")   # ❌ **[source]** message...
json_hint = bundle.render("json")     # {"harness_signal": {...}}
```

### 15.5 Running without an LLM (testing)

```python
engine = HarnessEngine.default()

# execute_tool works without an LLM client
result = await engine.execute_tool("read_file", path="README.md")

# engine.run() without llm_client returns a stub result immediately
result = await engine.run("some task")
print(result.output)  # "(No LLM client configured. Task: some task)"
```

### 15.6 Extending the interception pipeline

You can access the raw interceptor to add pre/post hooks:

```python
from harness0.tools.interceptor import ToolInterceptor

# Override registry methods for debugging
original_execute = engine.interceptor.execute

async def traced_execute(call):
    print(f"→ Calling tool: {call.name} with {call.arguments}")
    result = await original_execute(call)
    print(f"← Result: {result.output[:100]}")
    return result

engine.interceptor.execute = traced_execute
```

---

## 16. Troubleshooting

### 16.1 Tool not found

```
FeedbackSignal [error] tools.interceptor:
  Tool `my_tool` is not registered.
  Available tools: read_file, write_file.
```

**Cause**: The `@engine.tool` decorator was not applied, or the function was defined after `engine.run()` was called.

**Fix**: Register all tools before calling `engine.run()`. The decorator registers immediately when applied.

### 16.2 Schema validation failure

```
FeedbackSignal [error] tools.interceptor.write_file:
  Tool call `write_file` failed schema validation: Missing required parameter: `content`
```

**Cause**: The LLM omitted a required argument.

**Fix**: Improve the tool's description to make the required parameters obvious. The `fix_instructions` in the signal will guide the agent to retry with correct arguments.

### 16.3 Command blocked

```
FeedbackSignal [constraint] security.command_guard:
  Command blocked: `sudo apt install nginx` matches blocked pattern `sudo`.
```

**Fix**: The agent receives `fix_instructions` and will adjust on the next turn. If the operation is genuinely necessary, add it to an allow-list or switch `approval_mode` to `always` and let the user approve it.

### 16.4 Output truncated

```
FeedbackSignal [warning] tools.interceptor.grep_search:
  Tool output was truncated from ~12000 to 5000 tokens.
```

**Fix**: The agent receives `fix_instructions` to narrow its search scope. You can also increase `tools.max_output_tokens` in config.

### 16.5 Subprocess timeout

```
FeedbackSignal [error] security.sandbox:
  Command `npm install` exceeded the 30s timeout.
```

**Fix**: Increase `security.default_timeout` in config, or break the task into smaller commands. The agent receives `fix_instructions` guiding it to do this.

### 16.6 Context layer not loading

**Symptom**: System prompt is empty or missing expected content.

**Checklist**:
1. Is `disclosure_level` set to `"index"`? DETAIL layers are skipped unless the task matches a keyword.
2. Does the source file actually exist? `FileSource` raises `FileNotFoundError` on load — check the engine log for warnings.
3. Is the layer's token budget being exceeded? Check `total_token_budget` and per-layer `max_tokens`.

### 16.7 EntropyGardener not running

**Symptom**: No `GardenAction` objects returned.

**Checklist**:
1. `entropy.gardener_enabled` must be `True`
2. Gardener runs only every `gardener_interval_turns` turns — check `turn_count`
3. Golden rules are only checked if `golden_rules` is non-empty in config
4. `no_duplicate_tools` requires `tool_registry` to be passed to `EntropyGardener`
