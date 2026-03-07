# PolyForge — Claude Code Context

## NUMBER ONE RULE
You are not the creator of this project. You will not take over and write the entire project. You are an assistant that will help me build this project. I do not want you to write whole files. I want you to assist me when I am writing code. If i want code written i will ask. 

## What This Project Is

PolyForge is a CLI tool that lets developers ask questions about their code across
multiple LLMs simultaneously. It fans out queries to Claude, GPT-4o, and Gemini in
parallel, applies each model's suggested changes to an isolated copy of the repo,
runs the modified code in a Docker container per model, and returns a ranked
comparison of results alongside a synthesis recommendation.

**Stack:** Python 3.11+, asyncio, Docker SDK, Typer CLI, tiktoken  
**Status:** MVP v1.0 in active development  
**Docs:** See requirements doc and architecture doc in /docs for full design detail

---

## Project Structure

```
polyforge/
├── CLAUDE.md                        # this file
├── pyproject.toml                   # package config and dependencies
├── README.md
├── docs/
│   ├── PolyForge_Requirements_v1.docx
│   └── PolyForge_Architecture_v1.docx
├── polyforge/
│   ├── __init__.py
│   ├── cli.py                       # Typer CLI entry point
│   ├── orchestrator.py              # pipeline coordinator
│   ├── models.py                    # ALL dataclasses live here
│   ├── config.py                    # config loading (~/.polyforge/config.toml)
│   │
│   ├── providers/                   # LLM Provider Layer
│   │   ├── __init__.py
│   │   ├── base.py                  # LLMProvider ABC — all providers implement this
│   │   ├── claude.py                # ClaudeProvider
│   │   ├── openai.py                # OpenAIProvider
│   │   └── gemini.py                # GeminiProvider
│   │
│   ├── llm_components/              # LLM-powered pipeline stages
│   │   ├── __init__.py
│   │   ├── file_selection.py        # FileSelectionAssistant
│   │   └── synthesis.py             # SynthesisLayer
│   │
│   ├── repo/                        # Repo Manager
│   │   ├── __init__.py
│   │   ├── manager.py               # RepoManager — snapshots, patches, cleanup
│   │   ├── scanner.py               # file tree scanning and signature extraction
│   │   └── detector.py              # project type detection
│   │
│   ├── docker/                      # Docker Executor
│   │   ├── __init__.py
│   │   ├── executor.py              # DockerExecutor
│   │   └── parsers.py               # per-project test output parsers
│   │
│   ├── tokens/                      # Token Counter
│   │   ├── __init__.py
│   │   └── counter.py               # TokenCounter
│   │
│   └── renderer/                    # Results Renderer
│       ├── __init__.py
│       └── renderer.py              # terminal output formatting
│
└── tests/
    ├── test_providers.py
    ├── test_repo_manager.py
    ├── test_docker_executor.py
    ├── test_llm_components.py
    └── test_orchestrator.py
```

---

## Core Data Flow

Every component communicates through typed dataclasses defined in `models.py`.
No shared mutable state. Data flows forward only — never backwards.

```
Developer CLI input (interactive prompt — NOT flags for question)
    → QueryRequest
    → FileSelectionResult      (FileSelectionAssistant — hard gate, dev must confirm)
    → TokenEstimate            (TokenCounter — dev confirms cost before proceeding)
    → LLMRequest × N          (one per selected provider)
    → LLMResponse × N         (parallel async, return_exceptions=True)
    → RepoSnapshot × N        (RepoManager — full repo copy + patch applied)
    → ExecutionResult × N     (DockerExecutor — parallel async)
    → SynthesisResult         (SynthesisLayer — single LLM call)
    → FinalResult             (assembled by Orchestrator)
    → terminal output         (ResultsRenderer)
```

---

## Key Architecture Decisions

**No shared state between components.**
Every component receives typed dataclasses and returns typed dataclasses.
Nothing reaches into another component's internals.

