from langchain_openai import AzureChatOpenAI
from backend.config.settings import get_settings
from backend.utils.logger import get_logger
from functools import lru_cache

logger = get_logger(__name__)
settings = get_settings()


@lru_cache()
def get_llm() -> AzureChatOpenAI:
    """Return a cached AzureChatOpenAI instance."""
    logger.info(
        "Initialising Azure OpenAI LLM | deployment=%s endpoint=%s",
        settings.azure_openai_deployment_name,
        settings.azure_openai_endpoint,
    )
    return AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_deployment_name,
        api_version=settings.azure_openai_api_version,
        api_key=settings.azure_openai_api_key,
        temperature=0.3,
        max_tokens=1024,
    )
