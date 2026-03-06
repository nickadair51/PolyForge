**POLYFORGE**

System Architecture Document

*MVP v1.0 • Internal Engineering Reference*

Draft • March 5, 2026

**1. Architecture Overview**

PolyForge is structured as a sequential pipeline with a parallel
execution core. At a high level, a single developer query enters the
pipeline, fans out to N LLM providers simultaneously, reconverges when
all providers have responded (or timed out), and then fans out again to
N Docker containers for isolated code execution. Results are collected,
synthesized, and returned to the developer.

The architecture is deliberately layered --- each layer has a single
responsibility and communicates with adjacent layers through
well-defined interfaces. This makes individual components testable in
isolation and allows new LLM providers or execution backends to be added
without touching the core pipeline.

**2. End-to-End Pipeline**

The following describes the complete lifecycle of a single developer
query through the PolyForge system.

**2.1 Pipeline Stages**

> ┌─────────────────────────────────────────────────────────┐
>
> │ Developer (CLI) │
>
> └───────────────────────────┬─────────────────────────────┘
>
> │ \--repo, \--question, \--models
>
> ▼
>
> ┌─────────────────────────────────────────────────────────┐
>
> │ CLI Entry Point │
>
> │ (typer, argument validation) │
>
> └───────────────────────────┬─────────────────────────────┘
>
> │
>
> ▼
>
> ┌─────────────────────────────────────────────────────────┐
>
> │ File Selection Assistant │
>
> │ scan signatures → LLM suggests files → show to dev │
>
> │ │
>
> │ ████████████ HARD CONFIRMATION GATE ████████████ │
>
> │ Developer must type \'yes\' --- nothing proceeds │
>
> │ until files are explicitly confirmed │
>
> └───────────────────────────┬─────────────────────────────┘
>
> │ confirmed files (max 5)
>
> ▼
>
> ┌─────────────────────────────────────────────────────────┐
>
> │ Token Counter + Cost Estimate │
>
> │ Developer confirms cost before proceeding │
>
> └───────────────────────────┬─────────────────────────────┘
>
> │
>
> ▼
>
> ┌─────────────────────────────────────────────────────────┐
>
> │ Orchestrator │
>
> │ (pipeline coordinator, state mgmt) │
>
> └───────────────────────────┬─────────────────────────────┘
>
> │
>
> ▼
>
> ┌─────────────────────────────────────────────────────────┐
>
> │ LLM Provider Layer │
>
> │ ┌───────────┐ ┌───────────┐ ┌───────────┐ │
>
> │ │ Claude │ │ GPT-4o │ │ Gemini │ async │
>
> │ │ Provider │ │ Provider │ │ Provider │ parallel│
>
> │ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ │
>
> └──────────┼──────────────┼───────────────┼──────────────┘
>
> │ │ │
>
> └──────────────┴───────────────┘
>
> │ N LLMResponse objects
>
> ▼
>
> ┌─────────────────────────────────────────────────────────┐
>
> │ Patch Application Layer │
>
> │ parse response → create snapshot → apply file changes │
>
> └───────────────────────────┬─────────────────────────────┘
>
> │ N repo snapshots
>
> ▼
>
> ┌─────────────────────────────────────────────────────────┐
>
> │ Docker Execution Layer │
>
> │ ┌───────────┐ ┌───────────┐ ┌───────────┐ │
>
> │ │Container 1│ │Container 2│ │Container 3│ async │
>
> │ │ (claude) │ │ (gpt) │ │ (gemini) │ parallel │
>
> │ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ │
>
> └─────────┼──────────────┼───────────────┼───────────────┘
>
> │ │ │
>
> └──────────────┴───────────────┘
>
> │ N ExecutionResult objects
>
> ▼
>
> ┌─────────────────────────────────────────────────────────┐
>
> │ Synthesis Layer │
>
> │ (reads all results, picks best solution) │
>
> └───────────────────────────┬─────────────────────────────┘
>
> │
>
> ▼
>
> ┌─────────────────────────────────────────────────────────┐
>
> │ Results Renderer │
>
> │ (ranked display, diffs, cost summary) │
>
> └─────────────────────────────────────────────────────────┘

**2.2 Fan-Out / Fan-In Pattern**

PolyForge uses a fan-out / fan-in pattern twice in the pipeline.
Understanding this pattern is central to understanding the architecture.

-   **LLM Queries --- the orchestrator fires N async LLM API calls
    simultaneously using asyncio.gather(). All providers receive the
    same prompt at the same time.** Fan-Out 1:

-   **LLM Results --- asyncio.gather() with return_exceptions=True
    reconverges all responses. Failed or timed-out providers are
    captured as exceptions rather than crashing the pipeline.** Fan-In
    1:

-   **Docker Execution --- once patches are applied, N containers are
    spun up simultaneously, one per provider response.** Fan-Out 2:

-   **Execution Results --- all container outputs are collected once all
    containers finish or hit their timeout.** Fan-In 2:

