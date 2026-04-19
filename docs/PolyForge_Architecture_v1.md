**POLYFORGE**

System Architecture Document

*MVP v1.0 • Internal Engineering Reference*

Final • April 19, 2026

**1. Architecture Overview**

PolyForge is structured as a sequential pipeline with a parallel
execution core. A single developer query enters the pipeline, fans out
to N LLM providers simultaneously, reconverges when all providers have
responded (or timed out), and then fans out again to N Docker containers
for isolated code execution. Results are collected, synthesized via
blind evaluation, and returned to the developer.

The architecture is layered — each layer has a single responsibility and
communicates with adjacent layers through typed dataclasses defined in
`models.py`. This makes individual components testable in isolation and
allows new LLM providers to be added by implementing a single class.

**2. End-to-End Pipeline**

**2.1 Pipeline Stages**

```
┌─────────────────────────────────────────────────────────┐
│ Developer (CLI)                                         │
└───────────────────────────┬─────────────────────────────┘
                            │ --repo, --models, --verbose
                            ▼
┌─────────────────────────────────────────────────────────┐
│ CLI Entry Point (cli.py)                                │
│ (typer, argument validation, project type detection)    │
│                                                         │
│ → Interactive question prompt                           │
│ → Manual file selection with filename resolution        │
│ → Cost estimation + developer confirmation              │
└───────────────────────────┬─────────────────────────────┘
                            │ QueryRequest
                            ▼
┌─────────────────────────────────────────────────────────┐
│ Orchestrator (Orchestrator.py)                          │
│ (pipeline coordinator)                                  │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│ LLM Provider Layer                                      │
│ ┌───────────┐ ┌───────────┐ ┌───────────┐              │
│ │  Claude    │ │  GPT-4o   │ │  Gemini   │  async       │
│ │  Provider  │ │  Provider │ │  Provider │  parallel    │
│ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘              │
└───────┼──────────────┼──────────────┼───────────────────┘
        │              │              │
        └──────────────┴──────────────┘
                       │ N LLMResponse objects
                       ▼
┌─────────────────────────────────────────────────────────┐
│ Repo Manager (RepoManager.py)                           │
│ create snapshot → apply patch → generate diff           │
└───────────────────────────┬─────────────────────────────┘
                            │ N RepoSnapshot objects
                            ▼
┌─────────────────────────────────────────────────────────┐
│ Docker Execution Layer                                  │
│ ┌───────────┐ ┌───────────┐ ┌───────────┐              │
│ │Container 1│ │Container 2│ │Container 3│  async        │
│ │ (claude)  │ │  (gpt4o)  │ │ (gemini)  │  parallel    │
│ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘              │
└───────┼──────────────┼──────────────┼───────────────────┘
        │              │              │
        └──────────────┴──────────────┘
                       │ N ExecutionResult objects
                       ▼
┌─────────────────────────────────────────────────────────┐
│ Synthesis Layer (synthesis.py)                           │
│ (blind evaluation — Solution A/B/C labeling)            │
└───────────────────────────┬─────────────────────────────┘
                            │ SynthesisResult
                            ▼
┌─────────────────────────────────────────────────────────┐
│ CLI Output (inline in cli.py)                           │
│ (LLM results, Docker results, synthesis recommendation) │
└─────────────────────────────────────────────────────────┘
```

**2.2 Fan-Out / Fan-In Pattern**

PolyForge uses a fan-out / fan-in pattern twice in the pipeline:

-   **Fan-Out 1: LLM Queries** — the Orchestrator fires N async LLM API
    calls simultaneously using `asyncio.gather(return_exceptions=True)`.

-   **Fan-In 1: LLM Results** — all responses reconverge. Failed or
    timed-out providers are filtered out; pipeline continues with
    successful responses.

-   **Fan-Out 2: Docker Execution** — once patches are applied, N
    containers are spun up simultaneously.

-   **Fan-In 2: Execution Results** — all container outputs are collected.
    Results that are exceptions are filtered out.

The two fan-out stages are sequential, not nested. Docker execution
only begins after all LLM responses are collected.

