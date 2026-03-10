"""All dataclasses and exceptions for PolyForge.

Every component communicates through the typed objects defined here.
No shared mutable state. Data flows forward only — never backwards.
"""

from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PolyForgeError(Exception):
    """Base exception for all PolyForge errors."""


class UnknownProjectTypeError(PolyForgeError):
    """Raised when project type cannot be detected from repo manifests."""


class NoTestCommandError(PolyForgeError):
    """Raised when a project has no runnable test command."""


# ---------------------------------------------------------------------------
# Pipeline dataclasses
# ---------------------------------------------------------------------------

@dataclass
class QueryRequest:
    """Everything the developer submitted. Created by the CLI entry point."""
    repo_path:       str
    question:        str
    selected_files:  list[str]       # confirmed by developer, max 5
    selected_models: list[str]       # e.g. ['claude', 'gpt4o', 'gemini']
    query_id:        str             # uuid, used for workspace path
    timestamp:       datetime


@dataclass
class LLMRequest:
    """Sent to each LLM provider in parallel. Created by the Orchestrator."""
    query_id:      str
    provider:      str               # 'claude' | 'gpt4o' | 'gemini'
    system_prompt: str
    file_contents: dict[str, str]    # { filename: content }
    question:      str


@dataclass
class LLMResponse:
    """Returned by each provider. Contains raw response and parsed file changes."""
    query_id:        str
    provider:        str
    success:         bool
    raw_text:        str
    modified_files:  dict[str, str]  # { filename: new_content }
    input_tokens:    int
    output_tokens:   int
    cost:            float           # calculated cost of this response in USD
    latency_ms:      int
    error:           str | None      # populated if success=False
    retry_attempted: bool


@dataclass
class RepoSnapshot:
    """A full copy of the repo with one LLM's changes applied."""
    query_id:      str
    provider:      str
    snapshot_path: str               # ~/.polyforge/workspaces/<query_id>/<provider>/
    diff:          str               # unified diff of changes applied
    project_type:  str               # 'maven' | 'gradle' | 'node' | 'python' | 'rust'


@dataclass
class ExecutionResult:
    """Everything captured from a Docker container run."""
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
    """The Synthesis Layer's recommendation across all provider results."""
    recommended_provider: str | None  # None if all solutions failed
    justification:        str
    quality_warnings:     list[str]
    failure_analysis:     str | None  # populated when no solution passes
    closest_provider:     str | None  # best failed attempt


@dataclass
class FinalResult:
    """Complete output assembled by the Orchestrator, passed to ResultsRenderer."""
    query_id:          str
    query_request:     QueryRequest
    llm_responses:     list[LLMResponse]
    execution_results: list[ExecutionResult]
    synthesis:         SynthesisResult
    ranked_providers:  list[str]       # ordered best to worst
    estimated_cost:    float           # pre-query estimate
    actual_cost:       float           # based on actual token usage
    total_duration_ms: int


# ---------------------------------------------------------------------------
# Internal pipeline dataclasses (derived from architecture doc)
# These shapes may be refined during implementation.
# ---------------------------------------------------------------------------

@dataclass
class FileSelectionResult:
    """Confirmed file selection returned by the File Selection Assistant."""
    selected_files:  list[str]           # confirmed file paths (max 5)
    rationales:      dict[str, str]      # file path -> assistant rationale
    token_estimates: dict[str, int]      # file path -> approximate token count


@dataclass
class TokenEstimate:
    """Per-model cost estimate produced by the Token Counter."""
    total_tokens:         int
    file_token_counts:    dict[str, int]   # filename -> token count
    per_model_cost:       dict[str, float] # provider -> estimated cost in USD
    total_estimated_cost: float


@dataclass
class PatchResult:
    """Result of applying one LLM's changes to a repo snapshot."""
    provider:       str
    snapshot_path:  str
    diff:           str
    files_modified: list[str]
    files_created:  list[str]