*The two fan-out stages are sequential, not nested. Docker execution
only begins after all LLM responses are collected. This is intentional
--- patch application requires the complete LLM response before a
snapshot can be created.*

**3. Component Breakdown**

PolyForge is composed of 9 distinct components. Each has a single
well-defined responsibility and communicates with other components
through typed data objects rather than shared state.

  ------------------------------------------------------------------------
  **Component**   **Responsibility**             **Key Interfaces**
  --------------- ------------------------------ -------------------------
  CLI Entry Point Parses developer arguments,    Receives: sys.argv.
                  validates inputs, initializes  Emits: QueryRequest
                  config, and hands off to the   object.
                  Orchestrator.                  

  Orchestrator    Coordinates the full pipeline. Receives: QueryRequest.
                  Owns the execution order,      Emits: FinalResult. Calls
                  manages failure handling and   all other components.
                  retries, and passes data       
                  between layers.                

  Repo Manager    Scans repository structure,    Receives: repo path,
                  creates isolated snapshots,    LLMResponse. Emits:
                  applies LLM patches to         RepoSnapshot,
                  snapshots, generates diffs,    PatchResult.
                  and cleans up workspaces.      

  Token Counter   Computes token counts for      Receives: file list,
                  selected files and estimates   selected models. Emits:
                  per-model API cost in real     TokenEstimate with
                  time as file selection         per-model cost breakdown.
                  changes.                       

  File Selection  Extracts structural signatures Receives: repo path,
  Assistant       from repo files, calls an LLM  question. Emits:
                  to recommend relevant files    FileSelectionResult with
                  based on the question,         confirmed file paths.
                  presents suggestions to        Blocks pipeline until
                  developer, and enforces a hard developer confirms.
                  confirmation gate before       
                  anything else proceeds.        

  LLM Provider    Abstracts all three LLM        Receives: LLMRequest.
  Layer           providers behind a common      Emits: LLMResponse or
                  interface. Each provider       LLMFailure.
                  implementation handles auth,   
                  request formatting, response   
                  parsing, timeout enforcement,  
                  and one retry on failure.      

  Docker Executor Creates ephemeral containers   Receives: RepoSnapshot,
                  per snapshot, mounts the       ProjectType. Emits:
                  snapshot as a volume, runs     ExecutionResult.
                  build and test commands,       
                  enforces resource limits and   
                  timeouts, captures output, and 
                  cleans up containers.          

  Synthesis Agent Reads all LLM responses and    Receives: list of
                  execution results, identifies  ExecutionResult. Emits:
                  the best solution with         SynthesisResult.
                  justification, flags code      
                  quality concerns, and handles  
                  the case where no solution     
                  passes.                        

  Results         Formats and displays the       Receives: FinalResult.
  Renderer        ranked comparison, diffs,      Emits: terminal output
                  synthesis recommendation, and  only.
                  final cost summary to the      
                  developer in the terminal.     
  ------------------------------------------------------------------------

**4. Core Data Objects**

Components communicate by passing typed Python dataclasses. No shared
mutable state exists between components --- all data flows forward
through the pipeline as immutable objects. The key data objects are
defined below.

**4.1 QueryRequest**

*Created by the CLI Entry Point. Represents everything the developer
submitted.*

> \@dataclass
>
> class QueryRequest:
>
> repo_path: str \# absolute path to local repo
>
> question: str \# developer\'s question
>
> selected_files: list\[str\] \# confirmed file paths (max 5)
>
> selected_models: list\[str\] \# e.g. \[\'claude\', \'gpt4o\',
> \'gemini\'\]
>
> query_id: str \# uuid, used for workspace path
>
> timestamp: datetime

**4.2 LLMRequest**

*Created by the Orchestrator. Sent to each provider in parallel.*

> \@dataclass
>
> class LLMRequest:
>
> query_id: str
>
> provider: str \# \'claude\' \| \'gpt4o\' \| \'gemini\'
>
> system_prompt: str \# standardized structured output prompt
>
> file_contents: dict\[str,str\] \# { filename: content }
>
> question: str

**4.3 LLMResponse**

*Returned by each provider. Contains the raw response and parsed file
changes.*

> \@dataclass
>
> class LLMResponse:
>
> query_id: str
>
> provider: str
>
> success: bool
>
> raw_text: str \# full model response text
>
> modified_files: dict\[str,str\] \# { filename: new_content } parsed
> from response
>
> input_tokens: int \# actual tokens used (for cost tracking)
>
> output_tokens: int
>
> latency_ms: int
>
> error: str \| None \# populated if success=False
>
> retry_attempted: bool

**4.4 RepoSnapshot**

*Created by Repo Manager. Represents a full copy of the repo with one
LLM\'s changes applied.*

