from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .rule import (
    SUPPORTED_OPERATORS,
    SUPPORTED_THRESHOLD_TYPES,
    SemanticRule,
    VariableCondition,
    VerticalConstraints,
)


def load_rule(path: str | Path) -> SemanticRule:
    return parse_rule(json.loads(Path(path).read_text(encoding="utf-8")))


def parse_rule(raw: dict[str, Any]) -> SemanticRule:
    for key in ("rule_id", "rule_version", "semantic_type"):
        if key not in raw:
            raise ValueError(f"Semantic rule missing required key: {key}")

    logic = str(raw.get("logic", raw.get("logical_operator", "AND"))).upper()
    if logic not in {"AND", "OR"}:
        raise ValueError("Semantic rule logic must be AND or OR")

    variable_items = raw.get("variables", raw.get("conditions"))
    if not isinstance(variable_items, list) or not variable_items:
        raise ValueError("Semantic rule requires a non-empty variables list")

    variables: list[VariableCondition] = []
    for item in variable_items:
        name = item.get("name", item.get("variable"))
        operator = item.get("operator")
        if not name:
            raise ValueError("Each variable condition requires name")
        if operator not in SUPPORTED_OPERATORS:
            raise ValueError(f"Unsupported operator for {name}: {operator}")
        threshold = item.get("threshold", item.get("value"))
        if operator == "between":
            if not isinstance(threshold, list) or len(threshold) != 2:
                raise ValueError("between operator requires two threshold values")
        elif threshold is None:
            raise ValueError(f"Condition for {name} requires threshold")
        threshold_type = str(item.get("threshold_type", "absolute"))
        if threshold_type not in SUPPORTED_THRESHOLD_TYPES:
            raise ValueError(f"Unsupported threshold_type: {threshold_type}")
        variables.append(
            VariableCondition(
                name=str(name),
                operator=str(operator),
                threshold=threshold,
                threshold_type=threshold_type,
                unit=item.get("unit"),
                percentile_scope=str(item.get("percentile_scope", "global")),
            )
        )

    vertical_raw = raw.get("vertical_constraints", {})
    return SemanticRule(
        rule_id=str(raw["rule_id"]),
        rule_version=str(raw["rule_version"]),
        semantic_type=str(raw["semantic_type"]),
        variables=tuple(variables),
        logic=logic,
        vertical_constraints=VerticalConstraints(
            min_continuous_layers=int(vertical_raw.get("min_continuous_layers", 1)),
            min_thickness=float(vertical_raw.get("min_thickness", vertical_raw.get("min_thickness_m", 0.0))),
        ),
        depth_reference=str(raw.get("depth_reference", "surface")),
        output_attributes=tuple(raw.get("output_attributes", SemanticRule.__dataclass_fields__["output_attributes"].default)),
        metadata=dict(raw.get("metadata", {})),
    )
