# harness0 — Development TODO

> Tracks all planned work items after the initial L1–L5 core implementation (v0.0.3).
> Items are grouped by priority tier. Each item is self-contained and can be implemented independently.

---

## Tier 1 — Blockers (needed to run the engine end-to-end)

### T1-1: LLM Provider Layer (`llm/`)

**Why**: `HarnessEngine.run()` accepts any `llm_client`, but there's no built-in provider. Users must pass their own OpenAI client. The `llm/` module should handle key loading, retries, and provide a standard interface.

**Files to create**:
- `src/harness0/llm/base.py` — `LLMProvider` abstract base class
- `src/harness0/llm/openai.py` — OpenAI adapter (wraps `openai.AsyncOpenAI`)
- `src/harness0/llm/anthropic.py` — Anthropic adapter

**API design**:
```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        ...

class LLMResponse(BaseModel):
    content: str
    finish_reason: Literal["stop", "tool_calls", "length", "error"]
    tool_calls: list[ToolCallRequest] = []
    usage: TokenUsage | None = None

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
```

**Integration**: `HarnessConfig.llm` already defines `provider`, `model`, `api_key`, `base_url`. The engine should auto-build the provider from config when `llm_client` is not explicitly passed.

**Scope**: OpenAI adapter + base class. Anthropic optional.

---

### T1-2: Built-in Tool Plugins (`plugins/`)

**Why**: Every user currently hand-writes the same 4 tools (read_file, write_file, list_dir, run_command). These should ship with the library.

**Files to create**:
- `src/harness0/plugins/base.py` — `ToolPlugin` ABC
- `src/harness0/plugins/builtin/file_tools.py` — read_file, write_file, list_directory
- `src/harness0/plugins/builtin/shell_tools.py` — run_command (uses ProcessSandbox)
- `src/harness0/plugins/builtin/search_tools.py` — grep_search, glob_search

**API design**:
```python
class ToolPlugin(ABC):
    name: str

    @abstractmethod
    def get_tools(self) -> list[ToolDefinition]:
        ...

# Registration on the engine
engine.register_plugin(file_tools)
engine.register_plugin(shell_tools)
engine.register_all_builtins()  # convenience: all built-in plugins

# Or standalone
from harness0.plugins.builtin import file_tools, shell_tools, search_tools
```

**Scope**: `ToolPlugin` ABC + 3 builtin plugin files.

---

## Tier 2 — Core Quality (needed before open-source release)

### T2-1: Test Suite (`tests/`)

**Why**: Zero tests currently. All core layers are implemented and stable enough for tests.

**Files to create** (one per layer, plus integration):
- `tests/test_context.py` — ContextAssembler, DisclosureLevel, Freshness, sources
- `tests/test_tools.py` — ToolInterceptor pipeline, RiskLevel, schema validation
- `tests/test_security.py` — CommandGuard, ProcessSandbox, ApprovalManager
- `tests/test_feedback.py` — FeedbackSignal, FeedbackTranslator factory methods, rendering
- `tests/test_entropy.py` — EntropyManager (compression, dedup, conflicts), EntropyGardener, GoldenRule checkers
- `tests/test_engine.py` — HarnessEngine (decorator, execute_tool, run with stub LLM)
- `tests/test_config.py` — HarnessConfig.from_yaml, field defaults, validation

**Test setup** (`tests/conftest.py`):
```python
import pytest
from harness0 import HarnessEngine, HarnessConfig

@pytest.fixture
def engine():
    return HarnessEngine.default()

@pytest.fixture
def config():
    return HarnessConfig.default()
```

**Key behaviors to cover**:
- Progressive disclosure: INDEX always selected, DETAIL keyword matching
- Freshness cache: static/per_session/per_turn reload behavior
- Truncation: per-layer and total token budget enforcement
- Tool interceptor: missing tool, schema validation, truncation, timeout
- CommandGuard: blocklist match, safe command pass-through, fix_instructions content
- ApprovalManager: fingerprint cache hit/miss, auto-approve/deny backends
- EntropyManager: dedup, compression, stale signal removal
- EntropyGardener: staleness detection, duplicate tool detection, golden rule enforcement
- FeedbackSignal: XML/Markdown/JSON rendering, fix_instructions in XML

---

### T2-2: Working Example (`examples/simple_agent.py`)

**Why**: Docs reference this file, it doesn't exist. Should be a minimal but runnable example.

**File to create**: `examples/simple_agent.py`

**What it should demonstrate**:
1. `HarnessEngine.from_config("harness.yaml")` — config-driven setup
2. `@engine.tool` for read_file, write_file, run_command
3. `engine.run(task, llm_client=AsyncOpenAI())`
4. Printing `result.output`, `result.turn_count`, `result.signals`

Also create `examples/harness.yaml` with a minimal config and `examples/prompts/base.md` with a basic system prompt.

---

### T2-3: Checkpoint Persistence

