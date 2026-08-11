"""Construcción del grafo de diff con LangGraph."""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.graph.nodes import load_instance_a, load_instance_b, match, normalize, report
from src.graph.state import DiffState

RECURSION_LIMIT = 25


def construir_grafo():
    grafo = StateGraph(DiffState)

    grafo.add_node("load_instance_a", load_instance_a)
    grafo.add_node("load_instance_b", load_instance_b)
    grafo.add_node("normalize", normalize)
    grafo.add_node("match", match)
    grafo.add_node("report", report)

    grafo.set_entry_point("load_instance_a")
    grafo.add_edge("load_instance_a", "load_instance_b")
    grafo.add_edge("load_instance_b", "normalize")
    grafo.add_edge("normalize", "match")
    grafo.add_edge("match", "report")
    grafo.add_edge("report", END)

    return grafo.compile(checkpointer=MemorySaver())
