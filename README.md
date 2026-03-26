<p align="center">
  <img src="https://raw.githubusercontent.com/seekcontext/harness0/main/assets/harness0-banner.png" alt="harness0 — Layer 0 of Agent Reliability" width="100%">
</p>

<p align="center">
  <a href="https://pypi.org/project/harness0/"><img src="https://img.shields.io/pypi/v/harness0?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/harness0/"><img src="https://img.shields.io/pypi/pyversions/harness0" alt="Python 3.11+"></a>
  <a href="https://github.com/seekcontext/harness0/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT"></a>
</p>

<p align="center">
  <strong>Harness Engine for AI Agents.<br>A reliability layer that makes any agent stable.</strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#the-5-layer-harness-model">5-Layer Model</a> &middot;
  <a href="#use-individual-layers">Individual Layers</a> &middot;
  <a href="https://github.com/seekcontext/harness0/blob/main/docs/USER_MANUAL.md">User Manual</a> &middot;
  <a href="https://github.com/seekcontext/harness0/blob/main/docs/architecture.md">Architecture</a>
</p>

---

```
Agent = Loop(Model + Harness)
```

You provide the Model. **harness0** provides the Harness — the engineering infrastructure that makes the model work reliably in production.

```
┌─────────────────────────────────────────┐
│           Your Application              │
├─────────────────────────────────────────┤
│  Orchestration (pick one)               │
│  LangChain / CrewAI / PydanticAI / DIY  │
├─────────────────────────────────────────┤
│  ★ harness0 — reliability layer         │  ← Layer 0
│  Context · Tools · Security             │
│  Feedback · Entropy                     │
├─────────────────────────────────────────┤
│  LLM API                                │
│  OpenAI / Anthropic / DeepSeek / Local  │
└─────────────────────────────────────────┘
```

Keep using whatever framework you already use. harness0 is **complementary** — it adds the reliability layer underneath.

