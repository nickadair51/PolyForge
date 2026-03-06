**POLYFORGE**

Multi-LLM Code Review & Execution Platform

*Product Requirements Document • MVP v1.0*

Draft • March 5, 2026

**1. Project Overview**

PolyForge is a developer tool that allows engineers to ask questions
about their code across multiple large language models simultaneously.
Rather than querying a single LLM and accepting one answer, PolyForge
fans out the question to multiple providers in parallel, applies each
LLM\'s suggested code changes to an isolated copy of the repository,
executes the modified code inside a sandboxed Docker container, and
returns a ranked comparison of results --- showing not just what each
model suggested, but whether the suggestion actually works.

The MVP targets individual developers who want fast, validated,
multi-perspective code assistance without the cost and complexity of a
full agentic pipeline.

**2. Goals & Non-Goals**

**2.1 Goals**

-   Allow developers to query up to 3 LLMs simultaneously with a single
    question about their code.

-   Apply each LLM\'s suggested changes to an isolated copy of the
    codebase and execute them in a Docker container.

-   Return a side-by-side comparison of LLM responses alongside
    execution results (build success, test pass/fail, runtime errors).

-   Give developers full control over which models are queried per
    question to manage cost.

-   Display a real-time token counter and estimated cost breakdown per
    model before submission.

-   Hard cap file selection at 5 files per query to enforce cost
    predictability.

**2.2 Non-Goals (MVP)**

-   No web UI --- CLI interface only for v1.

-   No authentication or multi-user support.

-   No persistent storage of query history.

-   No support for VM-based execution (Docker only for MVP).

-   No automatic file relevance detection --- developer manually selects
    files.

-   No fine-tuning or custom model training.

**3. Core User Flow**

The end-to-end flow a developer experiences in the MVP:

-   Developer points the tool at their local repository directory.

-   Developer selects up to 5 files relevant to their question.

-   Tool computes token count for selected files and displays estimated
    cost per model.

-   Developer selects which LLMs to query (Claude, GPT-4o, Gemini ---
    any combination).

-   Developer types their question.

-   Tool fans out the question + selected file contents to each chosen
    LLM simultaneously.

-   Each LLM returns suggested code changes.

-   Tool parses each LLM response, extracts the modified file content,
    and applies changes to a snapshot of the full repo.

-   Tool spins up one Docker container per LLM response, each with the
    full modified repo.

-   Each container runs the project\'s build and test suite.

-   Tool collects results from all containers and displays a ranked
    comparison.

**4. Functional Requirements**

**4.1 Codebase Ingestion**

Requirements related to how the tool ingests and manages the
developer\'s repository.

  --------------------------------------------------------------------------------
  **REQ   **Requirement**                  **Priority**   **Notes**
  ID**                                                    
  ------- -------------------------------- -------------- ------------------------
  FR-01   The tool shall accept a local    High           CLI flag: \--repo
          directory path as the repository                \<path\>
          root.                                           

  FR-02   The tool shall recursively scan  High           Exclude .git,
          the repository and present a                    node_modules, build/
          file tree for selection.                        dirs by default

  FR-03   The tool shall allow the         High           Hard cap enforced at
          developer to select between 1                   selection time
          and 5 files from the file tree.                 

  FR-04   The tool shall auto-detect the   High           Determines Docker base
          project type by scanning for                    image and build/test
          pom.xml, package.json,                          commands
          requirements.txt, build.gradle,                 
          Cargo.toml.                                     

  FR-05   The tool shall create a full     High           Original repo must never
          snapshot (copy) of the repo                     be modified
          before applying any LLM changes.                
  --------------------------------------------------------------------------------

**4.2 Token Counter & Cost Estimation**

