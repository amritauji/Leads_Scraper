"""Research engine entry point.

Usage:
    from app.main import run_research
    result = run_research("Find SaaS companies in India...")

    # With NVIDIA Nemotron:
    from app.main import run_research
    result = run_research("Find SaaS companies in India...", use_nvidia=True)

CLI:
    python -m app.main                              # mock intelligence
    python -m app.main --use-nvidia                 # NVIDIA Nemotron reasoning
"""

from __future__ import annotations

import json
import sys
from typing import Any

from app.graph import build_research_graph
from app.intelligence import IntelligenceProvider, MockIntelligenceProvider
from app.state import create_initial_state


def run_research(
    research_request: str,
    max_iterations: int = 3,
    verbose: bool = True,
    use_nvidia: bool = False,
) -> dict[str, Any]:
    """Execute a full research workflow and return the result.

    Args:
        research_request: Natural language research request.
        max_iterations: Max research loop iterations before forced stop.
        verbose: If True, print execution logs.
        use_nvidia: If True, use NVIDIA Nemotron for reasoning.

    Returns:
        Final state dict containing leads, evidence, and logs.
    """
    intelligence: IntelligenceProvider
    if use_nvidia:
        from app.nvidia_intelligence import NvidiaIntelligenceProvider
        from app.providers.nvidia import NvidiaProvider

        nvidia = NvidiaProvider()  # reads NVIDIA_API_KEY from .env
        intelligence = NvidiaIntelligenceProvider(nvidia=nvidia)
        print("[init] Using NVIDIA Nemotron reasoning")
    else:
        intelligence = MockIntelligenceProvider()

    graph = build_research_graph(intelligence=intelligence)
    initial_state = create_initial_state(research_request, max_iterations=max_iterations)

    if verbose:
        print(f"\n{'='*70}")
        print(f"RESEARCH REQUEST: {research_request.strip()}")
        print(f"{'='*70}\n")

    # Execute the graph
    final_state = graph.invoke(initial_state)

    if verbose:
        _print_results(final_state)

    # Save JSON output to file
    output_dir = "output"
    import os
    os.makedirs(output_dir, exist_ok=True)

    leads = final_state.get("leads", [])
    evidence = final_state.get("evidence", [])

    leads_path = os.path.join(output_dir, "leads.json")
    evidence_path = os.path.join(output_dir, "evidence.json")

    with open(leads_path, "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, default=str)

    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, default=str)

    print(f"\n[output] Leads saved to: {leads_path}")
    print(f"[output] Evidence saved to: {evidence_path}")

    return final_state


def _print_results(state: dict[str, Any]) -> None:
    """Pretty-print the research execution results."""
    print("\n" + "=" * 70)
    print("EXECUTION LOG")
    print("=" * 70)
    for entry in state.get("log", []):
        print(f"  {entry}")

    print("\n" + "=" * 70)
    print("RESEARCH CRITERIA")
    print("=" * 70)
    print(json.dumps(state.get("criteria", {}), indent=2, default=str))

    print("\n" + "=" * 70)
    print("RESEARCH PLAN")
    print("=" * 70)
    for step in state.get("research_plan", []):
        print(f"  [{step['step']}] {step['goal']}")

    print("\n" + "=" * 70)
    print(f"COMPANIES FOUND: {len(state.get('companies', []))}")
    print("=" * 70)
    for company in state.get("companies", []):
        print(f"  - {company.get('name', 'Unknown')} | {company.get('website', 'N/A')} | {company.get('industry', 'N/A')} | {company.get('location', 'N/A')} | founded: {company.get('founded', 'N/A')} | revenue: {company.get('revenue', 'N/A')}")

    print("\n" + "=" * 70)
    print(f"PEOPLE FOUND: {len(state.get('people', []))}")
    print("=" * 70)
    for person in state.get("people", []):
        print(f"  - {person.get('name', 'Unknown')} | {person.get('title', 'N/A')} ({person.get('role', 'N/A')}) @ {person.get('company_name', 'N/A')}")

    print("\n" + "=" * 70)
    print(f"CONTACTS FOUND: {len(state.get('contacts', []))}")
    print("=" * 70)
    for contact in state.get("contacts", []):
        verified = "verified" if contact.get("email_verified") else "unverified"
        print(f"  - {contact.get('email', 'N/A')} ({verified}) | {contact.get('person_name', 'N/A')}")

    print("\n" + "=" * 70)
    print(f"EVIDENCE COLLECTED: {len(state.get('evidence', []))}")
    print("=" * 70)
    for ev in state.get("evidence", []):
        print(f"  - [{ev.get('provider', 'N/A')}] {ev.get('source_title', 'N/A')[:60]}")

    print("\n" + "=" * 70)
    print(f"MISSING INFORMATION: {state.get('missing_information', [])}")
    print(f"Iterations used: {state.get('iteration', 0) + 1} / {state.get('max_iterations', 3)}")
    print("=" * 70)

    print("\n" + "=" * 70)
    print("STANDARD LEAD JSON")
    print("=" * 70)
    leads = state.get("leads", [])
    if leads:
        print(json.dumps(leads, indent=2, default=str))
    else:
        print("  No leads generated.")

    print("\n" + "=" * 70)
    print("RESEARCH COMPLETE")
    print("=" * 70 + "\n")


def _parse_args() -> dict[str, Any]:
    """Parse CLI arguments."""
    args = sys.argv[1:]
    use_nvidia = "--use-nvidia" in args
    return {"use_nvidia": use_nvidia}


if __name__ == "__main__":
    parsed = _parse_args()
    result = run_research(
        "Find SaaS companies in India with 100-500 employees "
        "and identify their CEO/Founder and Marketing Head.",
        use_nvidia=parsed["use_nvidia"],
    )