**3. Component Breakdown**

PolyForge is composed of 7 components (MVP implementation):

| Component | File | Responsibility | Interfaces |
|-----------|------|---------------|------------|
| CLI Entry Point | `cli.py` | Parses arguments, validates inputs, runs interactive prompts, displays results | Receives: sys.argv. Creates: QueryRequest |
| Orchestrator | `Orchestrator.py` | Coordinates full pipeline, manages fan-out/fan-in, delegates to all components | Receives: QueryRequest, config. Returns: (LLMResponses, ExecutionResults, SynthesisResult) |
| LLM Providers | `providers/ClaudeProvider.py`, `OpenAIProvider.py`, `GeminiProvider.py` | API calls, retry logic, response parsing, cost calculation | Receives: LLMRequest. Returns: LLMResponse |
| Repo Manager | `repo/RepoManager.py` | Snapshot creation, patch application, diff generation, cleanup | Receives: LLMResponse, project_type. Returns: RepoSnapshot |
| Project Type Detector | `repo/ProjectTypeDetector.py` | Scans repo root for manifest files | Receives: repo_path. Returns: project type string |
| Docker Executor | `docker/executor.py` | Container lifecycle, output capture, test parsing | Receives: RepoSnapshot. Returns: ExecutionResult |
| Synthesis Layer | `llm_components/synthesis.py` | Blind evaluation of all solutions, recommendation | Receives: LLMResponses, ExecutionResults. Returns: SynthesisResult |

**4. Core Data Objects**

Components communicate by passing typed Python dataclasses defined in
`models.py`. No shared mutable state — all data flows forward.

**4.1 QueryRequest**

*Created by the CLI. Represents everything the developer submitted.*

```python
@dataclass
class QueryRequest:
    repo_path:       str              # path to local repo
    question:        str              # developer's question
    selected_files:  list[str]        # confirmed file paths (max 5)
    selected_models: list[str]        # e.g. ['claude', 'gpt4o', 'gemini']
    query_id:        str              # uuid, used for workspace path
    timestamp:       datetime
```

**4.2 LLMRequest**

*Created by the Orchestrator. Sent to each provider in parallel.*

```python
@dataclass
class LLMRequest:
    query_id:      str
    provider:      str               # 'claude' | 'gpt4o' | 'gemini'
    system_prompt: str
    file_contents: dict[str, str]    # { filename: content }
    question:      str
```

**4.3 LLMResponse**

*Returned by each provider. Contains raw response and parsed file changes.*

```python
@dataclass
class LLMResponse:
    query_id:        str
    provider:        str
    success:         bool
    raw_text:        str
    modified_files:  dict[str, str]  # { filename: new_content }
    input_tokens:    int
    output_tokens:   int
    cost:            float           # calculated cost in USD
    latency_ms:      int
    error:           str | None
    retry_attempted: bool
```

**4.4 RepoSnapshot**

*Created by Repo Manager. Full copy of the repo with one LLM's changes applied.*

```python
@dataclass
class RepoSnapshot:
    query_id:      str
    provider:      str
    snapshot_path: str               # ~/.polyforge/workspaces/<query_id>/<provider>/
    diff:          str               # unified diff of changes applied
    project_type:  str               # 'maven' | 'gradle' | 'node' | 'python' | 'rust'
```

**4.5 ExecutionResult**

*Returned by Docker Executor. Everything captured from the container.*

```python
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
```

**4.6 SynthesisResult**

*Returned by the Synthesis Layer. Recommendation shown in results.*

```python
@dataclass
class SynthesisResult:
    recommended_provider: str | None  # None if all solutions failed
    justification:        str
    quality_warnings:     list[str]
    failure_analysis:     str | None
    closest_provider:     str | None
    solution_rankings:    list[str]   # ordered best to worst
    synthesis_cost:       float       # cost of the synthesis LLM call
```

**4.7 FinalResult**

*Assembled by the Orchestrator. Not currently used for rendering (output is inline in cli.py).*

