from __future__ import annotations

from datetime import datetime, timezone

from lake_semantic_cube import __version__
from lake_semantic_cube.semantics.rule import SemanticRule
from lake_semantic_cube.vertical.reference import VerticalReference


def semantic_attrs(
    rule: SemanticRule,
    source_product: str,
    vertical_reference: VerticalReference,
    source_dataset_ids: list[str] | None = None,
) -> dict:
    return {
        "semantic_type": rule.semantic_type,
        "rule_id": rule.rule_id,
        "rule_version": rule.rule_version,
        "source_product": source_product,
        "source_variables": ",".join(rule.variable_names),
        "source_dataset_ids": ",".join(source_dataset_ids or []),
        "vertical_reference": str(vertical_reference.to_metadata()),
        "primary_segment_policy": "thickest",
        "created_by": "lake_semantic_cube",
        "software_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "index_role": "semantic_object_materialization_and_vertical_semantic_index",
    }
