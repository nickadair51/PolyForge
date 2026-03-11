import asyncio
from polyforge.models import LLMRequest
from polyforge.providers.OpenAIProvider import OpenAIProvider

async def main():
      provider = OpenAIProvider()

      request = LLMRequest(
          query_id="test-123",
          provider="openai",
          system_prompt="You are a helpful assistant. Respond with plain text.",
          file_contents={},
          question="Say hello in one sentence.",
      )

      response = await provider.query_llm(request)
      print(f"Success: {response.success}")
      print(f"Raw text: {response.raw_text}")
      print(f"Tokens: {response.input_tokens} in / {response.output_tokens} out")
      print(f"Latency: {response.latency_ms}ms")
      if response.error:
          print(f"Error: {response.error}")

asyncio.run(main())
