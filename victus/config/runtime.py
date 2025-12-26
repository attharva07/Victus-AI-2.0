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