Requirements related to real-time cost transparency before query
submission.

  --------------------------------------------------------------------------------
  **REQ   **Requirement**                  **Priority**   **Notes**
  ID**                                                    
  ------- -------------------------------- -------------- ------------------------
  FR-06   The tool shall compute the       High           Use tiktoken or
          approximate token count for                     equivalent tokenizer
          selected files as files are                     
          added or removed.                               

  FR-07   The tool shall display per-model High           Claude, GPT-4o, Gemini
          estimated cost based on current                 pricing
          token count and each provider\'s                
          published input pricing.                        

  FR-08   The tool shall display total     High           Developer must confirm
          estimated cost across all                       before proceeding
          selected models before the                      
          developer submits.                              

  FR-09   The tool shall warn the          Medium         Configurable in settings
          developer if estimated cost per                 file
          query exceeds a configurable                    
          threshold (default: \$0.50).                    

  FR-10   Token count and cost display     Medium         No manual refresh
          shall update in real time as                    required
          file selection or model                         
          selection changes.                              
  --------------------------------------------------------------------------------

**4.3 Model Selection**

Requirements related to which LLMs the developer can choose to query.

  --------------------------------------------------------------------------------
  **REQ   **Requirement**                  **Priority**   **Notes**
  ID**                                                    
  ------- -------------------------------- -------------- ------------------------
  FR-11   The tool shall support querying  High           3 providers in MVP
          Anthropic Claude (Sonnet),                      
          OpenAI GPT-4o, and Google Gemini                
          1.5 Pro.                                        

  FR-12   The developer shall be able to   High           Not required to query
          select any combination of 1 to 3                all 3
          models per query.                               

  FR-13   Each model\'s API key shall be   High           Never hardcoded
          configurable via a local config                 
          file or environment variables.                  

  FR-14   The tool shall gracefully handle Medium         Show clear message to
          the case where a model\'s API                   developer
          key is not configured and                       
          exclude it from available                       
          options.                                        
  --------------------------------------------------------------------------------

**4.4 LLM Query & Response Handling**

Requirements related to how queries are sent and responses are
processed.

  --------------------------------------------------------------------------------
  **REQ   **Requirement**                  **Priority**   **Notes**
  ID**                                                    
  ------- -------------------------------- -------------- ------------------------
  FR-15   The tool shall send queries to   High           Not sequential --- all
          all selected LLMs simultaneously                fire at once
          (parallel async calls).                         

  FR-16   The system prompt shall instruct High           Ensures parseable,
          each LLM to return modified file                patch-applicable
          contents in a structured JSON                   responses
          format specifying filename and                  
          full file content.                              

  FR-17   The tool shall enforce a         High           One slow model should
          per-provider timeout of 60                      not block the rest
          seconds. Timed-out providers                    
          shall be marked as failed                       
          without blocking results from                   
          others.                                         

  FR-18   The tool shall parse each LLM    High           Handle malformed
          response and extract modified                   responses gracefully
          file contents.                                  

  FR-19   If an LLM response cannot be     Medium         Still show the raw
          parsed into a valid file patch,                 response to the
          the tool shall flag that                        developer
          model\'s result as unparseable                  
          and skip execution for it.                      
  --------------------------------------------------------------------------------

**4.5 Code Patch Application**

Requirements related to applying LLM-suggested changes to repository
snapshots.

  --------------------------------------------------------------------------------
  **REQ   **Requirement**                  **Priority**   **Notes**
  ID**                                                    
  ------- -------------------------------- -------------- ------------------------
  FR-20   The tool shall create one        High           N models = N repo
          isolated copy of the full                       snapshots
          repository per LLM response.                    

  FR-21   The tool shall apply each LLM\'s High           Only overwrite files the
          suggested file changes to its                   LLM returned
          corresponding repo snapshot.                    

  FR-22   Files not referenced in the LLM  High           Partial changes are
          response shall remain unchanged                 valid
          in the snapshot.                                

  FR-23   The tool shall log a diff of     Medium         Standard unified diff
          changes applied to each snapshot                format
          for developer review.                           
  --------------------------------------------------------------------------------

**4.6 Docker Execution**

