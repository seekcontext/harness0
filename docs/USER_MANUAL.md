# Harness0 — User Manual

> **Status**: This manual describes the **planned** API and behavior of harness0. The project is under active development. APIs may change before the first stable release.

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
- [12. Framework Integrations](#12-framework-integrations)
- [13. Built-in Tool Plugins](#13-built-in-tool-plugins)
- [14. LLM Providers](#14-llm-providers)
- [15. Advanced Topics](#15-advanced-topics)
- [16. Troubleshooting](#16-troubleshooting)

---

## 1. Installation

### Basic installation

```bash
pip install harness0
```

This installs the core library with minimal dependencies: `pydantic`, `httpx`, `pyyaml`, `tiktoken`.

### With framework integration adapters

```bash
pip install harness0[langchain]      # LangChain Deep Agents middleware
pip install harness0[openai]         # OpenAI Agents SDK guardrails
pip install harness0[pydantic-ai]    # PydanticAI dependency injection
pip install harness0[crewai]         # CrewAI tool wrappers
```

### From source (development)

```bash
git clone https://github.com/YOUR_USERNAME/harness0.git
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

### 3.1 Minimal example

Create two files:

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
  total_token_budget: 8000

security:
  sandbox_enabled: true
  blocked_commands: ["rm -rf", "sudo"]
  approval_mode: risky_only

feedback:
  inject_hints: true

entropy:
  compression_threshold: 6000
  decay_check_interval: 10
```

**main.py**:

```python
import asyncio
from harness0 import HarnessEngine

engine = HarnessEngine.from_config("harness.yaml")

@engine.tool(risk_level="read")
async def read_file(path: str) -> str:
    """Read a file and return its contents."""
    with open(path) as f:
        return f.read()

@engine.tool(risk_level="write")
async def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    with open(path, "w") as f:
        f.write(content)
    return f"Written {len(content)} chars to {path}"

@engine.tool(risk_level="execute", requires_approval=True)
async def run_command(command: str) -> str:
    """Execute a shell command."""
    ...

async def main():
    result = await engine.run("Create a Python script that prints hello world")
    print(result.output)

asyncio.run(main())
```

**prompts/base.md**:

```markdown
You are a coding assistant. You help users by writing and modifying code.

Rules:
- Always read existing files before modifying them.
- Write clean, well-structured code.
- Prefer small, focused changes.
```

Run:

```bash
export OPENAI_API_KEY="sk-..."
python main.py
```

### 3.2 What happens at runtime

When you call `engine.run("Create a Python script...")`, the following sequence executes:

```
1. L1 ContextAssembler loads prompts/base.md and builds the system prompt
2. The task is sent to the LLM along with available tool definitions
3. LLM responds (e.g., calls write_file tool)
4. L2 ToolInterceptor validates the call:
   - Checks parameters against schema
   - Classifies risk level (WRITE)
   - write_file is WRITE risk, approval_mode is risky_only → no approval needed
5. L3 SecurityGuard checks the operation (if applicable)
6. Tool executes → result returned
7. L4 FeedbackTranslator checks for system events (truncation, errors, etc.)
   - If any: generates FeedbackSignal and injects into next turn
8. L5 EntropyManager checks if context quality has degraded
   - If degraded: compresses/cleans before next LLM call
9. Loop repeats until LLM produces a final response or max_iterations reached
```

### 3.3 Programmatic configuration (no YAML)

You can skip the YAML file and configure everything in code:

```python
from harness0 import HarnessEngine
from harness0.core.config import (
    HarnessConfig,
    ContextConfig,
    ToolGovernanceConfig,
    SecurityConfig,
    FeedbackConfig,
    EntropyConfig,
    LLMConfig,
)
from harness0.context import ContextLayer, FileSource

config = HarnessConfig(
    llm=LLMConfig(provider="openai", model="gpt-4o"),
    context=ContextConfig(
        layers=[
            ContextLayer(name="base", priority=0, source=FileSource("prompts/base.md")),
        ],
        total_token_budget=8000,
    ),
    tools=ToolGovernanceConfig(default_risk="read"),
    security=SecurityConfig(
        sandbox_enabled=True,
        blocked_commands=["rm -rf", "sudo"],
        approval_mode="risky_only",
    ),
    feedback=FeedbackConfig(inject_hints=True),
    entropy=EntropyConfig(compression_threshold=6000),
    max_iterations=50,
)

engine = HarnessEngine(config=config)
```

---

## 4. Configuration Reference

The `harness.yaml` file controls all 5 layers. Below is a complete reference with all available fields and their defaults.

### 4.1 Top-level fields

| Field | Type | Default | Description |
|---|---|---|---|
| `max_iterations` | int | `50` | Maximum agent loop iterations before forced stop |
| `checkpoint_enabled` | bool | `true` | Enable state checkpointing for long-task recovery |
| `checkpoint_dir` | string | `.harness0/checkpoints` | Directory for checkpoint files |

### 4.2 `llm` — LLM Provider

```yaml
llm:
  provider: openai          # "openai" | "anthropic"
  model: gpt-4o             # Model identifier
  api_key: ${OPENAI_API_KEY} # Supports env var expansion; omit to read from environment
  base_url: null             # Custom API endpoint (for proxies or compatible APIs)
  temperature: 0.0           # LLM temperature
  max_tokens: 4096           # Max tokens in LLM response
```

### 4.3 `context` — L1 Context Assembly

```yaml
context:
  layers:
    - name: base                # Unique layer name
      source: prompts/base.md   # File path, directory path, or "callable:function_name"
      priority: 0               # Lower = loaded first, higher = loaded later (higher override)
      freshness: static         # "static" | "per_session" | "per_turn"
      max_tokens: null           # Per-layer token budget (null = no limit)
      role: system              # Message role: "system" | "user" | "assistant"

    - name: project
      source: AGENTS.md
      priority: 10
      freshness: per_session

    - name: skills
      source: skills/           # Directory: all .md files loaded as separate sub-layers
      priority: 15
      freshness: static

    - name: runtime_state
      source: callable:get_current_state   # Python callable, registered at runtime
      priority: 20
      freshness: per_turn

  total_token_budget: 8000      # Total token budget across all layers
```

**Layer resolution order**: Layers are sorted by `priority` (ascending). Lower priority layers are loaded first. When the total token budget is exceeded, lower-priority layers are truncated first.

**Source types**:

| Source syntax | Resolved as |
|---|---|
| `path/to/file.md` | `FileSource` — load single file |
| `path/to/directory/` | `DirectorySource` — load all `.md`/`.yaml` files in directory |
| `callable:function_name` | `CallableSource` — call a registered Python function |
| (inline string in programmatic config) | `InlineSource` — use string directly |

**Freshness modes**:

| Mode | Behavior |
|---|---|
| `static` | Loaded once at engine initialization. Never reloaded. |
| `per_session` | Reloaded when a new session/run starts. |
| `per_turn` | Reloaded before every LLM call. Use for dynamic state. |

### 4.4 `tools` — L2 Tool Governance

```yaml
tools:
  default_risk: read            # Default risk level for tools without explicit risk_level
  max_output_tokens: 5000       # Max tokens in tool output before truncation
  default_timeout: 30           # Default tool execution timeout in seconds
  audit_enabled: true           # Log all tool calls to audit trail
  audit_file: null              # File path for audit log (null = in-memory only)
```

Tool-specific configuration is done via the `@engine.tool()` decorator or `ToolDefinition` objects, not in YAML. The YAML sets global defaults.

### 4.5 `security` — L3 Security Guard

```yaml
security:
  sandbox_enabled: true         # Enable subprocess sandboxing
  max_processes: 5              # Max concurrent subprocesses
  max_output_bytes: 100000      # Max output per subprocess (bytes), truncated beyond this
  default_timeout: 30           # Default subprocess timeout (seconds)

  blocked_commands:             # Command patterns to block (regex-capable)
    - "rm -rf"
    - "sudo"
    - "> /dev/sda"
    - "mkfs"
    - "dd if="
    - ":(){:|:&};:"             # Fork bomb

  approval_mode: risky_only     # "always" | "risky_only" | "never"
                                # always: approve every tool call
                                # risky_only: approve EXECUTE and CRITICAL risk levels
                                # never: no approval (use with caution)

  approval_cache: true          # Cache approved actions by fingerprint (skip repeat approvals)
```

### 4.6 `feedback` — L4 Feedback Loop

```yaml
feedback:
  inject_hints: true            # Inject FeedbackSignals into next turn's context
  signal_format: xml            # "xml" | "json" | "markdown" — format of injected hints
  max_signals_per_turn: 5       # Max feedback signals to inject per turn (oldest dropped first)
  include_suggestions: true     # Include actionable suggestions in signals
```

### 4.7 `entropy` — L5 Entropy Management

```yaml
entropy:
  enabled: true                   # Enable entropy management
  compression_threshold: 6000     # Token count that triggers compression
  decay_check_interval: 10        # Check for decay every N turns
  detect_conflicts: true          # Detect contradictory rules/instructions
  detect_staleness: true          # Detect temporally stale content
  staleness_threshold_hours: 24   # Content older than this is flagged as stale
  detect_repetition: true         # Detect duplicate/near-duplicate content
  compression_strategy: targeted  # "targeted" | "summarize" | "sliding_window"
                                  # targeted: remove/clean specific degraded content
                                  # summarize: LLM-based summarization of old content
                                  # sliding_window: keep only most recent N messages
```

---

## 5. L1: Context Assembly

### 5.1 What it does

The Context Assembler builds the LLM prompt dynamically each turn by loading, prioritizing, and budgeting content from multiple sources.

### 5.2 Why it matters

Without structured context assembly, developers end up with:
- One monolithic system prompt that grows until it exceeds token limits
- No control over which information the model prioritizes
- Stale project rules mixed with fresh runtime state
- No way to know what the model actually "sees"

### 5.3 Defining layers in YAML

```yaml
context:
  layers:
    - name: base
      source: prompts/base.md
      priority: 0
      freshness: static

    - name: soul
      source: SOUL.md
      priority: 5
      freshness: static
      max_tokens: 500

    - name: project
      source: AGENTS.md
      priority: 10
      freshness: per_session

    - name: skills
      source: skills/
      priority: 15
      freshness: static

    - name: runtime_state
      source: callable:get_current_state
      priority: 20
      freshness: per_turn
      max_tokens: 1000

  total_token_budget: 8000
```

### 5.4 Defining layers in code

```python
from harness0.context import (
    ContextAssembler,
    ContextLayer,
    FileSource,
    DirectorySource,
    CallableSource,
    InlineSource,
)

async def get_current_state() -> str:
    return "Current directory: /home/user/project\nModified files: main.py, utils.py"

assembler = ContextAssembler(
    layers=[
        ContextLayer(
            name="base",
            priority=0,
            source=FileSource("prompts/base.md"),
            freshness="static",
        ),
        ContextLayer(
            name="soul",
            priority=5,
            source=InlineSource("You are thoughtful, precise, and prefer simple solutions."),
            freshness="static",
            max_tokens=500,
        ),
        ContextLayer(
            name="skills",
            priority=15,
            source=DirectorySource("skills/"),
            freshness="static",
        ),
        ContextLayer(
            name="runtime_state",
            priority=20,
            source=CallableSource(get_current_state),
            freshness="per_turn",
            max_tokens=1000,
        ),
    ],
    total_token_budget=8000,
)
```

### 5.5 How assembly works

On each call to `assembler.assemble(turn_context)`:

1. **Load** — Each layer loads its content based on freshness policy. `static` layers use cached content. `per_turn` layers reload every time.
2. **Sort** — Layers are ordered by priority (ascending).
3. **Budget** — Token counts are calculated. If the total exceeds `total_token_budget`, lower-priority layers are truncated first. Per-layer `max_tokens` limits are enforced individually.
4. **Format** — Each layer's content is formatted into a `Message` object with the appropriate role.
5. **Return** — The assembled messages are returned as a `list[Message]`.

### 5.6 Registering callable sources

When using `callable:function_name` in YAML, you must register the function at runtime:

```python
engine = HarnessEngine.from_config("harness.yaml")

async def get_current_state() -> str:
    return "Working directory: /project\nGit branch: main"

engine.context.register_callable("get_current_state", get_current_state)
```

### 5.7 Recommended layer structure

A typical project might use this layering:

| Priority | Name | Content | Freshness |
|---|---|---|---|
| 0 | `base` | Core identity and instructions | static |
| 5 | `soul` | Personality and style preferences (SOUL.md) | static |
| 10 | `project` | Project-specific rules and context (AGENTS.md) | per_session |
| 15 | `skills` | Available skill descriptions (skills/*.md) | static |
| 20 | `state` | Current runtime state (working dir, open files, etc.) | per_turn |

---

## 6. L2: Tool Governance

### 6.1 What it does

The Tool Governance layer manages the full lifecycle of tool calls: registration, discovery, validation, risk classification, approval, execution, output management, and auditing.

### 6.2 Registering tools

**Via decorator** (recommended):

```python
@engine.tool(risk_level="read")
async def read_file(path: str) -> str:
    """Read a file and return its contents."""
    with open(path) as f:
        return f.read()

@engine.tool(risk_level="write")
async def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    with open(path, "w") as f:
        f.write(content)
    return f"Written {len(content)} chars to {path}"

@engine.tool(
    risk_level="execute",
    requires_approval=True,
    timeout=60,
    max_output_tokens=10000,
)
async def run_command(command: str) -> str:
    """Execute a shell command."""
    ...
```

**Via ToolDefinition** (programmatic):

```python
from harness0.tools import ToolDefinition, RiskLevel

tool_def = ToolDefinition(
    name="run_command",
    description="Execute a shell command",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The command to execute"},
        },
        "required": ["command"],
    },
    risk_level=RiskLevel.EXECUTE,
    requires_approval=True,
    timeout_seconds=60,
    max_output_tokens=10000,
)

engine.tools.register(tool_def, handler=run_command_handler)
```

### 6.3 Risk levels

| Level | Value | Meaning | Default approval behavior |
|---|---|---|---|
| `READ` | `"read"` | No side effects. Safe to execute freely. | No approval needed |
| `WRITE` | `"write"` | Modifies state (files, databases). | No approval by default |
| `EXECUTE` | `"execute"` | Runs code or shell commands. | Approval when `approval_mode: risky_only` |
| `CRITICAL` | `"critical"` | Irreversible or potentially dangerous. | Always requires approval |

### 6.4 The interception pipeline

Every tool call passes through this pipeline in order:

```
1. Schema Validation
   - Check that call parameters match the tool's JSON Schema
   - If invalid: reject with FeedbackSignal explaining the error

2. Risk Assessment
   - Look up the tool's RiskLevel
   - Determine if approval is required based on risk + approval_mode

3. Approval Check (if required)
   - Check fingerprint cache (skip if identical action was previously approved)
   - If not cached: request approval from the approval backend
   - If denied: reject with FeedbackSignal

4. Execute
   - Run the tool handler with the validated parameters
   - Enforce timeout (kill if exceeded)

5. Output Truncation
   - If output exceeds max_output_tokens: truncate and generate FeedbackSignal

6. Audit Log
   - Record: tool name, parameters, risk level, approval status, result (truncated),
     execution time, timestamp
```

### 6.5 Output truncation

When a tool returns more content than `max_output_tokens`, the output is truncated and a feedback signal is generated:

```
FeedbackSignal(
    type="warning",
    source="tools.interceptor",
    message="Tool 'grep_search' output was truncated from 12,340 to 5,000 tokens.",
    actionable=True,
    suggestion="Consider narrowing your search pattern or limiting the search scope."
)
```

The model receives the truncated output plus this signal, so it knows content was lost and can adjust its approach.

### 6.6 Audit trail

When `audit_enabled: true`, every tool call is logged:

```json
{
  "timestamp": "2026-03-25T10:30:45Z",
  "tool": "run_command",
  "parameters": {"command": "ls -la src/"},
  "risk_level": "execute",
  "approval": "approved",
  "result_tokens": 342,
  "truncated": false,
  "duration_ms": 1523,
  "error": null
}
```

If `audit_file` is set, logs are appended to that file. Otherwise, logs are kept in memory and accessible via `engine.tools.audit_log`.

---

## 7. L3: Security Guard

### 7.1 What it does

The Security Guard enforces safety boundaries at runtime. It does not rely on the model "being well-behaved" — it enforces boundaries regardless of model behavior.

### 7.2 ProcessSandbox

The ProcessSandbox manages subprocess execution with hard limits:

```yaml
security:
  sandbox_enabled: true
  max_processes: 5          # No more than 5 concurrent subprocesses
  max_output_bytes: 100000  # Output capped at ~100KB per process
  default_timeout: 30       # Processes killed after 30 seconds
```

**Behavior**:
- When a tool calls a subprocess, it goes through the sandbox.
- If `max_processes` is reached, new subprocess requests queue until a slot opens.
- If output exceeds `max_output_bytes`, the output is truncated and a FeedbackSignal is generated via L4.
- If a process exceeds `default_timeout`, it is killed and a FeedbackSignal is generated.
- When a session ends, all subprocesses are cleaned up automatically.

### 7.3 CommandGuard

The CommandGuard parses commands and checks them against a blocklist before execution:

```yaml
security:
  blocked_commands:
    - "rm -rf"
    - "sudo"
    - "> /dev/sda"
    - "mkfs"
    - "dd if="
    - ":(){:|:&};:"
```

**Behavior**:
- Commands are parsed and matched against each pattern.
- Patterns support regex for flexible matching.
- If a command matches any blocked pattern, execution is rejected.
- The rejection generates a `GuardResult` with a human-readable reason.
- The `GuardResult` is passed to L4 FeedbackTranslator, which creates a model-consumable signal.

**Example flow**:

```
Model calls: run_command("sudo rm -rf /tmp/old_files")

CommandGuard detects: matches "sudo" pattern
  → GuardResult(blocked=True, reason="Command contains 'sudo' which is blocked by security policy")
  → L4 translates to FeedbackSignal:
    "Command blocked: contains 'sudo'. Suggestion: run without sudo, or target specific files with 'rm /tmp/old_files/specific_file'"
  → Model receives signal in next turn and adjusts approach
```

### 7.4 ApprovalManager

The ApprovalManager gates risky actions behind human approval:

```yaml
security:
  approval_mode: risky_only   # "always" | "risky_only" | "never"
  approval_cache: true
```

**Approval modes**:

| Mode | Behavior |
|---|---|
| `always` | Every tool call requires approval, regardless of risk level |
| `risky_only` | Only `EXECUTE` and `CRITICAL` risk levels require approval |
| `never` | No approvals. Use only in trusted/sandboxed environments |

**Fingerprint caching**: When `approval_cache: true`, approved actions are cached by SHA-256 fingerprint (hash of tool name + parameters). If the same action is requested again, approval is skipped. This prevents repeatedly asking "allow ls -la?" in a loop.

**Custom approval backend**: The default approval backend prompts via stdin. You can provide a custom backend for integration with Slack, Telegram, web UI, etc.:

```python
from harness0.security import ApprovalManager, ApprovalBackend

class SlackApprovalBackend(ApprovalBackend):
    async def request_approval(self, action: str, details: dict) -> bool:
        # Send to Slack, wait for response
        ...

engine.security.set_approval_backend(SlackApprovalBackend())
```

---

## 8. L4: Feedback Loop

### 8.1 What it does

The Feedback Loop translates raw system events into structured signals that the model can understand and act on. Without this layer, the model sees cryptic errors. With it, the model sees actionable explanations.

### 8.2 FeedbackSignal structure

```python
class FeedbackSignal(BaseModel):
    type: SignalType           # "error" | "warning" | "info" | "constraint"
    source: str                # Subsystem that generated this signal
    message: str               # Clear explanation of what happened
    actionable: bool           # Can the model do something about it?
    suggestion: str | None     # Recommended next action (if actionable)
```

### 8.3 Signal types

| Type | When used | Example |
|---|---|---|
| `error` | Tool execution failed | "File '/nonexistent' not found." |
| `warning` | Something was degraded or limited | "Output truncated from 50K to 5K tokens." |
| `info` | Non-critical information | "Approval was granted for 'deploy' action." |
| `constraint` | Action was blocked by policy | "Command 'sudo apt install' blocked by security policy." |

### 8.4 Automatic translation

The FeedbackTranslator automatically translates events from other layers:

| Source Event | Signal Type | Example Message |
|---|---|---|
| L2: Schema validation failure | `error` | "Tool 'write_file' called with invalid parameters: 'content' is required." |
| L2: Output truncation | `warning` | "Tool output truncated from 12K to 5K tokens. Consider narrowing scope." |
| L3: Command blocked | `constraint` | "Command 'rm -rf /' blocked by security policy. Use targeted deletion." |
| L3: Subprocess timeout | `error` | "Command exceeded 30s timeout. Break into smaller steps." |
| L3: Approval denied | `constraint` | "Action 'deploy' denied by approval policy. Requires user confirmation." |
| L5: Context compression | `info` | "Older conversation history was compressed to stay within token budget." |
| L5: Rule conflict detected | `warning` | "Contradictory instructions detected: rule A says X, rule B says not-X." |

### 8.5 Signal injection

When `feedback.inject_hints: true`, signals are formatted and injected into the next turn's context. The format depends on `signal_format`:

**XML format** (`signal_format: xml`):

```xml
<system_hint source="security.command_guard" type="constraint">
Command 'sudo apt install nginx' was blocked by security policy.
Suggestion: Install packages without sudo, or ask the user to install manually.
</system_hint>
```

**JSON format** (`signal_format: json`):

```json
{"type": "constraint", "source": "security.command_guard", "message": "Command blocked...", "suggestion": "..."}
```

**Markdown format** (`signal_format: markdown`):

```markdown
> **[Security Guard]** Command 'sudo apt install nginx' was blocked by security policy.
> *Suggestion:* Install packages without sudo, or ask the user to install manually.
```

### 8.6 Accessing signals programmatically

```python
result = await engine.run("Deploy the app")

for signal in result.feedback_signals:
    print(f"[{signal.type}] {signal.source}: {signal.message}")
```

---

## 9. L5: Entropy Management

### 9.1 What it does

The Entropy Manager detects and repairs context degradation in long-running agent sessions. While other frameworks do passive compression (summarize when full), harness0 does active quality maintenance.

### 9.2 Configuration

```yaml
entropy:
  enabled: true
  compression_threshold: 6000     # Trigger compression when context exceeds this token count
  decay_check_interval: 10        # Run decay detection every N turns
  detect_conflicts: true
  detect_staleness: true
  staleness_threshold_hours: 24
  detect_repetition: true
  compression_strategy: targeted  # "targeted" | "summarize" | "sliding_window"
```

### 9.3 Degradation detection

The EntropyManager runs detection scans every `decay_check_interval` turns. It looks for:

**Rule conflicts**: Two instructions in the context that contradict each other.

```
Detected: Layer "base" says "Always use TypeScript"
          Layer "project" says "This project uses JavaScript only"
Resolution: Higher-priority layer (project, priority=10) takes precedence.
            Lower-priority conflicting instruction removed.
```

**Temporal staleness**: Content that references outdated state.

```
Detected: Tool result from turn 3 references "current file: old_main.py"
          But file was renamed to "main.py" in turn 15.
Resolution: Stale tool result summarized or removed.
```

**Repetition**: Duplicate or near-duplicate content accumulating in history.

```
Detected: The same error message "ModuleNotFoundError: No module named 'foo'"
          appears in tool results at turns 5, 8, 12, and 15.
Resolution: Keep most recent occurrence, summarize others as
            "Same error repeated 3 times previously."
```

**Low information density**: Large tool outputs that contain mostly noise.

```
Detected: Tool result from 'grep_search' is 4,000 tokens but only 200 tokens
          are relevant to the current task.
Resolution: Compress to relevant excerpts.
```

### 9.4 Compression strategies

| Strategy | Behavior | Best for |
|---|---|---|
| `targeted` | Detect specific issues (conflicts, staleness, repetition) and fix them surgically | Most situations — highest quality |
| `summarize` | Use the LLM to summarize older messages into a condensed form | Simple long conversations |
| `sliding_window` | Keep only the most recent N messages, discard the rest | Maximum simplicity, lowest cost |

### 9.5 Using standalone

```python
from harness0.entropy import EntropyManager

manager = EntropyManager(
    compression_threshold=6000,
    detect_conflicts=True,
    detect_staleness=True,
    detect_repetition=True,
    compression_strategy="targeted",
)

# messages: list of conversation messages (dicts with role/content)
report = await manager.analyze(messages)
print(f"Entropy score: {report.score}")      # 0-100, higher = more degraded
print(f"Issues found: {len(report.issues)}")
for issue in report.issues:
    print(f"  - [{issue.type}] {issue.description}")

cleaned_messages = await manager.process(messages)
```

---

## 10. The Agent Loop

### 10.1 How the loop works

The `AgentLoop` is the core execution cycle:

```
START
  │
  ▼
┌─────────────────────────────────────────────────┐
│ 1. L1 ContextAssembler.assemble()               │
│    Load all layers, apply budgets, build prompt  │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ 2. LLM Provider.chat()                          │
│    Send messages + tool definitions to LLM      │
└──────────────────────┬──────────────────────────┘
                       │
               ┌───────┴───────┐
               │               │
          Tool calls?     Final response?
               │               │
               ▼               ▼
┌──────────────────────┐  ┌──────────────┐
│ 3. For each tool call│  │ Return result│
│    L2 → L3 → Execute │  │ END          │
│    → L4 feedback      │  └──────────────┘
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────┐
│ 4. L5 EntropyManager.check()                     │
│    If degradation detected: clean context         │
└──────────────────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────┐
│ 5. Checkpoint state (if enabled)                  │
└──────────────────────┬───────────────────────────┘
           │
           ▼
       iteration < max_iterations?
           │              │
          Yes             No
           │              │
           ▼              ▼
     Loop back to 1    Force stop, return partial result
```

### 10.2 AgentState

The `AgentState` tracks everything about a running agent:

```python
class AgentState(BaseModel):
    task: str                              # The original task
    iteration: int                         # Current iteration count
    messages: list[Message]                # Full conversation history
    tool_history: list[ToolInteraction]    # All tool calls and results
    feedback_signals: list[FeedbackSignal] # Accumulated feedback signals
    metadata: dict                         # Arbitrary user metadata
```

### 10.3 Checkpointing and recovery

When `checkpoint_enabled: true`, the agent state is saved to disk after each iteration:

```python
# State is automatically saved during engine.run()

# To recover from a checkpoint:
result = await engine.run(
    "Continue the refactoring task",
    resume_from="path/to/checkpoint.json",
)
```

This is valuable for long-running tasks where:
- The process might crash
- The user wants to pause and resume later
- You want to inspect intermediate state

### 10.4 Stop conditions

The loop stops when any of these conditions is met:

1. The LLM returns a final response (no tool calls)
2. `max_iterations` is reached
3. An unrecoverable error occurs
4. The user manually stops (in interactive mode)

### 10.5 AgentResult

```python
result = await engine.run("Create a hello world script")

result.output               # str — the final LLM response
result.iterations           # int — how many loop iterations ran
result.tool_calls           # list — all tool calls made
result.feedback_signals     # list — all feedback signals generated
result.state                # AgentState — full state (for inspection/recovery)
result.token_usage          # TokenUsage — total tokens consumed
```

---

## 11. Using Individual Layers

Every layer can be imported and used independently. This is the recommended approach when you already have an agent system and want to enhance specific capabilities.

### 11.1 L1 only: Better prompt management

```python
from harness0.context import ContextAssembler, ContextLayer, FileSource

assembler = ContextAssembler(
    layers=[
        ContextLayer(name="system", priority=0, source=FileSource("system_prompt.md")),
        ContextLayer(name="project", priority=10, source=FileSource("AGENTS.md")),
    ],
    total_token_budget=8000,
)

messages = await assembler.assemble(turn_context)
# Use these messages with your own LLM call
```

### 11.2 L2 only: Governed tool execution

```python
from harness0.tools import ToolRegistry, ToolInterceptor, ToolDefinition, RiskLevel

registry = ToolRegistry()
registry.register(
    ToolDefinition(name="write_file", risk_level=RiskLevel.WRITE, ...),
    handler=my_write_file_function,
)

interceptor = ToolInterceptor(registry, max_output_tokens=5000)

# In your agent loop, instead of calling tools directly:
result = await interceptor.execute(tool_call)
# This validates, classifies risk, truncates output, and logs the audit trail.
```

### 11.3 L3 only: Sandboxed command execution

```python
from harness0.security import ProcessSandbox, CommandGuard

guard = CommandGuard(blocked_commands=["rm -rf", "sudo", "mkfs"])
sandbox = ProcessSandbox(max_processes=5, max_output_bytes=100000, default_timeout=30)

check = guard.check("ls -la /home/user")
if check.blocked:
    print(f"Blocked: {check.reason}")
else:
    result = await sandbox.execute("ls -la /home/user")
    print(result.stdout)
```

### 11.4 L4 only: Better error messages for models

```python
from harness0.feedback import FeedbackTranslator, FeedbackSignal

translator = FeedbackTranslator()

# When a tool fails in your system:
signal = translator.translate_tool_error(
    tool_name="run_command",
    error=TimeoutError("Process exceeded 30s"),
)
# signal.message = "Command exceeded 30s timeout. Consider breaking into smaller steps."
# signal.suggestion = "Try running a simpler command first, or increase the timeout."

# Inject this signal into your next LLM call as a system message
```

### 11.5 L5 only: Context cleanup

```python
from harness0.entropy import EntropyManager

manager = EntropyManager(
    compression_threshold=6000,
    detect_conflicts=True,
    compression_strategy="targeted",
)

# In your agent loop, periodically:
if turn_number % 10 == 0:
    cleaned_messages = await manager.process(messages)
```

---

## 12. Framework Integrations

Integration adapters map harness0's 5 layers to each framework's extension points. Adapters are installed as optional extras and do not add core dependencies.

### 12.1 LangChain

**Install**: `pip install harness0[langchain]`

**How it works**: harness0 layers are wrapped as LangChain middleware, hooking into the `before_model`, `after_model`, and `wrap_tool_call` lifecycle points.

| harness0 Layer | LangChain Hook | What it does |
|---|---|---|
| L1 ContextAssembler | `before_model` | Assembles context before each LLM call |
| L2 ToolInterceptor | `wrap_tool_call` | Wraps tool calls with validation, risk, audit |
| L3 SecurityGuard | `wrap_tool_call` | Checks commands against blocklist before execution |
| L4 FeedbackTranslator | `after_model` + `wrap_tool_call` | Collects events and injects feedback signals |
| L5 EntropyManager | `before_model` | Detects and cleans context degradation |

### 12.2 OpenAI Agents SDK

**Install**: `pip install harness0[openai]`

**How it works**: harness0 layers are wrapped as OpenAI guardrails (input guardrails and tool guardrails).

### 12.3 PydanticAI

**Install**: `pip install harness0[pydantic-ai]`

**How it works**: harness0 is injected via PydanticAI's dependency injection system as a `deps_type`.

### 12.4 CrewAI

**Install**: `pip install harness0[crewai]`

**How it works**: harness0 provides a `@harness_tool` decorator that wraps CrewAI tool functions with governance, security, and feedback translation.

> Note: The exact adapter APIs will be finalized after the core layers are stable and each framework's extension points have been verified against their latest versions.

---

## 13. Built-in Tool Plugins

harness0 ships with a set of common tool plugins that are pre-configured with appropriate risk levels.

### 13.1 File tools

| Tool | Risk Level | Description |
|---|---|---|
| `read_file` | READ | Read file contents |
| `write_file` | WRITE | Write content to a file |
| `list_directory` | READ | List files and directories |

```python
from harness0.plugins.builtin import file_tools

engine.tools.register_plugin(file_tools)
```

### 13.2 Shell tools

| Tool | Risk Level | Description |
|---|---|---|
| `run_command` | EXECUTE | Execute a shell command (goes through L3 SecurityGuard) |

```python
from harness0.plugins.builtin import shell_tools

engine.tools.register_plugin(shell_tools)
```

### 13.3 Search tools

| Tool | Risk Level | Description |
|---|---|---|
| `grep_search` | READ | Search file contents by regex pattern |
| `glob_search` | READ | Find files by glob pattern |

```python
from harness0.plugins.builtin import search_tools

engine.tools.register_plugin(search_tools)
```

### 13.4 Registering all built-in plugins

```python
engine.tools.register_all_builtins()
```

### 13.5 Writing custom plugins

```python
from harness0.plugins.base import ToolPlugin, ToolDefinition, RiskLevel

class DatabasePlugin(ToolPlugin):
    name = "database"

    def get_tools(self) -> list[tuple[ToolDefinition, Callable]]:
        return [
            (
                ToolDefinition(
                    name="query_db",
                    description="Execute a read-only SQL query",
                    parameters={...},
                    risk_level=RiskLevel.READ,
                ),
                self.query_db,
            ),
        ]

    async def query_db(self, sql: str) -> str:
        ...

engine.tools.register_plugin(DatabasePlugin())
```

---

## 14. LLM Providers

### 14.1 Supported providers

| Provider | Config value | Requirements |
|---|---|---|
| OpenAI | `provider: openai` | `OPENAI_API_KEY` env var or `api_key` in config |
| Anthropic | `provider: anthropic` | `ANTHROPIC_API_KEY` env var or `api_key` in config |

### 14.2 OpenAI-compatible endpoints

Any API that implements the OpenAI chat completions interface can be used:

```yaml
llm:
  provider: openai
  model: deepseek-chat
  base_url: https://api.deepseek.com/v1
  api_key: ${DEEPSEEK_API_KEY}
```

This works with DeepSeek, Together AI, Ollama (with OpenAI-compatible mode), vLLM, and others.

### 14.3 Custom LLM provider

```python
from harness0.llm.base import LLMProvider, Message, LLMResponse

class MyCustomProvider(LLMProvider):
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        # Call your LLM API
        ...

    async def count_tokens(self, text: str) -> int:
        # Return token count for the text
        ...

engine = HarnessEngine(config=config, llm_provider=MyCustomProvider())
```

---

## 15. Advanced Topics

### 15.1 Environment variable expansion in YAML

Configuration values support `${ENV_VAR}` syntax:

```yaml
llm:
  api_key: ${OPENAI_API_KEY}
  base_url: ${LLM_BASE_URL}
```

If the environment variable is not set, an error is raised at config load time.

### 15.2 Multiple config files

You can split configuration across files and merge them:

```python
engine = HarnessEngine.from_configs(
    "harness.yaml",           # Base config
    "harness.local.yaml",     # Local overrides (gitignored)
)
```

Later files override earlier files. This allows team-shared base configs with per-developer overrides.

### 15.3 Observing the agent loop

You can attach observers to monitor the agent loop in real time:

```python
from harness0.core.loop import LoopObserver

class MyObserver(LoopObserver):
    async def on_iteration_start(self, state: AgentState):
        print(f"--- Iteration {state.iteration} ---")

    async def on_tool_call(self, tool_name: str, params: dict):
        print(f"Calling tool: {tool_name}")

    async def on_feedback(self, signal: FeedbackSignal):
        print(f"Feedback: [{signal.type}] {signal.message}")

engine.loop.add_observer(MyObserver())
```

### 15.4 Token usage tracking

```python
result = await engine.run("Refactor the codebase")

print(f"Input tokens:  {result.token_usage.input_tokens}")
print(f"Output tokens: {result.token_usage.output_tokens}")
print(f"Total tokens:  {result.token_usage.total_tokens}")
print(f"LLM calls:     {result.token_usage.llm_calls}")
```

---

## 16. Troubleshooting

### Common issues

**"Config validation error: field X is required"**

Your `harness.yaml` is missing a required field. Check the [Configuration Reference](#4-configuration-reference) for required fields. At minimum, you need `llm.provider` and `llm.model`.

**"No tools registered"**

You must register at least one tool before calling `engine.run()`. Use `@engine.tool()` decorator or `engine.tools.register_plugin()`.

**"Context budget exceeded — layers truncated"**

Your `total_token_budget` is too small for all your layers. Either increase the budget or add `max_tokens` limits to lower-priority layers so they are truncated gracefully.

**"Approval timeout"**

In `approval_mode: risky_only` or `always`, the agent blocks waiting for human approval. If running non-interactively, either set `approval_mode: never` or provide a custom approval backend.

**"Command blocked by security policy"**

A tool tried to execute a command matching your `blocked_commands` list. This is working as intended. The model will receive a FeedbackSignal explaining why. If the command should be allowed, update your `blocked_commands` list.

### Getting help

- **GitHub Issues**: Report bugs and request features
- **GitHub Discussions**: Ask questions and share usage patterns
- **Documentation**: See [architecture.md](architecture.md) for technical details