> \@dataclass
>
> class RepoSnapshot:
>
> query_id: str
>
> provider: str
>
> snapshot_path: str \#
> \~/.polyforge/workspaces/\<query_id\>/\<provider\>/
>
> diff: str \# unified diff of changes applied
>
> project_type: str \# \'maven\' \| \'gradle\' \| \'npm\' \| \'python\'
> \| \'cargo\'

**4.5 ExecutionResult**

*Returned by Docker Executor. Contains everything that came out of the
container.*

> \@dataclass
>
> class ExecutionResult:
>
> query_id: str
>
> provider: str
>
> success: bool
>
> build_passed: bool
>
> tests_passed: int
>
> tests_failed: int
>
> tests_errored: int
>
> exit_code: int
>
> stdout: str
>
> stderr: str
>
> runtime_ms: int
>
> timed_out: bool
>
> error: str \| None

**4.6 SynthesisResult**

*Returned by the Synthesis Agent. The final recommendation shown at the
top of results.*

> \@dataclass
>
> class SynthesisResult:
>
> recommended_provider: str \| None \# None if all solutions failed
>
> justification: str
>
> quality_warnings: list\[str\] \# code smell flags
>
> failure_analysis: str \| None \# populated when no solution passes
>
> closest_provider: str \| None \# best failed attempt

**4.7 FinalResult**

*Assembled by the Orchestrator. The complete output passed to the
Results Renderer.*

> \@dataclass
>
> class FinalResult:
>
> query_id: str
>
> query_request: QueryRequest
>
> llm_responses: list\[LLMResponse\]
>
> execution_results: list\[ExecutionResult\]
>
> synthesis: SynthesisResult
>
> ranked_providers: list\[str\] \# ordered best to worst
>
> estimated_cost: float \# pre-query estimate
>
> actual_cost: float \# based on actual token usage
>
> total_duration_ms: int

**5. LLM Provider Layer**

The LLM Provider Layer abstracts all provider-specific logic behind a
common interface. The Orchestrator never calls a provider directly ---
it calls the interface, which dispatches to the correct implementation.
This means adding a new provider in the future requires only a new
class, with zero changes to the Orchestrator or any other component.

**5.1 Provider Interface**

> class LLMProvider(ABC):
>
> \@abstractmethod
>
> async def query(self, request: LLMRequest) -\> LLMResponse:
>
> \"\"\"Send query, enforce timeout, attempt one retry on failure.\"\"\"
>
> \...
>
> \@abstractmethod
>
> def count_tokens(self, text: str) -\> int:
>
> \"\"\"Estimate token count for cost calculation.\"\"\"
>
> \...
>
> \@abstractmethod
>
> def estimate_cost(self, input_tokens: int, output_tokens: int) -\>
> float:
>
> \"\"\"Return estimated cost in USD.\"\"\"
>
> \...

**5.2 Provider Implementations**

  -------------------- ----------------------------------------------------
  **ClaudeProvider**   Wraps anthropic SDK. Uses claude-sonnet-4-5 model.
                       Handles Anthropic-specific message format and
                       response parsing.

  **OpenAIProvider**   Wraps openai SDK. Uses gpt-4o model. Handles OpenAI
                       chat completion format.

  **GeminiProvider**   Wraps google-generativeai SDK. Uses gemini-1.5-pro
                       model. Handles Google-specific content format.
  -------------------- ----------------------------------------------------

**5.3 Retry & Timeout Logic**

Each provider implementation wraps its API call in the following logic.
This is implemented inside the provider, not the Orchestrator, so the
retry behavior is consistent regardless of which provider is called.

> async def query(self, request: LLMRequest) -\> LLMResponse:
>
> for attempt in range(2): \# max 2 attempts (1 retry)
>
> try:
>
> async with asyncio.timeout(60): \# 60s per attempt
>
> response = await self.\_call_api(request)
>
> return self.\_parse_response(response, retry_attempted=attempt\>0)
>
> except (asyncio.TimeoutError, APIError) as e:
>
> if attempt == 1: \# second failure --- give up
>
> return LLMResponse(success=False, error=str(e),
>
> retry_attempted=True, \...)
>
> await asyncio.sleep(2) \# brief pause before retry

**5.4 Structured Output Prompt**

All providers receive the same system prompt instructing them to return
changes in a parseable JSON format. Consistent structured output is
critical --- if the LLM returns prose-wrapped code, the patch
application layer cannot reliably extract file changes.

> SYSTEM_PROMPT = \"\"\"
>
> You are a code assistant. The user will provide source files and a
> question.
>
> Respond ONLY with a JSON object in the following format, with no text
> outside it:
>
> {
>
> \"explanation\": \"\<brief explanation of your changes\>\",
>
> \"modified_files\": {
>
> \"\<filename\>\": \"\<complete new file content\>\",
>
> \"\<filename\>\": \"\<complete new file content\>\"
>
> }
>
> }
>
> Return the COMPLETE file content for each modified file, not just the
> changed lines.
>
> Only include files you actually modified. Do not include unchanged
> files.
>
> \"\"\"

