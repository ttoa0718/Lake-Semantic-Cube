from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SUPPORTED_OPERATORS = {"<", "<=", ">", ">=", "==", "between", "gradient_abs_gt"}
SUPPORTED_THRESHOLD_TYPES = {"absolute", "percentile"}


@dataclass(frozen=True)
class VariableCondition:
    name: str
    operator: str
    threshold: float | list[float]
    threshold_type: str = "absolute"
    unit: str | None = None
    percentile_scope: str = "global"


@dataclass(frozen=True)
class VerticalConstraints:
    min_continuous_layers: int = 1
    min_thickness: float = 0.0


@dataclass(frozen=True)
class SemanticRule:
    rule_id: str
    rule_version: str
    semantic_type: str
    variables: tuple[VariableCondition, ...]
    logic: str = "AND"
    vertical_constraints: VerticalConstraints = field(default_factory=VerticalConstraints)
    depth_reference: str = "surface"
    output_attributes: tuple[str, ...] = (
        "occurrence",
        "z_top",
        "z_bottom",
        "thickness",
        "core_depth",
        "segment_count",
        "layer_start",
        "layer_end",
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def variable_names(self) -> list[str]:
        return sorted({item.name for item in self.variables})