```python
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

**5. LLM Provider Layer**

**5.1 Provider Interface**

All providers implement the `LLMProvider` ABC defined in `providers/LLMProvider.py`:

```python
class LLMProvider(ABC):
    @abstractmethod
    async def query_llm(self, request: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    async def estimate_cost_of_request(self, request: LLMRequest) -> float: ...

    @abstractmethod
    def calculate_cost_of_response(self, input_tokens: int, output_tokens: int) -> float: ...
```

**5.2 Provider Implementations**

| Provider | File | Model | SDK Client |
|----------|------|-------|------------|
| ClaudeProvider | `ClaudeProvider.py` | claude-sonnet-4-5 | AsyncAnthropic |
| OpenAIProvider | `OpenAIProvider.py` | gpt-4o | AsyncOpenAI (Responses API) |
| GeminiProvider | `GeminiProvider.py` | gemini-2.5-flash | genai.Client (async via .aio) |

Provider aliases in the Orchestrator:
- `claude` → ClaudeProvider
- `gpt4o`, `openai`, `chatgpt` → OpenAIProvider
- `gemini` → GeminiProvider

**5.3 Retry & Timeout Logic**

Retry logic is implemented inside each provider, not the Orchestrator:

```python
async def query_llm(self, request: LLMRequest) -> LLMResponse:
    retry_attempted = False
    for attempt in range(2):        # max 2 attempts (1 retry)
        try:
            async with asyncio.timeout(config.ExecutionConfig.llm_timeout_seconds):
                response = await self._call_api(request)
                return self._parse_response(response, ...)
        except Exception as e:
            if attempt == 1:        # second failure — give up
                return LLMResponse(success=False, error=str(e),
                                   retry_attempted=True, ...)
            retry_attempted = True
            await asyncio.sleep(2)  # brief pause before retry
```

**5.4 Structured Output Prompt**

All providers receive the same system prompt defined in `config.py`:

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

**5.5 Token Counting**

All providers use tiktoken for cost estimation (MVP approximation):
- Claude: `tiktoken.get_encoding("cl100k_base")`
- OpenAI: `tiktoken.encoding_for_model("gpt-4o")`
- Gemini: `tiktoken.get_encoding("cl100k_base")`

Estimated max output tokens: 8192 for all providers.

**6. Repo Manager**

The Repo Manager (`repo/RepoManager.py`) handles snapshot creation,
patch application, diff generation, and workspace cleanup.

**6.1 Workspace Structure**

```
~/.polyforge/
└── workspaces/
    └── <query_id>/                  # one per query (uuid)
        ├── snapshot_<provider>/      # full repo + provider's changes
        └── ...
```

**6.2 Project Type Detection**

`ProjectTypeDetector` scans the repository root for manifest files in priority order:

```python
DETECTION_RULES = [
    ('pom.xml',          'maven'),
    ('build.gradle',     'gradle'),
    ('package.json',     'node'),
    ('requirements.txt', 'python'),
    ('pyproject.toml',   'python'),
    ('Cargo.toml',       'rust'),
]
```

Returns `None` if no manifest is found.

**6.3 Snapshot Creation & Patch Application**

The `build_repo_snapshot` method handles both snapshot creation and patch application:

1. Copies the full repo to `~/.polyforge/workspaces/<query_id>/snapshot_<provider>/`
   using `shutil.copytree` (excludes `.git`, `__pycache__`, `node_modules`, etc.)
2. Applies LLM's modified files to the snapshot
3. Creates parent directories for new files (`os.makedirs(exist_ok=True)`)
4. Generates unified diff of all changes
5. Returns a `RepoSnapshot` object

Cleanup removes the entire query workspace directory in a `finally` block.

**7. Docker Executor**

The Docker Executor (`docker/executor.py`) manages container lifecycle.

**7.1 Docker Availability Check**

Docker availability is checked on `DockerExecutor.__init__`:

```python
try:
    self._client = docker.from_env(timeout=self._timeout)
    self._client.ping()
except docker.errors.DockerException as e:
    self._client = None
    self._docker_error = str(e)
```

If Docker is unavailable, `execute()` returns an error `ExecutionResult` immediately.

**7.2 Container Profiles**

Each project type maps to a hardcoded profile:

```python
DOCKER_PROFILES = {
    "node":   ("node:20-alpine",       "npm ci && npm test"),
    "python": ("python:3.11-slim",     "pip install -r requirements.txt -q && pytest"),
    "maven":  ("maven:3.9-openjdk-17", "mvn test -B"),
    "gradle": ("gradle:8-jdk17",       "gradle test --no-daemon"),
    "rust":   ("rust:1.75-slim",       "cargo test"),
}
```

**7.3 Container Configuration**

| Setting | Value | Source |
|---------|-------|--------|
| Volume mount | snapshot_path → /workspace (rw) | Hardcoded |
| Working directory | /workspace | Hardcoded |
| Network | network_disabled=False (NOTE: should be True) | Hardcoded |
| Memory limit | Configurable (default "2g") | config.docker.memory_limit |
| CPU limit | Configurable (default 2 cores) | config.docker.cpu_cores |
| Timeout | Configurable (default 120s) | config.execution.docker_timeout_seconds |
| Auto-remove | False (logs captured, then manual remove) | Hardcoded |

**7.4 Execution Flow**

```python
async def execute(self, snapshot: RepoSnapshot) -> ExecutionResult:
    # 1. Check Docker availability
    # 2. Look up profile for project type
    # 3. Run container (detached)
    # 4. Poll container status until exit or timeout
    # 5. Capture stdout/stderr logs
    # 6. Parse test output (generic regex parser)
    # 7. Return ExecutionResult
    # finally: container.remove(force=True)
```

Timeout is enforced via a polling loop (`container.reload()` every 2 seconds)
rather than blocking on `container.wait()`.

**7.5 Test Output Parsing**

`docker/parsers.py` provides a generic `parse_test_output(stdout, stderr)` function:

```python
@dataclass
class TestCounts:
    passed: int
    failed: int
    errored: int

_PASSED_PATTERN = re.compile(r"(\d+)\s+passed", re.IGNORECASE)
_FAILED_PATTERN = re.compile(r"(\d+)\s+failed", re.IGNORECASE)
_ERROR_PATTERN  = re.compile(r"(\d+)\s+errors?(?:ed)?", re.IGNORECASE)
```

Uses `max()` of all regex matches (not sum) to avoid double-counting when
test runners print subtotals before a final total. Works across Jest, pytest,
Maven Surefire, cargo test, etc.

**8. Synthesis Layer**

The Synthesis Layer (`llm_components/synthesis.py`) runs after all Docker
execution results are collected. It is a single LLM call — not a loop,
not an agent.

**8.1 Blind Evaluation**

Provider responses are anonymized using `SolutionKey` enum:

```python
class SolutionKey(Enum):
    SOLUTION_A = "Solution A"
    SOLUTION_B = "Solution B"
    SOLUTION_C = "Solution C"
```

Each solution section sent to the synthesis LLM includes:
- Modified files (full content)
- Test results (exit code, pass/fail/error counts)
- Test output (stdout/stderr)

Provider names are never included. The `key_to_provider` mapping is used
to decode blind keys back to provider names after synthesis returns.

**8.2 Provider Selection**

The synthesis LLM is selected using the internal preference order:

```python
INTERNAL_PROVIDER_PREFERENCE = ["claude", "gpt4o", "gemini"]
```

The Orchestrator selects the first available provider from the user's
configured models. The CLI displays which provider is being used.

**8.3 Synthesis Prompt**

The synthesis system prompt instructs the LLM to evaluate solutions on:
1. Correctness — do tests pass?
2. Code quality — clean, readable, maintainable?
3. Completeness — fully addresses the question?
4. Minimality — only necessary changes?

Response format: JSON with `recommended_solution`, `justification`,
`quality_warnings`, `failure_analysis`, `closest_solution`, `solution_rankings`.

**9. Orchestrator**

The Orchestrator (`Orchestrator.py`) coordinates the full pipeline.

**9.1 Constructor**

```python
class Orchestrator:
    def __init__(self, query_request: QueryRequest, config: PolyForgeConfig, project_type: str):
        # Instantiates providers from PROVIDER_MAP
        # Creates RepoManager with workspace path
        # Creates DockerExecutor with config
        # Builds LLM requests for all selected models
```

**9.2 Execution Sequence**

```python
async def run(self) -> tuple[list[LLMResponse], list[ExecutionResult], SynthesisResult]:
    try:
        # 1. Fan-out: query all providers in parallel
        responses = await asyncio.gather(*[...], return_exceptions=True)

        # 2. Filter: separate successful responses from failures/exceptions
        successful = [r for r in responses if isinstance(r, LLMResponse) and r.success]

        # 3. Create snapshots + apply patches for each success
        snapshots = [repo_manager.build_repo_snapshot(r, project_type) for r in successful]

        # 4. Fan-out: run Docker containers in parallel
        exec_results = await asyncio.gather(*[...], return_exceptions=True)

        # 5. Filter valid execution results
        exec_results = [r for r in exec_results if isinstance(r, ExecutionResult)]

        # 6. Synthesis — blind evaluation
        synthesis_result, _ = await synthesis_layer.synthesize(...)

        # 7. Return all results
        return llm_responses, exec_results, synthesis_result
    finally:
        # 8. Cleanup workspaces
        repo_manager.cleanup()
```

**9.3 Cost Estimation**

```python
async def estimate_cost_of_query(self) -> float:
    costs = await asyncio.gather(*[
        provider.estimate_cost_of_request(request)
        for model, request in llm_requests
    ], return_exceptions=True)
    return sum(c for c in costs if isinstance(c, float))
```

**10. Project Directory Structure (Actual)**

```
PolyForge/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── docs/
│   ├── PolyForge_Requirements_v1.md
│   └── PolyForge_Architecture_v1.md
├── polyforge/
│   ├── __init__.py
│   ├── cli.py                       # Typer CLI entry point + results display
│   ├── Orchestrator.py              # pipeline coordinator
│   ├── models.py                    # all dataclasses + exceptions
│   ├── config.py                    # config loading + SYSTEM_PROMPT
│   │
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── LLMProvider.py           # LLMProvider ABC
│   │   ├── ClaudeProvider.py        # claude-sonnet-4-5
│   │   ├── OpenAIProvider.py        # gpt-4o (Responses API)
│   │   └── GeminiProvider.py        # gemini-2.5-flash
│   │
│   ├── llm_components/
│   │   ├── __init__.py
│   │   └── synthesis.py             # SynthesisLayer (blind evaluation)
│   │
│   ├── repo/
│   │   ├── __init__.py
│   │   ├── RepoManager.py           # snapshots, patches, cleanup
│   │   └── ProjectTypeDetector.py   # manifest-based detection
│   │
│   └── docker/
│       ├── __init__.py
│       ├── executor.py              # DockerExecutor
│       └── parsers.py               # generic test output parser
│
└── tests/
    └── ProviderTests/               # test fixtures
```

**Not implemented as separate modules (functionality is inline):**
- `tokens/counter.py` — token counting is in each provider
- `renderer/renderer.py` — results display is in cli.py
- `repo/scanner.py` — no signature extraction (manual file selection)
- `llm_components/file_selection.py` — no File Selection Assistant (deferred to v1.5)

**11. Configuration**

**11.1 Environment Variables**

| Variable | Required When |
|----------|--------------|
| ANTHROPIC_API_KEY | Claude is selected as a provider |
| OPENAI_API_KEY | GPT-4o is selected as a provider |
| GOOGLE_API_KEY | Gemini is selected as a provider |

**11.2 Config File (~/.polyforge/config.toml)**

Created automatically on first run with these defaults:

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
# Optional overrides
# type        = "maven"
# test_cmd    = "mvn verify -B"
# docker_image = "maven:3.9-openjdk-21"
```
