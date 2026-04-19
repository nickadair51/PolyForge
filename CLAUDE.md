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
**Status:** MVP v1.0 complete

---

## Project Structure (Actual)

```
PolyForge/
├── CLAUDE.md                        # this file
├── pyproject.toml                   # package config and dependencies
├── README.md
├── docs/
│   ├── PolyForge_Requirements_v1.md
│   └── PolyForge_Architecture_v1.md
├── polyforge/
│   ├── __init__.py
│   ├── cli.py                       # Typer CLI entry point
│   ├── Orchestrator.py              # pipeline coordinator
│   ├── models.py                    # ALL dataclasses live here
│   ├── config.py                    # config loading (~/.polyforge/config.toml)
│   │
│   ├── providers/                   # LLM Provider Layer
│   │   ├── __init__.py
│   │   ├── LLMProvider.py           # LLMProvider ABC
│   │   ├── ClaudeProvider.py        # ClaudeProvider (claude-sonnet-4-5)
│   │   ├── OpenAIProvider.py        # OpenAIProvider (gpt-4o)
│   │   └── GeminiProvider.py        # GeminiProvider (gemini-2.5-flash)
│   │
│   ├── llm_components/              # LLM-powered pipeline stages
│   │   ├── __init__.py
│   │   └── synthesis.py             # SynthesisLayer (blind evaluation)
│   │
│   ├── repo/                        # Repo Manager
│   │   ├── __init__.py
│   │   ├── RepoManager.py           # RepoManager — snapshots, patches, cleanup
│   │   └── ProjectTypeDetector.py   # project type detection
│   │
│   ├── docker/                      # Docker Executor
│   │   ├── __init__.py
│   │   ├── executor.py              # DockerExecutor
│   │   └── parsers.py               # generic test output parser
│   │
│   └── (no tokens/ or renderer/ modules — functionality is inline)
│
└── tests/
    └── ProviderTests/               # test fixtures (Node.js project)
```

---

## Core Data Flow

Every component communicates through typed dataclasses defined in `models.py`.
No shared mutable state. Data flows forward only — never backwards.

```
Developer CLI input
    → repo scan (ProjectTypeDetector)
    → interactive question prompt
    → manual file selection (with filename resolution)
    → QueryRequest
    → cost estimate (Orchestrator.estimate_cost_of_query)
    → developer confirms cost
    → LLMRequest × N          (one per selected provider)
    → LLMResponse × N         (parallel async, return_exceptions=True)
    → RepoSnapshot × N        (RepoManager — full repo copy + patch applied)
    → ExecutionResult × N     (DockerExecutor — parallel async, test output parsed)
    → SynthesisResult         (SynthesisLayer — blind single LLM call)
    → terminal output         (inline in cli.py)
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
If a provider fails or times out, it retries once with a 2-second pause.
If the retry also fails, that provider is marked failed and excluded from results.
The pipeline continues with whatever providers succeeded — no total cancellation.

**File selection is manual with smart filename resolution.**
Developer enters filenames or relative paths. If a filename has one match in the
repo, it auto-resolves. If multiple matches exist, the developer picks from a
numbered list. Maximum 5 files per query.

**LLMs can create new files — not just modify existing ones.**
Patch application uses `os.makedirs(exist_ok=True)` and writes to any path
within the snapshot, not just existing files.

**Docker containers are fully configured by PolyForge — developer touches nothing.**
Project type is auto-detected from manifest files (pom.xml, package.json, etc).
Base image and build command are selected from hardcoded profiles.
Containers have resource limits and network restrictions.

**Synthesis Layer uses blind evaluation.**
Provider responses are labeled with anonymous keys (Solution A, Solution B, etc.)
so the evaluating LLM cannot be biased by provider identity. The Orchestrator
maps keys back to provider names after synthesis returns.

**Internal LLM components are provider-agnostic.**
The Synthesis Layer uses whichever provider the user has configured,
with a preference order: Claude → GPT-4o → Gemini.

**Test output parsing is generic, not per-framework.**
A single regex-based parser extracts pass/fail/error counts from any test
runner output. Uses `max()` instead of `sum()` to avoid double-counting
when subtotals appear before final totals.

---

## All Dataclasses (models.py)

These are the exact shapes as implemented.

```python
class PolyForgeError(Exception): ...
class UnknownProjectTypeError(PolyForgeError): ...
class NoTestCommandError(PolyForgeError): ...

class SolutionKey(Enum):
    SOLUTION_A = "Solution A"
    SOLUTION_B = "Solution B"
    SOLUTION_C = "Solution C"

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
    cost:            float          # calculated cost in USD
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
    recommended_provider: str | None
    justification:        str
    quality_warnings:     list[str]
    failure_analysis:     str | None
    closest_provider:     str | None
    solution_rankings:    list[str]   # ordered best to worst
    synthesis_cost:       float       # cost of the synthesis LLM call

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

