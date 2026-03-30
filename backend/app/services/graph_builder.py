"""
Graph build service — local SQLite replacement for Zep Cloud.

Flow: text → text chunking → LLM entity extraction → LocalGraph storage
"""

import threading
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .local_graph import LocalGraph, get_local_graph, ingest_text_to_graph
from .text_processor import TextProcessor

logger = get_logger('mirofish.graph_builder')


@dataclass
class GraphInfo:
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class GraphBuilderService:
    """Builds a local knowledge graph from text + ontology."""

    def __init__(self, api_key: Optional[str] = None):
        self.local_graph: LocalGraph = get_local_graph()
        self.task_manager = TaskManager()
        self._llm: Optional[LLMClient] = None

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            cheap = LLMClient.from_cheap_config()
            self._llm = cheap if cheap else LLMClient()
        return self._llm

    # ── Public API ───────────────────────────────────────────────────────────

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3,
    ) -> str:
        """Kick off async graph build. Returns task_id."""
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            },
        )
        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size),
            daemon=True,
        )
        thread.start()
        return task_id

    def create_graph(self, name: str) -> str:
        """Create a named graph, return graph_id."""
        return self.local_graph.create_graph(name, "MiroFish Social Simulation Graph")

    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """Persist ontology to the graph store."""
        self.local_graph.set_ontology(graph_id, ontology)

    def delete_graph(self, graph_id: str):
        self.local_graph.delete_graph(graph_id)

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """Return full graph data dict (nodes + edges)."""
        return self.local_graph.get_graph_data(graph_id)

    # ── Worker ───────────────────────────────────────────────────────────────

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
    ):
        try:
            self.task_manager.update_task(
                task_id, status=TaskStatus.PROCESSING, progress=5, message="Building graph..."
            )

            # 1. Create graph
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id, progress=10, message=f"Graph created: {graph_id}"
            )

            # 2. Store ontology
            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(task_id, progress=15, message="Ontology stored")

            # 3. Ingest text (extraction + storage)
            def on_progress(msg: str, prog: float):
                self.task_manager.update_task(
                    task_id,
                    progress=15 + int(prog * 75),  # 15–90%
                    message=msg,
                )

            stats = ingest_text_to_graph(
                graph_id=graph_id,
                text=text,
                ontology=ontology,
                llm=self._get_llm(),
                local_graph=self.local_graph,
                progress_callback=on_progress,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                batch_size=batch_size,
            )

            # 4. Read final counts
            self.task_manager.update_task(task_id, progress=90, message="Finalising...")
            info = self._get_graph_info(graph_id)

            self.task_manager.complete_task(
                task_id,
                {
                    "graph_id": graph_id,
                    "graph_info": info.to_dict(),
                    "chunks_processed": stats["chunks_processed"],
                },
            )

        except Exception as e:
            import traceback
            self.task_manager.fail_task(task_id, f"{e}\n{traceback.format_exc()}")

    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        d = self.local_graph.get_graph_info(graph_id)
        return GraphInfo(
            graph_id=d["graph_id"],
            node_count=d["node_count"],
            edge_count=d["edge_count"],
            entity_types=d["entity_types"],
        )
