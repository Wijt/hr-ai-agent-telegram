import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# src/config.py -> parent (src) -> parent (proje kökü). Data yolları cwd'den bağımsız olsun diye.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    app_env: str
    model_provider: str
    openai_api_key: str
    openai_model_id: str
    ollama_model_id: str
    ollama_base_url: str


def load_settings() -> Settings:
    return Settings(
        telegram_token=os.environ["TELEGRAM_TOKEN"],
        app_env=os.environ.get("APP_ENV", "production"),
        model_provider=os.environ.get("MODEL_PROVIDER", "openai"),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        openai_model_id=os.environ.get("OPENAI_MODEL_ID", "gpt-4o-mini"),
        ollama_model_id=os.environ.get("OLLAMA_MODEL_ID", "qwen2.5"),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
    )


settings = load_settings()
