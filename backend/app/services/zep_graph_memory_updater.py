"""
Graph memory updater — stores simulation agent activity to local SQLite.
Replaces Zep episode ingestion with direct edge writes.
Public API (AgentActivity, ZepGraphMemoryUpdater, ZepGraphMemoryManager) unchanged.
"""

import threading
from dataclasses import dataclass
from datetime import datetime
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from .local_graph import LocalGraph, get_local_graph

logger = get_logger('mirofish.zep_graph_memory_updater')


@dataclass
class AgentActivity:
    """Agent activity record."""
    platform: str
    agent_id: int
    agent_name: str
    action_type: str
    action_args: Dict[str, Any]
    round_num: int
    timestamp: str

    def to_episode_text(self) -> str:
        describe = {
            "CREATE_POST": self._describe_create_post,
            "LIKE_POST": self._describe_like_post,
            "DISLIKE_POST": self._describe_dislike_post,
            "REPOST": self._describe_repost,
            "QUOTE_POST": self._describe_quote_post,
            "FOLLOW": self._describe_follow,
            "CREATE_COMMENT": self._describe_create_comment,
            "LIKE_COMMENT": self._describe_like_comment,
            "DISLIKE_COMMENT": self._describe_dislike_comment,
            "SEARCH_POSTS": self._describe_search,
            "SEARCH_USER": self._describe_search_user,
            "MUTE": self._describe_mute,
        }
        fn = describe.get(self.action_type, self._describe_generic)
        return f"{self.agent_name}: {fn()}"

    def _describe_create_post(self) -> str:
        c = self.action_args.get("content", "")
        return f"posted: '{c}'" if c else "created a post"

    def _describe_like_post(self) -> str:
        c = self.action_args.get("post_content", "")
        a = self.action_args.get("post_author_name", "")
        return f"liked {a}'s post: '{c}'" if c and a else f"liked a post"

    def _describe_dislike_post(self) -> str:
        c = self.action_args.get("post_content", "")
        a = self.action_args.get("post_author_name", "")
        return f"disliked {a}'s post: '{c}'" if c and a else "disliked a post"

    def _describe_repost(self) -> str:
        c = self.action_args.get("original_content", "")
        a = self.action_args.get("original_author_name", "")
        return f"reposted {a}'s post: '{c}'" if c and a else "reposted a post"

    def _describe_quote_post(self) -> str:
        c = self.action_args.get("original_content", "")
        a = self.action_args.get("original_author_name", "")
        q = self.action_args.get("quote_content") or self.action_args.get("content", "")
        base = f"quoted {a}'s post '{c}'" if c and a else "quoted a post"
        return f"{base}, commenting: '{q}'" if q else base

    def _describe_follow(self) -> str:
        t = self.action_args.get("target_user_name", "")
        return f"followed '{t}'" if t else "followed a user"

    def _describe_create_comment(self) -> str:
        c = self.action_args.get("content", "")
        p = self.action_args.get("post_content", "")
        a = self.action_args.get("post_author_name", "")
        if c and p and a:
            return f"commented on {a}'s post '{p}': '{c}'"
        return f"commented: '{c}'" if c else "commented"

    def _describe_like_comment(self) -> str:
        c = self.action_args.get("comment_content", "")
        a = self.action_args.get("comment_author_name", "")
        return f"liked {a}'s comment: '{c}'" if c and a else "liked a comment"

    def _describe_dislike_comment(self) -> str:
        c = self.action_args.get("comment_content", "")
        a = self.action_args.get("comment_author_name", "")
        return f"disliked {a}'s comment: '{c}'" if c and a else "disliked a comment"

    def _describe_search(self) -> str:
        q = self.action_args.get("query") or self.action_args.get("keyword", "")
        return f"searched for '{q}'" if q else "searched"

    def _describe_search_user(self) -> str:
        q = self.action_args.get("query") or self.action_args.get("username", "")
        return f"searched for user '{q}'" if q else "searched for a user"

    def _describe_mute(self) -> str:
        t = self.action_args.get("target_user_name", "")
        return f"muted '{t}'" if t else "muted a user"

    def _describe_generic(self) -> str:
        return f"performed {self.action_type}"