Requirements related to spinning up and running containers per LLM
result.

  --------------------------------------------------------------------------------
  **REQ   **Requirement**                  **Priority**   **Notes**
  ID**                                                    
  ------- -------------------------------- -------------- ------------------------
  FR-24   The tool shall spin up one       High           Containers must be fully
          ephemeral Docker container per                  isolated from each other
          LLM response, mounting the                      
          corresponding modified repo                     
          snapshot.                                       

  FR-25   The tool shall select the        High           Determined from FR-04
          appropriate Docker base image                   project detection
          based on detected project type                  
          (e.g., maven:3.9-openjdk-17,                    
          python:3.11-slim,                               
          node:20-alpine).                                

  FR-26   The tool shall run the           High           Build + test in a single
          project\'s build command inside                 pass
          the container (e.g., mvn test,                  
          pytest, npm test).                              

  FR-27   Each container shall be subject  High           Prevent runaway builds
          to a configurable execution                     
          timeout (default: 120 seconds).                 

  FR-28   Containers shall have no         High           Security --- prevent
          outbound network access during                  LLM-generated code from
          execution.                                      making network calls

  FR-29   Containers shall be subject to   High           Configurable via
          resource limits: max 2 CPU cores                settings file
          and 2GB RAM by default.                         

  FR-30   The tool shall capture stdout,   High           All collected for
          stderr, exit code, and test                     results display
          results from each container.                    

  FR-31   All containers and temporary     High           No leftover containers
          repo snapshots shall be cleaned                 or temp files
          up automatically after results                  
          are collected.                                  
  --------------------------------------------------------------------------------

**4.7 Results Display**

Requirements related to how results are presented to the developer after
execution.

  --------------------------------------------------------------------------------
  **REQ   **Requirement**                  **Priority**   **Notes**
  ID**                                                    
  ------- -------------------------------- -------------- ------------------------
  FR-32   The tool shall display results   High           Tabular format in CLI
          for all LLMs side by side in the                
          terminal once all containers                    
          have completed or timed out.                    

  FR-33   For each LLM result, the tool    High           Core comparison data
          shall display: model name, build                
          status (pass/fail), test results                
          (X passed / Y failed), exit                     
          code, and any runtime                           
          exceptions.                                     

  FR-34   The tool shall display the diff  High           Unified diff format
          of changes each LLM applied so                  
          the developer can see what was                  
          modified.                                       

  FR-35   The tool shall display the raw   Medium         Truncated to 500 chars
          LLM response text for each model                in summary, full on
          so the developer can read the                   request
          explanation.                                    

  FR-36   The tool shall rank results by:  Medium         Best result shown first
          (1) all tests pass, (2) build                   
          succeeds but tests fail, (3)                    
          build fails, (4) parse/timeout                  
          failure.                                        

  FR-37   The tool shall display the       Medium         Based on actual token
          actual cost incurred for the                    usage from API responses
          query after completion alongside                
          the pre-query estimate.                         
  --------------------------------------------------------------------------------

**4.8 File Selection Assistant**

The File Selection Assistant is an LLM-powered interactive file picker
positioned at the very beginning of the pipeline --- before token
counting, before LLM calls, and before any cost is incurred. Rather than
being an autonomous agent that makes decisions, it functions as a smart
search tool that surfaces file candidates based on the developer\'s
question and the structural signatures of the codebase. The developer
retains full control and must explicitly confirm the final file
selection before anything proceeds.

A hard confirmation gate sits immediately after the assistant\'s
suggestions are shown. This gate cannot be bypassed --- no LLM calls, no
Docker execution, and no cost is incurred until the developer has
reviewed and confirmed the exact files they want to send. This protects
against the worst-case scenario of expensive pipeline runs producing
garbage results because the wrong files were selected.

