"""协议 envelope 与旧扁平消息兼容编解码。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .errors import ProtocolError

PROTOCOL_VERSION = 1


class ProtocolDecodeError(ValueError):
    """表示输入消息不满足协议结构。"""

    def __init__(self, error: ProtocolError):
        """保存可直接编码回客户端的稳定错误。"""
        super().__init__(error.message)
        self.error = error


@dataclass(frozen=True)
class DecodedMessage:
    """保存规范化业务消息和 envelope 元数据。"""

    message: dict[str, Any]
    is_envelope: bool
    request_id: str = ""
    session_id: str = ""
    sequence: int = 0


class ProtocolCodec:
    """兼容解码旧扁平消息，并为新消息构造统一 envelope。"""

    @staticmethod
    def decode(data: dict[str, Any]) -> DecodedMessage:
        """把输入字典规范化为带顶层 type 的业务消息。"""
        if not isinstance(data, dict):
            raise ProtocolDecodeError(ProtocolError("invalid_payload", "协议消息必须是 JSON 对象"))

        if "protocol_version" not in data:
            if not str(data.get("type") or ""):
                raise ProtocolDecodeError(ProtocolError("missing_type", "旧协议消息缺少 type"))
            return DecodedMessage(message=dict(data), is_envelope=False)

        version = data.get("protocol_version")
        if version != PROTOCOL_VERSION:
            raise ProtocolDecodeError(ProtocolError(
                "protocol_version_unsupported",
                f"不支持协议版本: {version}",
                details={"supported_versions": [PROTOCOL_VERSION]},
            ))

        msg_type = str(data.get("type") or "")
        payload = data.get("payload", {})
        if not msg_type:
            raise ProtocolDecodeError(ProtocolError("missing_type", "协议 envelope 缺少 type"))
        if not isinstance(payload, dict):
            raise ProtocolDecodeError(ProtocolError("invalid_payload", "协议 payload 必须是 JSON 对象"))

        message = dict(payload)
        message["type"] = msg_type
        request_id = str(data.get("request_id") or "")
        if request_id and not message.get("request_id"):
            message["request_id"] = request_id
        return DecodedMessage(
            message=message,
            is_envelope=True,
            request_id=request_id,
            session_id=str(data.get("session_id") or ""),
            sequence=int(data.get("sequence") or 0),
        )

    @staticmethod
    def encode(
        msg_type: str,
        payload: dict[str, Any],
        request_id: str,
        session_id: str,
        sequence: int,
        error: ProtocolError | None = None,
        warnings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """构造版本化协议 envelope。"""
        return {
            "protocol_version": PROTOCOL_VERSION,
            "type": msg_type,
            "request_id": request_id,
            "session_id": session_id,
            "sequence": sequence,
            "sent_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "payload": payload,
            "error": error.to_dict() if error else None,
            "warnings": warnings or [],
        }
