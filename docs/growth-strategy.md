# Harness0 — Growth Strategy

## Context

"Harness Engineering" is a rising concept in the agent community (2026 Q1). LangChain blog, dev.to, and dedicated sites are actively discussing it. The industry sentiment: **"The model is commodity. The harness is moat."** The concept education cost is low, but the window is finite — estimated 3-6 months before a major player claims the narrative.

## Growth Flywheel

```
Publish concept articles
  → Developers realize they lack a Harness
    → Try harness0 (pip install)
      → Evaluate with HarnessScore
        → Share scores and improvements (Twitter/Discord)
          → More developers discover harness0
            → Loop back ↑

Contribute integration adapters / entropy strategies
  → Framework compatibility increases
    → Attracts users from more frameworks
      → Loop back ↑
```

## Phase 1: Build Audience Before Code (Pre-Launch)

Most open-source projects skip this phase. The best ones already have an audience when they launch.

### 1.1 Publish the "5-Layer Model" Article Series

Establish authority as the concept definer, not the product promoter.

| Article | Channel | Purpose |
|---|---|---|
| "The Complete Harness Engineering Guide: The 5-Layer Model That Takes Agents From Demo to Production" | Personal blog / dev.to | Define the framework, establish authority |
| "Why Your Agent Gets Worse Over Time: The Ignored Problem of Entropy Management" | dev.to / Medium | Cut into a unique topic nobody covers |
| "LangChain Middleware vs Harness Systems: A Deep Comparison" | dev.to / Hacker News | Ride the LangChain Deep Agents launch buzz |
| "I Beat a New Model With an Old Model + Good Harness" | Twitter/X thread | High viral potential (counter-intuitive take) |

**Key tactic:** End articles with "I'm building this 5-layer model as an open-source project. Star/watch the repo if interested." Let readers convert naturally.

### 1.2 Bilingual Content Advantage

The harness engineering concept has Chinese community roots. This is an underestimated advantage.

- **Chinese channels**: WeChat Official Account, Juejin (掘金), Zhihu, Jike (即刻), Bilibili
- **Chinese agent developer community** is growing rapidly (DeepSeek, Qwen ecosystems)
- Most international agent frameworks have poor Chinese content

**Strategy**: README and docs in English (global reach). Deep technical writeups in Chinese communities. harness0 naturally grows a bilingual community.

### 1.3 Pre-Launch Checklist

- [ ] GitHub repo with README (vision + architecture diagram + "coming soon")
- [ ] At least 2 published articles establishing the 5-layer model
- [ ] Social media presence (Twitter/X account or personal brand)
- [ ] Email list or Discord for early interested developers

## Phase 2: Launch (First Week)

### 2.1 Multi-Channel Simultaneous Launch

Agent developers gather on these channels:

| Channel | Content Format | Priority |
|---|---|---|
| **Hacker News** (Show HN) | Concise intro + core differentiation | Highest — primary launch pad for tech projects |
| **Reddit** (r/MachineLearning, r/LocalLLaMA, r/artificial) | Technical deep-dive post | High |
| **Twitter/X** | Thread: 5-layer model visualization + demo GIF | High — most active real-time AI discussion |
| **dev.to** | Full technical article | Medium |
| **Discord** (Build Crew, LangChain, AI communities) | Share in relevant communities | Medium |
| **Juejin / Zhihu** (Chinese) | Chinese deep-dive technical article | High (Chinese market) |
| **Jike** (Chinese) | Short updates + discussion | Medium (Chinese market) |

### 2.2 Launch Day Must-Haves

Based on "0 to 1000 stars" growth research:

- **30-second runnable demo**: `pip install harness0 && python -m harness0.examples.simple`
- **One GIF/video**: Show the full loop — agent encounters dangerous command → blocked → receives feedback → auto-corrects behavior
- **One architecture diagram**: 5-layer model Mermaid diagram, instantly communicates positioning
- **Comparison table**: Feature matrix vs LangChain, OpenAI SDK, Microsoft AGT
- **"10 lines of code" example**: Proves minimal adoption cost

### 2.3 Launch Narrative

Do NOT say: "We built a new agent framework."

DO say:

> **"harness0 is not another agent framework. It's the reliability layer that makes any agent framework stable. 10 lines of code. 5 layers of protection."**

