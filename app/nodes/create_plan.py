"""Node: Create Research Plan

Generates a step-by-step research plan based on the interpreted criteria.
"""

from __future__ import annotations

from typing import Any

from app.intelligence import IntelligenceProvider
from app.state import ResearchState


def create_plan_node(intelligence: IntelligenceProvider):
    """Create a node function that generates the research plan."""

    def create_plan(state: ResearchState) -> dict[str, Any]:
        plan = intelligence.create_research_plan(state["criteria"])
        step_names = [s["step"] for s in plan]
        log_entry = f"[create_plan] Plan created with {len(plan)} steps: {' -> '.join(step_names)}"
        return {
            "research_plan": plan,
            "log": state["log"] + [log_entry],
        }

    return create_plan
