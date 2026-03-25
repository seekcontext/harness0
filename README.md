<p align="center">
  <h1 align="center">harness0</h1>
  <p align="center">
    <strong>Agent reliability through harness engineering.</strong>
  </p>
  <p align="center">
    <a href="#design-preview">Design Preview</a> &middot;
    <a href="#the-5-layer-harness-model">5-Layer Model</a> &middot;
    <a href="#planned-framework-integrations">Integrations</a> &middot;
    <a href="docs/architecture.md">Architecture</a> &middot;
    <a href="#contributing">Contributing</a>
  </p>
</p>

> **Status: Pre-Alpha — Under Active Development**
>
> This project is in the design and early implementation phase. The APIs shown below represent the **planned design** and are not yet available. Star/watch the repo to follow progress.

---

**harness0** is not another agent framework. It is a **harness reliability layer** designed to make any agent framework more reliable.

```
Agent = Loop(Model + Harness)
```

You provide the Model. harness0 provides the Harness.

```
┌─────────────────────────────────────────┐
│           Your Application              │
├─────────────────────────────────────────┤
│  Orchestration (pick one)               │
│  LangChain / CrewAI / PydanticAI / DIY  │
├─────────────────────────────────────────┤
│  ★ harness0 (harness layer)           │  ← Layer 0: we are here
│  Context Assembly │ Tool Governance     │
│  Feedback Loop    │ Entropy Management  │
│  Security Guard                         │
├─────────────────────────────────────────┤
│  LLM API                               │
│  OpenAI / Anthropic / DeepSeek / Local  │
└─────────────────────────────────────────┘
```

## Why "harness0"?

The **0** stands for **Layer 0** — the foundational layer beneath every agent framework. Just as Layer 0 in networking is the physical medium that all higher layers depend on, harness0 is the reliability substrate that every orchestration framework sits on top of.

> harness0: ground zero of agent reliability.

Every agent developer hits the same walls:

| Problem | Root Cause | harness0 Layer |
|---|---|---|
| "Demo works, production fails" | No structured context management | **L1** Context Assembly |
| "More tools = less stable" | Tools are an ungoverned bag of functions | **L2** Tool Governance |
| "Afraid to let agents run commands" | Security relies on prompt-level trust | **L3** Security Guard |
| "Agent fails but doesn't know why" | System errors aren't translated for the model | **L4** Feedback Loop |
| "Agent drifts on long tasks" | Context decays — stale rules, bloated history | **L5** Entropy Management |

Existing frameworks solve orchestration. harness0 solves **reliability** — and works **with** them, not against them.

## Design Preview

> The APIs below show the **planned** interface. Implementation is in progress.

### Installation (planned)

```bash
pip install harness0
```

### 10 Lines to a Reliable Agent (planned API)

```python
import asyncio
from harness0 import HarnessEngine

engine = HarnessEngine.from_config("harness.yaml")

@engine.tool(risk_level="read")
async def read_file(path: str) -> str:
    """Read a file and return its contents."""
    return open(path).read()

@engine.tool(risk_level="execute", requires_approval=True)
async def run_command(command: str) -> str:
    """Execute a shell command in the sandbox."""
    ...

async def main():
    result = await engine.run("Create a Python script that prints hello world")
    print(result.output)

asyncio.run(main())
```

### Configuration via `harness.yaml` (planned)

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
  detect_conflicts: true
```

One YAML. Five layers. Portable across projects, teams, and frameworks.

## The 5-Layer Harness Model

### L1: Context Assembly

Prompts are not documents — they are **assembly systems**.

```python
from harness0.context import ContextAssembler, ContextLayer, FileSource, CallableSource

assembler = ContextAssembler(layers=[
    ContextLayer(name="base", priority=0, source=FileSource("prompts/base.md")),
    ContextLayer(name="project", priority=10, source=FileSource("AGENTS.md"), freshness="per_session"),
    ContextLayer(name="state", priority=20, source=CallableSource(get_state), freshness="per_turn"),
])

messages = await assembler.assemble(turn_context)
```

Multiple sources, explicit priorities, freshness policies (`static` / `per_session` / `per_turn`), per-layer token budgets. No more guessing what the model sees.

### L2: Tool Governance

Tools are not a bag of functions — they are **governed runtime capabilities**.

```python
from harness0.tools import ToolDefinition, RiskLevel

@engine.tool(risk_level=RiskLevel.EXECUTE, requires_approval=True, timeout=30)
async def run_command(command: str) -> str:
    """Execute a shell command in the sandbox."""
    ...
```

Every tool call passes through a unified interception pipeline:

```
ToolCall → Validate → Classify Risk → Approve → Execute → Truncate Output → Audit
```

Four risk levels: `READ` (no side effects) → `WRITE` (modifies state) → `EXECUTE` (runs code) → `CRITICAL` (irreversible).

### L3: Security Guard

Security belongs at **runtime**, not in prompts.

Three lines of defense:

- **ProcessSandbox** — Subprocess pool with limits (max concurrent, output cap, timeout, auto-cleanup)
- **CommandGuard** — Command parsing + configurable blocklist with structured rejection reasons
- **ApprovalManager** — Risk-based approval with fingerprint caching (approve once, skip identical actions)

```yaml
security:
  sandbox_enabled: true
  blocked_commands: ["rm -rf", "sudo", "> /dev/sda"]
  approval_mode: risky_only   # always | risky_only | never