@dataclass
class FileSelectionResult:
    selected_files:  list[str]
    rationales:      dict[str, str]
    token_estimates: dict[str, int]

@dataclass
class TokenEstimate:
    total_tokens:         int
    file_token_counts:    dict[str, int]
    per_model_cost:       dict[str, float]
    total_estimated_cost: float

@dataclass
class PatchResult:
    provider:       str
    snapshot_path:  str
    diff:           str
    files_modified: list[str]
    files_created:  list[str]
```

---

## LLM Provider Layer

All providers implement this ABC in `providers/LLMProvider.py`:

```python
class LLMProvider(ABC):
    @abstractmethod
    async def query_llm(self, request: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    async def estimate_cost_of_request(self, request: LLMRequest) -> float: ...

    @abstractmethod
    def calculate_cost_of_response(self, input_tokens: int, output_tokens: int) -> float: ...
```

### Provider Implementations

| Provider | File | Model | SDK | Input Cost | Output Cost |
|----------|------|-------|-----|-----------|-------------|
| Claude | `ClaudeProvider.py` | `claude-sonnet-4-5` | `anthropic` (AsyncAnthropic) | $0.000003/token | $0.000015/token |
| OpenAI | `OpenAIProvider.py` | `gpt-4o` | `openai` (AsyncOpenAI) | $0.0000025/token | $0.000010/token |
| Gemini | `GeminiProvider.py` | `gemini-2.5-flash` | `google-genai` (genai.Client) | $0.0000001/token | $0.0000004/token |

### Retry & Timeout Logic

Each provider implements retry logic internally (not in the Orchestrator):
- Configurable timeout per attempt (default: 150s via config)
- One retry on failure with a 2-second pause
- Returns `LLMResponse(success=False)` on second failure — never raises

### Token Counting

All providers use tiktoken for cost estimation:
- Claude: `tiktoken.get_encoding("cl100k_base")`
- OpenAI: `tiktoken.encoding_for_model("gpt-4o")`
- Gemini: `tiktoken.get_encoding("cl100k_base")`

Estimated max output tokens: 8192 for all providers.

### Structured Output Prompt

All providers receive the same system prompt (defined in `config.py`):

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

### Provider Aliases

The CLI and Orchestrator accept these model names:
- `claude` → ClaudeProvider
- `gpt4o` → OpenAIProvider
- `openai` → OpenAIProvider
- `chatgpt` → OpenAIProvider
- `gemini` → GeminiProvider

---

## Docker Container Profiles

Project type is detected by `ProjectTypeDetector` scanning repo root for manifest
files in this priority order:
`pom.xml` → maven, `build.gradle` → gradle, `package.json` → node,
`requirements.txt` → python, `pyproject.toml` → python, `Cargo.toml` → rust

Each type maps to a hardcoded profile in `docker/executor.py`:

| Type   | Image                    | Command                                    |
|--------|--------------------------|---------------------------------------------|
| node   | node:20-alpine           | npm ci && npm test                          |
| python | python:3.11-slim         | pip install -r requirements.txt -q && pytest |
| maven  | maven:3.9-openjdk-17     | mvn test -B                                 |
| gradle | gradle:8-jdk17           | gradle test --no-daemon                     |
| rust   | rust:1.75-slim           | cargo test                                  |

Container configuration (from `PolyForgeConfig`):
- `mem_limit`: configurable (default "2g")
- `nano_cpus`: configurable (default 2 cores × 1,000,000,000)
- `network_disabled`: False (NOTE: should be True per security spec)
- `working_dir`: /workspace
- `auto_remove`: False (logs captured before manual removal)
- `timeout`: configurable (default 120s), enforced via polling loop

### Test Output Parsing

`docker/parsers.py` provides a generic `parse_test_output(stdout, stderr)` function:
- Regex patterns match `<N> passed`, `<N> failed`, `<N> error(s/ed)` (case-insensitive)
- Returns `TestCounts(passed, failed, errored)` dataclass
- Uses `max()` of all matches (not sum) to avoid double-counting subtotals
- Works across Jest, pytest, Maven Surefire, cargo test, etc.

---

## Workspace Layout

```
~/.polyforge/
├── config.toml                      # user configuration
└── workspaces/
    └── <query_id>/                  # one per query, cleaned up after results
        ├── snapshot_<provider>/      # full repo + provider's changes applied
        └── (meta.json not implemented)
```

---

## Configuration (~/.polyforge/config.toml)

```toml
[execution]
llm_timeout_seconds     = 150
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

## CLI Interface

The CLI is built with Typer. The developer's question is entered via an
interactive prompt, not a `--question` flag.

### CLI Flags
```bash
polyforge --repo <path>                              # required: path to local repository
polyforge --repo <path> --models claude,gpt4o        # optional: select specific models (default: claude,gpt4o,gemini)
polyforge --repo <path> --verbose                    # optional: show Docker stdout/stderr output
polyforge --repo <path> -v                           # short form of --verbose
```

### Interactive Flow
```
$ polyforge --repo ./my-project

[PolyForge] Scanning repository: ./my-project
Your repo is of type node

What is your question?
> Why are my API tests failing with a 401 error?

[PolyForge] Input up to 5 files that relate to your question
  You can enter filenames (e.g. auth.js) or relative paths (e.g. src/auth.js)

Enter file names (comma separated): auth.js, auth.test.js
  Resolved 'auth.js' → src/middleware/auth.js
  Resolved 'auth.test.js' → tests/api/auth.test.js

The price of your query is estimated to be 0.12
Is this acceptable? [y/N]: y

[PolyForge] Sending to models...
[PolyForge] Using claude for synthesis layer

--- claude (LLM) ---
  Success: True
  Latency: 3200ms
  Cost: $0.0450

--- gpt4o (LLM) ---
  ...

--- claude (Docker) ---
  Success: True
  Exit code: 0
  Runtime: 15200ms
  Timed out: False

--- Synthesis ---
  Recommended: claude
  Justification: ...
  Rankings: claude > gpt4o > gemini

[PolyForge] Done.
```

### File Resolution

Users can enter just a filename instead of the full relative path:
- If the filename matches exactly one file in the repo → auto-resolved
- If multiple matches → numbered list, user picks
- If no matches → skipped with error message
- Full relative paths still work directly

---

## Synthesis Layer (Blind Evaluation)

The Synthesis Layer (`llm_components/synthesis.py`) performs blind evaluation:

1. Each provider's response is labeled with an anonymous key (Solution A/B/C)
2. The synthesis LLM sees modified files + test results but NOT which provider produced them
3. Response is parsed and blind keys are mapped back to provider names
4. Returns `SynthesisResult` with recommendation, justification, rankings, and warnings

The synthesis provider is selected using the internal preference order:
Claude → GPT-4o → Gemini (whichever the user has configured).

---

## Orchestrator

The Orchestrator (`Orchestrator.py`) coordinates the full pipeline:

```python
class Orchestrator:
    def __init__(self, query_request, config, project_type): ...
    async def run(self) -> tuple[list[LLMResponse], list[ExecutionResult], SynthesisResult]: ...
    async def estimate_cost_of_query(self) -> float: ...
    def get_synthesis_provider_name(self) -> str: ...
```

Pipeline execution sequence:
1. Build LLM requests (one per selected model)
2. Fan-out: query all providers in parallel (`asyncio.gather`)
3. Filter successful responses
4. Create repo snapshots + apply patches for each successful response
5. Fan-out: run Docker containers in parallel (`asyncio.gather`)
6. Filter valid execution results
7. Run Synthesis Layer (blind evaluation)
8. Return results
9. Cleanup workspaces (in `finally` block)

---

## Build and Run

```bash
# Install in editable mode
pip install -e .

# Run the tool
polyforge --repo /path/to/project

# Run with verbose Docker output
polyforge --repo /path/to/project --verbose

# Run with specific models
polyforge --repo /path/to/project --models claude,gpt4o
```

---

## Non-Negotiable Rules

- **Never modify the developer's original repository.** All changes go to snapshots only.
- **Never hardcode API keys.** Read from environment variables exclusively.
- **Never log API keys** in any output, error message, or debug trace.
- **Always use `return_exceptions=True`** in asyncio.gather() calls.
- **Always clean up** Docker containers and workspace snapshots after results are collected,
  even if an exception occurs — use try/finally blocks.
- **Containers should have network_disabled=True.** This is a security constraint,
  not a configuration option.
- **Never raise from a provider.** Return LLMResponse(success=False, error=...) instead.
- **LLMs can create new files** — patch application must use `os.makedirs(exist_ok=True)`
  and write to any path within the snapshot, not just existing files.
- **Internal LLM components must not hardcode a provider.**
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

---

## Roadmap Context

**MVP v1.0 (current — complete):** Core pipeline, 3 providers, Docker execution,
manual file selection with filename resolution, SynthesisLayer, CLI interface with
`--verbose` flag, generic test output parsing.

**v1.5:** Web UI, Git URL support, File Selection Assistant (LLM-driven file
suggestion with signature extraction), dedicated Results Renderer module,
additional providers (Mistral, DeepSeek, Groq).

**v2.0:** Execution Feedback Loop Agent — each LLM iterates on its own solution
using Docker test output as feedback. Max 3 iterations, configurable cost ceiling.

**v2.5+:** VS Code extension, VM execution support, team/org mode.
