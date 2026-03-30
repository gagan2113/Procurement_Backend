from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    # Azure OpenAI
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_deployment_name: str = "gpt-4o"
    azure_openai_api_version: str = "2024-12-01-preview"

    # Database
    database_url: str = "sqlite:///./procurement.db"

    # App
    app_name: str = "Procurement AI System"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True

    # PDF storage
    pdf_dir: str = "pdfs"

    class Config:
        env_file = Path(__file__).resolve().parents[2] / ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
