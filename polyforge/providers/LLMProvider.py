"""All base classes for providers."""  
import asyncio
from polyforge import models
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    async def query_llm(self, request: models.LLMRequest) -> models.LLMResponse:
        """Query the LLM with the provided code and return the response."""
        pass

    @abstractmethod
    async def estimate_cost_of_request(self,request: models.LLMRequest) -> float:
         """Return an estimate of how much this request will cost in dollars."""
         pass
    
    @abstractmethod
    def calculate_cost_of_response(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate the cost of a response based on token usage."""
        pass

    
"""May need more, just have this for now"""