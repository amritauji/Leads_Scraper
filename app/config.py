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

# --- Phase 3: Pipeline Stages -----------------------------------------------
PIPELINE_STAGES = [
    "new",
    "assigned",
    "contacted",
    "qualified",
    "opportunity",
    "won",
    "lost",
]

# --- Phase 3: Activity Types ------------------------------------------------
ACTIVITY_TYPES = [
    "lead_created",
    "lead_assigned",
    "lead_reassigned",
    "lead_unassigned",
    "stage_changed",
    "priority_changed",
    "next_action_set",
    "next_action_cleared",
    "review_approved",
    "review_rejected",
    "note_added",
    "call_logged",
    "email_logged",
    "meeting_logged",
    "status_changed",
]

MANUAL_ACTIVITY_TYPES = [
    "note_added",
    "call_logged",
    "email_logged",
    "meeting_logged",
]

NEXT_ACTION_TYPES = [
    "call",
    "email",
    "meeting",
    "follow_up",
    "other",
]
