"""Core configuration helpers for the Swarm B2B runtime."""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

import openai
from swarm import Swarm


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / '.env'


def _load_environment() -> None:
    """Load environment variables from .env if python-dotenv is available."""
    if load_dotenv is None:
        return

    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH)
        print(f"[ENV] TUNNEL_URL: {os.getenv('TUNNEL_URL', 'Not set')}")


_load_environment()


OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini')

_openrouter_client = openai.OpenAI(
    base_url='https://openrouter.ai/api/v1',
    api_key=os.getenv('OPENROUTER_API_KEY')
)

client = Swarm(client=_openrouter_client)

# Expose raw client for utility helpers that need direct completions (e.g., timeframe parsing)
openrouter_client = _openrouter_client

print(f"[Swarm] Model: {OPENROUTER_MODEL}")
