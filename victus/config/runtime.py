from __future__ import annotations

import os

from dotenv import load_dotenv


# Load environment variables from a local .env file if present.
load_dotenv()


def get_openai_api_key() -> str | None:
    """Return the configured OpenAI API key, if any."""

    key = os.getenv("OPENAI_API_KEY")
    return key.strip() if key else None


def is_openai_configured() -> bool:
    """Indicate whether an OpenAI API key is available."""

    return bool(get_openai_api_key())


def require_openai_api_key() -> str:
    """Return the OpenAI API key or raise a clear error if missing."""

    key = get_openai_api_key()
    if not key:
        from victus.core.schemas import ExecutionError

        raise ExecutionError("OPENAI_API_KEY is required to use the OpenAI client.")

    return key


def get_llm_provider() -> str:
    """Return the configured LLM provider name (default: ollama)."""

    provider = os.getenv("LLM_PROVIDER", "ollama")
    return provider.strip().lower()


def is_outbound_llm_provider(provider: str | None = None) -> bool:
    """Return True when the provider sends data to a remote LLM service."""

    provider_name = (provider or get_llm_provider()).lower()
    return provider_name in {"openai", "gemini", "groq"}


def is_local_llm_provider(provider: str | None = None) -> bool:
    """Return True when the provider keeps data local to the device."""

    provider_name = (provider or get_llm_provider()).lower()
    return provider_name in {"ollama"}


def get_ollama_base_url() -> str:
    """Return the Ollama base URL (default: http://localhost:11434)."""

    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()


def get_ollama_model() -> str:
    """Return the Ollama model name (default: llama3.1:8b)."""

    return os.getenv("OLLAMA_MODEL", "llama3.1:8b").strip()
