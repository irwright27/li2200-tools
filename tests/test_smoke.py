from li2200tools.models import Observations, Record


def test_observations_parsed_flattens_rings():
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

    assert observations.parsed == [
        {
            "record_type": "A",
            "seq": 1,
            "dt": "2026-06-02 12:00:00",
            "sensor": "W1",
            "ring1": 1.0,
            "ring2": 2.0,
            "ring3": 3.0,
            "ring4": 4.0,
            "ring5": 5.0,
        },
        {
            "record_type": "L",
            "seq": 2,
            "dt": "2026-06-02 12:01:00",
            "sensor": "PAR1",
            "value": 800.0,
        },
    ]
