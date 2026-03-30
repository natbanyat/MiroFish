"""
Local SQLite-backed knowledge graph — drop-in Zep replacement.

Handles:
- Graph creation and ontology storage
- Entity (node) and relationship (edge) storage
- LLM-based entity extraction from text chunks
- Keyword-based search (replaces Zep vector search)
- Activity log ingestion (replaces Zep graph.add episodes)
"""

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.local_graph')


def _now() -> str:
    return datetime.utcnow().isoformat()


def _score(query_lower: str, keywords: List[str], text: str) -> int:
    """Simple keyword relevance score."""
    if not text:
        return 0
    tl = text.lower()
    if query_lower in tl:
        return 100
    return sum(2 for kw in keywords if kw in tl)


def _node_row(row) -> Dict[str, Any]:
    return {
        "uuid": row["uuid"],
        "name": row["name"],
        "labels": json.loads(row["labels"] or "[]"),
        "summary": row["summary"] or "",
        "attributes": json.loads(row["attributes"] or "{}"),
        "created_at": row["created_at"],
    }


def _edge_row(row, node_map: Dict[str, str] = None) -> Dict[str, Any]:
    nm = node_map or {}
    return {
        "uuid": row["uuid"],
        "name": row["name"] or "",
        "fact": row["fact"] or "",
        "source_node_uuid": row["source_node_uuid"],
        "target_node_uuid": row["target_node_uuid"],
        "source_node_name": nm.get(row["source_node_uuid"], ""),
        "target_node_name": nm.get(row["target_node_uuid"], ""),
        "attributes": json.loads(row["attributes"] or "{}"),
        "created_at": row["created_at"],
        "valid_at": row["valid_at"],
        "invalid_at": row["invalid_at"],
        "expired_at": row["expired_at"],
    }


