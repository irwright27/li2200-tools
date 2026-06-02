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


def _as_record_spec_tuple(records: RecordSpec | None) -> tuple[RecordSelector, ...]:
    if records is None:
        return ()

    if isinstance(records, (str, Record)):
        return (records,)

    return tuple(records)


def _parse_record_selector(selector: str) -> tuple[RecordType, int, int]:
    match = _RECORD_SELECTOR.fullmatch(selector.strip())
    if match is None:
        raise ValueError(
            f"Record selector {selector!r} must look like 'A2', 'B5', 'A1:A3', or 'B5:B6'"
        )

    start_type, start, end_type, end = match.groups()
    record_type = cast(RecordType, start_type.upper())

    if end_type is not None and end_type.upper() != record_type:
        raise ValueError(f"Record selector {selector!r} cannot span different record types")

    start_number = int(start)
    end_number = int(end) if end is not None else start_number

    if start_number < 1 or end_number < 1:
        raise ValueError(f"Record selector {selector!r} must use 1-based record numbers")

    if end_number < start_number:
        raise ValueError(f"Record selector {selector!r} cannot count backwards")

    return record_type, start_number, end_number


def locate_records(file: LI2200File, records: RecordSpec) -> tuple[Record, ...]:
    """
    Return records identified by compact selectors or explicit Record objects.

    Args:
        file: The input file in LI2200File object format.
        records: Records to locate. Use Record objects directly, single selectors
            like "A2" or "B5", or ranges like "A1:A3" and "B5:B6".

    Returns:
        Matching Record objects in the same order requested.
    """
    all_records = file.observations.records
    logical_records = {
        record_type: _record_logical_numbers(all_records, record_type)
        for record_type in ("A", "B", "G", "L")
    }

    located_records: list[Record] = []
    for item in _as_record_spec_tuple(records):
        if isinstance(item, Record):
            located_records.append(item)
            continue

        record_type, start, end = _parse_record_selector(item)
        records_by_number = logical_records[record_type]
        missing = [number for number in range(start, end + 1) if number not in records_by_number]
        if missing:
            missing_text = ", ".join(f"{record_type}{number}" for number in missing)
            raise ValueError(f"Record selector {item!r} did not match: {missing_text}")

        located_records.extend(records_by_number[number] for number in range(start, end + 1))

    return tuple(located_records)


def _record_ids(records: Iterable[Record]) -> set[int]:
    return {id(record) for record in records}


def _single_located_record(file: LI2200File, record: RecordSelector) -> Record:
    records = locate_records(file, record)
    if len(records) != 1:
        raise ValueError("Expected exactly one source record")
    return records[0]


def _logical_number_of_record(file: LI2200File, record: Record) -> int:
    if record.record_type is None:
        raise ValueError("Cannot locate logical number for record without a type")

    for number, typed_record in _record_logical_numbers(
        file.observations.records,
        record.record_type,
    ).items():
        if id(typed_record) == id(record):
            return number

    raise ValueError("Record does not belong to the file being edited")


def _parse_change_target(
    target: str | None,
    record_type: RecordType | None,
    n: int | None,
    default_record_type: RecordType,
    default_n: int,
) -> tuple[RecordType, int]:
    target_record_type = record_type
    target_n = n

    if target is not None:
        target = target.strip()
        match = re.fullmatch(r"([AB])?(\d+)?", target, re.IGNORECASE)
        if match is None or (match.group(1) is None and match.group(2) is None):
            raise ValueError("Change target must look like 'A6', 'B2', 'A', 'B', or '6'")

        if match.group(1) is not None:
            target_record_type = cast(RecordType, match.group(1).upper())

        if match.group(2) is not None:
            target_n = int(match.group(2))

    if target_record_type is None:
        target_record_type = default_record_type

    if target_n is None:
        target_n = default_n

    if target_record_type not in ("A", "B"):
        raise ValueError("change_record currently supports changing between A and B records")

    if target_n < 1:
        raise ValueError("Destination record number must be 1 or greater")

    return target_record_type, target_n


def _round_decimal_places(value: float, places: int) -> float:
    quantizer = Decimal("1").scaleb(-places)
    return float(Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP))


