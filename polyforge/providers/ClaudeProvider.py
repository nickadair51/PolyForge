import asyncio, json, os, time
from polyforge import models, config
from polyforge.providers.LLMProvider import LLMProvider
from anthropic import AsyncAnthropic

MODEL = "claude-sonnet-4-5"
ESTIMATED_MAX_OUTPUT_TOKENS = 8192
COST_PER_INPUT_TOKEN = 0.000003
COST_PER_OUTPUT_TOKEN = 0.000015

class ClaudeProvider(LLMProvider):
    def __init__(self):
        self._client = AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )

    async def query_llm(self, request: models.LLMRequest) -> models.LLMResponse:
        retry_attempted = False
        for attempt in range(2): # Only attempt one retry
            start_time = time.perf_counter()
            try:
                async with asyncio.timeout(config.ExecutionConfig.llm_timeout_seconds): # Give the LLM 150 seconds to respond before timing out
                    llm_response = await self._call_claude_api(request)
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    return self._parse_response(llm_response, request, latency_ms, retry_attempted)
            except Exception as e:
                if attempt == 1:
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    return models.LLMResponse(
                        query_id=request.query_id,
                        provider='claude',
                        success=False,
                        raw_text='',
                        modified_files={},
                        input_tokens=0,
                        output_tokens=0,
                        latency_ms=latency_ms,
                        error=str(e),
                        retry_attempted=True
                    )
                retry_attempted = True
                await asyncio.sleep(2)


    async def estimate_cost_of_request(self, request: models.LLMRequest) -> float:
        result = await self._client.messages.count_tokens(model=MODEL, 
                                                                     system=request.system_prompt,
                                                                     messages=[{"role": "user", "content":
                                                                        request.question}])
        input_token_count = result.input_tokens
        return (input_token_count * COST_PER_INPUT_TOKEN) + (ESTIMATED_MAX_OUTPUT_TOKENS * COST_PER_OUTPUT_TOKEN)
    
    def calculate_cost_of_response(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * COST_PER_INPUT_TOKEN) + (output_tokens * COST_PER_OUTPUT_TOKEN)
    
    
    async def _call_claude_api(self, request: models.LLMRequest):
        message = await self._client.messages.create(
            model=MODEL,
            max_tokens=ESTIMATED_MAX_OUTPUT_TOKENS,
            system=request.system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": self._build_user_message(request),
                }
            ],
        )
        return message

    def _build_user_message(self, request: models.LLMRequest) -> str:
        parts = []
        for filename, content in request.file_contents.items():
            parts.append(f"### {filename}\n```\n{content}\n```")
        parts.append(f"\n### Question\n{request.question}")
        return "\n\n".join(parts)
    
    def _parse_response(self, llm_response, request, latency_ms, retry_attempted: bool) -> models.LLMResponse:
        raw_text = llm_response.content[0].text if llm_response.content else ""
        modified_files, parse_error = self._parse_modified_files(raw_text)
        return models.LLMResponse(
            query_id=request.query_id,
            provider='claude',
            success=parse_error is None,
            raw_text=raw_text,
            modified_files=modified_files,
            input_tokens=llm_response.usage.input_tokens,
            output_tokens=llm_response.usage.output_tokens,
            cost=self.calculate_cost_of_response(llm_response.usage.input_tokens, 
                                                llm_response.usage.output_tokens),
            latency_ms=latency_ms,
            error=parse_error,
            retry_attempted=retry_attempted
            )

    def _parse_modified_files(self, raw_text: str) -> tuple[dict[str, str], str | None]:
        try:
          text = raw_text.strip()
          if text.startswith("```"):
              text = text.split("\n", 1)[1]       # drop the ```json line
              text = text.rsplit("```", 1)[0]     # drop the trailing ```
          data = json.loads(text.strip())
          modified_files = data.get("modified_files", {})
          if not isinstance(modified_files, dict):
                return {}, "Response 'modified_files' is not a dict"
          return modified_files, None
        except json.JSONDecodeError as e:
            return {}, f"Failed to parse JSON response: {e}"