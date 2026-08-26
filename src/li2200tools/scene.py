from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from li2200tools.models import LI2200File


@dataclass
class ObservationPoint:
    name: str
    x: float
    y: float
    z: float


@dataclass
class CanopyMesh:
    name: str
    vertices: list[tuple[float, float, float]]
    faces: list[tuple[int, int, int]]
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class OrchardScene:
    points: dict[str, ObservationPoint] = field(default_factory=dict)
    canopies: dict[str, CanopyMesh] = field(default_factory=dict)
    selected_points: set[str] = field(default_factory=set)

    def add_observation_point(self, name: str, x: float, y: float, z: float) -> ObservationPoint:
        point = ObservationPoint(name=name, x=x, y=y, z=z)
        self.points[name] = point
        return point

    def add_g_record_points(
        self,
        file: LI2200File,
        prefix: str = "G",
    ) -> tuple[str, ...]:
        names: list[str] = []
        for index, record in enumerate(
            (record for record in file.observations.records if record.record_type == "G"),
            start=1,
        ):
            try:
                x = float(record.parsed["lon"])
                y = float(record.parsed["lat"])
                z = float(record.parsed["alt"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    "G records must contain numeric 'lon', 'lat', and 'alt' fields"
                ) from exc

            name = f"{prefix}{index}"
            self.add_observation_point(name, x, y, z)
            names.append(name)

        if not names:
            raise ValueError("The LI2200File does not contain any G records")

        return tuple(names)

    def add_canopy_mesh(
        self,
        name: str,
        vertices: list[tuple[float, float, float]],
        faces: list[tuple[int, int, int]],
    ) -> CanopyMesh:
        mesh = CanopyMesh(name=name, vertices=vertices, faces=faces)
        self.canopies[name] = mesh
        return mesh

    def load_obj_mesh(self, name: str, path: str | Path) -> CanopyMesh:
        obj_path = Path(path)
        vertices: list[tuple[float, float, float]] = []
        faces: list[tuple[int, int, int]] = []

        with obj_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.startswith("v "):
                    parts = stripped.split()[1:]
                    if len(parts) >= 3:
                        vertices.append((float(parts[0]), float(parts[1]), float(parts[2])))
                elif stripped.startswith("f "):
                    parts = stripped.split()[1:]
                    if len(parts) >= 3:
                        face = tuple(int(part.split("/")[0]) - 1 for part in parts[:3])
                        faces.append(face)

        if not vertices:
            raise ValueError(f"OBJ file did not contain any vertices: {obj_path}")

        return self.add_canopy_mesh(name, vertices, faces)

    def select_points(self, names: list[str]) -> None:
        self.selected_points = set(names)

    def clear_selection(self) -> None:
        self.selected_points.clear()
