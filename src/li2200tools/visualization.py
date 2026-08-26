from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from li2200tools.editor import SceneEditor
from li2200tools.scene import OrchardScene

if TYPE_CHECKING:
    from li2200tools.models import LI2200File


class OrchardVisualizer:
    """Interactive Python viewer for orchard canopy meshes and LAI observation points."""

    def __init__(self, scene: OrchardScene | None = None, file: LI2200File | None = None):
        self.scene = scene or OrchardScene()
        self.file = file
        self.editor = SceneEditor(self.scene)
        self._plotter: Any | None = None
        self._point_mesh: Any | None = None

    def set_scene(self, scene: OrchardScene) -> None:
        self.scene = scene
        self.editor = SceneEditor(self.scene)
        self._plotter = None
        self._point_mesh = None

    def add_obj_mesh(self, name: str, obj_path: str | Path) -> None:
        self.scene.load_obj_mesh(name, obj_path)

    def select_points(self, names: list[str]) -> None:
        self.editor.select_points(names)

    def move_selected_points(self, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> None:
        self.editor.move_selected_points(dx=dx, dy=dy, dz=dz)

    def move_canopy(self, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0, name: str | None = None) -> None:
        self.editor.move_canopy(dx=dx, dy=dy, dz=dz, name=name)

    def save_adjustments(self) -> OrchardScene:
        return self.editor.save_adjustments()

    def save_to_file(self, file: LI2200File | None = None) -> LI2200File:
        source_file = file or self.file
        if source_file is None:
            raise ValueError("An LI2200File is required to save G-record adjustments")
        self.file = self.editor.save_to_file(source_file)
        return self.file

    def build_plotter(self) -> Any:
        try:
            import pyvista as pv
        except ImportError as exc:
            raise RuntimeError(
                "PyVista is required for 3D orchard visualization. Install it with "
                "`python -m pip install pyvista panel`."
            ) from exc

        if self._plotter is None:
            self._plotter = pv.Plotter(window_size=(1100, 700))
        self._plotter.clear()

        for canopy in self.scene.canopies.values():
            vertices = [
                (x + canopy.offset[0], y + canopy.offset[1], z + canopy.offset[2])
                for x, y, z in canopy.vertices
            ]
            face_array = [
                value
                for face in canopy.faces
                for value in (len(face), *face)
            ]
            mesh = pv.PolyData(vertices, faces=face_array)
            self._plotter.add_mesh(mesh, color="forestgreen", opacity=0.7, smooth_shading=True)

        if self.scene.points:
            points = [
                (point.x, point.y, point.z)
                for point in self.scene.points.values()
            ]
            cloud = pv.PolyData(points)
            self._point_mesh = cloud
            self._plotter.add_mesh(
                cloud,
                color="crimson",
                point_size=18,
                render_points_as_spheres=True,
            )

        self._plotter.add_axes()
        self._plotter.camera_position = "iso"
        return self._plotter

    def refresh_points(self) -> None:
        if self._point_mesh is None or self._plotter is None:
            return

        points = [
            (point.x, point.y, point.z)
            for point in self.scene.points.values()
        ]
        self._point_mesh.points = points
        self._point_mesh.GetPoints().Modified()
        self._point_mesh.Modified()
        self._plotter.render()

    def render(self) -> Any:
        return self.build_plotter()

    def show(self) -> None:
        plotter = self.build_plotter()
        plotter.show()

    def build_panel_ui(
        self,
        file: LI2200File | None = None,
        output_path: str | Path | None = None,
    ) -> Any:
        try:
            import panel as pn
        except ImportError as exc:
            raise RuntimeError(
                "Panel is required for the interactive slider UI. Install it with "
                "`python -m pip install pyvista panel`."
            ) from exc

        pn.extension("vtk")

        if file is not None:
            self.file = file

        save_path = Path(output_path) if output_path is not None else None

        point_names = sorted(self.scene.points)
        selected = pn.widgets.MultiSelect(
            name="Selected LAI points",
            options=point_names,
            value=sorted(self.scene.selected_points),
        )
        point_dx = pn.widgets.FloatSlider(name="Point Δx", start=-10, end=10, step=0.1, value=0.0)
        point_dy = pn.widgets.FloatSlider(name="Point Δy", start=-10, end=10, step=0.1, value=0.0)
        point_dz = pn.widgets.FloatSlider(name="Point Δz", start=-10, end=10, step=0.1, value=0.0)
        manual_x = pn.widgets.TextInput(name="X coordinate", value="0.0")
        manual_y = pn.widgets.TextInput(name="Y coordinate", value="0.0")
        manual_z = pn.widgets.TextInput(name="Z coordinate", value="0.0")
        plotter = self.build_plotter()
        vtk_pane = pn.pane.VTK(plotter.ren_win, sizing_mode="stretch_both", min_height=700)
        status = pn.pane.Markdown("Ready")
        coordinates = pn.pane.Markdown("No points selected")
        point_origins = {
            name: (point.x, point.y, point.z)
            for name, point in self.scene.points.items()
        }
        updating_controls = False

        def coordinate_text() -> str:
            selected_names = sorted(self.scene.selected_points)
            if not selected_names:
                return "No points selected"
            if len(selected_names) == 1:
                point = self.scene.points[selected_names[0]]
                return (
                    f"**{selected_names[0]}**  \n"
                    f"x: `{point.x:.3f}`  \n"
                    f"y: `{point.y:.3f}`  \n"
                    f"z: `{point.z:.3f}`"
                )
            rows = [f"**{len(selected_names)} points selected**"]
            rows.extend(
                f"- `{name}`: ({self.scene.points[name].x:.3f}, "
                f"{self.scene.points[name].y:.3f}, {self.scene.points[name].z:.3f})"
                for name in selected_names
            )
            return "\n".join(rows)

        def refresh_view() -> None:
            self.refresh_points()
            vtk_pane.param.trigger("object")
            coordinates.object = coordinate_text()
            status.object = "Point positions updated"

        offsets = {"x": 0.0, "y": 0.0, "z": 0.0}

        def set_slider_offset(axis: str, value: float, source: Any) -> None:
            nonlocal updating_controls
            if updating_controls:
                return
            offsets[axis] = float(value)

            for name in self.scene.selected_points:
                origin_x, origin_y, origin_z = point_origins[name]
                point = self.scene.points[name]
                point.x = origin_x + offsets["x"]
                point.y = origin_y + offsets["y"]
                point.z = origin_z + offsets["z"]
            update_manual_coordinates()
            refresh_view()

        def set_manual_coordinate(axis: str, value: str) -> None:
            nonlocal updating_controls
            if updating_controls:
                return
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                status.object = f"{axis.upper()} coordinate must be numeric"
                return

            for name in self.scene.selected_points:
                point = self.scene.points[name]
                setattr(point, axis, numeric_value)
                origin = list(point_origins[name])
                origin[{"x": 0, "y": 1, "z": 2}[axis]] = numeric_value
                point_origins[name] = tuple(origin)

            offsets[axis] = 0.0
            slider = {"x": point_dx, "y": point_dy, "z": point_dz}[axis]
            updating_controls = True
            slider.value = 0.0
            updating_controls = False
            refresh_view()

        def update_manual_coordinates() -> None:
            nonlocal updating_controls
            selected_names = sorted(self.scene.selected_points)
            widgets = {"x": manual_x, "y": manual_y, "z": manual_z}
            updating = {axis: "" for axis in widgets}
            if selected_names:
                for axis, widget in widgets.items():
                    values = {getattr(self.scene.points[name], axis) for name in selected_names}
                    if len(values) == 1:
                        updating[axis] = f"{values.pop():.3f}"
                    else:
                        updating[axis] = "mixed"

            updating_controls = True
            try:
                for axis, widget in widgets.items():
                    widget.value = updating[axis]
            finally:
                updating_controls = False

        def move_points(event: Any) -> None:
            self.select_points(list(selected.value))
            axis = {point_dx: "x", point_dy: "y", point_dz: "z"}[event.obj]
            set_slider_offset(axis, event.new, event.obj)

        def edit_manual_coordinate(event: Any) -> None:
            axis = {manual_x: "x", manual_y: "y", manual_z: "z"}[event.obj]
            set_manual_coordinate(axis, event.new)

        def update_selection(event: Any) -> None:
            nonlocal updating_controls
            self.select_points(list(selected.value))
            offsets.update(x=0.0, y=0.0, z=0.0)
            updating_controls = True
            for widget in (point_dx, point_dy, point_dz):
                widget.value = 0.0
            for widget in (manual_x, manual_y, manual_z):
                widget.value = ""
            updating_controls = False
            update_manual_coordinates()
            coordinates.object = coordinate_text()
            refresh_view()

        selected.param.watch(update_selection, "value")
        point_dx.param.watch(move_points, "value")
        point_dy.param.watch(move_points, "value")
        point_dz.param.watch(move_points, "value")
        manual_x.param.watch(edit_manual_coordinate, "value")
        manual_y.param.watch(edit_manual_coordinate, "value")
        manual_z.param.watch(edit_manual_coordinate, "value")
        save_button = pn.widgets.Button(name="Save G records", button_type="primary")

        def save_g_records(event: Any = None) -> None:
            updated_file = self.save_to_file()
            if save_path is None:
                status.object = "G records updated in memory"
                return

            from li2200tools.io import write_li2200

            write_li2200(updated_file, save_path, overwrite=True)
            status.object = f"Saved edited file to {save_path}"

        save_button.on_click(save_g_records)
        return pn.Column(
            pn.Row(
                pn.Column(
                    pn.pane.Markdown("### Orchard QA editor"),
                    selected,
                    coordinates,
                    pn.Column(point_dx, point_dy, point_dz),
                    pn.Column(manual_x, manual_y, manual_z),
                    save_button,
                    status,
                    width=420,
                ),
                vtk_pane,
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        )
