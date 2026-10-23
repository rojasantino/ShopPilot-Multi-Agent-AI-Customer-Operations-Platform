"""Supervisor graph.

classify -> supervisor <-> {order|returns|product|knowledge} -> compose -> review
                                                                   |-- fail (1st) -> retry -> compose
                                                                   |-- fail (2nd) -> escalate -> END
                                                                   `-- pass -> END
"""

from langgraph.graph import END, START, StateGraph

from app.agents.composer import compose_node
from app.agents.nodes import AGENT_NODES, classify_node, supervisor_node
from app.agents.reviewer import escalate_node, retry_node, review_node
from app.agents.state import AgentState

MAX_RETRIES = 1


def route_from_supervisor(state: AgentState) -> str:
    return state.get("next_agent") or "compose"


def route_after_review(state: AgentState) -> str:
    if state["review"]["passed"]:
        return "end"
    return "retry" if state.get("retries", 0) < MAX_RETRIES else "escalate"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("classify", classify_node)
    graph.add_node("supervisor", supervisor_node)
    for name, node in AGENT_NODES.items():
        graph.add_node(name, node)
    graph.add_node("compose", compose_node)
    graph.add_node("review", review_node)
    graph.add_node("retry", retry_node)
    graph.add_node("escalate", escalate_node)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "supervisor")
    graph.add_conditional_edges(
        "supervisor", route_from_supervisor, {**{n: n for n in AGENT_NODES}, "compose": "compose"}
    )
    for name in AGENT_NODES:
        graph.add_edge(name, "supervisor")
    graph.add_edge("compose", "review")
    graph.add_conditional_edges(
        "review", route_after_review, {"end": END, "retry": "retry", "escalate": "escalate"}
    )
    graph.add_edge("retry", "compose")
    graph.add_edge("escalate", END)
    return graph.compile()
