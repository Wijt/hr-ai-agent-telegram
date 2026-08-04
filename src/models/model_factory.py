from config import settings


def get_model():
    """Sağlayıcıyı MODEL_PROVIDER env değişkeni belirler.

    Tüm ajanlar modeli buradan alır; Ollama'ya geçiş kod değişikliği gerektirmez.
    """
    if settings.model_provider == "ollama":
        from agno.models.ollama import Ollama

        return Ollama(id=settings.ollama_model_id, host=settings.ollama_base_url)

    from agno.models.openai import OpenAIChat

    # reasoning_effort="none": bazı reasoning modelleri (ör. .env'deki proxy model)
    # tool çağrısıyla birlikte reasoning_effort gönderilirse 400 döndürüyor.
    return OpenAIChat(id=settings.openai_model_id, reasoning_effort="none")