**Why**: `checkpoint_enabled: true` is in config but does nothing. Long-running agents benefit from crash recovery.

**What to implement**:
- Serialize `AgentState` to JSON after each turn: `{session_id}.json`
- Load from checkpoint: `engine.run(task, resume_from="path/to/checkpoint.json")`
- `AgentState` is already a Pydantic model → `model_dump_json()` / `model_validate_json()`

**Files to modify**:
- `src/harness0/engine.py` — add `resume_from` param to `run()`, add `_save_checkpoint()` call each turn
- `src/harness0/core/types.py` — verify `AgentState` is fully JSON-serializable

---

### T2-4: Update Project Context Rule

**File**: `.cursor/rules/harness0-project-context.mdc`

**What to update**:
- `Status`: change from "Pre-Alpha (placeholder)" to "v0.0.3 — core implemented"
- `Current State & Next Steps`: replace with references to TODO.md items
- `Project Structure`: update to match actual file layout (remove `loop.py`, `state.py`, `compressor.py`, `decay.py`, `hints.py`; add `gardener.py`)

---

## Tier 3 — Framework Integrations (`integrations/`)

Each adapter is independent. Implement in order of community size.

### T3-1: OpenAI Agents SDK Integration

**File**: `src/harness0/integrations/openai_sdk.py`

**How it maps**:
| harness0 | OpenAI SDK |
|---|---|
| L1 ContextAssembler | Input guardrail pre-processing |
| L2 ToolInterceptor | Tool wrapper / guardrail |
| L3 SecurityGuard | Tool wrapper |
| L4 FeedbackTranslator | Output processing |
| L5 EntropyManager | Input guardrail pre-processing |

**Install extra**: `pip install harness0[openai]` → add `openai-agents` to optional deps.

---

### T3-2: LangChain Integration

**File**: `src/harness0/integrations/langchain.py`

**How it maps**:
| harness0 | LangChain |
|---|---|
| L1 ContextAssembler | `before_model` middleware |
| L2+L3 ToolInterceptor + SecurityGuard | `wrap_tool_call` |
| L4 FeedbackTranslator | `after_model` + `wrap_tool_call` |
| L5 EntropyManager | `before_model` |

**Install extra**: `pip install harness0[langchain]`

---

### T3-3: PydanticAI Integration

**File**: `src/harness0/integrations/pydantic_ai.py`

**Pattern**: Inject as `deps_type`. Tools wrapped via `RunContext[HarnessDeps]`.

**Install extra**: `pip install harness0[pydantic-ai]`

---

### T3-4: CrewAI Integration

**File**: `src/harness0/integrations/crewai.py`

**Pattern**: `@harness_tool` decorator wraps CrewAI tools.

**Install extra**: `pip install harness0[crewai]`

---

## Tier 4 — Enhancements

### T4-1: LLM-based Summarization for L5

**Why**: Current L5 compression drops old messages. LLM summarization would preserve more information.

**What to add**: `EntropyManager._llm_summarize(messages)` — requires `LLMProvider` (T1-1).

**Config field** (already in architecture doc): `entropy.compression_strategy: "targeted" | "summarize" | "sliding_window"`.

---

### T4-2: CallableSource in harness.yaml

**Why**: Currently `CallableSource` must be created in Python code. Config YAML can't reference callables.

**Spec**: Support `"callable:module.function_name"` in `source` field — `make_source()` imports and wraps it.

---

### T4-3: Token Usage Tracking

**Why**: `RunResult` has no token usage summary. Useful for cost monitoring.

**What to add**:
- `TokenUsage` model in `core/types.py`
- Accumulate usage in `engine.run()` from LLM responses
- Expose as `result.token_usage: TokenUsage | None`

---

### T4-4: `HarnessScore` Concept

**Why**: Described in `docs/growth-strategy.md` as a key differentiator. A per-session reliability score based on signal types, entropy actions, and tool success rates.

**What to add**:
- `HarnessScore` model: overall score + per-dimension breakdown (context_quality, tool_reliability, security_events, entropy_health)
- Computed from `RunResult.signals` and `interceptor.audit_log()`
- Expose as `result.harness_score: HarnessScore`

---

### T4-5: Async-safe ContextLayer caching

**Why**: `ContextLayer._content_cache` uses private attributes which Pydantic v2 doesn't track, and there's no async lock protecting concurrent access.

**What to fix**: Replace `_content_cache` with an `asyncio.Lock` + proper `__init__`-style setup, or convert `ContextLayer` to a non-Pydantic class.

---

## Deferred / Out of Scope

- `core/loop.py` — AgentLoop was merged into `engine.py`. Keep merged unless there's a use case for standalone loop.
- `core/state.py` — `AgentState` is in `core/types.py`. No reason to split unless state management becomes complex.
- `entropy/compressor.py` / `entropy/decay.py` — functionality is in `manager.py`. Extract only if the file grows > 300 lines.
- `feedback/hints.py` — SystemHint builder was merged into `translator.py`. No need to split.
