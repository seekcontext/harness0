# Harness0 — Project Vision

> **Agent reliability through harness engineering.**

## Core Formula

```
Agent = Loop(Model + Harness)
```

You provide the Model. harness0 provides the Harness.

## What Is harness0?

harness0 is **not** another agent framework. It is a **Harness reliability layer** that makes any agent framework more reliable.

It implements the complete 5-layer Harness model — Context Assembly, Tool Governance, Security Guard, Feedback Loop, and Entropy Management — as framework-agnostic, composable Python components.

## Why the "0"?

The **0** in harness0 carries three meanings:

1. **Layer 0** — In network architecture, Layer 0 is the physical foundation that all higher layers depend on. harness0 is the reliability foundation beneath orchestration frameworks (LangChain, CrewAI, etc.), LLM APIs, and your application logic.
2. **Ground Zero** — The starting point of agent reliability. Before optimizing prompts or adding tools, get your harness right. harness0 is where reliability begins.
3. **Zero-based** — Start from fundamentals. Don't patch symptoms; address the root cause of agent instability through structured engineering.

> harness0: ground zero of agent reliability.

## Positioning

```
┌─────────────────────────────────────────┐
│           Your Application              │
├─────────────────────────────────────────┤
│  Orchestration Layer (pick one)         │
│  LangChain / CrewAI / PydanticAI / DIY  │
├─────────────────────────────────────────┤
│  ★ Harness Layer (harness0)           │  ← Layer 0: we are here
│  Context Assembly │ Tool Governance     │
│  Feedback Loop    │ Entropy Management  │
│  Security Guard                         │
├─────────────────────────────────────────┤
│  LLM API                               │
│  OpenAI / Anthropic / DeepSeek / Local  │
└─────────────────────────────────────────┘
```

harness0 sits **between** your orchestration framework and your LLM. It is complementary, not competitive.

## Why This Positioning?

| Dimension | "Alternative framework" | "Reliability layer" (ours) |
|---|---|---|
| Competitive relationship | Head-to-head with LangChain/CrewAI | **Complementary** to all frameworks |
| Potential user base | "People choosing harness0" | "Everyone building agents" |
| Adoption barrier | Must switch frameworks | Keep your framework, add one layer |
| Value narrative | "We do X better than Y" | "No matter what you use, we make it stable" |

## The 5-Layer Harness Model

| Layer | Module | Core Responsibility |
|---|---|---|
| L1 | Context Assembly | Dynamic layered prompt assembly with multi-source injection, priority, freshness, and token budgets |
| L2 | Tool Governance | Tool registry, discovery, risk classification, interception pipeline, output truncation, audit |
| L3 | Security Guard | Subprocess sandbox, command blocklist, approval workflows, runtime-enforced boundaries |
| L4 | Feedback Loop | Translate system events (rejections, truncations, timeouts) into model-consumable structured signals |
| L5 | Entropy Management | Active context degradation detection — rule conflicts, temporal staleness, information density decay |

## Value Proposition

### Pain Point 1: "My agent demo is great but real tasks fail"

Prompts are a flat text blob. Context has no layered management. Information priority is left entirely to model guessing.

→ **L1 Context Assembly** turns prompts from "one big file" into a "layered assembly system." Each source has explicit priority, freshness policy, and token budget.

### Pain Point 2: "More tools I add, less stable my agent gets"

10 tools registered, the agent starts calling wrong ones, passing invalid params, using A when it should use B. No one knows why — tool calling is a black box.

→ **L2 Tool Governance** gives every tool a risk level, parameter validation, output truncation, and audit trail. Not "a bag of functions for the model" but "a governed capability system."

### Pain Point 3: "I'm afraid to let my agent run commands autonomously"

The agent can write files and run shells, but developers have no confidence. So they write "please don't execute dangerous commands" in the prompt and pray.

→ **L3 Security Guard** enforces boundaries at **runtime**, not in the prompt. Command blocklists, subprocess sandboxing, approval workflows — even if the model "misbehaves," the system has guardrails.

### Pain Point 4: "My agent fails but doesn't know why"

A tool returns a Python traceback. The model doesn't understand it, repeats the same error, or gives up. The developer sees it's a permission issue in the logs, but the model never learns.

→ **L4 Feedback Loop** translates "subprocess timed out," "command blocked by security," "output truncated due to length" into structured feedback: "This command was rejected because it contains sudo. Try a non-privileged approach instead."

### Pain Point 5: "My agent drifts on long tasks"

Fine at turn 1, incoherent at turn 30. The prompt is bloated, old tool outputs pollute context, earlier rules now contradict current state.

→ **L5 Entropy Management** actively detects context degradation — conflicting rules, expired information, repeated content — and surgically cleans it. Not passive compression, but active quality maintenance.

## Target Audience

### Tier 1: Core Users — "Developers Who've Hit the Wall"

- Built at least one agent project with OpenAI/Anthropic API
- Experienced "demo works, production doesn't" pain
- Individual developers or 3-5 person teams
- Don't need enterprise compliance (that's Microsoft AGT's job)
- Need **development efficiency and reliability**

**Usage**: `pip install harness0`, full 5-layer setup, reliable agent in 10 minutes.

### Tier 2: Composable Users — "Already Have an Agent, Want to Fix Gaps"

- Already using LangChain/CrewAI/custom frameworks
- Some parts work well, but specific areas (context management, security) need better solutions
- Don't want to switch frameworks, just want to plug in specific capabilities

**Usage**: Import individual layers, e.g. `from harness0.context import ContextAssembler`, embed in their own system.

### Tier 3: Learners — "Want to Understand Harness Engineering"

- Interested in agent development, exploring
- Read about Harness engineering, want to see a real implementation

**Usage**: Read README, run examples, study source code.

## Design Principles

1. **Composition over inheritance** — Every layer is an independent module, usable alone or together.
2. **Declarative over imperative** — Tool definitions, security rules, context layers all use declarative configuration.
3. **Zero magic** — No implicit behavior. All interception, injection, and truncation is explicit and observable.
4. **Model agnostic** — LLM Provider is a plugin. Core depends on no specific model.
5. **Progressive adoption** — Use just L1+L2 for lightweight agents, or all 5 layers for production systems.

## One-Line Summary

> **harness0 — Layer 0 of agent reliability. The only framework-agnostic reliability layer covering the complete 5-layer Harness model.**
