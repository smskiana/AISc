"""协议公共层测试。"""
from __future__ import annotations

import unittest

from backend.src.protocol.codec import ProtocolCodec, ProtocolDecodeError
from backend.src.protocol.deduplication import RequestDeduplicator
from backend.src.protocol.session import ProtocolSession


class ProtocolCodecTests(unittest.TestCase):
    """验证 envelope 与旧消息兼容解析。"""

    def test_legacy_message_remains_supported(self) -> None:
        """旧扁平消息应原样进入业务层。"""
        decoded = ProtocolCodec.decode({"type": "PING"})
        self.assertFalse(decoded.is_envelope)
        self.assertEqual(decoded.message["type"], "PING")

    def test_envelope_payload_is_normalized(self) -> None:
        """envelope payload 应恢复为带 type 和 request_id 的业务消息。"""
        decoded = ProtocolCodec.decode({
            "protocol_version": 1,
            "type": "hello",
            "request_id": "req_1",
            "session_id": "",
            "sequence": 1,
            "payload": {"client_role": "unity_game"},
        })
        self.assertEqual(decoded.message["type"], "hello")
        self.assertEqual(decoded.message["request_id"], "req_1")

    def test_unsupported_version_is_rejected(self) -> None:
        """未知协议版本必须返回稳定错误码。"""
        with self.assertRaises(ProtocolDecodeError) as caught:
            ProtocolCodec.decode({"protocol_version": 99, "type": "hello", "payload": {}})
        self.assertEqual(caught.exception.error.code, "protocol_version_unsupported")


class ProtocolSessionTests(unittest.TestCase):
    """验证连接 sequence 与幂等缓存。"""

    def test_sequence_gap_is_rejected(self) -> None:
        """同一连接的首包必须从 sequence 1 开始。"""
        session = ProtocolSession()
        with self.assertRaises(ProtocolDecodeError) as caught:
            session.accept({
                "protocol_version": 1,
                "type": "hello",
                "request_id": "req_1",
                "session_id": "",
                "sequence": 2,
                "payload": {},
            })
        self.assertEqual(caught.exception.error.code, "sequence_gap")

    def test_deduplicator_returns_copy(self) -> None:
        """调用方修改结果时不得污染幂等缓存。"""
        cache = RequestDeduplicator(capacity=2)
        cache.remember("req_1", {"success": True})
        result = cache.get("req_1")
        result["success"] = False
        self.assertTrue(cache.get("req_1")["success"])


if __name__ == "__main__":
    unittest.main()
