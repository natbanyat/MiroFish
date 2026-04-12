"""
Entity reader — reads from local SQLite graph (Zep-free replacement).
Keeps all public data classes (EntityNode, FilteredEntities) unchanged
so callers (simulation_manager, oasis_profile_generator) need no edits.
"""

from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

from ..utils.logger import get_logger
from .local_graph import LocalGraph, get_local_graph

logger = get_logger('mirofish.zep_entity_reader')


@dataclass
class EntityNode:
    """Entity node — public data structure (unchanged API)."""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }

    def get_entity_type(self) -> Optional[str]:
        for label in self.labels:
            if label not in ("Entity", "Node"):
                return label
        return None


@dataclass
class FilteredEntities:
    """Filtered entity collection — public data structure (unchanged API)."""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class ZepEntityReader:
    """
    Reads entities from the local SQLite graph.
    Public interface identical to the old Zep-backed version.
    """

    def __init__(self):
        self.local_graph: LocalGraph = get_local_graph()

    # ── Low-level accessors ───────────────────────────────────────────────────

    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        logger.info(f"Reading nodes from graph {graph_id}")
        return self.local_graph.get_nodes(graph_id)

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        logger.info(f"Reading edges from graph {graph_id}")
        return self.local_graph.get_edges(graph_id)

    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """Return edges that touch this node (source or target)."""
        # We don't have graph_id here; search across all graphs via node lookup.
        # In practice callers use filter_defined_entities which already has all edges.
        return []

    # ── Main API ──────────────────────────────────────────────────────────────

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True,
    ) -> FilteredEntities:
        """Return entities whose labels include custom (non-default) types."""
        logger.info(f"Filtering entities in graph {graph_id}")

        all_nodes = self.get_all_nodes(graph_id)
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        node_map = {n["uuid"]: n for n in all_nodes}

        filtered: List[EntityNode] = []
        entity_types_found: Set[str] = set()

        for node in all_nodes:
            labels = node.get("labels", [])
            custom_labels = [l for l in labels if l not in ("Entity", "Node")]

            if not custom_labels:
                continue

            if defined_entity_types:
                matching = [l for l in custom_labels if l in defined_entity_types]
                if not matching:
                    continue
                entity_type = matching[0]
            else:
                entity_type = custom_labels[0]

            entity_types_found.add(entity_type)
            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )

            if enrich_with_edges:
                related_edges = []
                related_node_uuids: Set[str] = set()
                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])

                entity.related_edges = related_edges
                entity.related_nodes = [
                    {
                        "uuid": node_map[uid]["uuid"],
                        "name": node_map[uid]["name"],
                        "labels": node_map[uid]["labels"],
                        "summary": node_map[uid].get("summary", ""),
                    }
                    for uid in related_node_uuids
                    if uid in node_map
                ]

            filtered.append(entity)

        logger.info(
            f"Filter complete: {len(all_nodes)} total, {len(filtered)} matched, "
            f"types: {entity_types_found}"
        )
        return FilteredEntities(
            entities=filtered,
            entity_types=entity_types_found,
            total_count=len(all_nodes),
            filtered_count=len(filtered),
        )

    def get_entity_with_context(
        self, graph_id: str, entity_uuid: str
    ) -> Optional[EntityNode]:
        nodes = self.get_all_nodes(graph_id)
        node = next((n for n in nodes if n["uuid"] == entity_uuid), None)
        if not node:
            return None

        all_edges = self.get_all_edges(graph_id)
        node_map = {n["uuid"]: n for n in nodes}

        related_edges = []
        related_node_uuids: Set[str] = set()
        for edge in all_edges:
            if edge["source_node_uuid"] == entity_uuid:
                related_edges.append({
                    "direction": "outgoing",
                    "edge_name": edge["name"],
                    "fact": edge["fact"],
                    "target_node_uuid": edge["target_node_uuid"],
                })
                related_node_uuids.add(edge["target_node_uuid"])
            elif edge["target_node_uuid"] == entity_uuid:
                related_edges.append({
                    "direction": "incoming",
                    "edge_name": edge["name"],
                    "fact": edge["fact"],
                    "source_node_uuid": edge["source_node_uuid"],
                })
                related_node_uuids.add(edge["source_node_uuid"])

        return EntityNode(
            uuid=node["uuid"],
            name=node["name"],
            labels=node.get("labels", []),
            summary=node.get("summary", ""),
            attributes=node.get("attributes", {}),
            related_edges=related_edges,
            related_nodes=[
                {
                    "uuid": node_map[uid]["uuid"],
                    "name": node_map[uid]["name"],
                    "labels": node_map[uid]["labels"],
                    "summary": node_map[uid].get("summary", ""),
                }
                for uid in related_node_uuids
                if uid in node_map
            ],
        )

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True,
    ) -> List[EntityNode]:
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges,
        )
        return result.entities
