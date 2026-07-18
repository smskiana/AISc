"""前后端协议执行闭环测试。"""
from __future__ import annotations

import unittest

from backend.src.application.dialogue_service import PlayerDialogueService
from backend.src.config import Config, _apply_yaml
from backend.src.dialogue.perception_context import PerceptionContextBuilder
from backend.src.dialogue.prompt_builder import _resolve_location_context
from backend.src.dialogue.llm_client import LLMClient
from backend.src.world.location_state import build_transit_location
from backend.src.world.proximity import are_nearby, is_same_zone


class FakeDatabase:
    """记录测试期间提交的 SQL。"""

    def __init__(self):
        self.executed: list[tuple[str, tuple]] = []
        self.rows: dict[str, dict] = {}

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.executed.append((sql, params))

    def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        return self.rows.get(str(params[0])) if params else None


class FakeClock:
    """提供对话服务构造所需的最小时间接口。"""


class FakeWebSocket:
    """收集服务发送的协议消息。"""

    def __init__(self):
        self.messages: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)


class TransitLocationTests(unittest.TestCase):
    """验证途中位置不参与任何地区关系。"""

    def test_transit_is_not_same_or_near_even_itself(self) -> None:
        """同一个 transit 标记也不能构成同区或邻近关系。"""
        transit = build_transit_location("sakura", "request_1")

        self.assertFalse(is_same_zone(transit, transit))
        self.assertFalse(are_nearby(transit, transit))
        self.assertFalse(is_same_zone(transit, "flower_shop.counter"))
        self.assertFalse(are_nearby(transit, "street.crossroad"))

    def test_prompt_renders_origin_and_target(self) -> None:
        """Prompt 位置应明确表达从起点到终点的途中。"""
        transit = build_transit_location("sakura", "request_1")
        location_id, text = _resolve_location_context({
            "current_location": transit,
            "movement_origin": "flower_shop.counter",
            "movement_target": "street.crossroad",
            "movement_status": "moving",
        }, "flower_shop.counter")

        self.assertEqual(location_id, transit)
        self.assertEqual(text, "从花店柜台到商店街路口的途中（移动中，不属于任何地区）")

    def test_transit_perception_excludes_regional_scene(self) -> None:
        """途中感知不得加载出发地或目标地的固定现场信息。"""
        builder = PerceptionContextBuilder("backend/config/npc_profiles")
        context = builder.build_player_dialogue(
            "sakura",
            "player",
            build_transit_location("sakura", "request_1"),
            "第1天 08:00",
        )

        self.assertIn("正在移动途中，不属于任何地区", context)
        self.assertIn("不要引用出发地或目标地", context)

class DialoguePrepareTests(unittest.IsolatedAsyncioTestCase):
    """验证对话准备阶段不直接建立正式会话。"""

    async def test_prepare_returns_correlated_message(self) -> None:
        """PREPARED 回包应复用请求 ID，并保持正式会话为空。"""
        service = PlayerDialogueService(None, FakeDatabase(), None)
        ws = FakeWebSocket()

        await service.prepare_dialogue(ws, {
            "type": "DIALOGUE_START",
            "request_id": "dialogue_1",
            "npc_id": "sakura",
            "player_location": "flower_shop.doorway",
            "game_time": {"day": 1, "hour": 8, "minute": 0, "weather": "sunny", "time_revision": 1},
        })

        self.assertEqual(ws.messages[0]["type"], "DIALOGUE_PREPARED")
        self.assertEqual(ws.messages[0]["request_id"], "dialogue_1")
        self.assertIn("dialogue_1", service._prepared_dialogues)
        self.assertEqual(service._active_dialogues, {})


class AsyncStreamTests(unittest.IsolatedAsyncioTestCase):
    """验证同步供应商流不会直接阻塞异步消费接口。"""

    async def test_async_stream_forwards_all_tokens(self) -> None:
        """线程桥接应保持 token 顺序并完整结束。"""
        client = LLMClient.__new__(LLMClient)
        client.chat_stream = lambda messages, **kwargs: iter(["你", "好"])
        tokens = []

        async for token in client.chat_stream_async([]):
            tokens.append(token)

        self.assertEqual(tokens, ["你", "好"])


class LlmThinkingModeTests(unittest.TestCase):
    """验证 LongCat 官方 thinking 请求参数集中配置且可以省略。"""

    def test_prepare_kwargs_adds_disabled_thinking_mode(self) -> None:
        """disabled 模式应按官方格式写入 extra_body。"""
        client = LLMClient.__new__(LLMClient)
        client.thinking_mode = "disabled"

        prepared = client._prepare_request_kwargs({"temperature": 0.7})

        self.assertEqual(prepared["temperature"], 0.7)
        self.assertEqual(prepared["extra_body"], {"thinking": {"type": "disabled"}})

    def test_prepare_kwargs_preserves_existing_extra_body(self) -> None:
        """注入 thinking 时不得覆盖调用方的其他供应商扩展字段。"""
        client = LLMClient.__new__(LLMClient)
        client.thinking_mode = "enabled"
        source = {"extra_body": {"custom": "value"}}

        prepared = client._prepare_request_kwargs(source)

        self.assertEqual(prepared["extra_body"]["custom"], "value")
        self.assertEqual(prepared["extra_body"]["thinking"], {"type": "enabled"})
        self.assertEqual(source, {"extra_body": {"custom": "value"}})

    def test_prepare_kwargs_skips_empty_mode(self) -> None:
        """空模式应使用供应商默认行为，不发送 thinking 字段。"""
        client = LLMClient.__new__(LLMClient)
        client.thinking_mode = ""
        source = {"temperature": 0.7}

        prepared = client._prepare_request_kwargs(source)

        self.assertEqual(prepared, source)
        self.assertIsNot(prepared, source)

    def test_yaml_can_switch_or_omit_thinking_mode(self) -> None:
        """YAML 配置应能切换思考模式，并保留空值省略语义。"""
        config = Config()

        _apply_yaml(config, {"llm": {"thinking_mode": "disabled"}})
        self.assertEqual(config.llm_thinking_mode, "disabled")

        _apply_yaml(config, {"llm": {"thinking_mode": ""}})
        self.assertEqual(config.llm_thinking_mode, "")


if __name__ == "__main__":
    unittest.main()
