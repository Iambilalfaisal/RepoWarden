from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import ConfigurableField
from langchain_openai import ChatOpenAI

from app.core.config import settings


def build_llm() -> BaseChatModel:
    # Configurable model: the model name and temperature can be overridden
    # per-invocation via RunnableConfig (config={"configurable": {...}})
    # instead of being fixed at construction time.
    return ChatOpenAI(
        model=settings.openrouter_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    ).configurable_fields(
        model_name=ConfigurableField(
            id="model_name", name="Model", description="OpenRouter model slug to use"
        ),
        temperature=ConfigurableField(
            id="temperature", name="Temperature", description="Sampling temperature"
        ),
    )
