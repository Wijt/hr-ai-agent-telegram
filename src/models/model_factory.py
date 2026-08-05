from config import settings


def get_model():
    """Sağlayıcıyı MODEL_PROVIDER env değişkeni belirler.

    Tüm ajanlar modeli buradan alır; Ollama'ya geçiş kod değişikliği gerektirmez.
    """
    if settings.model_provider == "ollama":
        from agno.models.ollama import Ollama

        # num_ctx Ollama API'sine options içinde gider. Ollama'nın varsayılan penceresi
        # (4096) bu botun tek turluk prompt'una yetmiyor ve cevap hata vermeden cümle
        # ortasında kesiliyor — OLLAMA_NUM_CTX ile büyütülür. Boş bırakılırsa hiç
        # gönderilmez, Ollama sunucusunun kendi ayarı geçerli kalır.
        options = {"num_ctx": settings.ollama_num_ctx} if settings.ollama_num_ctx else None
        return Ollama(
            id=settings.ollama_model_id,
            host=settings.ollama_base_url,
            options=options,
        )

    from agno.models.openai import OpenAIChat

    # reasoning_effort="none": bazı reasoning modelleri (ör. .env'deki proxy model)
    # tool çağrısıyla birlikte reasoning_effort gönderilirse 400 döndürüyor.
    return OpenAIChat(id=settings.openai_model_id, reasoning_effort="none")
