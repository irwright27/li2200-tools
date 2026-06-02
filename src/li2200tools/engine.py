from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Iterable, Literal, Union, cast

from li2200tools.models import LI2200File, Observations, Record, RecordType


NumberSpec = Union[int, str, range, Iterable[Union[int, str, range]]]
RecordSelector = Union[str, Record]
RecordSpec = Union[RecordSelector, Iterable[RecordSelector]]
AveragePlacement = Literal["beginning", "end", "first", "last"]
InterpolationMethod = Literal["linear", "connect"]


_RECORD_SELECTOR = re.compile(r"^([ABGL])(\d+)(?::([ABGL])?(\d+))?$", re.IGNORECASE)
_DATETIME_FORMATS = (
    "%Y%m%d %H:%M:%S.%f",
    "%Y%m%d %H:%M:%S",
    "%Y%m%d %H:%M",
    "%Y%m%dT%H:%M:%S.%f",
    "%Y%m%dT%H:%M:%S",
    "%Y%m%dT%H:%M",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y/%m/%d %H:%M:%S.%f",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%m/%d/%Y %H:%M:%S.%f",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%y %H:%M:%S.%f",
    "%m/%d/%y %H:%M:%S",
    "%m/%d/%y %H:%M",
)


def _expand_numbers(spec: NumberSpec | None) -> set[int] | None:
    """
    Expand notebook-friendly number specs.

    Integers are 1-based logical numbers. Strings like "24:30" are inclusive.
    """
    if spec is None:
        return None

    if isinstance(spec, int):
        return {spec}

    if isinstance(spec, range):
        return set(spec)

    if isinstance(spec, str):
        if ":" in spec:
            start, stop = spec.split(":", 1)
            return set(range(int(start), int(stop) + 1))
        return {int(spec)}

    numbers: set[int] = set()
    for item in spec:
        expanded = _expand_numbers(item)
        if expanded is not None:
            numbers.update(expanded)
    return numbers


def _record_logical_numbers(records: tuple[Record, ...], record_type: RecordType) -> dict[int, Record]:
    typed_records = (record for record in records if record.record_type == record_type)
    return {i: record for i, record in enumerate(typed_records, start=1)}


def filter_file(
    path_or_file: str | Path | LI2200File,
    rec_type: RecordType | Iterable[RecordType] | None = None,
    nA: NumberSpec | None = None,
    nB: NumberSpec | None = None,
    dt: tuple[str, str] | list[str] | None = None,
    seq: NumberSpec | None = None,
) -> LI2200File:
    """
    Return a new LI2200File with filtered observations.

    Filtering order:
      1. dt narrows the available observations first.
      2. rec_type and seq filter the remaining observations.
      3. nA/nB select 1-based logical A/B records from the dt-filtered set.

    nA and nB override seq for their respective record types.
    """
    li = path_or_file if isinstance(path_or_file, LI2200File) else read_li2200(Path(path_or_file))

    records = li.observations.records

    if dt is not None:
        start, stop = dt
        records = tuple(record for record in records if start <= record.parsed["dt"] <= stop)

    if rec_type is None:
        allowed_types = None
    elif isinstance(rec_type, str):
        allowed_types = {rec_type}
    else:
        allowed_types = set(rec_type)

    seq_numbers = _expand_numbers(seq)
    nA_numbers = _expand_numbers(nA)
    nB_numbers = _expand_numbers(nB)

    selected_a = _record_logical_numbers(records, "A") if nA_numbers is not None else {}
    selected_b = _record_logical_numbers(records, "B") if nB_numbers is not None else {}

    filtered_records: list[Record] = []
    for record in records:
        if allowed_types is not None and record.record_type not in allowed_types:
            continue

        if record.record_type == "A" and nA_numbers is not None:
            if record in (selected_a[i] for i in nA_numbers if i in selected_a):
                filtered_records.append(record)
            continue

        if record.record_type == "B" and nB_numbers is not None:
            if record in (selected_b[i] for i in nB_numbers if i in selected_b):
                filtered_records.append(record)
            continue

        if seq_numbers is not None and record.parsed.get("seq") not in seq_numbers:
            continue

        filtered_records.append(record)

    observations = Observations(
        raw="".join(record.raw for record in filtered_records),
        records=tuple(filtered_records),
    )
    return li.copy(observations=observations)


def delete_records(
    file: LI2200File,
    rec_type=None,
    nA=None,
    nB=None,
    dt=None,
    seq=None,
) -> LI2200File:
    records = file.observations.records

    if dt is not None:
        start, stop = dt
        records_in_dt = tuple(
            record for record in records
            if start <= record.parsed["dt"] <= stop
        )
    else:
        records_in_dt = records

    if rec_type is None:
        allowed_types = None
    elif isinstance(rec_type, str):
        allowed_types = {rec_type}
    else:
        allowed_types = set(rec_type)

    seq_numbers = _expand_numbers(seq)
    nA_numbers = _expand_numbers(nA)
    nB_numbers = _expand_numbers(nB)

    selected_a = (
        _record_logical_numbers(records_in_dt, "A")
        if nA_numbers is not None
        else {}
    )

    selected_b = (
        _record_logical_numbers(records_in_dt, "B")
        if nB_numbers is not None
        else {}
    )

    records_to_delete = set()

    for record in records_in_dt:
        if allowed_types is not None and record.record_type not in allowed_types:
            continue

        if record.record_type == "A" and nA_numbers is not None:
            if record in (selected_a[i] for i in nA_numbers if i in selected_a):
                records_to_delete.add(record)
            continue

        if record.record_type == "B" and nB_numbers is not None:
            if record in (selected_b[i] for i in nB_numbers if i in selected_b):
                records_to_delete.add(record)
            continue

        if seq_numbers is not None and record.parsed.get("seq") in seq_numbers:
            records_to_delete.add(record)
            continue

        if seq_numbers is None and nA_numbers is None and nB_numbers is None:
            records_to_delete.add(record)

    kept_records = tuple(
        record for record in records
        if record not in records_to_delete
    )

    observations = Observations(
        raw="".join(record.raw for record in kept_records),
        records=kept_records,
    )

    return file.copy(observations=observations)
