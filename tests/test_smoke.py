from li2200tools.models import Observations, Record


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
