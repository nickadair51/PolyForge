from polyforge.models import PolyForgeError
from polyforge.providers.LLMProvider import LLMProvider

INTERNAL_PROVIDER_PREFERENCE = ['claude', 'gpt4o', 'gemini']

def get_internal_provider(configured_providers: dict[str, LLMProvider]) -> LLMProvider:
    """Return the best available provider for internal LLM components (file selection, synthesis)."""
    for name in INTERNAL_PROVIDER_PREFERENCE:
        if name in configured_providers:
            return configured_providers[name]
    raise PolyForgeError(
        "No LLM provider configured. "
        "Set at least one API key: ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY"
    )
