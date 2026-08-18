"""LangGraph research workflow definition.

Wires all nodes together with conditional edges for the research loop.

Graph flow:
START -> interpret_request -> create_research_plan -> discover_companies
       -> research_companies -> find_people -> enrich_contacts
       -> evaluate_evidence -> [sufficient?] -> research_missing (loop)
                                                       |
                                                       v
                                              evaluate_evidence
                                                       |
                                                       v
                                              build_standard_lead -> END
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from app.intelligence import IntelligenceProvider, MockIntelligenceProvider
from app.providers.exa import ExaProvider
from app.providers.firecrawl import FirecrawlProvider
from app.providers.hunter import HunterProvider
from app.providers.tavily import TavilyProvider
from app.state import ResearchState
from app.nodes.interpret_request import create_interpret_request_node
from app.nodes.create_plan import create_plan_node
from app.nodes.discover_companies import create_discover_companies_node
from app.nodes.research_companies import create_research_companies_node
from app.nodes.find_people import create_find_people_node
from app.nodes.enrich_contacts import create_enrich_contacts_node
from app.nodes.evaluate_evidence import create_evaluate_evidence_node
from app.nodes.research_missing import create_research_missing_node
from app.nodes.build_lead import create_build_lead_node


def _should_continue_research(state: ResearchState) -> Literal["sufficient", "research_missing"]:
    """Conditional edge: decide whether to continue researching or build the lead."""
    missing = state.get("missing_information", [])
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 3)

    if not missing:
        return "sufficient"
    if iteration >= max_iter:
        return "sufficient"
    return "research_missing"


def build_research_graph(
    intelligence: IntelligenceProvider | None = None,
    exa: ExaProvider | None = None,
    tavily: TavilyProvider | None = None,
    firecrawl: FirecrawlProvider | None = None,
    hunter: HunterProvider | None = None,
) -> StateGraph:
    """Build and return the compiled research graph.

    If providers are not supplied, mock/default implementations are used.
    """

    intelligence = intelligence or MockIntelligenceProvider()
    exa = exa or ExaProvider()
    tavily = tavily or TavilyProvider()
    firecrawl = firecrawl or FirecrawlProvider()
    hunter = hunter or HunterProvider()

    # Create node functions
    interpret_request = create_interpret_request_node(intelligence)
    create_plan = create_plan_node(intelligence)
    discover_companies = create_discover_companies_node(intelligence, exa, tavily)
    research_companies = create_research_companies_node(intelligence, firecrawl)
    find_people = create_find_people_node(intelligence, exa, tavily)
    enrich_contacts = create_enrich_contacts_node(intelligence, hunter)
    evaluate_evidence = create_evaluate_evidence_node(intelligence)
    research_missing = create_research_missing_node(intelligence, exa, tavily)
    build_lead = create_build_lead_node(intelligence)

    # Build the graph
    graph = StateGraph(ResearchState)

    # Add nodes
    graph.add_node("interpret_request", interpret_request)
    graph.add_node("create_research_plan", create_plan)
    graph.add_node("discover_companies", discover_companies)
    graph.add_node("research_companies", research_companies)
    graph.add_node("find_people", find_people)
    graph.add_node("enrich_contacts", enrich_contacts)
    graph.add_node("evaluate_evidence", evaluate_evidence)
    graph.add_node("research_missing", research_missing)
    graph.add_node("build_standard_lead", build_lead)

    # Wire edges
    graph.set_entry_point("interpret_request")
    graph.add_edge("interpret_request", "create_research_plan")
    graph.add_edge("create_research_plan", "discover_companies")
    graph.add_edge("discover_companies", "research_companies")
    graph.add_edge("research_companies", "find_people")
    graph.add_edge("find_people", "enrich_contacts")
    graph.add_edge("enrich_contacts", "evaluate_evidence")

    # Conditional edge from evaluate_evidence
    graph.add_conditional_edges(
        "evaluate_evidence",
        _should_continue_research,
        {
            "sufficient": "build_standard_lead",
            "research_missing": "research_missing",
        },
    )

    # research_missing loops back to evaluate_evidence
    graph.add_edge("research_missing", "evaluate_evidence")

    # build_standard_lead is the final node
    graph.add_edge("build_standard_lead", END)

    return graph.compile()
