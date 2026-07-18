"""
记忆图边语义规则。
集中维护各类边在双向上的初始 clarity，避免不同入口各写各的。
"""


def _clamp_clarity(value: float, low: float = 0.05, high: float = 1.0) -> float:
    return round(max(low, min(high, value)), 4)


def initial_relationship_clarity(recognition_importance: float = 0.9, bond: float = 0.0,
                                 is_core_person: bool = True) -> tuple[float, float]:
    """返回冷启动核心人物关系的基础认知 clarity，bond 只做小幅修正。"""
    imp = max(0.1, min(1.0, float(recognition_importance or 0.9)))
    bond_value = max(-1.0, min(1.0, float(bond or 0.0)))
    bond_adjust = max(-0.08, min(0.08, (bond_value - 0.2) * 0.08))

    if is_core_person:
        base_ab = max(0.74, 0.74 + (imp - 0.9) * 0.08)
        base_ba = max(0.62, 0.62 + (imp - 0.9) * 0.06)
        return (
            _clamp_clarity(base_ab + bond_adjust, low=0.72, high=1.0),
            _clamp_clarity(base_ba + bond_adjust * 0.75, low=0.60, high=1.0),
        )

    base_ab = max(0.48, imp * 0.72)
    base_ba = max(0.42, imp * 0.62)
    return (
        _clamp_clarity(base_ab + bond_adjust),
        _clamp_clarity(base_ba + bond_adjust * 0.75),
    )


def resolve_edge_clarity(edge_type: str, target_importance: float,
                         node_a_type: str = "", node_b_type: str = "") -> tuple[float, float]:
    """按边类型和节点类型返回 (clarity_ab, clarity_ba)。"""
    imp = max(0.1, min(1.0, float(target_importance or 0.5)))
    etype = (edge_type or "associated_with").strip()
    a_type = (node_a_type or "").strip()
    b_type = (node_b_type or "").strip()

    if etype == "relationship":
        return (
            _clamp_clarity(max(0.18, imp)),
            _clamp_clarity(max(0.15, imp * 0.88)),
        )

    if etype == "involved":
        if a_type == "event" and b_type in {"person", "self"}:
            return (
                _clamp_clarity(max(0.82, imp)),
                _clamp_clarity(max(0.62, imp * 0.84)),
            )
        if b_type == "event" and a_type in {"person", "self"}:
            return (
                _clamp_clarity(max(0.62, imp * 0.84)),
                _clamp_clarity(max(0.82, imp)),
            )
        return (
            _clamp_clarity(max(0.72, imp * 0.96)),
            _clamp_clarity(max(0.55, imp * 0.78)),
        )

    if etype == "located_at":
        if a_type == "event":
            return (
                _clamp_clarity(max(0.74, imp * 0.98)),
                _clamp_clarity(max(0.44, imp * 0.62)),
            )
        if b_type == "event":
            return (
                _clamp_clarity(max(0.44, imp * 0.62)),
                _clamp_clarity(max(0.74, imp * 0.98)),
            )
        return (
            _clamp_clarity(max(0.6, imp * 0.86)),
            _clamp_clarity(max(0.4, imp * 0.58)),
        )

    if etype == "happened_at":
        if a_type == "event":
            return (
                _clamp_clarity(max(0.7, imp * 0.95)),
                _clamp_clarity(max(0.38, imp * 0.52)),
            )
        if b_type == "event":
            return (
                _clamp_clarity(max(0.38, imp * 0.52)),
                _clamp_clarity(max(0.7, imp * 0.95)),
            )
        return (
            _clamp_clarity(max(0.56, imp * 0.8)),
            _clamp_clarity(max(0.34, imp * 0.5)),
        )

    if etype == "felt":
        return (
            _clamp_clarity(max(0.7, imp * 0.92)),
            _clamp_clarity(max(0.62, imp * 0.84)),
        )

    if etype == "mentioned":
        return (
            _clamp_clarity(max(0.58, imp * 0.84)),
            _clamp_clarity(max(0.36, imp * 0.56)),
        )

    if etype == "sequenced":
        return (
            _clamp_clarity(max(0.5, imp * 0.78)),
            _clamp_clarity(max(0.46, imp * 0.72)),
        )

    if etype == "contains":
        return (
            _clamp_clarity(max(0.72, imp * 0.96)),
            _clamp_clarity(max(0.34, imp * 0.5)),
        )

    return (
        _clamp_clarity(max(0.52, imp * 0.88)),
        _clamp_clarity(max(0.34, imp * 0.6)),
    )
