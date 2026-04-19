from polyforge import models
from polyforge.models import (
    QueryRequest, LLMRequest, LLMResponse, RepoSnapshot,
    ExecutionResult, SynthesisResult, FinalResult,
)
from polyforge.providers.ClaudeProvider import ClaudeProvider
from polyforge.providers.OpenAIProvider import OpenAIProvider
from polyforge.providers.GeminiProvider import GeminiProvider
from polyforge.repo.RepoManager import RepoManager
from polyforge.docker.executor import DockerExecutor
from polyforge.llm_components.synthesis import SynthesisLayer
from polyforge.providers.LLMProvider import LLMProvider
from polyforge.config import SYSTEM_PROMPT, PolyForgeConfig
from pathlib import Path
import asyncio

PROVIDER_MAP = {
      "claude": ClaudeProvider,
      "gpt4o": OpenAIProvider,
      "gemini": GeminiProvider,
      "chatgpt": OpenAIProvider,
      "openai": OpenAIProvider
  }

INTERNAL_PROVIDER_PREFERENCE = ["claude", "gpt4o", "gemini"]

class Orchestrator:
    def __init__(self, query_request: QueryRequest, config: PolyForgeConfig, project_type: str):
        self._query_request = query_request
        self._project_type = project_type
        self._llm_requests = {}
        self._providers = {
              name: PROVIDER_MAP[name]()
              for name in query_request.selected_models
          }
        self._repo_manager = RepoManager(
            repo_path=query_request.repo_path,
            workspace_base=config.workspace.base_path,
            query_id=query_request.query_id,
        )
        self._docker_executor = DockerExecutor(config)
        self._create_llm_requests()
    
    async def run(self) -> tuple[list[LLMResponse], list[ExecutionResult], SynthesisResult]:
        try:
            # Fan-out: query all providers in parallel
            responses: list[LLMResponse] = await asyncio.gather(*[
                self._providers[model].query_llm(self._llm_requests[model])
                for model in self._query_request.selected_models
            ], return_exceptions=True)

            # Separate successful responses from failures
            llm_responses = []
            for r in responses:
                if isinstance(r, Exception):
                    # gather with return_exceptions=True can return exceptions
                    # providers should never raise, but handle it defensively
                    continue
                llm_responses.append(r)

            successful = [r for r in llm_responses if r.success]

            # Create snapshots and apply patches for each successful response
            snapshots: list[RepoSnapshot] = [
                self._repo_manager.build_repo_snapshot(r, self._project_type)
                for r in successful
            ]

            # Fan-out: run Docker containers in parallel
            execution_results: list[ExecutionResult] = await asyncio.gather(*[
                self._docker_executor.execute(snapshot)
                for snapshot in snapshots
            ], return_exceptions=True)

            # Filter out any exceptions from gather
            exec_results = [r for r in execution_results if isinstance(r, ExecutionResult)]

            # Synthesis — blind evaluation of all solutions
            _, synthesis_provider = self._get_internal_provider()
            synthesis_layer = SynthesisLayer(synthesis_provider)
            synthesis_result, _ = await synthesis_layer.synthesize(
                question=self._query_request.question,
                llm_responses=successful,
                execution_results=exec_results,
                query_id=self._query_request.query_id,
            )

            return llm_responses, exec_results, synthesis_result

        finally:
            self._repo_manager.cleanup()

    async def estimate_cost_of_query(self) -> float:
      costs = await asyncio.gather(*[
          self._providers[model].estimate_cost_of_request(self._llm_requests[model])
          for model in self._query_request.selected_models
      ], return_exceptions=True)
      return sum(c for c in costs if isinstance(c, float))


    def _create_llm_requests(self):
        for model in self._query_request.selected_models:
            self._llm_requests[model] = LLMRequest(
                    query_id=self._query_request.query_id,
                    provider=model,
                    system_prompt=SYSTEM_PROMPT,
                    file_contents=self._gather_file_contents(),
                    question=self._query_request.question
                )
    
    def get_synthesis_provider_name(self) -> str:
        """Return the name of the provider that will be used for synthesis."""
        name, _ = self._get_internal_provider()
        return name

    def _get_internal_provider(self) -> tuple[str, LLMProvider]:
        """Return the best available provider for internal LLM components."""
        for name in INTERNAL_PROVIDER_PREFERENCE:
            if name in self._providers:
                return name, self._providers[name]
        raise models.PolyForgeError(
            "No LLM provider configured. "
            "Set at least one API key: ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY"
        )

    def _gather_file_contents(self) -> dict[str,str]:
        file_contents = {}
        for file_path in self._query_request.selected_files:
            full_path = Path(self._query_request.repo_path) / file_path
            if not full_path.exists():
                print(f"File {file_path} does not exist. Skipping incorrect file.") 
                continue
            file_contents[str(file_path)] = full_path.read_text()
        return file_contents