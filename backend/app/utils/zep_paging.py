"""
zep_paging.py — stub module kept for import compatibility.
Zep Cloud has been replaced by local SQLite (local_graph.py).
These functions are no longer used but kept to avoid ImportError
if any module has a stale reference.
"""

from ..utils.logger import get_logger

logger = get_logger('mirofish.zep_paging')


def fetch_all_nodes(client, graph_id, **kwargs):
    logger.warning("fetch_all_nodes called on stub — Zep removed. Use LocalGraph.get_nodes().")
    return []


def fetch_all_edges(client, graph_id, **kwargs):
    logger.warning("fetch_all_edges called on stub — Zep removed. Use LocalGraph.get_edges().")
    return []
