import pytest

from li2200tools.engine import change_record
from li2200tools.io import write_li2200
from li2200tools.models import Header, LI2200File, Metadata, Observations, Record, Results, Sensors, Summary


def _record(record_type, seq):
    return Record(
        raw=f"{record_type}\t{seq}\t2026-06-02 12:00:00\tW1\t1\t2\t3\t4\t5\n",
        record_type=record_type,
        parsed={
            "seq": seq,
            "dt": "2026-06-02 12:00:00",
            "sensor": "W1",
            "rings": [1.0, 2.0, 3.0, 4.0, 5.0],
        },
    )


def _file(records):
    return LI2200File(
        path=None,
        raw="",
        header=Header(raw="", key="LAI_FILE", value="test"),
        metadata=Metadata(raw=""),
        results=Results(raw=""),
        summary=Summary(raw=""),
        sensors=Sensors(raw=""),
        observations=Observations(raw="", records=tuple(records)),
    )


def test_change_record_preserves_global_position_when_already_valid_for_target_number():
    file = _file(
        [
            _record("A", 31),
            _record("B", 32),
            _record("A", 33),
            _record("A", 34),
            _record("A", 35),
            _record("B", 36),
        ]
    )

    changed = change_record(file, "A3", "B2")
    parsed = changed.observations.parsed

    assert list(parsed["seq"]) == [31, 32, 33, 34, 35, 36]
    assert list(parsed["record_type"]) == ["A", "B", "A", "B", "A", "B"]


def test_change_record_preserves_global_position_for_type_change_in_other_direction():
    file = _file(
        [
            _record("A", 108),
            _record("B", 109),
            _record("A", 110),
            _record("B", 111),
            _record("B", 112),
            _record("B", 113),
            _record("A", 114),
        ]
    )

    changed = change_record(file, "B3", "A3")
    parsed = changed.observations.parsed

    assert list(parsed["seq"]) == [108, 109, 110, 111, 112, 113, 114]
    assert list(parsed["record_type"]) == ["A", "B", "A", "B", "A", "B", "A"]


def test_change_record_type_only_target_preserves_global_position():
    file = _file(
        [
            _record("A", 1),
            _record("B", 2),
            _record("A", 3),
            _record("B", 4),
            _record("A", 5),
            _record("B", 6),
            _record("A", 7),
            _record("B", 8),
            _record("A", 9),
            _record("B", 10),
        ]
    )

    changed = change_record(file, "A5", "B")
    parsed = changed.observations.parsed

    assert list(parsed["seq"]) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert list(parsed["record_type"]) == ["A", "B", "A", "B", "B", "B", "A", "B", "A", "B"]


def test_change_record_type_only_keyword_preserves_global_position():
    file = _file(
        [
            _record("A", 1),
            _record("B", 2),
            _record("A", 3),
            _record("B", 4),
            _record("A", 5),
            _record("B", 6),
            _record("A", 7),
            _record("B", 8),
            _record("A", 9),
            _record("B", 10),
        ]
    )

    changed = change_record(file, "A5", record_type="B")
    parsed = changed.observations.parsed

    assert list(parsed["seq"]) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert list(parsed["record_type"]) == ["A", "B", "A", "B", "B", "B", "A", "B", "A", "B"]


def test_write_li2200_refuses_to_overwrite_by_default(tmp_path):
    out_path = tmp_path / "output.TXT"
    out_path.write_text("existing")

    with pytest.raises(FileExistsError):
        write_li2200(_file([_record("A", 1)]), out_path)

    assert out_path.read_text() == "existing"


def test_write_li2200_overwrites_when_requested(tmp_path):
    out_path = tmp_path / "output.TXT"
    out_path.write_text("existing")

    written_path = write_li2200(_file([_record("A", 1)]), out_path, overwrite=True)

    assert written_path == out_path
    assert out_path.read_text() != "existing"
    assert "### Observations\nA\t1\t2026-06-02 12:00:00\tW1\t1\t2\t3\t4\t5\n" in out_path.read_text()


def test_observations_parsed_flattens_rings():
    import pandas as pd

    observations = Observations(
        raw="",
        records=(
            Record(
                raw="A\t1\t2026-06-02 12:00:00\tW1\t1\t2\t3\t4\t5\n",
                record_type="A",
                parsed={
                    "seq": 1,
                    "dt": "2026-06-02 12:00:00",
                    "sensor": "W1",
                    "rings": [1.0, 2.0, 3.0, 4.0, 5.0],
                },
            ),
            Record(
                raw="L\t2\t2026-06-02 12:01:00\tPAR1\t800\n",
                record_type="L",
                parsed={
                    "seq": 2,
                    "dt": "2026-06-02 12:01:00",
                    "sensor": "PAR1",
                    "value": 800.0,
                },
            ),
        ),
    )

    parsed = observations.parsed

    assert list(parsed.columns) == [
        "record_type",
        "seq",
        "dt",
        "sensor",
        "ring1",
        "ring2",
        "ring3",
        "ring4",
        "ring5",
        "value",
    ]
    assert parsed.loc[0, "record_type"] == "A"
    assert parsed.loc[0, "seq"] == 1
    assert parsed.loc[0, "dt"] == "2026-06-02 12:00:00"
    assert parsed.loc[0, "sensor"] == "W1"
    assert parsed.loc[0, "ring1"] == 1.0
    assert parsed.loc[0, "ring5"] == 5.0
    assert pd.isna(parsed.loc[0, "value"])

    assert parsed.loc[1, "record_type"] == "L"
    assert parsed.loc[1, "seq"] == 2
    assert parsed.loc[1, "dt"] == "2026-06-02 12:01:00"
    assert parsed.loc[1, "sensor"] == "PAR1"
    assert pd.isna(parsed.loc[1, "ring1"])
    assert parsed.loc[1, "value"] == 800.0
