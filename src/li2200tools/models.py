# src/li2200tools/models.py
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

RecordType = Literal["A", "B"]  # extend if LI-2200 has more types


@dataclass(frozen=True)
class Header:
    """The main header/title line, preserved for round-tripping."""
    raw: str
    key: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class Metadata:
    """
    A parsed dictionary of LI2200 file metadata (Date, Model used, General GPS info, etc)
    """

    raw: str
    parsed: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Results:
    """
    A parsed dictionary of LI2200 results (e.g. LAI, SEL, ACF, etc)
    """

    raw: str
    parsed: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Summary:
    """
    Summary block from MASK through GAPS.

    `parsed` maps each summary key -> 5 ring values (ring1..ring5).
    Values are int/float when possible, otherwise kept as str.
    """

    raw: str
    parsed: dict[str, tuple[Any, Any, Any, Any, Any]] = field(default_factory=dict)

    def get(self, key: str) -> tuple[Any, Any, Any, Any, Any] | None:
        return self.parsed.get(key)
    
@dataclass(frozen=True)
class Sensors:

    """
    Saves raw "Contributing Sensors" section
    DOES NOT PROPERLY PARSE SENSORS SECTION FOR MATCHING
    If you want to make a match() function, you will need to parse the sensors section
    """

    raw: str
    parsed: dict[str, dict[str, Any]] = field(default_factory=dict)



@dataclass(frozen=True)
class Observations:
    """
    A list of records, each of which is dataclass:Record
    
    Keep both:
        - raw: original text (lossless, round-trip if nothing changes)
        - parsed: a list of individual Records (each Record is, in turn, a dictionary)
    """

    raw: str
    records: tuple[Record, ...] = ()

    def above(self) -> "Observations":
        return self.filter(lambda r: r.record_type == "A")
    
    def below(self) -> "Observations":
        return self.filter(lambda r: r.record_type == "B")
    
    def above_n(self, n: int) -> Record:
        return self.above().nth(lambda r: True, n)


@dataclass(frozen=True)
class Record:
    """
    One measurement record.

    Keep both:
      - raw: original line (lossless, round-trip if nothing changes)
      - parsed: a dict of parsed fields (optional at first, can grow later)
    """
    raw: str
    record_type: RecordType | None = None   # "A", "B", "L", "G", etc.
    parsed: dict[str, Any] = field(default_factory=dict)

    def with_type(self, new_type: RecordType) -> "Record":
        # You’ll implement the exact rewrite rule in serializer later.
        return replace(self, record_type=new_type)


@dataclass(frozen=True)
class LI2200File:
    """
    In-memory representation of a whole LI-2200 text file.
    Includes path, whole raw text, and all the components
    WORKING: COMPLETE TRAILING
    """
    path: Path | None
    raw: str
    header: Header
    metadata: Metadata
    results: Results
    summary: Summary
    sensors: Sensors
    observations: Observations   # Observations is a tuple of Records
    trailing: list[str] = field(default_factory=list)  # blank lines, footer, etc.

    def copy(self, **changes: Any) -> "LI2200File":
        return replace(self, **changes)