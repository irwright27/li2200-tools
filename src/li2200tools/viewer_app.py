from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import panel as pn

from li2200tools import engine, io
from li2200tools.scene import OrchardScene
from li2200tools.visualization import OrchardVisualizer


def _read_gps_points(path: Path, limit: int | None) -> list[tuple[float, float, float]]:
    frame = pd.read_csv(path)
    required_columns = {"Latitude", "Longitude", "Elevation_m"}
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"GPS CSV is missing required columns: {missing}")

    rows = frame[["Latitude", "Longitude", "Elevation_m"]].dropna()
    if limit is not None:
        rows = rows.head(limit)

    return [
        (float(latitude), float(longitude), float(elevation))
        for latitude, longitude, elevation in rows.itertuples(index=False, name=None)
    ]


def build_app(
    input_path: str | Path,
    obj_path: str | Path,
    output_path: str | Path | None = None,
    gps_csv: str | Path | None = None,
    gps_limit: int | None = None,
    gps_timezone: str = "America/Los_Angeles",
    g_source_crs: str = "EPSG:4326",
    target_crs: str = "EPSG:32610",
) -> pn.viewable.Viewable:
    input_path = Path(input_path)
    obj_path = Path(obj_path)
    output_path = Path(output_path) if output_path is not None else input_path.with_name(
        f"{input_path.stem}_edited{input_path.suffix}"
    )

    file = io.read_li2200(input_path)
    if not any(record.record_type == "G" for record in file.observations.records):
        if gps_csv is None:
            raise ValueError("The LI2200File has no G records; provide --gps-csv")
        gps_points = _read_gps_points(Path(gps_csv), gps_limit)
        file = engine.add_g_records(
            file,
            "B",
            points=gps_points,
            timezone=gps_timezone,
        )

    file = engine.g_records_to_crs(
        file,
        "all",
        source_crs=g_source_crs,
        target_crs=target_crs,
    )

    scene = OrchardScene()
    scene.load_obj_mesh("orchard", obj_path)
    point_names = scene.add_g_record_points(file)

    viewer = OrchardVisualizer(scene, file=file)
    viewer.select_points(list(point_names))
    return viewer.build_panel_ui(output_path=output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive LI-2200 orchard point editor")
    parser.add_argument("input_path", type=Path, help="Input LI-2200 TXT file")
    parser.add_argument("obj_path", type=Path, help="Orchard OBJ file")
    parser.add_argument("--output-path", type=Path, help="Edited output TXT path")
    parser.add_argument("--gps-csv", type=Path, help="GPS CSV used when the input has no G records")
    parser.add_argument("--gps-limit", type=int, help="Maximum GPS CSV rows to import")
    parser.add_argument("--gps-timezone", default="America/Los_Angeles")
    parser.add_argument("--g-source-crs", default="EPSG:4326")
    parser.add_argument("--target-crs", default="EPSG:32610")
    parser.add_argument("--port", type=int, default=5006)
    parser.add_argument("--no-show", action="store_true", help="Do not open a browser automatically")
    args = parser.parse_args()

    app = build_app(
        args.input_path,
        args.obj_path,
        output_path=args.output_path,
        gps_csv=args.gps_csv,
        gps_limit=args.gps_limit,
        gps_timezone=args.gps_timezone,
        g_source_crs=args.g_source_crs,
        target_crs=args.target_crs,
    )
    pn.serve(app, port=args.port, show=not args.no_show, title="LI-2200 Orchard Editor")


if __name__ == "__main__":
    main()