**Original repo is never modified.**
All LLM changes are applied to isolated snapshots in `~/.polyforge/workspaces/<query_id>/`.
The Repo Manager creates one full copy of the repo per provider response.

**Fan-out happens twice — both times with asyncio.gather().**
First fan-out: LLM queries (all providers fire simultaneously).
Second fan-out: Docker execution (all containers spin up simultaneously).
Both use `return_exceptions=True` so one failure never blocks the rest.

**One retry per provider, then partial results.**
If a provider fails or times out (60s limit), it retries once.
If the retry also fails, that provider is marked failed and excluded from results.
The pipeline continues with whatever providers succeeded — no total cancellation.

**Hard confirmation gate after file selection.**
Nothing proceeds — no tokens sent, no cost incurred — until the developer
explicitly confirms the file selection. This gate cannot be bypassed in MVP.

**File Selection Assistant uses signatures, not file names or full contents.**
Generic file names (Manager.java, Handler.java) provide no signal.
Full file contents are too expensive at the pre-confirmation stage.
Signatures (class name, method signatures, package path, implements/extends)
give the LLM real structural context at ~15-30 lines per file.

**Docker containers are fully configured by PolyForge — developer touches nothing.**
Project type is auto-detected from manifest files (pom.xml, package.json, etc).
Base image, build command, and test parser are selected from hardcoded profiles.
Containers have no network access, 2GB RAM limit, 2 CPU limit, 120s timeout.

**The File Selection Assistant and Synthesis Layer are NOT agents.**
They are single LLM calls with focused prompts. No loops, no tool use.
The only true agent is the Execution Feedback Loop planned for v2.0.

---

## Decisions Made (Design Session Log)

These decisions were made during pre-dev design review and override anything
in the requirements or architecture docs that conflicts. Claude Code should
treat these as authoritative.

### 1. LLMs can create new files — not just modify existing ones
The architecture doc's `apply_patch` method originally had an
`if os.path.exists(target)` guard that would silently skip new files.
**Remove this guard.** LLMs should be free to create new files (new test files,
utility classes, config files, etc.) within the snapshot. Use `os.makedirs`
on the parent directory before writing to handle new nested paths.

```python
# CORRECT — allow new file creation
def apply_patch(snapshot: RepoSnapshot, response: LLMResponse) -> PatchResult:
    for filename, new_content in response.modified_files.items():
        target = os.path.join(snapshot.snapshot_path, filename)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'w') as f:
            f.write(new_content)
    diff = generate_diff(snapshot)
    return PatchResult(diff=diff, ...)
```

### 2. File Selection Assistant and Synthesis Layer are provider-agnostic
The architecture doc hardcodes Claude Sonnet for both internal LLM components.
**Do not hardcode a provider.** Instead, use whichever provider the user has
a key configured for, with a preference order:

```
Claude → GPT-4o → Gemini
```

If the user only has an OpenAI key, the File Selection Assistant and Synthesis
Layer use GPT-4o. If they only have a Gemini key, those components use Gemini.
The user should never be locked out of the tool because they lack a specific
provider's key.

### 3. The question is an interactive prompt — not a CLI flag
The developer's question is collected via an interactive prompt in the terminal,
not via a `--question` CLI flag. The CLI flags are for configuration
(`--repo <path>`, `--models claude,gpt4o`, `--manual-select`, etc.)
but the question itself is typed interactively after file selection is confirmed.

### 4. Token counting uses tiktoken across all providers (MVP)
For MVP, use tiktoken (cl100k_base encoding) as a rough estimate for all three
providers. This is not perfectly accurate for Gemini or Claude but is close
enough for cost estimation purposes. Per-provider tokenizers can be added in
a future version if accuracy becomes an issue.

### 5. Node.js is the primary dogfood target
The first real-world testing will be against Node.js projects. This means:
- The Node container profile (`node:20-alpine`, `npm ci && npm test`) should
  be the most thoroughly tested
- The Jest output parser should handle common edge cases robustly
- The JS/TS signature extractor should be built and tested first
- Other project types (Maven, Python, etc.) can be more bare-bones initially