```

Even if the model "misbehaves," the system has boundaries.

### L4: Feedback Loop

System events must be **translated** into model-consumable signals.

| What Happened | Raw Output | What the Model Receives |
|---|---|---|
| Command blocked | `PermissionError` | "Command blocked by security policy. Try a non-privileged approach." |
| Output truncated | Silent cutoff | "Output truncated from 50K to 5K tokens. Narrow your search scope." |
| Subprocess timeout | `TimeoutError` | "Command exceeded 30s timeout. Break into smaller steps." |

Every signal includes: what happened, why, and **what to do next**. Injected into the next turn's context automatically.

### L5: Entropy Management

Agent systems **decay** over time. Active maintenance is required.

|  | Passive Compression (others) | Entropy Management (harness0) |
|---|---|---|
| Trigger | Token count near limit | Every N turns, proactively |
| Method | Summarize old messages | Detect + classify + targeted cleanup |
| Detects rule conflicts? | No | **Yes** |
| Detects stale info? | No | **Yes** |
| Detects repetition? | No | **Yes** |

Not just making space — **maintaining context quality**.

## Use Individual Layers (planned)

Every layer is designed to be independently importable. No need to buy into the full framework.

```python
# Just context assembly
from harness0.context import ContextAssembler
assembler = ContextAssembler(layers=[...])
messages = await assembler.assemble(turn_context)

# Just tool governance
from harness0.tools import ToolInterceptor
result = await interceptor.execute(tool_call)

# Just entropy management
from harness0.entropy import EntropyManager
cleaned = await manager.process(bloated_messages)
```

Use what you need. Leave the rest.

## Planned Framework Integrations

harness0 is designed to work **with** your existing framework, not instead of it. Integration adapters are on the roadmap for these frameworks:

| Framework | Install | Adapter Strategy |
|---|---|---|
| LangChain | `pip install harness0[langchain]` | Wrap as LangChain middleware (`before_model`, `wrap_tool_call` hooks) |
| OpenAI Agents SDK | `pip install harness0[openai]` | Wrap as input/output/tool guardrails |
| PydanticAI | `pip install harness0[pydantic-ai]` | Integrate via dependency injection |
| CrewAI | `pip install harness0[crewai]` | Wrap as tool decorators |

Each integration maps harness0's 5 layers to the target framework's extension points. The exact APIs will be finalized after the core layers are stable.

> See [architecture.md](docs/architecture.md) for detailed integration design sketches.

## How It Compares

> Comparison based on publicly available documentation as of March 2026. harness0 column reflects **planned** capabilities.

| Capability | LangChain Deep Agents | OpenAI Agents SDK | Microsoft AGT | harness0 (planned) |
|---|---|---|---|---|
| Multi-layer context assembly | — | Basic (2-tier) | — | **Core** |
| Tool risk classification | — | allow/reject/raise | Policy engine | **4-level** |
| Sandbox execution | Remote sandbox | — | 4 privilege rings | **Lightweight** |
| Approval workflows | HITL middleware | approve/reject | Yes | **Yes** |
| Feedback translation | — | — | — | **Core** |
| Entropy detection | — | — | — | **Core** |
| Declarative config | — | — | OPA/Rego | **YAML** |
| Framework agnostic | No | No | Yes | **Yes** |

Based on our research, three capabilities are not addressed by major frameworks: multi-layer context assembly, feedback translation, and entropy management. See [competitive-analysis.md](docs/competitive-analysis.md) for detailed methodology.

## Conceptual Background

harness0 is built on the **Harness Engineering** philosophy:

> The model is the engine. The harness is what makes it driveable.

The same model in different harness environments can produce dramatically different results. Industry practitioners have reported significant agent performance improvements by modifying only the harness while keeping the model fixed.

The concept was first introduced by Ryan Lopopolo at OpenAI in February 2026. See the original post: [Harness Engineering: Leveraging Codex in an Agent-First World](https://openai.com/index/harness-engineering/).

## Project Structure

```
src/harness0/
├── engine.py                # HarnessEngine facade (entry point)
├── core/                    # AgentLoop, AgentState, HarnessConfig
├── context/                 # L1: ContextAssembler, layers, sources
├── tools/                   # L2: ToolRegistry, governance, interceptor
├── security/                # L3: ProcessSandbox, CommandGuard, ApprovalManager
├── feedback/                # L4: FeedbackTranslator, signals, hints
├── entropy/                 # L5: EntropyManager, compressor, decay detector
├── llm/                     # LLM provider abstraction (OpenAI, Anthropic)
├── integrations/            # Framework adapters (optional dependencies)
└── plugins/                 # Built-in tool plugins (file, shell, search)
```

## Requirements

- Python 3.11+
- Core dependencies: `pydantic`, `httpx`, `pyyaml`, `tiktoken`
- Framework adapters are optional installs

## Contributing

Contributions are welcome! Areas where help is especially valuable:

- **New integration adapters** — Help harness0 work with more frameworks
- **Entropy detection strategies** — Novel ways to detect context degradation
- **Built-in tool plugins** — Expand the toolkit agents can use out of the box
- **Documentation and examples** — Make harness engineering accessible to more developers
- **Benchmarks** — Measure the impact of harness engineering on agent performance

## License

MIT

## Links

- [Project Vision](docs/project-vision.md)
- [Technical Architecture](docs/architecture.md)
- [Competitive Analysis](docs/competitive-analysis.md)
- [Growth Strategy](docs/growth-strategy.md)
