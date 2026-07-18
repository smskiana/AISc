"""Prompt 组装输出纪律测试。"""

from backend.src.prompting import PromptAssembler


def test_structured_contract_is_short_and_not_json_example() -> None:
    """结构化任务只声明字段，不塞冗长 JSON 样例。"""
    message = PromptAssembler().build("memory_route", {"max_select": 2})[0]["content"]
    assert "selected" in message
    assert "```" not in message
    assert '"nodes":[{' not in message


def test_dialogue_is_not_json_wrapped() -> None:
    """对白任务保持自然文本输出。"""
    message = PromptAssembler().build("player_dialogue", {})[0]["content"]
    assert "JSON" not in message
    assert "自然口语" in message
