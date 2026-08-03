from config import settings


def get_model():
    """AGENTS.md §8 — sağlayıcıyı MODEL_PROVIDER env değişkeni belirler.

    Tüm ajanlar modeli buradan alır; Ollama'ya geçiş kod değişikliği gerektirmez.
    """
    if settings.model_provider == "ollama":
        from agno.models.ollama import Ollama

        return Ollama(id=settings.ollama_model_id, host=settings.ollama_base_url)

    # Responses API (Chat Completions değil): gpt-5.x reasoning modelleri function
    # tool'ları Chat Completions'ta reddediyor ("use /v1/responses" 400 hatası).
    # Agno'nun resmi örnekleri de gpt-5.x için OpenAIResponses kullanıyor.
    from agno.models.openai import OpenAIResponses

    return OpenAIResponses(id=settings.openai_model_id)
