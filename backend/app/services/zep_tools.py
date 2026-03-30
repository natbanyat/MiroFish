"""
Graph retrieval tools — local SQLite replacement for Zep Cloud.

All public data classes and method signatures are preserved so that
report_agent.py and other callers need no changes.

Core tools:
1. insight_forge   — deep multi-query search with LLM sub-question decomposition
2. panorama_search — full-graph scan with active/historical split
3. quick_search    — fast keyword search
4. interview_agents — OASIS simulation agent interviews (no Zep dependency)
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .local_graph import LocalGraph, get_local_graph

logger = get_logger('mirofish.zep_tools')


# ── Data classes (public API unchanged) ──────────────────────────────────────

@dataclass
class SearchResult:
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count,
        }

    def to_text(self) -> str:
        parts = [f"Query: {self.query}", f"Found: {self.total_count} facts"]
        if self.facts:
            parts.append("\n### Facts:")
            for i, f in enumerate(self.facts, 1):
                parts.append(f"{i}. {f}")
        return "\n".join(parts)


@dataclass
class NodeInfo:
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
        }

    def to_text(self) -> str:
        etype = next((l for l in self.labels if l not in ("Entity", "Node")), "Entity")
        return f"Entity: {self.name} (type: {etype})\nSummary: {self.summary}"


@dataclass
class EdgeInfo:
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at,
        }

    def to_text(self, include_temporal: bool = False) -> str:
        src = self.source_node_name or self.source_node_uuid[:8]
        tgt = self.target_node_name or self.target_node_uuid[:8]
        txt = f"Relation: {src} --[{self.name}]--> {tgt}\nFact: {self.fact}"
        if include_temporal and (self.valid_at or self.invalid_at):
            txt += f"\nValid: {self.valid_at or '?'} - {self.invalid_at or 'now'}"
        return txt

    @property
    def is_expired(self) -> bool:
        return self.expired_at is not None

    @property
    def is_invalid(self) -> bool:
        return self.invalid_at is not None


@dataclass
class InsightForgeResult:
    query: str
    simulation_requirement: str
    sub_queries: List[str]
    semantic_facts: List[str] = field(default_factory=list)
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)
    relationship_chains: List[str] = field(default_factory=list)
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships,
        }

    def to_text(self) -> str:
        parts = [
            f"## Deep Analysis: {self.query}",
            f"Facts: {self.total_facts} | Entities: {self.total_entities} | Relations: {self.total_relationships}",
        ]
        if self.semantic_facts:
            parts.append("\n### Key Facts")
            for i, f in enumerate(self.semantic_facts[:20], 1):
                parts.append(f'{i}. "{f}"')
            if len(self.semantic_facts) > 20:
                parts.append(f"... ({len(self.semantic_facts) - 20} more)")
        if self.entity_insights:
            parts.append("\n### Core Entities")
            for e in self.entity_insights[:10]:
                parts.append(f"- **{e.get('name')}** ({e.get('type')}): {e.get('summary', '')[:100]}")
        if self.relationship_chains:
            parts.append("\n### Relationship Chains")
            for c in self.relationship_chains[:10]:
                parts.append(f"- {c}")
        return "\n".join(parts)


@dataclass
class PanoramaResult:
    query: str
    all_nodes: List[NodeInfo] = field(default_factory=list)
    all_edges: List[EdgeInfo] = field(default_factory=list)
    active_facts: List[str] = field(default_factory=list)
    historical_facts: List[str] = field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [n.to_dict() for n in self.all_nodes],
            "all_edges": [e.to_dict() for e in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count,
        }

    def to_text(self) -> str:
        parts = [
            "## Panorama Search (Full Graph View)",
            f"Query: {self.query}",
            f"- Active facts: {self.active_count} | Historical: {self.historical_count}",
        ]
        if self.active_facts:
            parts.append("\n### Active Facts")
            for i, f in enumerate(self.active_facts[:25], 1):
                parts.append(f'{i}. "{f}"')
            if len(self.active_facts) > 25:
                parts.append(f"... ({len(self.active_facts) - 25} more)")
        if self.historical_facts:
            parts.append("\n### Historical Facts")
            for i, f in enumerate(self.historical_facts[:15], 1):
                parts.append(f'{i}. "{f}"')
        if self.all_nodes:
            parts.append(f"\n### Entities ({self.total_nodes})")
            for node in self.all_nodes[:15]:
                etype = next((l for l in node.labels if l not in ("Entity", "Node")), "Entity")
                parts.append(f"- **{node.name}** ({etype})")
        return "\n".join(parts)


@dataclass
class AgentInterview:
    agent_name: str
    agent_role: str
    agent_bio: str
    question: str
    response: str
    key_quotes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes,
        }

    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        text += f"_Bio: {self.agent_bio}_\n\n"
        text += f"**Q:** {self.question}\n\n"
        text += f"**A:** {self.response}\n"
        if self.key_quotes:
            text += "\n**Key Quotes:**\n"
            for quote in self.key_quotes:
                clean = quote.strip()
                if clean and len(clean) >= 10:
                    text += f'> "{clean}"\n'
        return text


@dataclass
class InterviewResult:
    interview_topic: str
    interview_questions: List[str]
    selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    interviews: List[AgentInterview] = field(default_factory=list)
    selection_reasoning: str = ""
    summary: str = ""
    total_agents: int = 0
    interviewed_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "selected_agents": self.selected_agents,
            "interviews": [i.to_dict() for i in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count,
        }

    def to_text(self) -> str:
        parts = [
            "## Deep Interview Report",
            f"**Topic:** {self.interview_topic}",
            f"**Interviewed:** {self.interviewed_count} / {self.total_agents} agents",
            "\n### Agent Selection Rationale",
            self.selection_reasoning or "(auto-selected)",
            "\n---\n### Interview Transcripts",
        ]
        for i, iv in enumerate(self.interviews, 1):
            parts.append(f"\n#### Interview #{i}: {iv.agent_name}")
            parts.append(iv.to_text())
            parts.append("\n---")
        parts.append("\n### Summary")
        parts.append(self.summary or "(none)")
        return "\n".join(parts)


# ── Service ───────────────────────────────────────────────────────────────────

_EMPTY_NODE = NodeInfo("", "", [], "", {})


class ZepToolsService:
    """
    Graph retrieval service backed by local SQLite.
    Public interface identical to the old Zep-backed version.
    """

    _CACHE_TTL = 120  # seconds

    def __init__(self, api_key: Optional[str] = None, llm_client: Optional[LLMClient] = None):
        # api_key kept for signature compatibility — not used
        self.local_graph: LocalGraph = get_local_graph()
        self._llm_client = llm_client
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}
        logger.info("ZepToolsService (local SQLite) initialised")

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def _get_cached(self, key: str):
        ts = self._cache_ts.get(key, 0)
        if time.time() - ts < self._CACHE_TTL and key in self._cache:
            return self._cache[key]
        return None

    def _set_cached(self, key: str, value):
        self._cache[key] = value
        self._cache_ts[key] = time.time()

    def invalidate_cache(self, graph_id: str = None):
        if graph_id:
            for k in [k for k in self._cache if k.startswith(f"{graph_id}:")]:
                self._cache.pop(k, None)
                self._cache_ts.pop(k, None)
        else:
            self._cache.clear()
            self._cache_ts.clear()

    @property
    def llm(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    # ── Node / edge accessors ─────────────────────────────────────────────────

    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        cache_key = f"{graph_id}:nodes"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        raw = self.local_graph.get_nodes(graph_id)
        result = [
            NodeInfo(
                uuid=n["uuid"],
                name=n["name"],
                labels=n["labels"],
                summary=n["summary"],
                attributes=n["attributes"],
            )
            for n in raw
        ]
        self._set_cached(cache_key, result)
        logger.info(f"Loaded {len(result)} nodes for graph {graph_id}")
        return result

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        cache_key = f"{graph_id}:edges"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        raw = self.local_graph.get_edges(graph_id)
        result = [
            EdgeInfo(
                uuid=e["uuid"],
                name=e["name"],
                fact=e["fact"],
                source_node_uuid=e["source_node_uuid"],
                target_node_uuid=e["target_node_uuid"],
                source_node_name=e.get("source_node_name"),
                target_node_name=e.get("target_node_name"),
                created_at=e.get("created_at"),
                valid_at=e.get("valid_at"),
                invalid_at=e.get("invalid_at"),
                expired_at=e.get("expired_at"),
            )
            for e in raw
        ]
        self._set_cached(cache_key, result)
        logger.info(f"Loaded {len(result)} edges for graph {graph_id}")
        return result

    def get_node_detail(self, node_uuid: str) -> Optional[NodeInfo]:
        # Scan all cached nodes — avoid per-node queries
        for key, val in self._cache.items():
            if key.endswith(":nodes") and isinstance(val, list):
                for n in val:
                    if n.uuid == node_uuid:
                        return n
        return None

    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        return [
            e for e in self.get_all_edges(graph_id)
            if e.source_node_uuid == node_uuid or e.target_node_uuid == node_uuid
        ]

    def get_entities_by_type(self, graph_id: str, entity_type: str) -> List[NodeInfo]:
        return [n for n in self.get_all_nodes(graph_id) if entity_type in n.labels]

    # ── Search ────────────────────────────────────────────────────────────────

    def search_graph(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges",
    ) -> SearchResult:
        """Keyword-based search (replaces Zep semantic search)."""
        query = query[:400]
        logger.info(f"Searching graph {graph_id}: {query[:50]}...")

        query_lower = query.lower()
        keywords = [w for w in query_lower.replace(",", " ").split() if len(w) > 1]

        def score(text: str) -> int:
            if not text:
                return 0
            tl = text.lower()
            if query_lower in tl:
                return 100
            return sum(10 for kw in keywords if kw in tl)

        facts, edges_out, nodes_out = [], [], []

        if scope in ("edges", "both"):
            scored = []
            for edge in self.get_all_edges(graph_id):
                s = score(edge.fact) + score(edge.name)
                if s > 0:
                    scored.append((s, edge))
            scored.sort(key=lambda x: x[0], reverse=True)
            for _, edge in scored[:limit]:
                if edge.fact:
                    facts.append(edge.fact)
                edges_out.append({
                    "uuid": edge.uuid,
                    "name": edge.name,
                    "fact": edge.fact,
                    "source_node_uuid": edge.source_node_uuid,
                    "target_node_uuid": edge.target_node_uuid,
                })

        if scope in ("nodes", "both"):
            scored_n = []
            for node in self.get_all_nodes(graph_id):
                s = score(node.name) + score(node.summary)
                if s > 0:
                    scored_n.append((s, node))
            scored_n.sort(key=lambda x: x[0], reverse=True)
            for _, node in scored_n[:limit]:
                nodes_out.append({
                    "uuid": node.uuid,
                    "name": node.name,
                    "labels": node.labels,
                    "summary": node.summary,
                })
                if node.summary:
                    facts.append(f"[{node.name}]: {node.summary}")

        logger.info(f"Search complete: {len(facts)} facts")
        return SearchResult(facts=facts, edges=edges_out, nodes=nodes_out, query=query, total_count=len(facts))

    # ── High-level tools ──────────────────────────────────────────────────────

    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 3,
    ) -> InsightForgeResult:
        """Deep multi-query search with LLM sub-question generation."""
        logger.info(f"InsightForge: {query[:50]}")

        result = InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[],
        )

        # 1. Generate sub-queries
        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries,
        )
        result.sub_queries = sub_queries

        # 2. Search main query + each sub-query (no sleep needed — local DB)
        all_facts: List[str] = []
        all_edges: List[Dict] = []
        seen_facts: set = set()

        for q in [query] + sub_queries:
            sr = self.search_graph(graph_id=graph_id, query=q, limit=20, scope="edges")
            for fact in sr.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)
            all_edges.extend(sr.edges)

        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)

        # 3. Resolve entity insights from cached nodes
        entity_uuids = set()
        for edge_data in all_edges:
            entity_uuids.add(edge_data.get("source_node_uuid", ""))
            entity_uuids.add(edge_data.get("target_node_uuid", ""))
        entity_uuids.discard("")

        all_nodes = self.get_all_nodes(graph_id)
        node_map = {n.uuid: n for n in all_nodes}

        entity_insights = []
        for uid in entity_uuids:
            node = node_map.get(uid)
            if not node:
                continue
            etype = next((l for l in node.labels if l not in ("Entity", "Node")), "Entity")
            entity_insights.append({
                "uuid": node.uuid,
                "name": node.name,
                "type": etype,
                "summary": node.summary,
                "related_facts": [f for f in all_facts if node.name.lower() in f.lower()][:5],
            })

        result.entity_insights = entity_insights[:15]
        result.total_entities = len(entity_insights)

        # 4. Relationship chains
        chains: List[str] = []
        seen_chains: set = set()
        for edge_data in all_edges:
            if len(chains) >= 20:
                break
            src_name = node_map.get(edge_data.get("source_node_uuid", ""), _EMPTY_NODE).name
            tgt_name = node_map.get(edge_data.get("target_node_uuid", ""), _EMPTY_NODE).name
            chain = f"{src_name} --[{edge_data.get('name', '')}]--> {tgt_name}"
            if chain not in seen_chains:
                chains.append(chain)
                seen_chains.add(chain)

        result.relationship_chains = chains
        result.total_relationships = len(chains)

        logger.info(
            f"InsightForge done: {result.total_facts} facts, "
            f"{result.total_entities} entities, {result.total_relationships} chains"
        )
        return result

    def panorama_search(
        self,
        graph_id: str,
        query: str,
        include_expired: bool = True,
        limit: int = 50,
    ) -> PanoramaResult:
        """Full-graph scan with active/historical split."""
        logger.info(f"PanoramaSearch: {query[:50]}")

        result = PanoramaResult(query=query)

        all_nodes = self.get_all_nodes(graph_id)
        node_map = {n.uuid: n for n in all_nodes}
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)

        all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.all_edges = all_edges
        result.total_edges = len(all_edges)

        query_lower = query.lower()
        keywords = [w for w in query_lower.replace(",", " ").split() if len(w) > 1]

        def relevance(fact: str) -> int:
            fl = fact.lower()
            if query_lower in fl:
                return 100
            return sum(10 for kw in keywords if kw in fl)

        active_facts, historical_facts = [], []
        for edge in all_edges:
            if not edge.fact:
                continue
            if edge.is_expired or edge.is_invalid:
                valid_at = edge.valid_at or "?"
                end = edge.invalid_at or edge.expired_at or "?"
                historical_facts.append(f"[{valid_at} - {end}] {edge.fact}")
            else:
                active_facts.append(edge.fact)

        active_facts.sort(key=relevance, reverse=True)
        historical_facts.sort(key=relevance, reverse=True)

        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)

        logger.info(f"PanoramaSearch done: {result.active_count} active, {result.historical_count} historical")
        return result

    def quick_search(self, graph_id: str, query: str, limit: int = 10) -> SearchResult:
        """Fast keyword search."""
        logger.info(f"QuickSearch: {query[:50]}")
        return self.search_graph(graph_id=graph_id, query=query, limit=limit, scope="edges")

    def get_entity_summary(self, graph_id: str, entity_name: str) -> Dict[str, Any]:
        search_result = self.search_graph(graph_id=graph_id, query=entity_name, limit=20)
        all_nodes = self.get_all_nodes(graph_id)
        entity_node = next((n for n in all_nodes if n.name.lower() == entity_name.lower()), None)
        related_edges = self.get_node_edges(graph_id, entity_node.uuid) if entity_node else []
        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges),
        }

    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)
        entity_types: Dict[str, int] = {}
        for n in nodes:
            for l in n.labels:
                if l not in ("Entity", "Node"):
                    entity_types[l] = entity_types.get(l, 0) + 1
        relation_types: Dict[str, int] = {}
        for e in edges:
            relation_types[e.name] = relation_types.get(e.name, 0) + 1
        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types,
        }

    def get_simulation_context(
        self,
        graph_id: str,
        simulation_requirement: str,
        limit: int = 30,
    ) -> Dict[str, Any]:
        search_result = self.search_graph(graph_id=graph_id, query=simulation_requirement, limit=limit)
        all_nodes = self.get_all_nodes(graph_id)
        all_edges = self.get_all_edges(graph_id)
        entity_types: Dict[str, int] = {}
        entities = []
        for n in all_nodes:
            custom = [l for l in n.labels if l not in ("Entity", "Node")]
            for l in custom:
                entity_types[l] = entity_types.get(l, 0) + 1
            if custom:
                entities.append({"name": n.name, "type": custom[0], "summary": n.summary})
        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": {
                "graph_id": graph_id,
                "total_nodes": len(all_nodes),
                "total_edges": len(all_edges),
                "entity_types": entity_types,
            },
            "entities": entities[:limit],
            "total_entities": len(entities),
        }

    # ── LLM helpers ───────────────────────────────────────────────────────────

    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 3,
    ) -> List[str]:
        system = (
            "Decompose the question into independently searchable sub-questions covering different angles. "
            'Return JSON: {"sub_queries": ["q1", ...]}'
        )
        user = f"Context: {simulation_requirement[:300]}\nQuestion: {query}\nGenerate {max_queries} sub-questions."
        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
                max_tokens=512,
            )
            return [str(q) for q in response.get("sub_queries", [])[:max_queries]]
        except Exception as e:
            logger.warning(f"Sub-query generation failed: {e}")
            return [
                f"Main participants and roles in {query}",
                f"Causes, effects and developments of {query}",
                f"Reactions and stances regarding {query}",
            ][:max_queries]

    # ── Interview agents (no graph dependency — unchanged logic) ──────────────

    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: List[str] = None,
    ) -> InterviewResult:
        from .simulation_runner import SimulationRunner

        logger.info(f"InterviewAgents: {interview_requirement[:50]}")

        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or [],
        )

        profiles = self._load_agent_profiles(simulation_id)
        if not profiles:
            result.summary = "No agent profiles found for this simulation."
            return result

        result.total_agents = len(profiles)

        selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents,
        )
        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning

        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents,
            )

        combined_prompt = "\n".join(
            [f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)]
        )
        INTERVIEW_PREFIX = (
            "You are being interviewed. Answer based on your persona and past memories.\n"
            "Requirements:\n"
            "1. Answer in natural language — no tool calls\n"
            "2. Do not return JSON or tool-call format\n"
            "3. Answer each question prefixed with 'Question X:'\n"
            "4. Separate answers with blank lines\n\n"
        )
        optimized_prompt = f"{INTERVIEW_PREFIX}{combined_prompt}"

        try:
            interviews_request = [
                {"agent_id": idx, "prompt": optimized_prompt}
                for idx in selected_indices
            ]
            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None,
                timeout=180.0,
            )

            if not api_result.get("success", False):
                result.summary = f"Interview API failed: {api_result.get('error', 'unknown error')}"
                return result

            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}

            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", "unknown")
                agent_bio = agent.get("bio", "")

                twitter_res = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_res = results_dict.get(f"reddit_{agent_idx}", {})
                tw = self._clean_tool_call_response(twitter_res.get("response", ""))
                rd = self._clean_tool_call_response(reddit_res.get("response", ""))

                tw_text = tw if tw else "(no response)"
                rd_text = rd if rd else "(no response)"
                response_text = f"[Twitter]\n{tw_text}\n\n[Reddit]\n{rd_text}"

                combined = f"{tw} {rd}"
                clean = re.sub(r"#{1,6}\s+", "", combined)
                clean = re.sub(r"\{[^}]*tool_name[^}]*\}", "", clean)
                sentences = re.split(r"[.!?。！？]", clean)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150 and not s.strip().startswith("{")
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "." for s in meaningful[:3]]

                result.interviews.append(AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5],
                ))

            result.interviewed_count = len(result.interviews)

        except (ValueError, Exception) as e:
            logger.error(f"Interview failed: {e}")
            result.summary = f"Interview failed: {e}"
            return result

        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement,
            )

        logger.info(f"InterviewAgents done: {result.interviewed_count} agents interviewed")
        return result

    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        if not response or not response.strip().startswith("{"):
            return response
        text = response.strip()
        if "tool_name" not in text[:80]:
            return response
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "arguments" in data:
                for key in ("content", "text", "body", "message", "reply"):
                    if key in data["arguments"]:
                        return str(data["arguments"][key])
        except Exception:
            m = re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if m:
                return m.group(1).replace("\\n", "\n").replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        import csv
        import os

        sim_dir = os.path.join(
            os.path.dirname(__file__), f"../../uploads/simulations/{simulation_id}"
        )
        profiles = []

        reddit_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_path):
            try:
                with open(reddit_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read reddit_profiles.json: {e}")

        twitter_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_path):
            try:
                with open(twitter_path, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "unknown",
                        })
                return profiles
            except Exception as e:
                logger.warning(f"Failed to read twitter_profiles.csv: {e}")

        return profiles

    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int,
    ):
        summaries = [
            {
                "index": i,
                "name": p.get("realname", p.get("username", f"Agent_{i}")),
                "profession": p.get("profession", "unknown"),
                "bio": p.get("bio", "")[:200],
            }
            for i, p in enumerate(profiles)
        ]
        system = (
            "Select the most relevant agents to interview based on the requirement. "
            'Return JSON: {"selected_indices": [...], "reasoning": "..."}'
        )
        user = (
            f"Requirement: {interview_requirement}\n"
            f"Background: {simulation_requirement or 'n/a'}\n"
            f"Agents: {json.dumps(summaries, ensure_ascii=False)}\n"
            f"Select up to {max_agents} agents."
        )
        try:
            resp = self.llm.chat_json(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.3,
            )
            indices = resp.get("selected_indices", [])[:max_agents]
            reasoning = resp.get("reasoning", "auto-selected")
            valid = [(i, profiles[i]) for i in indices if 0 <= i < len(profiles)]
            return [p for _, p in valid], [i for i, _ in valid], reasoning
        except Exception as e:
            logger.warning(f"Agent selection failed: {e}")
            n = min(max_agents, len(profiles))
            return profiles[:n], list(range(n)), "default selection"

    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: List[Dict[str, Any]],
    ) -> List[str]:
        roles = [a.get("profession", "unknown") for a in selected_agents]
        system = (
            "Generate 3-5 open interview questions for the given topic. "
            'Return JSON: {"questions": [...]}'
        )
        user = (
            f"Topic: {interview_requirement}\n"
            f"Background: {simulation_requirement or 'n/a'}\n"
            f"Agent roles: {', '.join(roles)}"
        )
        try:
            resp = self.llm.chat_json(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.5,
            )
            return resp.get("questions", [f"What is your view on {interview_requirement}?"])
        except Exception as e:
            logger.warning(f"Question generation failed: {e}")
            return [
                f"What is your view on {interview_requirement}?",
                "How has this affected you or those you represent?",
                "What changes would you recommend?",
            ]

    def _generate_interview_summary(
        self, interviews: List[AgentInterview], interview_requirement: str
    ) -> str:
        if not interviews:
            return "No interviews completed."
        texts = [
            f"[{iv.agent_name} ({iv.agent_role})]\n{iv.response[:500]}"
            for iv in interviews
        ]
        system = (
            "Summarise the key views from these interviews in ≤800 words. "
            "Use plain paragraphs; no Markdown headings or dividers."
        )
        user = f"Topic: {interview_requirement}\n\n{''.join(texts)}"
        try:
            return self.llm.chat(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.3,
                max_tokens=800,
            )
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            return f"Interviewed {len(interviews)} agents: " + ", ".join(i.agent_name for i in interviews)
