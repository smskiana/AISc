"""冷启动初始事实的配置校验、可见性判断与观察者视角投影。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import json
import re
from string import Formatter
from typing import Iterable, Mapping, Sequence


class KnowledgeScope(str, Enum):
    """初始事实的知识权限范围。"""

    PUBLIC = "public"
    COMMUNITY = "community"
    PARTICIPANTS = "participants"
    EXPLICIT_KNOWERS = "explicit_knowers"
    PRIVATE = "private"


class FactType(str, Enum):
    """第一版允许进入初始知识配置的事实类型。"""

    IDENTITY = "identity"
    EVENT = "event"
    RELATIONSHIP = "relationship"
    BACKGROUND = "background"
    RUMOR = "rumor"
    SECRET = "secret"


class SourceType(str, Enum):
    """投影事实的稳定来源类型。"""

    PUBLIC_RECORD = "public_record"
    COMMUNITY_GOSSIP = "community_gossip"
    PARTICIPANT_MEMORY = "participant_memory"
    EXPLICIT_STATEMENT = "explicit_statement"
    PRIVATE_MEMORY = "private_memory"


_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_ALLOWED_PROJECTION_KEYS = {"default", "subject", "participant", "explicit_knower", "rumor"}
_ALLOWED_TEMPLATE_FIELDS = {
    "canonical_summary",
    "fact_id",
    "observer_id",
    "subject_ids",
    "location_ids",
    "participant_ids",
    "knower_ids",
    "created_day",
    "player_nickname",
    "player_name",
}
_RUNTIME_PLAYER_TOKENS = {
    "player_nickname": "{player_nickname}",
    "player_name": "{player_name}",
}


@dataclass(frozen=True)
class InitialKnowledgeFact:
    """经过配置校验的稳定初始事实。"""

    fact_id: str
    fact_type: FactType
    subject_ids: tuple[str, ...]
    location_ids: tuple[str, ...]
    canonical_summary: str
    knowledge_scope: KnowledgeScope
    knower_ids: tuple[str, ...]
    participant_ids: tuple[str, ...]
    excluded_observer_ids: tuple[str, ...]
    source_type: SourceType
    confidence: float
    importance: float
    created_day: int
    projections: Mapping[str, str]


@dataclass(frozen=True)
class KnowledgeRelationshipContext:
    """为 community scope 提供统一的观察者关系上下文。"""

    community_observer_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class KnowledgeVisibilityDecision:
    """记录单个观察者对事实的纳入或排除决定。"""

    fact_id: str
    observer_id: str
    included: bool
    rule: str
    reason: str


@dataclass(frozen=True)
class ProjectedMemory:
    """表示一个可写入观察者独立图的确定性记忆投影。"""

    projection_id: str
    observer_id: str
    source_fact_id: str
    fact_type: str
    knowledge_scope: str
    value: str
    node_type: str
    subject_ids: tuple[str, ...]
    location_ids: tuple[str, ...]
    source_type: str
    confidence: float
    importance: float
    created_day: int
    visibility_rule: str
    visibility_reason: str


@dataclass(frozen=True)
class KnowledgeProjectionResult:
    """同时承载已纳入投影和被排除事实，供写入与诊断共用。"""

    observer_id: str
    projections: tuple[ProjectedMemory, ...]
    excluded: tuple[KnowledgeVisibilityDecision, ...]


def load_initial_knowledge(
    path: Path,
    known_ids: Iterable[str] | None = None,
) -> tuple[InitialKnowledgeFact, ...]:
    """读取并严格校验初始事实配置，失败时阻止冷启动继续。"""
    known = frozenset(known_ids or {
        "player", "sakura", "chihaya", "kazuha", "tatsunosuke", "kujo",
    })
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"initial_knowledge_config_error:{error}") from error

    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("invalid_schema_version")
    raw_facts = payload.get("facts")
    if not isinstance(raw_facts, list):
        raise ValueError("facts_must_be_array")

    facts: list[InitialKnowledgeFact] = []
    seen_ids: set[str] = set()
    for raw_fact in raw_facts:
        fact = _parse_fact(raw_fact, known)
        if fact.fact_id in seen_ids:
            raise ValueError(f"duplicate_fact_id:{fact.fact_id}")
        seen_ids.add(fact.fact_id)
        facts.append(fact)
    return tuple(facts)


def project_initial_knowledge(
    facts: Sequence[InitialKnowledgeFact],
    observer_id: str,
    relationship_context: KnowledgeRelationshipContext,
) -> KnowledgeProjectionResult:
    """按最强匹配权限生成确定性的观察者视角记忆投影。"""
    _validate_id(observer_id, "observer_id")
    projections: list[ProjectedMemory] = []
    excluded: list[KnowledgeVisibilityDecision] = []
    for fact in facts:
        decision = _decide_visibility(fact, observer_id, relationship_context)
        if not decision.included:
            excluded.append(decision)
            continue
        value = _render_projection(fact, observer_id, decision.rule)
        projections.append(
            ProjectedMemory(
                projection_id=f"initial_knowledge__{observer_id}__{fact.fact_id}",
                observer_id=observer_id,
                source_fact_id=fact.fact_id,
                fact_type=fact.fact_type.value,
                knowledge_scope=fact.knowledge_scope.value,
                value=value,
                node_type="event" if fact.fact_type == FactType.RUMOR else fact.fact_type.value,
                subject_ids=fact.subject_ids,
                location_ids=fact.location_ids,
                source_type=fact.source_type.value,
                confidence=fact.confidence,
                importance=fact.importance,
                created_day=fact.created_day,
                visibility_rule=decision.rule,
                visibility_reason=decision.reason,
            )
        )
    return KnowledgeProjectionResult(observer_id, tuple(projections), tuple(excluded))


def _parse_fact(raw_fact: object, known_ids: frozenset[str]) -> InitialKnowledgeFact:
    """将一个 JSON 对象转换为已校验事实 DTO。"""
    if not isinstance(raw_fact, dict):
        raise ValueError("fact_must_be_object")
    fact_id = _required_id(raw_fact, "fact_id")
    fact_type = _parse_enum(raw_fact, "fact_type", FactType)
    scope = _parse_enum(raw_fact, "knowledge_scope", KnowledgeScope)
    source_type = _parse_enum(raw_fact, "source_type", SourceType)
    subject_ids = _id_list(raw_fact, "subject_ids", known_ids)
    location_ids = _id_list(raw_fact, "location_ids", None)
    knower_ids = _id_list(raw_fact, "knower_ids", known_ids)
    participant_ids = _id_list(raw_fact, "participant_ids", known_ids)
    excluded_ids = _id_list(raw_fact, "excluded_observer_ids", known_ids)
    summary = raw_fact.get("canonical_summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(f"missing_canonical_summary:{fact_id}")
    confidence = _probability(raw_fact.get("confidence"), "confidence", fact_id)
    importance = _probability(raw_fact.get("importance"), "importance", fact_id)
    created_day = raw_fact.get("created_day")
    if isinstance(created_day, bool) or not isinstance(created_day, int) or created_day < 0:
        raise ValueError(f"invalid_created_day:{fact_id}")
    projections = _projections(raw_fact.get("projections"), fact_id)
    _validate_applicable_templates(fact_id, fact_type, scope, source_type, projections)
    return InitialKnowledgeFact(
        fact_id=fact_id,
        fact_type=fact_type,
        subject_ids=subject_ids,
        location_ids=location_ids,
        canonical_summary=summary.strip(),
        knowledge_scope=scope,
        knower_ids=knower_ids,
        participant_ids=participant_ids,
        excluded_observer_ids=excluded_ids,
        source_type=source_type,
        confidence=confidence,
        importance=importance,
        created_day=created_day,
        projections=projections,
    )


def _decide_visibility(
    fact: InitialKnowledgeFact,
    observer_id: str,
    context: KnowledgeRelationshipContext,
) -> KnowledgeVisibilityDecision:
    """应用排除优先和固定强度顺序，得到唯一权限依据。"""
    if observer_id in fact.excluded_observer_ids:
        return KnowledgeVisibilityDecision(
            fact.fact_id, observer_id, False, "excluded_observer", "excluded_by_fact_configuration",
        )

    candidates: list[tuple[int, str, str]] = []
    if fact.knowledge_scope == KnowledgeScope.PRIVATE:
        if observer_id in fact.subject_ids:
            candidates.append((50, "subject", "observer_is_subject"))
        if observer_id in fact.knower_ids:
            candidates.append((40, "explicit_knower", "observer_is_explicit_knower"))
    elif fact.knowledge_scope == KnowledgeScope.EXPLICIT_KNOWERS:
        if observer_id in fact.knower_ids:
            candidates.append((40, "explicit_knower", "observer_is_explicit_knower"))
    elif fact.knowledge_scope == KnowledgeScope.PARTICIPANTS:
        if observer_id in fact.participant_ids:
            candidates.append((30, "participant", "observer_is_participant"))
    elif fact.knowledge_scope == KnowledgeScope.COMMUNITY:
        if observer_id in context.community_observer_ids:
            candidates.append((20, "community", "observer_is_community_member"))
    elif fact.knowledge_scope == KnowledgeScope.PUBLIC:
        candidates.append((10, "public", "fact_is_public"))

    if not candidates:
        return KnowledgeVisibilityDecision(
            fact.fact_id, observer_id, False, "scope_denied", "observer_does_not_match_knowledge_scope",
        )
    _, rule, reason = max(candidates, key=lambda item: item[0])
    return KnowledgeVisibilityDecision(fact.fact_id, observer_id, True, rule, reason)


def _render_projection(fact: InitialKnowledgeFact, observer_id: str, rule: str) -> str:
    """只用事实字段和受控玩家 token 渲染确定性文本。"""
    key = _projection_key(fact, rule)
    template = fact.projections[key]
    values = {
        "canonical_summary": fact.canonical_summary,
        "fact_id": fact.fact_id,
        "observer_id": observer_id,
        "subject_ids": ", ".join(fact.subject_ids),
        "location_ids": ", ".join(fact.location_ids),
        "participant_ids": ", ".join(fact.participant_ids),
        "knower_ids": ", ".join(fact.knower_ids),
        "created_day": fact.created_day,
        **_RUNTIME_PLAYER_TOKENS,
    }
    try:
        return template.format_map(values)
    except (KeyError, ValueError) as error:
        raise ValueError(f"invalid_projection_template:{fact.fact_id}") from error


def _projection_key(fact: InitialKnowledgeFact, rule: str) -> str:
    """将可见性规则映射到配置中的确定性模板键。"""
    if fact.fact_type == FactType.RUMOR or fact.source_type == SourceType.COMMUNITY_GOSSIP:
        return "rumor"
    if rule in {"subject", "participant", "explicit_knower"} and rule in fact.projections:
        return rule
    return "default"


def _validate_applicable_templates(
    fact_id: str,
    fact_type: FactType,
    scope: KnowledgeScope,
    source_type: SourceType,
    projections: Mapping[str, str],
) -> None:
    """校验每种可能的观察者角色都有显式模板可用。"""
    required = {"default"}
    if scope == KnowledgeScope.PARTICIPANTS:
        required = {"participant"}
    elif scope == KnowledgeScope.EXPLICIT_KNOWERS:
        required = {"explicit_knower"}
    elif scope == KnowledgeScope.PRIVATE:
        required = {"subject", "explicit_knower"}
    if fact_type == FactType.RUMOR or source_type == SourceType.COMMUNITY_GOSSIP:
        required = {"rumor"}
    missing = sorted(required - projections.keys())
    if missing:
        raise ValueError(f"missing_projection_template:{fact_id}:{','.join(missing)}")


def _projections(raw: object, fact_id: str) -> Mapping[str, str]:
    """校验模板键和占位符白名单，保留配置文本原样。"""
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"missing_projections:{fact_id}")
    parsed: dict[str, str] = {}
    for key, value in raw.items():
        if key not in _ALLOWED_PROJECTION_KEYS:
            raise ValueError(f"invalid_projection_key:{fact_id}:{key}")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"invalid_projection_template:{fact_id}:{key}")
        for _, field_name, _, _ in Formatter().parse(value):
            if field_name and field_name not in _ALLOWED_TEMPLATE_FIELDS:
                raise ValueError(f"invalid_projection_placeholder:{fact_id}:{field_name}")
        parsed[key] = value
    return parsed


def _id_list(raw: Mapping[str, object], field_name: str, known_ids: frozenset[str] | None) -> tuple[str, ...]:
    """解析稳定 ID 数组并拒绝重复、非法或未知人物 ID。"""
    values = raw.get(field_name, [])
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"invalid_{field_name}")
    result = tuple(values)
    if len(result) != len(set(result)):
        raise ValueError(f"duplicate_{field_name}")
    for value in result:
        _validate_id(value, field_name)
        if known_ids is not None and value not in known_ids:
            raise ValueError(f"unknown_id:{field_name}:{value}")
    return result


def _required_id(raw: Mapping[str, object], field_name: str) -> str:
    """解析必填单个稳定 ID。"""
    value = raw.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"missing_{field_name}")
    _validate_id(value, field_name)
    return value


def _validate_id(value: str, field_name: str) -> None:
    """统一校验小写 snake_case 稳定标识。"""
    if not _ID_PATTERN.fullmatch(value):
        raise ValueError(f"invalid_{field_name}:{value}")


def _parse_enum(raw: Mapping[str, object], field_name: str, enum_type: type[Enum]) -> Enum:
    """将配置字符串解析为受控枚举值。"""
    value = raw.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"missing_{field_name}")
    try:
        return enum_type(value)
    except ValueError as error:
        raise ValueError(f"invalid_{field_name}:{value}") from error


def _probability(value: object, field_name: str, fact_id: str) -> float:
    """校验 confidence 和 importance 的闭区间数值。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"invalid_{field_name}:{fact_id}")
    return float(value)
