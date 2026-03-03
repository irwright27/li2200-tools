# src/li2200tools/models.py
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

RecordType = Literal["A", "B"]  # extend if LI-2200 has more types


@dataclass(frozen=True)
class Header:
    """A group of header lines, preserved for round-tripping."""
    raw: str
    key: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class Record:
    """
    One measurement record.

    Keep both:
      - raw: original line (lossless round-trip)
      - parsed: a dict of parsed fields (optional at first, can grow later)
    """
    raw: str
    record_type: RecordType | None = None
    parsed: dict[str, Any] = field(default_factory=dict)

    def with_type(self, new_type: RecordType) -> "Record":
        # You’ll implement the exact rewrite rule in serializer later.
        return replace(self, record_type=new_type)


@dataclass(frozen=True)
class LI2200File:
    """
    In-memory representation of an LI-2200 text file.
    """
    path: Path | None
    header: list[HeaderLine]
    records: list[Record]
    trailing: list[str] = field(default_factory=list)  # blank lines, footer, etc.
    metadata: dict[str, Any] = field(default_factory=dict)

    def copy(self, **changes: Any) -> "LI2200File":
        return replace(self, **changes)