class ZepGraphMemoryUpdater:
    """
    Accumulates agent activities and writes them as edges to the local graph.
    Replaces Zep Cloud episode ingestion.
    """

    BATCH_SIZE = 5
    PLATFORM_DISPLAY_NAMES = {"twitter": "World 1", "reddit": "World 2"}

    def __init__(self, graph_id: str):
        self.graph_id = graph_id
        self.local_graph: LocalGraph = get_local_graph()

        self._activity_queue: Queue = Queue()
        self._platform_buffers: Dict[str, List[AgentActivity]] = {
            "twitter": [],
            "reddit": [],
        }
        self._buffer_lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        # Stats
        self._total_activities = 0
        self._total_sent = 0
        self._total_items_sent = 0
        self._failed_count = 0
        self._skipped_count = 0

        logger.info(f"ZepGraphMemoryUpdater (local) init: graph_id={graph_id}")

    def start(self):
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name=f"MemoryUpdater-{self.graph_id[:8]}",
        )
        self._worker_thread.start()

    def stop(self):
        self._running = False
        self._flush_remaining()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
        logger.info(
            f"ZepGraphMemoryUpdater stopped: graph={self.graph_id}, "
            f"items_sent={self._total_items_sent}, failed={self._failed_count}"
        )

    def add_activity(self, activity: AgentActivity):
        if activity.action_type == "DO_NOTHING":
            self._skipped_count += 1
            return
        self._activity_queue.put(activity)
        self._total_activities += 1

    def add_activity_from_dict(self, data: Dict[str, Any], platform: str):
        if "event_type" in data:
            return
        self.add_activity(AgentActivity(
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=data.get("action_args", {}),
            round_num=data.get("round", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        ))

    def _worker_loop(self):
        while self._running or not self._activity_queue.empty():
            try:
                try:
                    activity = self._activity_queue.get(timeout=1)
                    platform = activity.platform.lower()
                    with self._buffer_lock:
                        if platform not in self._platform_buffers:
                            self._platform_buffers[platform] = []
                        self._platform_buffers[platform].append(activity)
                        if len(self._platform_buffers[platform]) >= self.BATCH_SIZE:
                            batch = self._platform_buffers[platform][: self.BATCH_SIZE]
                            self._platform_buffers[platform] = self._platform_buffers[platform][self.BATCH_SIZE :]
                            self._flush_batch(batch, platform)
                except Empty:
                    pass
            except Exception as e:
                logger.error(f"Worker loop error: {e}")

    def _flush_batch(self, activities: List[AgentActivity], platform: str):
        """Write activity batch as an edge fact in the local graph."""
        if not activities:
            return
        try:
            # Ensure a platform node exists
            platform_node_uuid = self.local_graph.upsert_node(
                graph_id=self.graph_id,
                name=f"Platform:{platform}",
                labels=["Entity", "Platform"],
                summary=f"Social media platform: {platform}",
            )

            for activity in activities:
                # Ensure agent node exists
                agent_node_uuid = self.local_graph.upsert_node(
                    graph_id=self.graph_id,
                    name=activity.agent_name,
                    labels=["Entity", "Agent"],
                    summary=f"Simulation agent on {platform}",
                )
                fact = activity.to_episode_text()
                self.local_graph.add_edge(
                    graph_id=self.graph_id,
                    source_uuid=agent_node_uuid,
                    target_uuid=platform_node_uuid,
                    name=activity.action_type,
                    fact=fact,
                    attributes={"round": activity.round_num, "platform": platform},
                )

            self._total_sent += 1
            self._total_items_sent += len(activities)
            display = self.PLATFORM_DISPLAY_NAMES.get(platform, platform)
            logger.info(f"Stored {len(activities)} {display} activities to local graph")

        except Exception as e:
            logger.error(f"Failed to store batch to local graph: {e}")
            self._failed_count += 1

    def _flush_remaining(self):
        while not self._activity_queue.empty():
            try:
                activity = self._activity_queue.get_nowait()
                platform = activity.platform.lower()
                with self._buffer_lock:
                    if platform not in self._platform_buffers:
                        self._platform_buffers[platform] = []
                    self._platform_buffers[platform].append(activity)
            except Empty:
                break
        with self._buffer_lock:
            for platform, buffer in self._platform_buffers.items():
                if buffer:
                    self._flush_batch(buffer, platform)
            for p in self._platform_buffers:
                self._platform_buffers[p] = []

    def get_stats(self) -> Dict[str, Any]:
        with self._buffer_lock:
            buffer_sizes = {p: len(b) for p, b in self._platform_buffers.items()}
        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_activities": self._total_activities,
            "batches_sent": self._total_sent,
            "items_sent": self._total_items_sent,
            "failed_count": self._failed_count,
            "skipped_count": self._skipped_count,
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes,
            "running": self._running,
        }


class ZepGraphMemoryManager:
    """Manages per-simulation memory updaters."""

    _updaters: Dict[str, ZepGraphMemoryUpdater] = {}
    _lock = threading.Lock()
    _stop_all_done = False

    @classmethod
    def create_updater(cls, simulation_id: str, graph_id: str) -> ZepGraphMemoryUpdater:
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
            updater = ZepGraphMemoryUpdater(graph_id)
            updater.start()
            cls._updaters[simulation_id] = updater
            logger.info(f"Created memory updater: sim={simulation_id}, graph={graph_id}")
            return updater

    @classmethod
    def get_updater(cls, simulation_id: str) -> Optional[ZepGraphMemoryUpdater]:
        return cls._updaters.get(simulation_id)

    @classmethod
    def stop_updater(cls, simulation_id: str):
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
                del cls._updaters[simulation_id]

    @classmethod
    def stop_all(cls):
        if cls._stop_all_done:
            return
        cls._stop_all_done = True
        with cls._lock:
            for sim_id, updater in list(cls._updaters.items()):
                try:
                    updater.stop()
                except Exception as e:
                    logger.error(f"Failed to stop updater {sim_id}: {e}")
            cls._updaters.clear()

    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        return {sid: u.get_stats() for sid, u in cls._updaters.items()}