**6. Repo Manager**

The Repo Manager is responsible for everything related to the physical
codebase --- scanning it, snapshotting it, applying patches to
snapshots, generating diffs, and cleaning up workspaces after execution.

**6.1 Workspace Structure**

Every query gets a unique workspace under \~/.polyforge/workspaces/. The
workspace is created at the start of a query and torn down after results
are collected.

> \~/.polyforge/
>
> └── workspaces/
>
> └── \<query_id\>/ \# one per query (uuid)
>
> ├── snapshot_claude/ \# full repo + claude\'s changes
>
> ├── snapshot_gpt4o/ \# full repo + gpt\'s changes
>
> ├── snapshot_gemini/ \# full repo + gemini\'s changes
>
> └── meta.json \# query metadata, timestamps

**6.2 Project Type Detection**

The Repo Manager detects the project type by scanning the repository
root for known manifest files. The detected type drives Docker base
image selection and build command determination. Full detection logic
and the manifest priority order are documented in section 7.2.

**6.3 Snapshot Creation & Patch Application**

> def create_snapshot(repo_path, provider, query_id) -\> RepoSnapshot:
>
> snapshot_path =
> f\'\~/.polyforge/workspaces/{query_id}/snapshot\_{provider}\'
>
> shutil.copytree(repo_path, snapshot_path, \# full copy
>
> ignore=shutil.ignore_patterns(\'.git\',\'\*.pyc\'))
>
> return RepoSnapshot(snapshot_path=snapshot_path, \...)
>
> def apply_patch(snapshot: RepoSnapshot, response: LLMResponse) -\>
> PatchResult:
>
> for filename, new_content in response.modified_files.items():
>
> target = os.path.join(snapshot.snapshot_path, filename)
>
> if os.path.exists(target): \# only patch known files
>
> with open(target, \'w\') as f:
>
> f.write(new_content)
>
> diff = generate_diff(snapshot) \# unified diff for display
>
> return PatchResult(diff=diff, \...)

**7. Docker Executor**

The Docker Executor manages the full container lifecycle for each
provider snapshot --- image selection, container creation, execution,
output capture, and cleanup. All containers run in parallel using
asyncio, mirroring the LLM fan-out pattern.

Critically, the developer never configures Docker directly. PolyForge
handles all container setup automatically --- the only prerequisite is
that Docker Desktop (macOS) or Docker Engine (Linux) is installed and
running on the host machine.

**7.1 Developer Prerequisites**

PolyForge performs a Docker availability check at the very start of
every query --- before any LLM calls or file operations. If Docker is
not running, the developer receives a clear actionable error immediately
rather than a cryptic SDK failure deep in the pipeline.

> def check_docker_available():
>
> try:
>
> client = docker.from_env()
>
> client.ping() \# fails fast if Docker daemon is not running
>
> except DockerException:
>
> raise PolyForgeError(
>
> \'Docker is not running. \'
>
> \'Please start Docker Desktop and try again.\'
>
> )

  ------------------ ----------------------------------------------------
  **Developer        Docker Desktop (macOS) or Docker Engine (Linux) ---
  installs**         one time only

  **Developer        Nothing --- PolyForge handles all container setup
  configures**       

  **PolyForge        Image pulls, container creation, resource limits,
  handles**          cleanup
  ------------------ ----------------------------------------------------

**7.2 Project Type Detection**

Before a container can be configured, PolyForge must know what kind of
project it is working with. The Repo Manager scans the repository root
for known manifest files in priority order. The detected project type
drives every subsequent Docker decision --- base image, build command,
and test output parser.

> DETECTION_RULES = \[
>
> (\'pom.xml\', \'maven\'),
>
> (\'build.gradle\', \'gradle\'),
>
> (\'build.gradle.kts\', \'gradle\'),
>
> (\'package.json\', \'node\'),
>
> (\'requirements.txt\', \'python\'),
>
> (\'pyproject.toml\', \'python\'),
>
> (\'Cargo.toml\', \'rust\'),
>
> \]
>
> def detect_project_type(repo_path: str) -\> str:
>
> for filename, project_type in DETECTION_RULES:
>
> if os.path.exists(os.path.join(repo_path, filename)):
>
> return project_type
>
> raise UnknownProjectTypeError(
>
> \'Could not detect project type. \'
>
> \'Supported: Maven, Gradle, Node.js, Python, Rust. \'
>
> \'You can override this in \~/.polyforge/config.toml\'
>
> )

**7.3 Container Profiles**

Each detected project type maps to a pre-defined container profile.
These profiles are hardcoded by PolyForge --- the developer never writes
a Dockerfile or docker-compose.yml. The profile determines the Docker
base image, the build and test command, and which test output parser to
use.

> CONTAINER_PROFILES = {
>
> \'maven\': ContainerProfile(
>
> image = \'maven:3.9-openjdk-17\',
>
> build_cmd = \'mvn test -B\', \# -B = batch mode, no color codes
>
> test_parser = MavenOutputParser(),
>
> work_dir = \'/app\',
>
> ),
>
> \'gradle\': ContainerProfile(
>
> image = \'gradle:8-jdk17\',
>
> build_cmd = \'gradle test \--no-daemon\',
>
> test_parser = GradleOutputParser(),
>
> work_dir = \'/app\',
>
> ),
>
> \'node\': ContainerProfile(
>
> image = \'node:20-alpine\',
>
> build_cmd = \'npm ci && npm test\', \# ci = clean reproducible install
>
> test_parser = JestOutputParser(),
>
> work_dir = \'/app\',
>
> ),
>
> \'python\': ContainerProfile(
>
> image = \'python:3.11-slim\',
>
> build_cmd = \'pip install -r requirements.txt -q && pytest\',
>
> test_parser = PytestOutputParser(),
>
> work_dir = \'/app\',
>
> ),
>
> \'rust\': ContainerProfile(
>
> image = \'rust:1.75-slim\',
>
> build_cmd = \'cargo test\',
>
> test_parser = CargoOutputParser(),
>
> work_dir = \'/app\',
>
> ),
>
> }

**7.4 Build Command Resolution**

For most project types the build command from the profile is used
directly. However, two project types require additional inspection of
the project\'s manifest before the command can be finalized.

**Node.js --- Test Script Detection**

Not all Node projects define a \'test\' script in package.json.
PolyForge inspects the scripts block before assuming npm test will work.

> def resolve_node_cmd(repo_path: str) -\> str:
>
> with open(os.path.join(repo_path, \'package.json\')) as f:
>
> pkg = json.load(f)
>
> scripts = pkg.get(\'scripts\', {})
>
> if \'test\' in scripts:
>
> return \'npm ci && npm test\'
>
> raise NoTestCommandError(
>
> \"No \'test\' script found in package.json. \"
>
> \"Add one or specify a custom command in \~/.polyforge/config.toml\"
>
> )

**Python --- Dependency Manager Detection**

Python projects use a variety of dependency management tools. PolyForge
detects which one is in use and adjusts the install command accordingly.

> def resolve_python_cmd(repo_path: str) -\> str:
>
> def exists(f): return os.path.exists(os.path.join(repo_path, f))
>
> if exists(\'requirements.txt\'):
>
> install = \'pip install -r requirements.txt -q\'
>
> elif exists(\'pyproject.toml\'):
>
> install = \'pip install -e . -q\'
>
> elif exists(\'Pipfile\'):
>
> install = \'pip install pipenv -q && pipenv install\'
>
> else:
>
> install = \'\' \# no dependencies, run pytest directly
>
> return f\'{install} && pytest\'.strip(\' &&\')

**7.5 First-Run Image Pull**

Docker base images are pulled automatically on first use per project
type. After the initial pull the image is cached locally and all
subsequent queries are instant. PolyForge displays clear progress
messaging during the pull so the developer understands why the first
query takes longer.

> def ensure_image(project_type: str):
>
> image = CONTAINER_PROFILES\[project_type\].image
>
> try:
>
> client.images.get(image) \# already cached locally --- instant
>
> except ImageNotFound:
>
> \# First time for this project type --- pull and cache
>
> print(f\'\[PolyForge\] Pulling {image} (first time only)\...\')
>
> client.images.pull(image)
>
> print(f\'\[PolyForge\] Image cached. Future queries will be
> instant.\')

  -------------------------- ----------------------------------------------------
  **maven:3.9-openjdk-17**   \~500MB --- pulled once, cached permanently

  **gradle:8-jdk17**         \~450MB --- pulled once, cached permanently

  **node:20-alpine**         \~180MB --- pulled once, cached permanently

  **python:3.11-slim**       \~130MB --- pulled once, cached permanently

  **rust:1.75-slim**         \~240MB --- pulled once, cached permanently
  -------------------------- ----------------------------------------------------

**7.6 Container Configuration**

Every container is created with the same security and resource
constraints regardless of provider or project type. These values are all
configurable via \~/.polyforge/config.toml but have sensible defaults
that work for most projects.

  ------------------ ----------------------------------------------------
  **Base image**     Determined by project type detection (section 7.2)

  **Volume mount**   snapshot_path → /app (read-write)

  **Working          /app
  directory**        

  **Network**        Disabled entirely (network_disabled=True) ---
                     non-configurable security constraint

  **Memory limit**   2GB default (configurable: docker.memory_limit in
                     config.toml)

  **CPU limit**      2 cores default (configurable: docker.cpu_cores in
                     config.toml)

  **Execution        120 seconds default (configurable:
  timeout**          execution.docker_timeout_seconds)

  **Auto-remove**    True --- container deleted automatically on exit
  ------------------ ----------------------------------------------------

**7.7 Container Override via Config**

For projects that don\'t fit standard profiles --- unusual build tools,
non-standard JDK versions, custom test runners --- the developer can
override any profile setting in config.toml without touching Docker
directly.

> \# \~/.polyforge/config.toml
>
> \[project\]
>
> type = \'maven\' \# force if auto-detect fails
>
> test_cmd = \'mvn verify -B\' \# override default test command
>
> docker_image = \'maven:3.9-openjdk-21\' \# override JDK version

*This covers the edge cases that automatic detection cannot handle. The
developer specifies what to run --- not how to configure the container.
All security constraints (no network, resource limits) still apply
regardless of overrides.*

**7.8 Execution Flow**

> async def execute(snapshot: RepoSnapshot) -\> ExecutionResult:
>
> profile = CONTAINER_PROFILES\[snapshot.project_type\]
>
> cmd = resolve_build_cmd(snapshot) \# profile cmd + manifest inspection
>
> ensure_image(snapshot.project_type) \# pull if not cached
>
> container = client.containers.run(
>
> profile.image, cmd,
>
> volumes={snapshot.snapshot_path: {\'bind\': \'/app\', \'mode\':
> \'rw\'}},
>
> working_dir=\'/app\',
>
> network_disabled=True,
>
> mem_limit=\'2g\',
>
> nano_cpus=2_000_000_000,
>
> detach=True,
>
> auto_remove=False \# capture logs before removal
>
> )
>
> try:
>
> async with asyncio.timeout(120):
>
> result = await asyncio.to_thread(container.wait)
>
> stdout = container.logs(stdout=True, stderr=False).decode()
>
> stderr = container.logs(stdout=False, stderr=True).decode()
>
> return profile.test_parser.parse(result, stdout, stderr,
>
> snapshot.provider)
>
> except asyncio.TimeoutError:
>
> container.kill()
>
> return ExecutionResult(timed_out=True, success=False, \...)
>
> finally:
>
> container.remove(force=True)

**7.9 Test Result Parsing**

Each project type produces test output in a different format. The Docker
Executor includes a dedicated parser per project type that extracts
structured pass/fail counts from stdout.

  ------------------ ----------------------------------------------------
  **Maven**          Parses \'Tests run: X, Failures: Y, Errors: Z\' from
                     Surefire output

  **Gradle**         Parses \'X tests completed, Y failed\' from Gradle
                     test output

  **pytest**         Parses \'X passed, Y failed, Z error\' from pytest
                     summary line

  **npm/jest**       Parses \'Tests: X passed, Y failed\' from Jest
                     output

  **cargo**          Parses \'test result: ok. X passed; Y failed\' from
                     cargo test output
  ------------------ ----------------------------------------------------

**8. LLM-Powered Pipeline Components**

PolyForge includes two LLM-powered components beyond the main provider
queries --- the File Selection Assistant and the Synthesis Layer. Both
make focused single LLM calls with specialized prompts. Neither is an
autonomous agent --- they do not loop, do not use tools, and do not make
decisions on the developer\'s behalf. They are more accurately described
as smart pipeline stages that use LLM reasoning to reduce friction and
improve output quality.

**8.1 File Selection Assistant**

The File Selection Assistant is the first thing that runs when a
developer submits a query. Its purpose is to help the developer identify
which files to send to the main LLM providers --- because sending the
wrong files wastes money and produces garbage results. It is positioned
before token counting, before model selection, and before any cost is
incurred.

The critical design decision here is that the assistant sends file
signatures --- not just file names and not full file contents. Generic
file names like Manager.java or Handler.java provide no useful signal.
Full file contents are too expensive at this pre-confirmation stage.
Signatures --- class names, method signatures, package paths,
implemented interfaces --- give the LLM meaningful structural context at
roughly 15-30 lines per file regardless of actual file length.

**Signature Extraction**

> def extract_signatures(file_path: str, project_type: str) -\> str:
>
> \"\"\"
>
> Extracts structural skeleton from a source file.
>
> Returns \~15-30 lines regardless of actual file length.
>
> \"\"\"
>
> if project_type == \'maven\' or project_type == \'gradle\':
>
> return extract_java_signatures(file_path)
>
> \# Extracts: package, imports summary, class declaration,
>
> \# implements/extends, all public method signatures
>
> if project_type == \'python\':
>
> return extract_python_signatures(file_path)
>
> \# Extracts: module docstring, class definitions,
>
> \# all function signatures with type hints
>
> if project_type == \'node\':
>
> return extract_js_signatures(file_path)
>
> \# Extracts: exports, class/function declarations

Example --- a 400-line Java file reduces to this before being sent to
the assistant:

> // com.company.payments.TransactionProcessor.java
>
> package com.company.payments;
>
> public class TransactionProcessor implements PaymentHandler, Auditable
> {
>
> public ProcessResult processTransaction(Transaction t)
>
> public void validatePayment(Payment p) throws ValidationException
>
> public RefundResult refundTransaction(String transactionId)
>
> private void auditLog(String event, Transaction t)
>
> }

**Hard Confirmation Gate**

After the assistant returns its suggestions, a hard confirmation gate
blocks all further execution. The developer must explicitly confirm the
file selection before a single token is sent to any main LLM provider.
This gate cannot be bypassed --- it is a deliberate MVP constraint that
protects against expensive pipeline runs on the wrong files.

> ┌─────────────────────────────────────────────────────────┐
>
> │ File Selection Assistant Suggestions │
>
> │ │
>
> │ ✓ com/payments/TransactionProcessor.java │
>
> │ → Processes and validates payment transactions │
>
> │ → \~2,400 tokens │
>
> │ │
>
> │ ✓ com/payments/PaymentValidator.java │
>
> │ → Validates payment data before processing │
>
> │ → \~1,800 tokens │
>
> │ │
>
> │ ? com/auth/SessionManager.java │
>
> │ → Possibly related to payment session handling │
>
> │ → \~3,100 tokens │
>
> │ │
>
> │ Selected models: Claude ✓ GPT-4o ✓ Gemini ✗ │
>
> │ Total tokens: \~7,200 │
>
> │ Estimated cost: \~\$0.08 │
>
> │ │
>
> │ \[a\] Add file \[r\] Remove file \[m\] Select manually │
>
> │ │
>
> │ Confirm these files? (yes/no): \_ │
>
> └─────────────────────────────────────────────────────────┘

**Assistant Implementation**

> async def run_file_selection(repo_path, question) -\>
> FileSelectionResult:
>
> \# Step 1: Extract signatures from all files
>
> signatures = {}
>
> for file in scan_repo(repo_path):
>
> signatures\[file.qualified_path\] = extract_signatures(file)
>
> \# Step 2: Single LLM call with signatures + question
>
> response = await claude_provider.query(LLMRequest(
>
> system_prompt = FILE_SELECTION_SYSTEM_PROMPT,
>
> question = build_selection_prompt(signatures, question),
>
> file_contents = {} \# no full file contents at this stage
>
> ))
>
> \# Step 3: Parse structured response
>
> \# Response JSON: { files: \[{path, rationale, confidence}\] }
>
> suggestions = parse_file_selection(response.raw_text)
>
> \# Step 4: Hard confirmation gate --- blocks until developer confirms
>
> confirmed = await cli.confirm_file_selection(
>
> suggestions = suggestions,
>
> repo_path = repo_path,
>
> allow_edit = True \# developer can add/remove/replace
>
> )
>
> \# Nothing downstream runs until this returns
>
> return confirmed

*Estimated cost: \~\$0.01-0.02 per query using signature extraction.
Higher than the original file-tree-only estimate but substantially more
accurate --- worth the small additional cost to avoid the much larger
cost of a wasted full pipeline run on wrong files.*

**8.2 Synthesis Layer**

The Synthesis Layer runs after all execution results are collected. It
is a single LLM call --- not a loop, not an agent --- that reads all
provider responses and Docker execution outcomes and produces one clear
recommendation. It is the last processing stage before results are
rendered to the developer.

> async def run_synthesis(results: list\[ExecutionResult\],
>
> responses: list\[LLMResponse\]) -\> SynthesisResult:
>
> context = build_synthesis_context(results, responses)
>
> \# context includes: each model\'s explanation, diff, build status,
>
> \# test counts, stdout/stderr snippets
>
> response = await claude_provider.query(LLMRequest(
>
> system_prompt=SYNTHESIS_SYSTEM_PROMPT,
>
> question=context,
>
> file_contents={}
>
> ))
>
> \# Response is JSON: { recommended_provider, justification,
>
> \# quality_warnings, failure_analysis }
>
> return parse_synthesis(response.raw_text)

*Like the File Selection Assistant, the Synthesis Layer always uses
Claude Sonnet. It is a single shot with no iteration --- it reads all
results once and produces one recommendation.*

**9. Orchestrator**

The Orchestrator is the central coordinator. It owns the pipeline
execution order, wires components together, and manages the overall
state of a query from intake to final result. It does not implement any
business logic itself --- it delegates entirely to the components it
coordinates.

**9.1 Orchestrator Execution Sequence**

> async def run(request: QueryRequest) -\> FinalResult:
>
> \# 1. Docker availability check --- fail fast before any cost
>
> check_docker_available()
>
> \# 2. File Selection Assistant + hard confirmation gate
>
> \# Nothing proceeds until developer explicitly confirms files
>
> confirmed_files = await file_selection_assistant.run(
>
> repo_path = request.repo_path,
>
> question = request.question
>
> ) \# blocks here until developer types \'yes\'
>
> \# 3. Token count + cost estimate → developer confirms cost
>
> estimate = token_counter.estimate(confirmed_files,
> request.selected_models)
>
> await cli.confirm_cost(estimate) \# second confirmation: cost
>
> \# 4. Build LLM requests
>
> llm_requests = \[build_llm_request(request, confirmed_files, model)
>
> for model in request.selected_models\]
>
> \# 5. Fan-out to LLM providers (parallel)
>
> llm_responses = await asyncio.gather(
>
> \*\[provider_map\[r.provider\].query(r) for r in llm_requests\],
>
> return_exceptions=True
>
> )
>
> \# 6. Create snapshots + apply patches
>
> snapshots = \[\]
>
> for response in successful(llm_responses):
>
> snapshot = repo_manager.create_snapshot(request.repo_path,
>
> response.provider,
>
> request.query_id)
>
> repo_manager.apply_patch(snapshot, response)
>
> snapshots.append(snapshot)
>
> \# 7. Fan-out to Docker containers (parallel)
>
> exec_results = await asyncio.gather(
>
> \*\[docker_executor.execute(s) for s in snapshots\],
>
> return_exceptions=True
>
> )
>
> \# 8. Synthesis Layer --- single LLM call, picks best result
>
> synthesis = await synthesis_layer.run(exec_results, llm_responses)
>
> \# 9. Rank + assemble final result
>
> ranked = rank_results(exec_results)
>
> final = assemble_final_result(request, llm_responses, exec_results,
>
> synthesis, ranked, estimate)
>
> \# 10. Cleanup workspaces
>
> repo_manager.cleanup(request.query_id)
>
> return final

**10. Project Directory Structure**

The recommended source layout for the PolyForge Python package.

> polyforge/
>
> ├── pyproject.toml \# package config, dependencies
>
> ├── README.md
>
> ├── polyforge/
>
> │ ├── \_\_init\_\_.py
>
> │ ├── cli.py \# Typer CLI entry point
>
> │ ├── orchestrator.py \# pipeline coordinator
>
> │ ├── models.py \# all dataclasses (QueryRequest, LLMResponse, etc)
>
> │ ├── config.py \# config loading (\~/.polyforge/config.toml)
>
> │ │
>
> │ ├── providers/ \# LLM Provider Layer
>
> │ │ ├── \_\_init\_\_.py
>
> │ │ ├── base.py \# LLMProvider ABC
>
> │ │ ├── claude.py \# ClaudeProvider
>
> │ │ ├── openai.py \# OpenAIProvider
>
> │ │ └── gemini.py \# GeminiProvider
>
> │ │
>
> │ ├── llm_components/ \# LLM-Powered Pipeline Components
>
> │ │ ├── \_\_init\_\_.py
>
> │ │ ├── file_selection.py \# FileSelectionAssistant
>
> │ │ └── synthesis.py \# SynthesisLayer
>
> │ │
>
> │ ├── repo/ \# Repo Manager
>
> │ │ ├── \_\_init\_\_.py
>
> │ │ ├── manager.py \# RepoManager
>
> │ │ ├── scanner.py \# file tree scanning
>
> │ │ └── detector.py \# project type detection
>
> │ │
>
> │ ├── docker/ \# Docker Executor
>
> │ │ ├── \_\_init\_\_.py
>
> │ │ ├── executor.py \# DockerExecutor
>
> │ │ └── parsers.py \# per-project test output parsers
>
> │ │
>
> │ ├── tokens/ \# Token Counter
>
> │ │ ├── \_\_init\_\_.py
>
> │ │ └── counter.py \# TokenCounter
>
> │ │
>
> │ └── renderer/ \# Results Renderer
>
> │ ├── \_\_init\_\_.py
>
> │ └── renderer.py \# terminal output formatting
>
> │
>
> └── tests/
>
> ├── test_providers.py
>
> ├── test_repo_manager.py
>
> ├── test_docker_executor.py
>
> ├── test_agents.py
>
> └── test_orchestrator.py

**11. Configuration**

PolyForge reads configuration from two sources: environment variables
for secrets (API keys), and a TOML file for behavioral settings. The
config file is created automatically on first run with sensible
defaults.

**11.1 Environment Variables**

  ----------------------- ----------------------------------------------------
  **ANTHROPIC_API_KEY**   Required if Claude is selected as a provider

  **OPENAI_API_KEY**      Required if GPT-4o is selected as a provider

  **GOOGLE_API_KEY**      Required if Gemini is selected as a provider
  ----------------------- ----------------------------------------------------

**11.2 Config File (\~/.polyforge/config.toml)**

> \[execution\]
>
> llm_timeout_seconds = 60
>
> docker_timeout_seconds = 120
>
> max_files = 5
>
> cost_warning_threshold = 0.50 \# warn if estimated cost exceeds this
>
> \[docker\]
>
> memory_limit = \'2g\'
>
> cpu_cores = 2
>
> \[llm_components\]
>
> file_selection_enabled = true
>
> synthesis_enabled = true
>
> \[workspace\]
>
> base_path = \'\~/.polyforge/workspaces\'
>
> auto_cleanup = true