> **Concept origin**: [Harness Engineering](https://openai.com/index/harness-engineering/) was introduced by OpenAI (Feb 2026), based on building a 1M-line, fully agent-generated codebase. The key insight: *the model is the engine; the harness is what makes it driveable.* harness0 is the first open-source library built entirely around this discipline.

## The Problem

Every agent developer hits the same walls:

| Problem | Root Cause | harness0 Layer |
|---|---|---|
| "Demo works, production fails" | No structured context management | **L1** Context Assembly |
| "More tools = less stable" | Tools are an ungoverned bag of functions | **L2** Tool Governance |
| "Afraid to let agents run commands" | Security relies on prompt-level trust | **L3** Security Guard |
| "Agent fails but doesn't know why" | System errors aren't translated for the model | **L4** Feedback Loop |
| "Agent drifts on long tasks" | Context decays — stale rules, bloated history | **L5** Entropy Management |

Existing frameworks solve orchestration. harness0 solves **reliability**.

---

## Quick Start

```bash
pip install harness0
```

```python
import asyncio
from openai import AsyncOpenAI
from harness0 import HarnessEngine, RiskLevel

engine = HarnessEngine.default()

@engine.tool(risk_level=RiskLevel.READ)
async def read_file(path: str) -> str:
    """Read a file and return its contents."""
    return open(path).read()

@engine.tool(risk_level=RiskLevel.EXECUTE, requires_approval=True, timeout=30)
async def run_command(command: str) -> str:
    """Execute a shell command."""
    import subprocess
    return subprocess.check_output(command, shell=True, text=True)

async def main():
    result = await engine.run("Summarise README.md", llm_client=AsyncOpenAI())
    print(result.output)

asyncio.run(main())
```

> **v0.0.4** — L1–L5 and `HarnessEngine` are implemented and functional. Framework integrations are planned. See [TODO.md](https://github.com/seekcontext/harness0/blob/main/TODO.md).

<details>
<summary><b>With <code>harness.yaml</code> — declarative configuration</b></summary>

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
      source: docs/security.md
      priority: 10
      disclosure_level: detail
      keywords: ["security", "permission", "auth"]
  total_token_budget: 8000

security:
  blocked_commands: ["rm -rf", "sudo", "> /dev/sda"]
  approval_mode: risky_only

entropy:
  gardener_enabled: true
  gardener_interval_turns: 5
  golden_rules:
    - id: no_duplicate_tools
      description: "No two tools may share the same description"
      severity: error
    - id: no_stale_layers
      description: "All FileSource layers must be fresher than 24h"
      severity: warning
```

```python
engine = HarnessEngine.from_config("harness.yaml")
```

</details>

---

## The 5-Layer Harness Model

### L1: Context Assembly

**Prompts are assembly systems, not documents.**

Give the agent a map, not a 1,000-page manual. `INDEX` layers are always injected (base prompt, rules summary). `DETAIL` layers are keyword-gated — loaded only when the task mentions relevant terms. Per-layer and total token budgets prevent context overflow.

```python
assembler = ContextAssembler(layers=[
    ContextLayer(name="base", source=FileSource("base.md"),
                 disclosure_level=DisclosureLevel.INDEX),          # always loaded
    ContextLayer(name="security", source=FileSource("security.md"),
                 disclosure_level=DisclosureLevel.DETAIL,          # loaded only for security tasks
                 keywords=["security", "auth"]),
    ContextLayer(name="state", source=CallableSource(get_state),
                 freshness=Freshness.PER_TURN),                    # dynamic per turn
], total_token_budget=8000)
```

### L2: Tool Governance

**Tools are governed capabilities, not a bag of functions.**

Four risk levels (`READ` → `WRITE` → `EXECUTE` → `CRITICAL`), schema validation, output truncation, and full audit trail. Every tool call passes through a unified pipeline; every failure emits a structured signal the agent can act on.

```python
@engine.tool(risk_level=RiskLevel.EXECUTE, requires_approval=True, timeout=30)
async def run_command(command: str) -> str: ...
```

```
ToolCall → Validate → CommandGuard → Approval → Execute → Truncate → Audit → ToolResult
```

### L3: Security Guard

**Security at runtime, not in prompts.**

Three lines of defense: **CommandGuard** (pattern blocklist with fix instructions), **ProcessSandbox** (configurable resource limits), **ApprovalManager** (human-in-the-loop with SHA-256 fingerprint cache — approve once per session, not once per call).

```python
result = engine.command_guard.check("sudo rm -rf /tmp")
result.allowed          # False
result.matched_pattern  # "sudo"
result.signal.fix_instructions
# "1. Do NOT retry — matches the security blocklist.
#  2. Reason: `sudo` causes irreversible side effects.
#  3. Safer alternatives: run without sudo, or use targeted delete."
```

Even if the model "misbehaves," the system has hard boundaries.

### L4: Feedback Loop

**System events must be translated into model-consumable signals.**

The agent should never see a bare `PermissionError`. It should see *what* happened, *why*, and *what to do next*:

| System Event | Without L4 | With L4 |
|---|---|---|
| Command blocked | `PermissionError` | "Command blocked: `sudo`. Step 1: don't retry. Step 2: run without sudo." |
| Output truncated | Silent cutoff | "Output truncated 12K→5K tokens. Narrow your search scope." |
| Subprocess timeout | `TimeoutError` | "Exceeded 30s timeout. Break into smaller steps or increase timeout." |
| Schema invalid | `ValidationError` | "Missing required parameter `content`. Check the tool schema and retry." |

Every signal carries a `fix_instructions` field — numbered steps the agent can execute immediately. Signals are rendered as XML and auto-injected into the next turn's context via L1:

```xml
<harness:signal id="a3f8c1d2" type="constraint" source="security.command_guard">
  <message>Command `sudo apt install` blocked.</message>
  <fix_instructions>1. Do NOT retry.
2. Install without sudo.
3. Or request user approval.</fix_instructions>
</harness:signal>
```

### L5: Entropy Management

**Active quality maintenance, not passive compression.**

Agent context **decays** over time. Other frameworks react only when tokens overflow. harness0 proactively detects and repairs degradation every turn:

| | Passive (other frameworks) | Active (harness0) |
|---|---|---|
| Trigger | Token count near limit | Every turn, proactively |
| Method | LLM summarizes old messages | Detect + classify + targeted fix |
| Stale signal removal | No | **Yes** |
| Duplicate detection | No | **Yes** |
| Conflict detection | No | **Yes** |
| Background GC | No | **Yes** — `EntropyGardener` |

**Golden rules** are mechanically verifiable invariants declared in YAML. Violations emit `FeedbackSignal`s — the agent can self-repair:

```yaml
entropy:
  golden_rules:
    - id: no_duplicate_tools
      description: "No two tools may share the same description"
      severity: error
    - id: no_stale_layers
      description: "All FileSource layers must be fresher than 24h"
      severity: warning
```

### Cross-Layer Coordination

The 5 layers are not independent pipelines — they form a coordinated feedback loop:

```
L3 SecurityGuard blocks "rm -rf /"
  → L4 FeedbackTranslator generates signal with fix_instructions
    → L1 ContextAssembler injects signal into next turn's context
      → LLM receives actionable feedback, adjusts behavior
        → L5 EntropyManager garbage-collects stale signals later
```

→ **[Full API reference → User Manual](https://github.com/seekcontext/harness0/blob/main/docs/USER_MANUAL.md)**

---

## Use Individual Layers

Every layer is independently importable. No full buy-in required.

```python
from harness0.context import ContextAssembler       # L1 — multi-layer prompt assembly
from harness0.tools import ToolInterceptor           # L2 — governed tool execution
from harness0.security import CommandGuard            # L3 — security enforcement
from harness0.feedback import FeedbackTranslator      # L4 — better error messages for models
from harness0.entropy import EntropyManager           # L5 — context quality maintenance
```

Use just L3 for security, just L1 for prompt assembly, or all 5 together. Each layer has zero dependencies on the others.

→ **[Individual layer usage examples → User Manual §11](https://github.com/seekcontext/harness0/blob/main/docs/USER_MANUAL.md#11-using-individual-layers)**

---

## How It Compares

> Based on publicly available documentation as of March 2026. See [competitive-analysis.md](https://github.com/seekcontext/harness0/blob/main/docs/competitive-analysis.md) for methodology.

| Capability | LangChain | OpenAI SDK | MS AGT | **harness0** |
|---|---|---|---|---|
| Multi-layer context assembly | — | Basic (2-tier) | — | ✅ L1 |
| Progressive disclosure | — | — | — | ✅ INDEX/DETAIL |
| Tool risk classification | — | allow/reject | Policy engine | ✅ 4-level |
| Sandbox execution | Remote | — | 4 privilege rings | ✅ Lightweight |
| Approval workflows | HITL | approve/reject | Yes | ✅ + fingerprint cache |
| Feedback translation | — | — | — | ✅ L4 |
| Entropy detection + GC | — | — | — | ✅ L5 |
| Golden rule enforcement | — | — | — | ✅ `EntropyGardener` |
| Declarative config | — | — | OPA/Rego | ✅ `harness.yaml` |
| Framework agnostic | No | No | Yes | ✅ |

**Three capabilities no major framework addresses**: multi-layer context assembly, feedback translation, and entropy management.

---

## Framework Integrations [Planned]

harness0 works **with** your existing framework. Adapters are on the roadmap:

| Framework | Install | Strategy |
|---|---|---|
| LangChain | `pip install harness0[langchain]` | Middleware hooks |
| OpenAI Agents SDK | `pip install harness0[openai]` | Input/output/tool guardrails |
| PydanticAI | `pip install harness0[pydantic-ai]` | Dependency injection |
| CrewAI | `pip install harness0[crewai]` | `@harness_tool` decorator |

→ **[Integration architecture → Architecture docs](https://github.com/seekcontext/harness0/blob/main/docs/architecture.md#integration-architecture)**

---

## Why "harness0"?

The **0** means **Layer 0** — the foundational reliability substrate beneath every agent framework, like Layer 0 in networking is the physical medium all higher layers depend on. Ground zero of agent reliability.

Three lessons from [OpenAI's harness engineering](https://openai.com/index/harness-engineering/) that directly shaped the design:

1. **"Give the agent a map, not a manual"** → L1 Progressive Disclosure (INDEX/DETAIL)
2. **"Error messages must contain fix instructions"** → L4 `fix_instructions` on every signal
3. **"Entropy is inevitable — automate the gardening"** → L5 `EntropyGardener` with golden rules

---

## Requirements

- Python 3.11+
- Dependencies: `pydantic>=2.0` · `pyyaml>=6.0` · `tiktoken>=0.7` · `httpx>=0.27` · `aiofiles>=24.0`
- Any `openai.AsyncOpenAI`-compatible LLM client

## Contributing

Contributions welcome. See [TODO.md](https://github.com/seekcontext/harness0/blob/main/TODO.md) for the full roadmap.

**Priority areas**: test suite · LLM provider layer · built-in tool plugins · framework adapters · entropy detection strategies

## License

MIT

---

<p align="center">
  <a href="https://github.com/seekcontext/harness0/blob/main/docs/USER_MANUAL.md">User Manual</a> &middot;
  <a href="https://github.com/seekcontext/harness0/blob/main/docs/architecture.md">Architecture</a> &middot;
  <a href="https://github.com/seekcontext/harness0/blob/main/docs/competitive-analysis.md">Competitive Analysis</a> &middot;
  <a href="https://github.com/seekcontext/harness0/blob/main/docs/project-vision.md">Vision</a> &middot;
  <a href="https://github.com/seekcontext/harness0/blob/main/TODO.md">Roadmap</a>
</p>
