"""跨端协议 envelope、连接会话和幂等基础能力。"""

from .codec import ProtocolCodec, ProtocolDecodeError
from .deduplication import RequestDeduplicator
from .session import ProtocolSession

__all__ = ["ProtocolCodec", "ProtocolDecodeError", "ProtocolSession", "RequestDeduplicator"]
