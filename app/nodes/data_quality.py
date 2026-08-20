from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from app.quality import process_leads

# ---------------------------------------------------------------------------
# WIRING NOTES (align these two things with your codebase, then delete this):
#   1. STATE KEY: this node reads/writes the list of Standard Lead dicts on the
#      state under `LEADS_KEY`. Set it to whatever build_lead writes (e.g.
#      "leads" or "final_leads"). If your state stores Pydantic StandardLead
#      objects, set USE_PYDANTIC = True and adjust _to_dict / _from_dict.
#   2. GRAPH EDGES in app/graph.py:
#         graph.add_node("data_quality", create_data_quality_node(emit=emit))
#         graph.add_edge("build_lead", "data_quality")
#         graph.add_edge("data_quality", END)   # or "confidence" once built
# ---------------------------------------------------------------------------

LEADS_KEY = "leads"
USE_PYDANTIC = False
MASTER_PATH = Path("output/lead_master.json")


def _to_dict(lead: Any) -> dict[str, Any]:
    if USE_PYDANTIC and hasattr(lead, "model_dump"):
        return lead.model_dump(by_alias=True)
    return dict(lead)


def _load_master() -> list[dict[str, Any]]:
    if MASTER_PATH.exists():
        try:
            return json.loads(MASTER_PATH.read_text())
        except json.JSONDecodeError:
            return []
    return []


def _save_master(master: list[dict[str, Any]], new_leads: list[dict[str, Any]]) -> None:
    MASTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    MASTER_PATH.write_text(json.dumps(master + new_leads, indent=2, ensure_ascii=False))


def create_data_quality_node(
    emit: Callable[[str, dict[str, Any]], None] | None = None,
    persist_master: bool = True,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Factory for the Data Quality Engine node.

    emit: optional callback matching your SSE emitter, called as
          emit("node_start"/"node_complete", payload).
    persist_master: append the surviving uniques to output/lead_master.json so
          future runs are deduped against them (the diagram's LEAD MASTER store).
    """

    def data_quality_node(state: dict[str, Any]) -> dict[str, Any]:
        if emit:
            emit("node_start", {"node": "data_quality"})

        raw = state.get(LEADS_KEY) or []
        leads = [_to_dict(l) for l in raw]
        master = _load_master() if persist_master else []

        clean_leads, report = process_leads(leads, existing_master=master)

        state[LEADS_KEY] = clean_leads
        state["quality_report"] = report.model_dump()

        if persist_master and clean_leads:
            _save_master(master, clean_leads)

        if emit:
            emit(
                "node_complete",
                {"node": "data_quality", "report": report.model_dump()},
            )
        return state

    return data_quality_node
