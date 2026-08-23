import os
import logging
from typing import Optional, Any, Dict
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models import FakeListChatModel
from app.config import settings

logger = logging.getLogger("havenkeep.model_adapter")

class ModelProviderAdapter:
    """
    Multi-Provider Model Abstraction Layer with Dynamic Provider Default Resolution.
    Instantiates standard LangChain chat models dynamically per agent role.
    If no specific model name is passed, it automatically resolves to the provider's standard default model.
    """
    
    # Standard Default Models per Provider
    DEFAULT_PROVIDER_MODELS: Dict[str, str] = {
        "ollama": "gemma3:latest",
        "anthropic": "claude-3-5-sonnet-20240620",
        "openai": "gpt-4o-mini",
        "google": "gemini-1.5-flash",
        "google_genai": "gemini-1.5-flash",
        "gemini": "gemini-1.5-flash",
        "groq": "llama-3.3-70b-versatile",
        "openrouter": "deepseek/deepseek-r1",
    }

    @staticmethod
    def get_model(
        role: str, 
        temperature: float = 0.0,
        mock_responses: Optional[list[str]] = None
    ) -> BaseChatModel:
        if mock_responses:
            return FakeListChatModel(responses=mock_responses)
            
        if os.getenv("TESTING") == "1":
            return ModelProviderAdapter._get_mock_model(role)

        role_map = {
            "supervisor": (settings.supervisor_provider, settings.supervisor_model),
            "planner": (settings.planner_provider, settings.planner_model),
            "worker": (settings.worker_provider, settings.worker_model),
            "critic": (settings.critic_provider, settings.critic_model),
        }
        
        provider, configured_model = role_map.get(role.lower(), (settings.worker_provider, settings.worker_model))
        provider_lower = provider.lower()
        
        # Resolve model name: use configured_model if provided, else provider default
        model_name = configured_model or ModelProviderAdapter.DEFAULT_PROVIDER_MODELS.get(provider_lower, "gpt-4o-mini")

        # 1. Ollama (Local Provider)
        if provider_lower == "ollama":
            try:
                from langchain_ollama import ChatOllama
                return ChatOllama(
                    model=model_name,
                    base_url=settings.ollama_base_url,
                    temperature=temperature
                )
            except Exception as e:
                logger.warning(f"Could not initialize ChatOllama for model '{model_name}': {e}. Falling back to mock model.")
                return ModelProviderAdapter._get_mock_model(role)

        # 2. Google Gemini / Google GenAI
        if provider_lower in ("google", "google_genai", "gemini"):
            api_key = settings.google_api_key or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                logger.info(f"Google API key missing for role '{role}'. Using mock/heuristic fallback.")
                return ModelProviderAdapter._get_mock_model()
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                kwargs: dict[str, Any] = {"model": model_name, "google_api_key": api_key, "temperature": temperature}
                if settings.google_base_url:
                    kwargs["client_options"] = {"api_endpoint": settings.google_base_url}
                return ChatGoogleGenerativeAI(**kwargs)
            except Exception as e:
                logger.warning(f"Error initializing ChatGoogleGenerativeAI: {e}")
                return ModelProviderAdapter._get_mock_model()

        # 3. Groq API
        if provider_lower == "groq":
            api_key = settings.groq_api_key or os.getenv("GROQ_API_KEY")
            if not api_key:
                logger.info(f"Groq API key missing for role '{role}'. Using mock/heuristic fallback.")
                return ModelProviderAdapter._get_mock_model()
            try:
                from langchain_groq import ChatGroq
                kwargs = {"model_name": model_name, "groq_api_key": api_key, "temperature": temperature}
                if settings.groq_base_url:
                    kwargs["groq_api_base"] = settings.groq_base_url
                return ChatGroq(**kwargs)
            except Exception as e:
                logger.warning(f"Error initializing ChatGroq: {e}")
                return ModelProviderAdapter._get_mock_model()

        # 4. OpenRouter API
        if provider_lower == "openrouter":
            api_key = settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                logger.info(f"OpenRouter API key missing for role '{role}'. Using mock/heuristic fallback.")
                return ModelProviderAdapter._get_mock_model()
            try:
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model_name=model_name,
                    openai_api_key=api_key,
                    openai_api_base=settings.openrouter_base_url or "https://openrouter.ai/api/v1",
                    temperature=temperature
                )
            except Exception as e:
                logger.warning(f"Error initializing OpenRouter ChatOpenAI: {e}")
                return ModelProviderAdapter._get_mock_model()

        # 5. Anthropic API
        if provider_lower == "anthropic":
            api_key = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.info(f"Anthropic API key absent for role '{role}'. Using mock/heuristic fallback.")
                return ModelProviderAdapter._get_mock_model()
            try:
                from langchain_anthropic import ChatAnthropic
                kwargs = {"model": model_name, "anthropic_api_key": api_key, "temperature": temperature}
                if settings.anthropic_base_url:
                    kwargs["anthropic_api_url"] = settings.anthropic_base_url
                return ChatAnthropic(**kwargs)
            except Exception as e:
                logger.warning(f"Error initializing ChatAnthropic: {e}")
                return ModelProviderAdapter._get_mock_model()

        # 6. OpenAI API
        if provider_lower == "openai":
            api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                if settings.openai_base_url:
                    api_key = "mock_key_for_custom_endpoint"
                else:
                    logger.info(f"OpenAI API key absent for role '{role}'. Using mock/heuristic fallback.")
                    return ModelProviderAdapter._get_mock_model(role)
            try:
                from langchain_openai import ChatOpenAI
                kwargs = {"model_name": model_name, "openai_api_key": api_key, "temperature": temperature}
                if settings.openai_base_url:
                    kwargs["openai_api_base"] = settings.openai_base_url
                return ChatOpenAI(**kwargs)
            except Exception as e:
                logger.warning(f"Error initializing ChatOpenAI: {e}")
                return ModelProviderAdapter._get_mock_model(role)

        # Universal standard init_chat_model attempt
        try:
            from langchain.chat_models import init_chat_model
            return init_chat_model(
                model=model_name,
                model_provider=provider,
                temperature=temperature,
            )
        except Exception:
            return ModelProviderAdapter._get_mock_model(role)

    @staticmethod
    def _get_mock_model(role: str = "worker") -> BaseChatModel:
        role_lower = role.lower()
        if role_lower == "supervisor":
            res = '{"task_type": "GENERAL_QA", "risk_score": 0.2, "lane": "fast_lane", "confidence": 0.95}'
        elif role_lower in ("critic", "guardrail"):
            res = '{"passed": true, "feedback": "Response passed quality guardrails.", "adjusted_output": null}'
        else:
            res = "Synchronous execution blocks the current thread until completion, while asynchronous execution yields execution during I/O operations."
        return FakeListChatModel(responses=[res])
