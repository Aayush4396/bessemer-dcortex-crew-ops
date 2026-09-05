"""
src/agent/client.py
===================
Initializes the Sarvam AI (Sarvam-105B) model via the standard LangChain ChatOpenAI interface.
Loads credentials dynamically from environment variables.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env", override=True)


def get_llm(
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = 2048,
) -> ChatOpenAI:
    """
    Initialize and return a ChatOpenAI instance pointing to Sarvam AI.

    Parameters
    ----------
    model : str, optional
        Model identifier, defaults to SARVAM_MODEL env var (sarvam-105b).
    temperature : float, optional
        Sampling temperature, default 0.0 for deterministic tool parameter selection.
    max_tokens : int, optional
        Maximum completion tokens.

    Returns
    -------
    ChatOpenAI
    """
    api_key = os.getenv("SARVAM_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai/v1")
    model_name = model or os.getenv("SARVAM_MODEL", "sarvam-105b")

    if not api_key or api_key.startswith("your_"):
        raise RuntimeError(
            "SARVAM_API_KEY is not configured. Set it in the project .env file "
            "or provide OPENAI_API_KEY before starting the backend."
        )

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )
