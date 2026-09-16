from __future__ import annotations

import uuid
from pathlib import Path


NAMESPACE = uuid.UUID("55d57f71-7985-5caa-9c74-676c0a557bbb")


def deterministic_dataset_uuid(
    product: str,
    uri: str | Path,
    time_start: str | None,
    time_end: str | None,
    rule_id: str | None = None,
    rule_version: str | None = None,
) -> str:
    key = "|".join(
        [
            product,
            str(uri),
            str(time_start),
            str(time_end),
            str(rule_id or ""),
            str(rule_version or ""),
        ]
    )
    return str(uuid.uuid5(NAMESPACE, key))