*Because generic file names alone provide insufficient signal for
accurate recommendations, the assistant sends file signatures --- class
names, method signatures, package paths --- rather than just file names.
This gives the LLM meaningful structural context at a fraction of the
cost of sending full file contents.*

  --------------------------------------------------------------------------------
  **REQ   **Requirement**                  **Priority**   **Notes**
  ID**                                                    
  ------- -------------------------------- -------------- ------------------------
  AG-01   The File Selection Assistant     High           Positioned at CLI entry
          shall be the first step in the                  --- nothing else starts
          pipeline, running before token                  until files are
          estimation, model selection                     confirmed
          confirmation, and all LLM                       
          provider calls.                                 

  AG-02   The assistant shall extract      High           Balances context quality
          structural signatures from each                 vs token cost. \~15-30
          file --- class names, method                    lines per file
          signatures, package paths, and                  regardless of file
          implemented interfaces ---                      length
          rather than sending file names                  
          alone or full file contents.                    

  AG-03   The assistant shall send         High           Hard cap matches the
          extracted signatures alongside                  global 5-file limit
          the developer\'s question to an                 
          LLM and return up to 5                          
          recommended files with a brief                  
          rationale for each.                             

  AG-04   After receiving suggestions, the High           Developer sees exactly
          developer shall be presented                    what will be sent before
          with an interactive confirmation                committing
          screen showing each suggested                   
          file, its rationale, and its                    
          approximate token count.                        

  AG-05   A hard confirmation gate shall   High           Cannot be bypassed ---
          block all pipeline execution                    this is a deliberate MVP
          until the developer explicitly                  constraint
          confirms the file selection by                  
          typing \'yes\' or pressing a                    
          confirm key.                                    

  AG-06   The developer shall be able to   High           Assistant assists, never
          add files not suggested by the                  decides
          assistant, remove suggested                     
          files, or replace the entire                    
          suggestion with a manual                        
          selection before confirming.                    

  AG-07   The developer shall be able to   Medium         CLI flag:
          bypass the assistant entirely                   \--manual-select. Gate
          and select files manually via a                 always present
          CLI flag, in which case the                     regardless.
          confirmation gate still applies                 
          to the manual selection.                        

  AG-08   The token count and cost         High           Developer sees cost
          estimate shall be shown on the                  before confirming, not
          confirmation screen, updating in                after
          real time as the developer                      
          adjusts the file selection.                     

  AG-09   The cost of the File Selection   Medium         Full cost transparency
          Assistant\'s LLM call shall be                  
          included in the total cost                      
          estimate displayed to the                       
          developer.                                      
  --------------------------------------------------------------------------------

**Confirmation Screen Format**

The confirmation screen shall display the following information clearly
before the developer is asked to confirm:

-   Each suggested file path with its rationale from the assistant

-   Approximate token count per file

-   Running total token count and estimated cost per selected model

-   Instructions for adding, removing, or replacing files

-   A clear prompt requiring explicit confirmation before proceeding

**4.9 Agent: Synthesis**

After all LLM providers have responded and Docker execution results are
collected, the Synthesis Agent reads all N model responses alongside
their execution outcomes and produces a single recommended answer. This
elevates PolyForge from a comparison tool to an intelligent advisor ---
rather than leaving the developer to manually evaluate three different
suggestions, the Synthesis Agent reasons across all results and
recommends the best path forward with a clear justification.

*Estimated cost impact: low (\~\$0.04--0.08 flat per query, one call).
Input is large but it is a single shot with no iteration.*

  --------------------------------------------------------------------------------
  **REQ   **Requirement**                  **Priority**   **Notes**
  ID**                                                    
  ------- -------------------------------- -------------- ------------------------
  AG-08   The tool shall invoke a          High           Runs once at the end of
          Synthesis Agent after all LLM                   the pipeline
          provider results and Docker                     
          execution results are collected.                

  AG-09   The Synthesis Agent shall        High           Full result context
          receive all model responses,                    required for accurate
          their suggested diffs, and                      synthesis
          execution results (build status,                
          test pass/fail, errors) as                      
          input.                                          

  AG-10   The Synthesis Agent shall        High           e.g. \'Claude\'s
          identify the best-performing                    solution is recommended
          solution and provide a written                  --- all tests passed and
          justification referencing                       no new dependencies were
          execution results.                              introduced\'

  AG-11   The Synthesis Agent shall flag   Medium         Best effort ---
          any solutions that passed tests                 LLM-based heuristic, not
          but introduced code quality                     static analysis
          concerns (e.g. global state,                    
          code duplication, hardcoded                     
          values).                                        

  AG-12   If multiple solutions pass all   Medium         Prefer smallest correct
          tests, the Synthesis Agent shall                diff
          compare them and recommend the                  
          most minimal, readable change.                  

  AG-13   If no solution passes tests, the Medium         Constructive failure
          Synthesis Agent shall identify                  analysis
          which solution got closest and                  
          explain what would be needed to                 
          fix it.                                         

  AG-14   The Synthesis Agent output shall High           Developer sees
          be displayed as a clearly                       recommendation before
          labeled section at the top of                   raw model results
          the results view.                               

  AG-15   The Synthesis Agent shall be     Low            Config flag:
          optional and can be disabled via                synthesis_agent: false
          config for developers who prefer                
          to evaluate results themselves.                 
  --------------------------------------------------------------------------------

