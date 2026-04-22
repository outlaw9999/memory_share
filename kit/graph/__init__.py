"""
KIT Graph Module v0.3

Execution-aware dependency graph with materialized queries.
"""

from kit.graph.api import GraphQueryAPI
from kit.graph.cache import QueryCache, cached_blast, cached_impact, clear_all_caches
from kit.graph.materializer import Materializer, GraphSnapshot, materialize_file, create_snapshot
from kit.graph.query import get_blast_radius, TraversalDirection
from kit.graph.resolver import CallResolver, ResolutionMethod, resolve_all_calls, get_resolution_stats
from kit.graph.schema import init_graph_db, migrate_call_resolutions, get_edge_counts

__all__ = [
    "GraphQueryAPI",
    "QueryCache",
    "Materializer",
    "GraphSnapshot",
    "CallResolver",
    "ResolutionMethod",
    "get_blast_radius",
    "TraversalDirection",
    "resolve_all_calls",
    "get_resolution_stats",
    "init_graph_db",
    "migrate_call_resolutions",
    "get_edge_counts",
    "materialize_file",
    "create_snapshot",
    "cached_blast",
    "cached_impact",
    "clear_all_caches",
]