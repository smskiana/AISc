"""应用层服务容器。"""
from dataclasses import dataclass
from typing import Any

from ..database.sqlite_client import SQLiteClient
from ..dialogue.prompt_builder import PromptBuilder
from ..memory.manager import MemoryManager
from ..memory.retrieval import RetrievalEngine
from ..memory.evolution import EvolutionEngine
from ..memory.player_events import PlayerEventMemoryWriter
from ..npc.state_manager import StateManager
from ..npc.behavior_engine import BehaviorEngine
from ..npc.npc_dialogue import NpcDialogueManager
from ..save.manager import SaveManager
from ..save.memory_checkpoint import MemoryCheckpointService


@dataclass
class AppServices:
    """运行时内聚后的后端服务集合。"""

    sqlite: SQLiteClient
    vector_store: Any
    state_mgr: StateManager
    prompt_builder: PromptBuilder
    mem_mgr: MemoryManager
    retrieval: RetrievalEngine
    evolution: EvolutionEngine
    save_mgr: SaveManager
    memory_checkpoints: MemoryCheckpointService
    behavior: BehaviorEngine
    npc_dialogue: NpcDialogueManager
    player_events: PlayerEventMemoryWriter
