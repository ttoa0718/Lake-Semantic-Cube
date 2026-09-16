from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DatasetRecord:
    id: str
    product: str
    uri: str
    data_type: str
    variables: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    time_start: str | None = None
    time_end: str | None = None


class ODCCatalog:
    """Small adapter with an ODC-like interface and metadata-only fallback."""

    def __init__(self, metadata_path: str | Path | None = None):
        self.metadata_path = Path(metadata_path) if metadata_path else None
        self.products: dict[str, dict[str, Any]] = {}
        self.records: list[DatasetRecord] = []
        if self.metadata_path and self.metadata_path.exists():
            raw = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            self.products = raw.get("products", {})
            self.records = [DatasetRecord(**item) for item in raw.get("datasets", [])]

    def add(self, record: DatasetRecord) -> None:
        self.records = [item for item in self.records if item.id != record.id]
        self.records.append(record)
        self.save()

    def register_product(self, name: str, definition: dict[str, Any] | None = None) -> None:
        """Register a product definition in the metadata fallback catalog."""
        self.products[name] = definition or {"name": name}
        self.save()

    def register_datasets(self, records: list[DatasetRecord]) -> None:
        """Register one or more dataset records, replacing matching ids."""
        existing = {item.id: item for item in self.records}
        for record in records:
            existing[record.id] = record
        self.records = list(existing.values())
        self.save()

    def save(self) -> None:
        if not self.metadata_path:
            return
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.write_text(
            json.dumps(
                {"products": self.products, "datasets": [item.__dict__ for item in self.records]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def find_base_datasets(
        self,
        product: str | None = None,
        variables: list[str] | None = None,
        product_type: str | None = None,
        time: tuple[str, str] | None = None,
        space: Any | None = None,
    ) -> list[DatasetRecord]:
        _ = (time, space)
        results = [item for item in self.records if item.data_type != "semantic"]
        if product:
            results = [item for item in results if item.product == product]
        if product_type:
            results = [item for item in results if item.data_type == product_type]
        if variables:
            results = [item for item in results if set(variables).issubset(set(item.variables))]
        return results

    def find_semantic_datasets(
        self,
        semantic_type: str,
        product: str | None = None,
        time: tuple[str, str] | None = None,
        space: Any | None = None,
    ) -> list[DatasetRecord]:
        _ = (time, space)
        results = [item for item in self.records if item.data_type == "semantic"]
        results = [item for item in results if item.properties.get("semantic:type") == semantic_type]
        if product:
            results = [item for item in results if item.product == product]
        return results