### 6. Tests come after working MVP
Do not write tests during initial implementation. Focus on getting a working
end-to-end pipeline first. Tests will be backfilled once the MVP is functional.
This means: do not create test files, do not write pytest fixtures, do not
set up test infrastructure until explicitly asked to.

### 7. Claude Code owns the repo — chat Claude is design partner
The repo is initialized and managed in the IDE via Claude Code.
Chat Claude (this context) is used for design decisions, implementation
guidance, debugging help, and reviewing component logic. Do not duplicate
scaffolding work that Claude Code is handling.

---

## All Dataclasses (models.py)

These are the exact shapes. Do not change field names without updating all consumers.

```python
@dataclass
class QueryRequest:
    repo_path:       str
    question:        str
    selected_files:  list[str]      # confirmed by developer, max 5
    selected_models: list[str]      # e.g. ['claude', 'gpt4o', 'gemini']
    query_id:        str            # uuid
    timestamp:       datetime

@dataclass
class LLMRequest:
    query_id:       str
    provider:       str             # 'claude' | 'gpt4o' | 'gemini'
    system_prompt:  str
    file_contents:  dict[str, str]  # { filename: content }
    question:       str

@dataclass
class LLMResponse:
    query_id:        str
    provider:        str
    success:         bool
    raw_text:        str
    modified_files:  dict[str, str] # { filename: new_content }
    input_tokens:    int
    output_tokens:   int
    latency_ms:      int
    error:           str | None
    retry_attempted: bool

@dataclass
class RepoSnapshot:
    query_id:      str
    provider:      str
    snapshot_path: str              # ~/.polyforge/workspaces/<query_id>/<provider>/
    diff:          str              # unified diff of changes applied
    project_type:  str              # 'maven' | 'gradle' | 'node' | 'python' | 'rust'

@dataclass
class ExecutionResult:
    query_id:      str
    provider:      str
    success:       bool
    build_passed:  bool
    tests_passed:  int
    tests_failed:  int
    tests_errored: int
    exit_code:     int
    stdout:        str
    stderr:        str
    runtime_ms:    int
    timed_out:     bool
    error:         str | None

@dataclass
class SynthesisResult:
    recommended_provider: str | None  # None if all solutions failed
    justification:        str
    quality_warnings:     list[str]
    failure_analysis:     str | None
    closest_provider:     str | None

@dataclass
class FinalResult:
    query_id:          str
    query_request:     QueryRequest
    llm_responses:     list[LLMResponse]
    execution_results: list[ExecutionResult]
    synthesis:         SynthesisResult
    ranked_providers:  list[str]
    estimated_cost:    float
    actual_cost:       float
    total_duration_ms: int
```

---

## LLM Provider Layer

All providers implement this ABC in `providers/base.py`:

```python
class LLMProvider(ABC):
    @abstractmethod
    async def query(self, request: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    def count_tokens(self, text: str) -> int: ...

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float: ...
```

Retry and timeout logic lives inside each provider, not the Orchestrator:
- 60 second timeout per attempt
- One retry on failure with a 2 second pause
- Returns LLMResponse(success=False) on second failure — never raises

All providers use this structured output system prompt:

```
You are a code assistant. The user will provide source files and a question.
Respond ONLY with a JSON object in the following format, with no text outside it:

{
  "explanation": "<brief explanation of your changes>",
  "modified_files": {
    "<filename>": "<complete new file content>",
    "<filename>": "<complete new file content>"
  }
}

Return COMPLETE file content for each modified file, not just changed lines.
Only include files you actually modified. Do not include unchanged files.
You MAY create new files if your solution requires them.
```

---

## Docker Container Profiles

Project type is detected by scanning repo root for manifest files in this priority order:
`pom.xml` → maven, `build.gradle` → gradle, `package.json` → node,
`requirements.txt` → python, `pyproject.toml` → python, `Cargo.toml` → rust

Each type maps to a hardcoded profile:

| Type   | Image                    | Command                                    | Priority |
|--------|--------------------------|--------------------------------------------|----------|
| maven  | maven:3.9-openjdk-17     | mvn test -B                                | Standard |
| gradle | gradle:8-jdk17           | gradle test --no-daemon                    | Standard |
| node   | node:20-alpine           | npm ci && npm test                         | **PRIMARY — test first** |
| python | python:3.11-slim         | pip install -r requirements.txt -q && pytest | Standard |
| rust   | rust:1.75-slim           | cargo test                                 | Standard |

All containers: network_disabled=True, mem_limit=2g, nano_cpus=2_000_000_000,
auto_remove=False (logs captured before removal), timeout=120s.

**Node.js is the primary test target.** The Jest output parser and Node container
profile should be the most robust. Other project types can be more minimal initially.

---

## Workspace Layout

```
~/.polyforge/
├── config.toml                      # user configuration
└── workspaces/
    └── <query_id>/                  # one per query, cleaned up after results
        ├── snapshot_claude/         # full repo + claude's changes applied
        ├── snapshot_gpt4o/          # full repo + gpt's changes applied
        ├── snapshot_gemini/         # full repo + gemini's changes applied
        └── meta.json                # query metadata and timestamps
```

---

## Configuration (~/.polyforge/config.toml)

```toml
[execution]
llm_timeout_seconds     = 60
docker_timeout_seconds  = 120
max_files               = 5
cost_warning_threshold  = 0.50

[docker]
memory_limit            = "2g"
cpu_cores               = 2

[llm_components]
file_selection_enabled  = true
synthesis_enabled       = true

[workspace]
base_path               = "~/.polyforge/workspaces"
auto_cleanup            = true

[project]
# Optional overrides — only set if auto-detection fails
# type        = "maven"
# test_cmd    = "mvn verify -B"
# docker_image = "maven:3.9-openjdk-21"
```

API keys are read from environment variables only — never from config file:
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`

---

## CLI Interaction Model

The CLI is **interactive**, not purely flag-driven. The developer's question
is entered via an interactive prompt, not a `--question` flag.

### CLI Flags (configuration only)
```bash
polyforge --repo <path>              # required: path to local repository
polyforge --repo <path> --models claude,gpt4o   # optional: pre-select models
polyforge --repo <path> --manual-select         # skip file selection assistant
```

### Interactive Flow
```
$ polyforge --repo ./my-project

[PolyForge] Scanning repository...
[PolyForge] Detected project type: node (package.json)

What is your question?
> Why are my API tests failing with a 401 error?

[File Selection Assistant running...]

┌─────────────────────────────────────────────────────────┐
│ Suggested Files                                         │
│                                                         │
│  ✓ src/middleware/auth.js                               │
│    → Handles JWT validation for API routes              │
│    → ~1,200 tokens                                      │
│                                                         │
│  ✓ tests/api/auth.test.js                               │
│    → Test suite for authentication endpoints            │
│    → ~800 tokens                                        │
│                                                         │
│  [a] Add file  [r] Remove file  [m] Select manually     │
│                                                         │
│  Selected models: Claude ✓  GPT-4o ✓  Gemini ✗          │
│  Total tokens: ~2,000                                   │
│  Estimated cost: ~$0.03                                 │
│                                                         │
│  Confirm these files? (yes/no): _                       │
└─────────────────────────────────────────────────────────┘
```

---

## Internal LLM Component Provider Selection

The File Selection Assistant and Synthesis Layer need an LLM provider but
should NOT require a specific one. Use the first available provider from
the user's configured API keys in this preference order:

```python
INTERNAL_PROVIDER_PREFERENCE = ['claude', 'gpt4o', 'gemini']

def get_internal_provider(configured_providers: dict[str, LLMProvider]) -> LLMProvider:
    """Return the best available provider for internal LLM components."""
    for name in INTERNAL_PROVIDER_PREFERENCE:
        if name in configured_providers:
            return configured_providers[name]
    raise PolyForgeError(
        "No LLM provider configured. "
        "Set at least one API key: ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY"
    )
