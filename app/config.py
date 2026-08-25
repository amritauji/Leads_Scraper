"""Central config — loads .env and exposes all API keys."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


def get(key: str, default: str = "") -> str:
    """Get an environment variable value."""
    return os.environ.get(key, default)


# --- API Keys ---------------------------------------------------------------

NVIDIA_API_KEY = get("NVIDIA_API_KEY")
EXA_API_KEY = get("EXA_API_KEY")
TAVILY_API_KEY = get("TAVILY_API_KEY")
FIRECRAWL_API_KEY = get("FIRECRAWL_API_KEY")
HUNTER_API_KEY = get("HUNTER_API_KEY")

# --- Database ----------------------------------------------------------------
DATABASE_URL = get("DATABASE_URL")
