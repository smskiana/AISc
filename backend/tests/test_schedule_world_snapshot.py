"""日程物理快照的拒绝与 owner 投影测试。"""
import unittest
from backend.src.npc.schedule_world_snapshot import ScheduleWorldSnapshot, ScheduleWorldSnapshotStore

class ScheduleWorldSnapshotTests(unittest.TestCase):
    def test_unknown_and_revision_rejection(self):
        """非法枚举降为 unknown，倒退版本不得覆盖。"""
        store = ScheduleWorldSnapshotStore()
        first = ScheduleWorldSnapshot.from_dict({"snapshot_id":"a","time_revision":2,"world_revision":3,"locations":[{"location_id":"shop","open_state":"bad"}],"npcs":[{"npc_id":"sakura","location_id":"shop"}]})
        store.put(first)
        self.assertEqual("unknown", first.locations["shop"]["open_state"])
        self.assertEqual("a", store.require("a",2,3).physical_state_for("sakura")["snapshot_id"])
        with self.assertRaisesRegex(ValueError, "stale"):
            store.put(ScheduleWorldSnapshot.from_dict({"snapshot_id":"b","time_revision":1,"world_revision":3}))