**5. Non-Functional Requirements**

  ---------------------------------------------------------------------------------
  **REQ    **Requirement**                  **Priority**   **Notes**
  ID**                                                     
  -------- -------------------------------- -------------- ------------------------
  NFR-01   The tool shall complete the full High           Assuming models respond
           cycle (query → execution →                      within 60s and build
           results) within 3 minutes for a                 completes within 120s
           standard Java Maven project.                    

  NFR-02   API keys shall never be logged,  High           Security baseline
           printed to stdout, or included                  
           in error messages.                              

  NFR-03   The tool shall run on macOS and  High           Docker required on host
           Linux. Windows support is out of                machine
           scope for MVP.                                  

  NFR-04   The tool shall be installable    Medium         Low friction onboarding
           via a single command (e.g., pip                 
           install or npm install).                        

  NFR-05   LLM provider integrations shall  Medium         Extensibility for future
           be abstracted behind a common                   providers
           interface to allow new providers                
           to be added with minimal code                   
           changes.                                        

  NFR-06   All Docker operations shall use  Medium         Reliability and
           the Docker SDK/API --- no shell                 portability
           exec of docker CLI commands.                    

  NFR-07   The tool shall surface clear,    Medium         Developer experience
           human-readable error messages                   
           for the 5 most common failure                   
           modes: API key missing, Docker                  
           not running, repo path invalid,                 
           build timeout, parse failure.                   
  ---------------------------------------------------------------------------------

**6. Constraints & Limits**

  ---------------------------------------------------------------------------------
  **REQ    **Requirement**                  **Priority**   **Notes**
  ID**                                                     
  -------- -------------------------------- -------------- ------------------------
  CON-01   Maximum 5 files may be selected  High           Hard enforced limit
           per query.                                      

  CON-02   Maximum 3 LLM providers may be   High           Claude, GPT-4o, Gemini
           queried simultaneously.                         

  CON-03   Container execution timeout is   High           Default value
           120 seconds (configurable).                     

  CON-04   LLM API call timeout is 60       High           Default value
           seconds per provider                            
           (configurable).                                 

  CON-05   Container resource limits: 2 CPU High           Default values
           cores, 2GB RAM (configurable).                  

  CON-06   Containers have no outbound      High           Non-configurable
           network access.                                 security constraint

  CON-07   The tool does not modify the     High           All changes applied to
           developer\'s original repository                snapshots only
           under any circumstances.                        
  ---------------------------------------------------------------------------------

**7. Product Roadmap**

The following table outlines the planned release progression for
PolyForge beyond the MVP. Items are sequenced by dependency, complexity,
and cost risk.

**v1.0 --- MVP (Current Scope)**

-   Core parallel LLM query pipeline (Claude, GPT-4o, Gemini).

-   Local repository ingestion with manual or agent-assisted file
    selection (up to 5 files).

-   Real-time token counter and per-model cost estimation.

-   Docker-based isolated execution per LLM response.

-   File Selection Assistant --- recommends relevant files using
    signature extraction, with a mandatory hard confirmation gate before
    any cost is incurred.

-   Synthesis Agent --- reads all results and recommends the best
    solution with justification.

-   CLI interface with ranked results display and unified diff output.

