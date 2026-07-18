"""单个 WebSocket 连接的协议会话。"""
from __future__ import annotations

import uuid

from .codec import DecodedMessage, ProtocolCodec, ProtocolDecodeError
from .errors import ProtocolError


class ProtocolSession:
    """管理连接 session、收发 sequence 和版本握手。"""

    def __init__(self):
        """为新连接生成独立 session 并初始化双向序号。"""
        self.session_id = f"session_{uuid.uuid4().hex}"
        self._last_received_sequence = 0
        self._next_send_sequence = 1
        self.is_negotiated = False

    def accept(self, data: dict) -> DecodedMessage:
        """解码消息并校验 envelope 的 session 与单调 sequence。"""
        decoded = ProtocolCodec.decode(data)
        if not decoded.is_envelope:
            return decoded
        if decoded.session_id and decoded.session_id != self.session_id:
            raise ProtocolDecodeError(ProtocolError("session_mismatch", "消息 session 与当前连接不一致"))
        if decoded.sequence <= self._last_received_sequence:
            raise ProtocolDecodeError(ProtocolError("sequence_replayed", "消息 sequence 已处理"))
        if decoded.sequence != self._last_received_sequence + 1:
            raise ProtocolDecodeError(ProtocolError(
                "sequence_gap",
                "消息 sequence 不连续",
                retryable=True,
                details={"expected": self._last_received_sequence + 1, "actual": decoded.sequence},
            ))
        self._last_received_sequence = decoded.sequence
        return decoded

    def response(self, msg_type: str, payload: dict, request_id: str = "", error: ProtocolError | None = None) -> dict:
        """构造当前 session 的下一个有序响应。"""
        result = ProtocolCodec.encode(
            msg_type,
            payload,
            request_id,
            self.session_id,
            self._next_send_sequence,
            error=error,
        )
        self._next_send_sequence += 1
        return result
