# src/li2200tools/models.py
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Literal

RecordType = Literal["A", "B", "G", "L"]  # LI-2200 observation record types currently parsed by io.rec


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

    def _parsed_rows(self) -> list[dict[str, Any]]:
        rows = []
        for record in self.records:
            row = {"record_type": record.record_type, **record.parsed}
            rings = row.pop("rings", None)
            if rings is not None:
                row.update({f"ring{i}": value for i, value in enumerate(rings, start=1)})
            rows.append(row)
        return rows

    @property
    def parsed(self) -> Any:
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "Observations.parsed requires pandas. Install it with "
                "`python -m pip install pandas`."
            ) from exc

        df = pd.DataFrame(self._parsed_rows())
        preferred_columns = [
            "record_type",
            "seq",
            "dt",
            "sensor",
            "gps_id",
            "ring1",
            "ring2",
            "ring3",
            "ring4",
            "ring5",
            "value",
        ]
        ordered_columns = [
            column for column in preferred_columns
            if column in df.columns
        ]
        ordered_columns.extend(
            column for column in df.columns
            if column not in preferred_columns
        )
        return df.loc[:, ordered_columns]

    def filter(self, predicate: Callable[[Record], bool]) -> "Observations":
        records = tuple(record for record in self.records if predicate(record))
        return replace(self, raw="".join(record.raw for record in records), records=records)

    def nth(self, predicate: Callable[[Record], bool], n: int) -> Record:
        records = tuple(record for record in self.records if predicate(record))
        return records[n-1]

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
