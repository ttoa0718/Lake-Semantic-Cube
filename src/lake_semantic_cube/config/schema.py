from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VariableInfo:
    """Controlled variable metadata used by formal modules."""

    name: str
    unit: str | None = None
    code: str | int | None = None
    description: str | None = None


def parse_variables(raw: dict) -> dict[str, VariableInfo]:
    variables: dict[str, VariableInfo] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            variables[value] = VariableInfo(name=value, code=key)
        elif isinstance(value, dict):
            name = str(value.get("name", key))
            variables[name] = VariableInfo(
                name=name,
                unit=value.get("unit"),
                code=value.get("code", key),
                description=value.get("description"),
            )
        else:
            raise ValueError(f"Invalid variable metadata for {key!r}")
    return variables
