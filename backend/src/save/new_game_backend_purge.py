"""新游戏后端可重建运行数据的统一清理边界。"""
from __future__ import annotations


class NewGameBackendPurgeError(RuntimeError):
    """携带不会泄漏内部异常类型的稳定清理失败码。"""


class NewGameBackendPurgeService:
    """串行清理日程快照、记忆检查点和日程内存幂等状态。"""

    def __init__(self, sqlite, memory_checkpoints, behavior):
        self._sqlite = sqlite
        self._memory_checkpoints = memory_checkpoints
        self._behavior = behavior

    def purge(self) -> None:
        """执行复合清理；检查点失败时恢复已删除的 SQLite 日程快照。"""
        try:
            removed = self._sqlite.purge_daily_schedule_snapshots()
        except Exception as error:
            raise NewGameBackendPurgeError("schedule_snapshot_purge_failed") from error
        try:
            self._memory_checkpoints.purge_all()
        except Exception as error:
            try:
                self._sqlite.restore_daily_schedule_snapshots(removed)
            except Exception as restore_error:
                raise NewGameBackendPurgeError("new_game_backend_purge_failed") from restore_error
            raise NewGameBackendPurgeError("memory_checkpoint_purge_failed") from error
        self._behavior.reset_prepared_days()