**v1.5 --- Developer Experience**

-   Web UI with side-by-side visual diff viewer and syntax-highlighted
    code comparison.

-   Git repository URL support --- clone and analyze remote repos,
    target specific branches or commits.

-   Query history and result persistence across sessions.

-   Per-language execution profiles with pre-warmed Docker images for
    faster cold starts.

-   Support for additional LLM providers: Mistral, DeepSeek, Groq/Llama.

**v2.0 --- Execution Feedback Loop Agent**

The Execution Feedback Loop Agent is the most technically ambitious
feature on the roadmap. It transforms each LLM from a one-shot code
suggester into an autonomous agent that iterates on its own solution
using real test output as feedback. Rather than simply reporting that
tests failed, each LLM agent reads the failure, reasons about the cause,
revises its fix, and re-runs the container --- repeating up to a
configurable maximum number of iterations until tests pass or the
iteration cap is reached.

*This feature is deliberately deferred to v2.0 for two reasons. First,
it increases per-query cost by up to 3x (each iteration is a full LLM
call with full file context). Second, it requires the core pipeline to
be proven stable before layering iterative agent loops on top of it.
Once real usage data exists from v1.x, iteration caps and cost
guardrails can be tuned to real-world patterns rather than estimates.*

  --------------------------------------------------------------------------------
  **REQ   **Requirement**                  **Priority**   **Notes**
  ID**                                                    
  ------- -------------------------------- -------------- ------------------------
  RM-01   Each LLM provider shall operate  High           v2.0 target
          as a stateful agent capable of                  
          receiving Docker execution                      
          output (stdout, stderr, test                    
          results) as feedback.                           

  RM-02   The agent shall decide after     High           v2.0 target
          each execution whether to revise                
          its solution or accept the                      
          current result.                                 

  RM-03   The maximum number of feedback   High           v2.0 target --- cost
          iterations per agent shall be                   control critical
          configurable (default: 3).                      

  RM-04   Each iteration\'s token cost     High           v2.0 target
          shall be tracked and added to                   
          the running query cost total                    
          shown to the developer.                         

  RM-05   The agent shall maintain full    High           v2.0 target
          conversation history across                     
          iterations so it understands the                
          progression of its own attempts.                

  RM-06   The developer shall be able to   Medium         v2.0 target --- safety
          set a per-query cost ceiling                    guardrail
          that halts agent iteration if                   
          exceeded.                                       
  --------------------------------------------------------------------------------

**v2.5 and Beyond**

-   VM-based execution support for projects that cannot run in Docker.

-   VS Code extension integration for in-editor usage.

-   Team and org mode with shared API key management, usage dashboards,
    and role-based access.

-   Vector similarity search over the repo for fully automatic file
    relevance detection.

-   Fine-tuned synthesis model trained on PolyForge\'s own historical
    query and result data.

**8. Recommended MVP Tech Stack**

  ----------------------------------------------------------------------------------
  **REQ     **Requirement**                  **Priority**   **Notes**
  ID**                                                      
  --------- -------------------------------- -------------- ------------------------
  TECH-01   Primary language: Python 3.11+   High           Strong async support,
                                                            rich Docker SDK, all LLM
                                                            SDKs available

  TECH-02   LLM SDKs: anthropic, openai,     High           Official provider SDKs
            google-generativeai                             

  TECH-03   Async orchestration: asyncio +   High           Parallel LLM fan-out
            aiohttp                                         

  TECH-04   Docker integration: docker       High           No shell exec of docker
            Python SDK                                      CLI

  TECH-05   Token counting: tiktoken         High           Real-time cost
            (OpenAI) + provider-specific                    estimation
            counters                                        

  TECH-06   CLI framework: Typer or Click    Medium         Clean developer-facing
                                                            CLI UX

  TECH-07   Config management:               Medium         API keys and defaults
            python-dotenv + TOML config file                

  TECH-08   Diff generation: Python difflib  Medium         Patch application and
            or unidiff                                      display
  ----------------------------------------------------------------------------------
