from li2200tools.editor import SceneEditor
from li2200tools.models import Header, LI2200File, Metadata, Observations, Record, Results, Sensors, Summary
from li2200tools.scene import OrchardScene


def test_scene_editor_moves_selected_points_only():
    scene = OrchardScene()
    scene.add_observation_point("P1", 0.0, 0.0, 0.0)
    scene.add_observation_point("P2", 10.0, 0.0, 0.0)
    scene.add_observation_point("P3", 0.0, 5.0, 0.0)

    editor = SceneEditor(scene)
    editor.select_points(["P1", "P3"])
    editor.move_selected_points(dx=1.0, dy=2.0, dz=3.0)

    assert scene.points["P1"].x == 1.0
    assert scene.points["P1"].y == 2.0
    assert scene.points["P1"].z == 3.0
    assert scene.points["P2"].x == 10.0
    assert scene.points["P2"].y == 0.0
    assert scene.points["P2"].z == 0.0


def test_scene_editor_moves_canopy_transform_without_touching_points():
    scene = OrchardScene()
    scene.add_observation_point("P1", 1.0, 1.0, 1.0)
    scene.add_canopy_mesh("canopy", vertices=[(0.0, 0.0, 0.0)], faces=[(0, 0, 0)])

    editor = SceneEditor(scene)
    editor.move_canopy(dx=3.0, dy=-2.0, dz=1.5)

    assert scene.canopies["canopy"].offset == (3.0, -2.0, 1.5)
    assert scene.points["P1"].x == 1.0
    assert scene.points["P1"].y == 1.0
    assert scene.points["P1"].z == 1.0


def test_scene_adds_points_from_projected_g_records():
    file = LI2200File(
        path=None,
        raw="",
        header=Header(raw=""),
        metadata=Metadata(raw=""),
        results=Results(raw=""),
        summary=Summary(raw=""),
        sensors=Sensors(raw=""),
        observations=Observations(
            raw="",
            records=(
                Record(
                    raw="",
                    record_type="G",
                    parsed={"lon": 595200.0, "lat": 4239650.0, "alt": 12.5},
                ),
            ),
        ),
    )

    scene = OrchardScene()

    names = scene.add_g_record_points(file)

    assert names == ("G1",)
    assert scene.points["G1"].x == 595200.0
    assert scene.points["G1"].y == 4239650.0
    assert scene.points["G1"].z == 12.5


def test_scene_editor_saves_point_coordinates_to_g_records():
    original = Record(
        raw="G\t2\t2026-06-02 12:00:00\tG0\t45.0\t-123.0\t10.0\t3\t0.67\t20260602 19:00:00\n",
        record_type="G",
        parsed={
            "seq": 2,
            "dt": "2026-06-02 12:00:00",
            "gps_id": "G0",
            "lat": 45.0,
            "lon": -123.0,
            "alt": 10.0,
            "gpsnum": 3,
            "hdop": 0.67,
            "fix_dt": "20260602 19:00:00",
        },
    )
    file = LI2200File(
        path=None,
        raw="",
        header=Header(raw=""),
        metadata=Metadata(raw=""),
        results=Results(raw=""),
        summary=Summary(raw=""),
        sensors=Sensors(raw=""),
        observations=Observations(raw="", records=(original,)),
    )
    scene = OrchardScene()
    scene.add_observation_point("G1", 595201.0, 4239651.0, 11.0)

    changed = SceneEditor(scene).save_to_file(file)

    saved = changed.observations.records[0]
    assert saved.raw == ""
    assert saved.parsed["lon"] == 595201.0
    assert saved.parsed["lat"] == 4239651.0
    assert saved.parsed["alt"] == 11.0
