from config import settings


def get_model():
    """Sağlayıcıyı MODEL_PROVIDER env değişkeni belirler.

    Tüm ajanlar modeli buradan alır; Ollama'ya geçiş kod değişikliği gerektirmez.
    """
    if settings.model_provider == "ollama":
        from agno.models.ollama import Ollama

        return Ollama(id=settings.ollama_model_id, host=settings.ollama_base_url)

    from agno.models.openai import OpenAIChat

    return OpenAIChat(id=settings.openai_model_id)