def _round_half_up(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _parse_datetime(value: str) -> tuple[datetime, str | None]:
    for dt_format in _DATETIME_FORMATS:
        try:
            return datetime.strptime(value, dt_format), dt_format
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(value), None
    except ValueError as exc:
        raise ValueError(f"Timestamp {value!r} is not in a supported datetime format") from exc


def _format_datetime(value: datetime, dt_format: str | None, template: str) -> str:
    if dt_format is not None:
        if "%f" not in dt_format:
            value = value.replace(microsecond=0)
        if "%S" not in dt_format:
            value = value.replace(second=0)
        return value.strftime(dt_format)

    separator = "T" if "T" in template else " "
    if "." in template:
        timespec = "microseconds"
    elif re.search(r"\d{1,2}:\d{2}:\d{2}", template):
        timespec = "seconds"
    else:
        timespec = "minutes"
    if timespec == "seconds":
        value = value.replace(microsecond=0)
    elif timespec == "minutes":
        value = value.replace(second=0, microsecond=0)
    return value.isoformat(sep=separator, timespec=timespec)


def _average_datetimes(values: Iterable[str]) -> str:
    timestamps = tuple(values)
    first_datetime, first_format = _parse_datetime(timestamps[0])
    datetimes = [first_datetime]

    for timestamp in timestamps[1:]:
        parsed, _ = _parse_datetime(timestamp)
        datetimes.append(parsed)

    average_seconds = sum(
        (value - first_datetime).total_seconds()
        for value in datetimes
    ) / len(datetimes)

    if first_format is not None and "%f" in first_format:
        average_microseconds = _round_half_up(average_seconds * 1_000_000)
        average_datetime = first_datetime + timedelta(microseconds=average_microseconds)
    elif first_format is not None and "%S" not in first_format:
        average_minutes = _round_half_up(average_seconds / 60)
        average_datetime = first_datetime + timedelta(minutes=average_minutes)
    elif first_format is None and "." in timestamps[0]:
        average_microseconds = _round_half_up(average_seconds * 1_000_000)
        average_datetime = first_datetime + timedelta(microseconds=average_microseconds)
    elif first_format is None and not re.search(r"\d{1,2}:\d{2}:\d{2}", timestamps[0]):
        average_minutes = _round_half_up(average_seconds / 60)
        average_datetime = first_datetime + timedelta(minutes=average_minutes)
    else:
        average_datetime = first_datetime + timedelta(seconds=_round_half_up(average_seconds))

    return _format_datetime(average_datetime, first_format, timestamps[0])


def filter_file(
    file: LI2200File,
    records: RecordSpec | None = None,
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
      2. records, rec_type, and seq filter the remaining observations.
      3. nA/nB select 1-based logical A/B records from the dt-filtered set.

    Use records for compact selectors like "A2", "B5", "A1:A3", or "B5:B6".
    nA and nB override seq for their respective record types.

    Args:
        file: The input file in LI2200File object format.
        records: Records to keep. Use Record objects directly, single selectors
            like "A2" or "B5", or ranges like "A1:A3" and "B5:B6".
        rec_type: Record type or types to keep, such as "A" or ["A", "B"].
        nA: 1-based logical A record numbers to keep.
        nB: 1-based logical B record numbers to keep.
        dt: Optional start and stop datetime strings to narrow records first.
        seq: Sequence number or numbers to keep.

    Returns:
        A new LI2200File with only the selected records.
    """
    all_records = file.observations.records
    selected_record_ids = _record_ids(locate_records(file, records)) if records is not None else None

    if dt is not None:
        start, stop = dt
        all_records = tuple(record for record in all_records if start <= record.parsed["dt"] <= stop)

    if rec_type is None:
        allowed_types = None
    elif isinstance(rec_type, str):
        allowed_types = {rec_type}
    else:
        allowed_types = set(rec_type)

    seq_numbers = _expand_numbers(seq)
    nA_numbers = _expand_numbers(nA)
    nB_numbers = _expand_numbers(nB)

    selected_a = _record_logical_numbers(all_records, "A") if nA_numbers is not None else {}
    selected_b = _record_logical_numbers(all_records, "B") if nB_numbers is not None else {}

    filtered_records: list[Record] = []
    for record in all_records:
        if selected_record_ids is not None and id(record) not in selected_record_ids:
            continue

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
