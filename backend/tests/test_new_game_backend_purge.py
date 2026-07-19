"""新游戏后端复合清理 service 测试。"""
import unittest

from backend.src.save.new_game_backend_purge import NewGameBackendPurgeError, NewGameBackendPurgeService


class _SQLite:
    def __init__(self):
        self.restored = None

    def purge_daily_schedule_snapshots(self):
        return [{"game_day": 1}]

    def restore_daily_schedule_snapshots(self, rows):
        self.restored = rows


class _Checkpoints:
    def __init__(self, fail=False):
        self.fail = fail

    def purge_all(self):
        if self.fail:
            raise OSError("hidden")


class _Behavior:
    def __init__(self):
        self.reset = False

    def reset_prepared_days(self):
        self.reset = True


class NewGameBackendPurgeTests(unittest.TestCase):
    """验证复合清理成功与补偿后的稳定失败码。"""

    def test_success_resets_memory_cache(self):
        behavior = _Behavior()
        NewGameBackendPurgeService(_SQLite(), _Checkpoints(), behavior).purge()
        self.assertTrue(behavior.reset)

    def test_checkpoint_failure_restores_schedule_rows(self):
        sqlite = _SQLite()
        with self.assertRaisesRegex(NewGameBackendPurgeError, "memory_checkpoint_purge_failed"):
            NewGameBackendPurgeService(sqlite, _Checkpoints(True), _Behavior()).purge()
        self.assertEqual([{"game_day": 1}], sqlite.restored)


if __name__ == "__main__":
    unittest.main()
