from polyforge.models import QueryRequest, LLMRequest, LLMResponse
from polyforge.providers.ClaudeProvider import ClaudeProvider
from polyforge.providers.OpenAIProvider import OpenAIProvider
from polyforge.providers.GeminiProvider import GeminiProvider
from polyforge.config import SYSTEM_PROMPT
from pathlib import Path
import asyncio

PROVIDER_MAP = {
      "claude": ClaudeProvider,
      "gpt4o": OpenAIProvider,
      "gemini": GeminiProvider,
  }

class Orchestrator:
    def __init__(self, query_request: QueryRequest):
        self._query_request = query_request
        self._llm_requests = {}
        self._providers = {
              name: PROVIDER_MAP[name]()
              for name in query_request.selected_models
          }            
        self._create_llm_requests()
    
    async def run(self):
        #Todo
        pass


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
    
    def _gather_file_contents(self) -> dict[str,str]:
        file_contents = {}
        for file_path in self._query_request.selected_files:
            full_path = Path(self._query_request.repo_path) / file_path
            if not full_path.exists():
                print("File does not exist. Exiting")
                exit(1) 
            file_contents[str(file_path)] = full_path.read_text()
        return file_contents