**POLYFORGE**

Multi-LLM Code Review & Execution Platform

*Product Requirements Document • MVP v1.0*

Final • April 19, 2026

**1. Project Overview**

PolyForge is a developer tool that allows engineers to ask questions
about their code across multiple large language models simultaneously.
Rather than querying a single LLM and accepting one answer, PolyForge
fans out the question to multiple providers in parallel, applies each
LLM's suggested code changes to an isolated copy of the repository,
executes the modified code inside a sandboxed Docker container, and
returns a ranked comparison of results — showing not just what each
model suggested, but whether the suggestion actually works.

The MVP targets individual developers who want fast, validated,
multi-perspective code assistance without the cost and complexity of a
full agentic pipeline.

**2. Goals & Non-Goals**

**2.1 Goals**

-   Allow developers to query up to 3 LLMs simultaneously with a single
    question about their code.

-   Apply each LLM's suggested changes to an isolated copy of the
    codebase and execute them in a Docker container.

-   Return a side-by-side comparison of LLM responses alongside
    execution results (build success, test pass/fail, runtime errors).

-   Give developers full control over which models are queried per
    question to manage cost.

-   Display an estimated cost breakdown before submission with a
    confirmation gate.

-   Hard cap file selection at 5 files per query to enforce cost
    predictability.

-   Provide a synthesis recommendation identifying the best solution
    with justification.

**2.2 Non-Goals (MVP)**

-   No web UI — CLI interface only for v1.

-   No authentication or multi-user support.

-   No persistent storage of query history.

-   No support for VM-based execution (Docker only for MVP).

-   No automatic file relevance detection — developer manually selects
    files (with filename resolution assist).

-   No fine-tuning or custom model training.

-   No File Selection Assistant (LLM-driven file suggestion) — deferred to v1.5.

-   No dedicated Results Renderer module — output is inline in CLI.

**3. Core User Flow**

The end-to-end flow a developer experiences in the MVP:

-   Developer points the tool at their local repository directory via
    `--repo <path>`.

-   Tool auto-detects project type from manifest files.

-   Developer types their question interactively.

-   Developer enters up to 5 files (by filename or relative path).
    Filenames are auto-resolved against the repo; ambiguous names
    prompt the developer to choose.

-   Tool computes estimated cost across all selected models and displays it.

-   Developer confirms cost before proceeding.

-   Tool fans out the question + selected file contents to each chosen
    LLM simultaneously.

-   Each LLM returns suggested code changes in structured JSON format.

-   Tool parses each LLM response, extracts the modified file content,
    and applies changes to a snapshot of the full repo.

-   Tool spins up one Docker container per LLM response, each with the
    full modified repo.

-   Each container runs the project's build and test suite.

-   Tool collects results from all containers and runs a blind synthesis
    evaluation.

-   Tool displays LLM results, Docker execution results, and synthesis
    recommendation.

**4. Functional Requirements**

**4.1 Codebase Ingestion**

| REQ ID | Requirement | Priority | Status | Notes |
|--------|-------------|----------|--------|-------|
| FR-01 | Accept a local directory path as the repository root | High | Done | CLI option: `--repo <path>` |
| FR-02 | Allow the developer to select between 1 and 5 files | High | Done | Manual entry with filename resolution |
| FR-03 | Hard cap at 5 files per query | High | Done | Excess files trimmed with warning |
| FR-04 | Auto-detect project type from manifest files | High | Done | pom.xml, package.json, etc. |
| FR-05 | Create a full snapshot of the repo before applying changes | High | Done | Original repo never modified |
| FR-06 | Support filename-only input with auto-resolution | High | Done | Single match auto-resolves; multiple matches prompt |

**4.2 Token Counter & Cost Estimation**

| REQ ID | Requirement | Priority | Status | Notes |
|--------|-------------|----------|--------|-------|
| FR-07 | Compute approximate token count for selected files | High | Done | tiktoken cl100k_base for all providers |
| FR-08 | Display total estimated cost before submission | High | Done | Developer must confirm before proceeding |
| FR-09 | Per-provider cost estimation | High | Done | Each provider estimates its own cost |

**4.3 Model Selection**

| REQ ID | Requirement | Priority | Status | Notes |
|--------|-------------|----------|--------|-------|
| FR-10 | Support Claude (Sonnet 4.5), GPT-4o, and Gemini 2.5 Flash | High | Done | 3 providers implemented |
| FR-11 | Developer selects any combination of 1 to 3 models | High | Done | `--models` flag, default: all three |
| FR-12 | API keys read from environment variables | High | Done | ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY |
| FR-13 | Support provider aliases (openai, chatgpt → OpenAIProvider) | Medium | Done | Mapped in Orchestrator |

**4.4 LLM Query & Response Handling**

| REQ ID | Requirement | Priority | Status | Notes |
|--------|-------------|----------|--------|-------|
| FR-14 | Send queries to all selected LLMs simultaneously | High | Done | asyncio.gather with return_exceptions=True |
| FR-15 | Structured JSON output format for all providers | High | Done | System prompt enforces JSON response |
| FR-16 | Per-provider timeout with one retry | High | Done | Configurable timeout (default 150s), 2s pause between attempts |
| FR-17 | Parse LLM response and extract modified file contents | High | Done | Handles markdown code fences |
| FR-18 | Failed providers marked as failed, not blocking | High | Done | Pipeline continues with successful providers |

**4.5 Code Patch Application**

| REQ ID | Requirement | Priority | Status | Notes |
|--------|-------------|----------|--------|-------|
| FR-19 | One isolated repo copy per LLM response | High | Done | shutil.copytree to snapshot directory |
| FR-20 | Apply LLM file changes to corresponding snapshot | High | Done | Overwrites existing files, creates new ones |
| FR-21 | Support LLM creating new files (not just modifying) | High | Done | os.makedirs(exist_ok=True) before write |
| FR-22 | Generate unified diff of applied changes | High | Done | difflib used for diff generation |