```

This ensures the tool works for users who only have one or two provider keys.

---

## Build and Test

```bash
# Install in editable mode
pip install -e .

# Run the tool
polyforge --repo /path/to/project

# Run all tests (AFTER MVP is working — not during initial build)
pytest

# Run with coverage
pytest --cov=polyforge tests/
```

**Testing strategy: MVP first, tests after.**
Do not write tests during initial implementation. Focus on getting an end-to-end
working pipeline. Tests will be backfilled once the MVP is functional and
manually validated.

---

## Implementation Order (Recommended)

Build components in this order — each layer depends on the one before it:

1. `models.py` — all dataclasses, no dependencies
2. `config.py` — config loading, no dependencies  
3. `providers/base.py` — LLMProvider ABC
4. `providers/claude.py` — first provider implementation
5. `tokens/counter.py` — token counting and cost estimation (tiktoken cl100k_base for all providers)
6. `repo/detector.py` — project type detection
7. `repo/scanner.py` — file tree scanning and signature extraction (**prioritize JS/TS signatures**)
8. `repo/manager.py` — snapshot creation, patch application (with new file creation support), cleanup
9. `docker/parsers.py` — per-project test output parsers (**prioritize Jest parser**)
10. `docker/executor.py` — container lifecycle management
11. `providers/openai.py` and `providers/gemini.py` — remaining providers
12. `llm_components/file_selection.py` — FileSelectionAssistant (uses `get_internal_provider`, not hardcoded Claude)
13. `llm_components/synthesis.py` — SynthesisLayer (uses `get_internal_provider`, not hardcoded Claude)
14. `orchestrator.py` — pipeline coordinator wiring everything together
15. `renderer/renderer.py` — terminal output formatting
16. `cli.py` — Typer CLI entry point with interactive question prompt

---

## Non-Negotiable Rules

- **Never modify the developer's original repository.** All changes go to snapshots only.
- **Never hardcode API keys.** Read from environment variables exclusively.
- **Never log API keys** in any output, error message, or debug trace.
- **Always use `return_exceptions=True`** in asyncio.gather() calls.
- **Always clean up** Docker containers and workspace snapshots after results are collected,
  even if an exception occurs — use try/finally blocks.
- **The hard confirmation gate cannot be bypassed.** Developer must confirm files
  before any provider is queried.
- **Containers must have network_disabled=True.** This is a security constraint,
  not a configuration option.
- **Never raise from a provider.** Return LLMResponse(success=False, error=...) instead.
- **LLMs can create new files** — patch application must use `os.makedirs(exist_ok=True)`
  and write to any path within the snapshot, not just existing files.
- **Internal LLM components (File Selection, Synthesis) must not hardcode a provider.**
  Use the preference order: Claude → GPT-4o → Gemini, falling back to whatever key
  the user has configured.

---

## Dev Mode (Cost Control During Development)

To avoid API costs while building and testing non-LLM components,
use mock providers that return canned responses:

```python
# Set in environment to skip real API calls
POLYFORGE_DEV_MODE=true

# MockProvider returns this without hitting any API
MOCK_RESPONSE = {
    "explanation": "Mock response for development testing",
    "modified_files": {
        "src/index.js": "// mock modified content\nconsole.log('hello');\n"
    }
}
```

Use real providers only when specifically testing LLM integration.
Switch to Claude Haiku (not Sonnet) for integration tests — ~10x cheaper.

---

## Roadmap Context

**MVP (current):** Core pipeline, 3 providers, Docker execution,
FileSelectionAssistant, SynthesisLayer, CLI interface.

**v1.5:** Web UI, Git URL support, additional providers (Mistral, DeepSeek, Groq).

**v2.0:** Execution Feedback Loop Agent — each LLM iterates on its own solution
using Docker test output as feedback. Max 3 iterations, configurable cost ceiling.
This is the only true agent in the system.

**v2.5+:** VS Code extension, VM execution support, team/org mode.