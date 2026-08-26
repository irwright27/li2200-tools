from __future__ import annotations

from dataclasses import dataclass

from li2200tools.engine import update_g_records
from li2200tools.models import LI2200File
from li2200tools.scene import OrchardScene


@dataclass
class SceneEditor:
    scene: OrchardScene

    def select_points(self, names: list[str]) -> None:
        self.scene.select_points(names)

    def move_selected_points(self, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> None:
        for name in self.scene.selected_points:
            point = self.scene.points[name]
            point.x += dx
            point.y += dy
            point.z += dz

    def move_canopy(self, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0, name: str | None = None) -> None:
        if name is None:
            for canopy in self.scene.canopies.values():
                canopy.offset = (
                    canopy.offset[0] + dx,
                    canopy.offset[1] + dy,
                    canopy.offset[2] + dz,
                )
            return

        canopy = self.scene.canopies[name]
        canopy.offset = (
            canopy.offset[0] + dx,
            canopy.offset[1] + dy,
            canopy.offset[2] + dz,
        )

    def save_adjustments(self) -> OrchardScene:
        return self.scene

    def save_to_file(self, file: LI2200File) -> LI2200File:
        points = {
            name: (point.x, point.y, point.z)
            for name, point in self.scene.points.items()
            if name.startswith("G")
        }
        return update_g_records(file, points)