**4.6 Docker Execution**

| REQ ID | Requirement | Priority | Status | Notes |
|--------|-------------|----------|--------|-------|
| FR-23 | One ephemeral container per LLM response | High | Done | Containers run in parallel |
| FR-24 | Select Docker base image from project type | High | Done | 5 profiles: node, python, maven, gradle, rust |
| FR-25 | Run build + test command inside container | High | Done | Profile-specific commands |
| FR-26 | Configurable execution timeout (default 120s) | High | Done | Polling loop with deadline |
| FR-27 | Resource limits: configurable memory and CPU | High | Done | Default 2GB / 2 cores |
| FR-28 | Capture stdout, stderr, exit code | High | Done | Logs captured before container removal |
| FR-29 | Clean up containers after execution | High | Done | container.remove(force=True) in finally block |
| FR-30 | Parse test output for pass/fail/error counts | High | Done | Generic regex parser in docker/parsers.py |
| FR-31 | Docker availability check at startup | High | Done | Ping on DockerExecutor init |

**4.7 Results Display**

| REQ ID | Requirement | Priority | Status | Notes |
|--------|-------------|----------|--------|-------|
| FR-32 | Display LLM results (success, latency, cost, errors) | High | Done | Per-provider summary in CLI |
| FR-33 | Display Docker results (success, exit code, runtime) | High | Done | Per-provider summary in CLI |
| FR-34 | Docker stdout/stderr behind --verbose flag | Medium | Done | Hidden by default to reduce noise |
| FR-35 | Display synthesis recommendation and rankings | High | Done | Synthesis section in CLI output |
| FR-36 | Display synthesis cost | Medium | Done | Shown in synthesis section |

**4.8 Synthesis Layer**

| REQ ID | Requirement | Priority | Status | Notes |
|--------|-------------|----------|--------|-------|
| AG-01 | Synthesis runs after all Docker results collected | High | Done | Single LLM call at end of pipeline |
| AG-02 | Blind evaluation — provider identity hidden | High | Done | Solution A/B/C labeling |
| AG-03 | Recommend best solution with justification | High | Done | Parsed from JSON response |
| AG-04 | Flag quality warnings | Medium | Done | quality_warnings field |
| AG-05 | Handle all-failed case with closest analysis | Medium | Done | failure_analysis and closest_provider |
| AG-06 | Provider-agnostic — uses preference order | High | Done | Claude → GPT-4o → Gemini |
| AG-07 | Solution rankings | Medium | Done | Ordered best to worst |

**5. Non-Functional Requirements**

| REQ ID | Requirement | Priority | Status | Notes |
|--------|-------------|----------|--------|-------|
| NFR-01 | API keys never logged or printed | High | Done | Environment variables only |
| NFR-02 | Runs on macOS and Linux | High | Done | Docker required on host |
| NFR-03 | Installable via pip install | Medium | Done | pyproject.toml configured |
| NFR-04 | Provider interface abstracted (LLMProvider ABC) | Medium | Done | New providers require only a new class |
| NFR-05 | All Docker operations via Docker SDK | Medium | Done | No shell exec of docker CLI |

**6. Constraints & Limits**

| REQ ID | Constraint | Value | Configurable |
|--------|-----------|-------|--------------|
| CON-01 | Maximum files per query | 5 | No (hard limit) |
| CON-02 | Maximum simultaneous providers | 3 | No |
| CON-03 | Container execution timeout | 120s | Yes (config.toml) |
| CON-04 | LLM API call timeout | 150s | Yes (config.toml) |
| CON-05 | Container memory limit | 2GB | Yes (config.toml) |
| CON-06 | Container CPU limit | 2 cores | Yes (config.toml) |
| CON-07 | Container network access | Disabled | No (security constraint) |
| CON-08 | Original repo modification | Never | No |

**7. Product Roadmap**

**v1.0 — MVP (Current — Complete)**

-   Core parallel LLM query pipeline (Claude Sonnet 4.5, GPT-4o, Gemini 2.5 Flash).

-   Manual file selection with smart filename resolution.

-   Token counting and cost estimation with confirmation gate.

-   Docker-based isolated execution per LLM response.

-   Generic test output parsing (pass/fail/error counts).

-   Synthesis Layer — blind evaluation recommending best solution.

-   CLI interface with `--verbose` flag and `--models` selection.

**v1.5 — Developer Experience**

-   Web UI with side-by-side visual diff viewer.

-   File Selection Assistant — LLM-driven file suggestion using
    signature extraction with hard confirmation gate.

-   Dedicated Results Renderer module.

-   Git repository URL support.

-   Query history and result persistence.

-   Additional LLM providers: Mistral, DeepSeek, Groq/Llama.

**v2.0 — Execution Feedback Loop Agent**

-   Each LLM iterates on its own solution using Docker test output
    as feedback (max 3 iterations).

-   Per-query cost ceiling that halts iteration.

-   Full conversation history across iterations.

**v2.5 and Beyond**

-   VM-based execution support.

-   VS Code extension integration.

-   Team and org mode with shared API key management.

**8. Tech Stack (Implemented)**

| Component | Technology | Notes |
|-----------|-----------|-------|
| Language | Python 3.11+ | Strong async support |
| LLM SDKs | anthropic, openai, google-genai | Official provider SDKs |
| Async | asyncio | Parallel fan-out |
| Docker | docker Python SDK | No shell exec |
| Token counting | tiktoken (cl100k_base) | All providers |
| CLI | Typer | Interactive prompts |
| Config | tomllib + tomli_w | TOML format |
| Diff | difflib | Unified diff |