Why this narrative works:
- No competition with existing frameworks (friendly, doesn't trigger defensive reactions)
- Implies "your current framework has gaps" (creates demand)
- "10 lines of code" is concrete and actionable (lowers psychological barrier)

### Naming Narrative: The "0" Story

The name **harness0** itself is a marketing asset. The "0" tells a story:

- **Layer 0** — "We're the layer beneath your framework. LangChain is Layer 1, you are Layer 2, we are Layer 0." This positions the project as infrastructure, not competition.
- **Ground zero** — "Agent reliability starts here." Use as a tagline in social media, talks, and docs.
- **Zero-based** — "Don't patch the symptoms. Start from zero and build reliability into the foundation."

Use this narrative consistently across articles, talks, and social channels. The "0" is memorable and triggers curiosity ("why zero?"), which drives organic discovery.

## Phase 3: Root (Months 1-3)

### 3.1 Integration-Driven Growth (Highest Leverage Strategy)

The logic:

> Every LangChain user is a potential harness0 user.
> Every OpenAI SDK user is too.
> Every PydanticAI user is too.

**Execution steps:**

1. Release `harness0[langchain]` adapter. Publish article: "Add 5-Layer Harness Protection to Your LangChain Deep Agent in 3 Lines of Code." Share in LangChain community.

2. Release `harness0[openai]` adapter. Publish article: "OpenAI Agents SDK Guardrails Not Enough? harness0 Adds the Other Three Layers." Share in OpenAI community.

3. Submit **integration documentation PRs** to major frameworks. E.g., PR to LangChain docs to add harness0 in "Third-party Middleware" page. Free, long-term exposure.

**Why this works:** You don't need to convince users to switch frameworks. Just convince them to install one more package. `pip install harness0[langchain]` has near-zero decision cost.

### 3.2 HarnessScore — Create a Spreadable Metric

Create a quantitative indicator that developers want to share:

```python
from harness0 import HarnessScore

score = HarnessScore.evaluate(your_agent)
# Output:
# Harness Score: 62/100
#   L1 Context Assembly:  ███████░░░  70%
#   L2 Tool Governance:   ████░░░░░░  40%
#   L3 Security Guard:    ██████████  100%
#   L4 Feedback Loop:     ██░░░░░░░░  20%
#   L5 Entropy Management:░░░░░░░░░░  0%
```

**Why this spreads:**
- Developers love scores and badges (like Lighthouse Score, Code Coverage)
- People share scores on Twitter ("My Agent Harness Score improved to 85!")
- Low scores create anxiety → drives adoption
- Can be a GitHub Badge: `![Harness Score](https://img.shields.io/badge/harness--score-85-green)`

### 3.3 Community Building

- **Discord server** with channels per layer (#context-assembly, #tool-governance, #security, #feedback, #entropy)
- **GitHub Discussions** for technical discussions and RFCs
- **Regular "Harness Review" sessions**: Community members submit their agent configs, group reviews the harness design (like code review but for harness)
- **"good first issues"** that are genuinely achievable — early contributors are critical for signaling project activity

## Phase 4: Accelerate (Months 3-6)

### 4.1 Benchmark Proof — Let Data Speak

LangChain already proved: modifying only the harness (not the model) improved coding agent from rank 30 to rank 5 on Terminal Bench 2.0 (52.8% → 66.5%).

We should produce similar benchmarks:

> **Same model (GPT-4o), same task (SWE-Bench), three configs:**
> 1. Raw API calls: X%
> 2. LangChain Deep Agent: Y%
> 3. LangChain + harness0: Z%

If Z > Y, this is the **most compelling growth material**. Data proving "adding one Harness layer improves performance."

### 4.2 Collect Real User Stories

> "I added harness0's entropy management to my coding agent. Long-task success rate went from 40% to 72%."

One real user story is worth a hundred technical articles. Proactively reach out to early users. Help them write case studies.

### 4.3 Awesome Harness Engineering

Create `awesome-harness-engineering` repository. Collect all harness engineering resources: articles, tools, case studies, videos. **Make harness0 the entry point for the entire field.**

### 4.4 Conference Talks

Submit talks to relevant conferences and meetups:
- PyCon (Python community)
- AI Engineer Summit
- Local AI/LLM meetups
- Online tech talks (Bilibili, YouTube)

Topic: "Harness Engineering: Why Agent Reliability Is a Software Engineering Problem"

## Key Metrics to Track

| Phase | Metric | Target |
|---|---|---|
| Pre-launch | Article views / engagement | 10K+ total views across articles |
| Launch week | GitHub stars | 500+ first week |
| Month 1 | PyPI downloads | 1,000+ monthly |
| Month 3 | GitHub stars | 3,000+ |
| Month 3 | Integration adapters | 2+ frameworks supported |
| Month 6 | GitHub stars | 10,000+ |
| Month 6 | Community size | 500+ Discord members |
| Month 6 | User case studies | 3+ published stories |

## Risk Mitigation

| Risk | Mitigation |
|---|---|
| Launch falls flat | Ensure pre-launch articles have built initial audience; have a backup plan for iterating on positioning |
| Competition releases similar features | Accelerate integration adapters; double down on framework-agnostic positioning |
| Community doesn't form | Lower barrier to contribution; actively engage on Twitter/Reddit; run harness review sessions |
| Chinese and English communities diverge | Maintain bilingual core team; cross-post key content |

## Summary

The growth strategy has one core principle: **be the standard-bearer for Harness Engineering as a discipline, not just the seller of a tool.** The tool is the vehicle, but the concept is the brand. If the industry thinks "harness0" when they think "harness engineering" — like they think "Docker" for "containers" — the project succeeds regardless of individual feature competition.