class LocalGraph:
    """SQLite-backed knowledge graph. Thread-safe via WAL + lock."""

    _lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = db_path
        else:
            uploads = Path(Config.UPLOAD_FOLDER)
            self.db_path = str(uploads.parent / "graphs.db")
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        with self._lock, self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS graphs (
                    graph_id   TEXT PRIMARY KEY,
                    name       TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    ontology   TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS nodes (
                    uuid       TEXT PRIMARY KEY,
                    graph_id   TEXT NOT NULL,
                    name       TEXT NOT NULL,
                    labels     TEXT DEFAULT '[]',
                    summary    TEXT DEFAULT '',
                    attributes TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS edges (
                    uuid             TEXT PRIMARY KEY,
                    graph_id         TEXT NOT NULL,
                    name             TEXT DEFAULT '',
                    fact             TEXT DEFAULT '',
                    source_node_uuid TEXT NOT NULL,
                    target_node_uuid TEXT NOT NULL,
                    attributes       TEXT DEFAULT '{}',
                    valid_at         TEXT,
                    invalid_at       TEXT,
                    expired_at       TEXT,
                    created_at       TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_nodes_graph ON nodes(graph_id);
                CREATE INDEX IF NOT EXISTS idx_nodes_name  ON nodes(graph_id, name);
                CREATE INDEX IF NOT EXISTS idx_edges_graph ON edges(graph_id);
                CREATE INDEX IF NOT EXISTS idx_edges_src   ON edges(source_node_uuid);
                CREATE INDEX IF NOT EXISTS idx_edges_tgt   ON edges(target_node_uuid);
            """)

    # ── Graph CRUD ──────────────────────────────────────────────────────────

    def create_graph(self, name: str, description: str = "", graph_id: str = None) -> str:
        gid = graph_id or f"mirofish_{uuid.uuid4().hex[:16]}"
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO graphs (graph_id, name, description, ontology, created_at) "
                "VALUES (?,?,?,'{}',?)",
                (gid, name, description, _now()),
            )
        logger.info(f"Graph created: {gid}")
        return gid

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        with self._lock, self._conn() as conn:
            conn.execute(
                "UPDATE graphs SET ontology=? WHERE graph_id=?",
                (json.dumps(ontology, ensure_ascii=False), graph_id),
            )

    def get_ontology(self, graph_id: str) -> Dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT ontology FROM graphs WHERE graph_id=?", (graph_id,)
            ).fetchone()
        return json.loads(row["ontology"] or "{}") if row else {}

    def delete_graph(self, graph_id: str):
        with self._lock, self._conn() as conn:
            conn.execute("DELETE FROM edges WHERE graph_id=?", (graph_id,))
            conn.execute("DELETE FROM nodes WHERE graph_id=?", (graph_id,))
            conn.execute("DELETE FROM graphs WHERE graph_id=?", (graph_id,))
        logger.info(f"Graph deleted: {graph_id}")

    # ── Node CRUD ────────────────────────────────────────────────────────────

    def upsert_node(
        self,
        graph_id: str,
        name: str,
        labels: List[str],
        summary: str = "",
        attributes: Dict = None,
    ) -> str:
        """Insert or update node by (graph_id, name). Returns uuid."""
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT uuid FROM nodes WHERE graph_id=? AND name=?", (graph_id, name)
            ).fetchone()
            if row:
                node_uuid = row["uuid"]
                conn.execute(
                    "UPDATE nodes SET labels=?, summary=?, attributes=? WHERE uuid=?",
                    (
                        json.dumps(labels),
                        summary or "",
                        json.dumps(attributes or {}),
                        node_uuid,
                    ),
                )
            else:
                node_uuid = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO nodes (uuid, graph_id, name, labels, summary, attributes, created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        node_uuid,
                        graph_id,
                        name,
                        json.dumps(labels),
                        summary or "",
                        json.dumps(attributes or {}),
                        _now(),
                    ),
                )
        return node_uuid

    def get_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM nodes WHERE graph_id=?", (graph_id,)
            ).fetchall()
        return [_node_row(r) for r in rows]

    # ── Edge CRUD ────────────────────────────────────────────────────────────

    def add_edge(
        self,
        graph_id: str,
        source_uuid: str,
        target_uuid: str,
        name: str,
        fact: str,
        attributes: Dict = None,
    ) -> str:
        edge_uuid = str(uuid.uuid4())
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT INTO edges "
                "(uuid, graph_id, name, fact, source_node_uuid, target_node_uuid, attributes, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    edge_uuid,
                    graph_id,
                    name,
                    fact,
                    source_uuid,
                    target_uuid,
                    json.dumps(attributes or {}),
                    _now(),
                ),
            )
        return edge_uuid

    def get_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM edges WHERE graph_id=?", (graph_id,)
            ).fetchall()
        node_map = {n["uuid"]: n["name"] for n in self.get_nodes(graph_id)}
        return [_edge_row(r, node_map) for r in rows]

    # ── Search ───────────────────────────────────────────────────────────────

    def search(self, graph_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Keyword relevance search over edge facts."""
        query_lower = query.lower()
        keywords = [w for w in query_lower.replace(",", " ").split() if len(w) > 1]
        all_edges = self.get_edges(graph_id)
        scored = []
        for edge in all_edges:
            combined = (edge.get("fact") or "") + " " + (edge.get("name") or "")
            s = _score(query_lower, keywords, combined)
            if s > 0:
                scored.append((s, edge))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    # ── Graph info ───────────────────────────────────────────────────────────

    def get_graph_info(self, graph_id: str) -> Dict[str, Any]:
        nodes = self.get_nodes(graph_id)
        edges = self.get_edges(graph_id)
        entity_types: set = set()
        for n in nodes:
            for label in n.get("labels", []):
                if label not in ("Entity", "Node"):
                    entity_types.add(label)
        return {
            "graph_id": graph_id,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "entity_types": sorted(entity_types),
        }

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """Full graph data dict — mirrors graph_builder.get_graph_data output."""
        nodes = self.get_nodes(graph_id)
        edges = self.get_edges(graph_id)
        entity_types: set = set()
        typed_node_count = 0
        for n in nodes:
            custom = [l for l in n.get("labels", []) if l not in ("Entity", "Node")]
            if custom:
                typed_node_count += 1
                entity_types.update(custom)
        return {
            "graph_id": graph_id,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "typed_node_count": typed_node_count,
            "entity_types": sorted(entity_types),
        }


# ── Singleton accessor ────────────────────────────────────────────────────────

_instance: Optional[LocalGraph] = None
_instance_lock = threading.Lock()


def get_local_graph() -> LocalGraph:
    """Return the process-wide LocalGraph singleton."""
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = LocalGraph()
    return _instance


# ── LLM Entity Extraction ─────────────────────────────────────────────────────

_EXTRACT_SYSTEM = (
    "You are an entity extractor. Extract entities and relationships from the text "
    "according to the given ontology. Return ONLY valid JSON with no markdown fences."
)

_EXTRACT_USER = """Entity types in ontology: {entity_types}
Relationship types: {edge_types}

Text to analyse:
---
{text}
---

Return JSON only:
{{
  "entities": [
    {{"name": "EntityName", "type": "EntityType", "summary": "one-sentence description", "attributes": {{}}}}
  ],
  "relationships": [
    {{"source": "SourceName", "type": "RelationType", "target": "TargetName", "fact": "Factual sentence."}}
  ]
}}

Rules:
- Only use entity types that appear in the ontology list.
- Return empty arrays if nothing matches.
- Deduplicate entities by name."""


def extract_entities_from_text(
    text: str,
    ontology: Dict[str, Any],
    llm,
) -> Dict[str, Any]:
    """LLM-based entity/relationship extraction from one text chunk."""
    entity_types = [e["name"] for e in ontology.get("entity_types", [])]
    edge_types = [e["name"] for e in ontology.get("edge_types", [])]

    if not entity_types:
        return {"entities": [], "relationships": []}

    prompt = _EXTRACT_USER.format(
        entity_types=", ".join(entity_types),
        edge_types=", ".join(edge_types) if edge_types else "none",
        text=text[:3000],
    )

    try:
        result = llm.chat_json(
            messages=[
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )
        return result or {"entities": [], "relationships": []}
    except Exception as e:
        logger.warning(f"Entity extraction failed: {e}")
        return {"entities": [], "relationships": []}


def ingest_text_to_graph(
    graph_id: str,
    text: str,
    ontology: Dict[str, Any],
    llm,
    local_graph: LocalGraph,
    progress_callback: Optional[Callable] = None,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    batch_size: int = 3,
) -> Dict[str, Any]:
    """
    Chunk text, extract entities + relationships via LLM, store in LocalGraph.
    Returns stats: {nodes_added, edges_added, chunks_processed}.
    """
    from .text_processor import TextProcessor

    chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
    total = len(chunks)
    nodes_added = 0
    edges_added = 0

    logger.info(f"Ingesting {total} chunks into graph {graph_id}")

    for i in range(0, total, batch_size):
        batch = chunks[i : i + batch_size]
        batch_text = "\n\n".join(batch)
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size

        if progress_callback:
            progress = (i + len(batch)) / total
            progress_callback(
                f"Extracting entities from batch {batch_num}/{total_batches}...",
                progress,
            )

        extracted = extract_entities_from_text(batch_text, ontology, llm)

        # Upsert entities
        name_to_uuid: Dict[str, str] = {}
        for ent in extracted.get("entities", []):
            name = (ent.get("name") or "").strip()
            etype = ent.get("type", "Entity")
            summary = ent.get("summary", "")
            attrs = ent.get("attributes") or {}
            if not name:
                continue
            labels = ["Entity"] if etype == "Entity" else ["Entity", etype]
            node_uuid = local_graph.upsert_node(graph_id, name, labels, summary, attrs)
            name_to_uuid[name] = node_uuid
            nodes_added += 1

        # Upsert relationships
        for rel in extracted.get("relationships", []):
            src = (rel.get("source") or "").strip()
            tgt = (rel.get("target") or "").strip()
            rtype = rel.get("type", "")
            fact = rel.get("fact", "")
            if not src or not tgt or not fact:
                continue
            if src not in name_to_uuid:
                name_to_uuid[src] = local_graph.upsert_node(graph_id, src, ["Entity"])
            if tgt not in name_to_uuid:
                name_to_uuid[tgt] = local_graph.upsert_node(graph_id, tgt, ["Entity"])
            local_graph.add_edge(
                graph_id=graph_id,
                source_uuid=name_to_uuid[src],
                target_uuid=name_to_uuid[tgt],
                name=rtype,
                fact=fact,
            )
            edges_added += 1

    if progress_callback:
        progress_callback(
            f"Ingestion complete: {nodes_added} entities, {edges_added} relationships",
            1.0,
        )

    logger.info(
        f"Graph {graph_id} ingested: {nodes_added} nodes, {edges_added} edges, {total} chunks"
    )
    return {"nodes_added": nodes_added, "edges_added": edges_added, "chunks_processed": total}
