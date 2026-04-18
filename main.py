import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QPoint, QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


@dataclass
class Shape:
    shape_type: str
    start: Tuple[float, float]
    end: Tuple[float, float]
    layer: str
    selected: bool = False

    @property
    def start_point(self) -> QPointF:
        return QPointF(self.start[0], self.start[1])

    @property
    def end_point(self) -> QPointF:
        return QPointF(self.end[0], self.end[1])

    def set_points(self, start: QPointF, end: QPointF) -> None:
        self.start = (start.x(), start.y())
        self.end = (end.x(), end.y())

    def normalized_rect(self) -> QRectF:
        return QRectF(self.start_point, self.end_point).normalized()

    def move_by(self, dx: float, dy: float) -> None:
        self.start = (self.start[0] + dx, self.start[1] + dy)
        self.end = (self.end[0] + dx, self.end[1] + dy)

    def length(self) -> float:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        return math.hypot(dx, dy)

    def area(self) -> float:
        rect = self.normalized_rect()
        if self.shape_type == "rectangle":
            return rect.width() * rect.height()
        if self.shape_type == "circle":
            radius_x = rect.width() / 2
            radius_y = rect.height() / 2
            radius = min(radius_x, radius_y)
            return math.pi * radius * radius
        return 0.0

    def contains_point(self, point: QPointF, tolerance: float = 8.0) -> bool:
        if self.shape_type == "line":
            return self._distance_to_line(point) <= tolerance
        rect = self.normalized_rect().adjusted(-tolerance, -tolerance, tolerance, tolerance)
        return rect.contains(point)

    def _distance_to_line(self, point: QPointF) -> float:
        x1, y1 = self.start
        x2, y2 = self.end
        px, py = point.x(), point.y()

        line_len_sq = (x2 - x1) ** 2 + (y2 - y1) ** 2
        if line_len_sq == 0:
            return math.hypot(px - x1, py - y1)

        t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / line_len_sq
        t = max(0.0, min(1.0, t))
        cx = x1 + t * (x2 - x1)
        cy = y1 + t * (y2 - y1)
        return math.hypot(px - cx, py - cy)


class CADCanvas(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(980, 620)
        self.setMouseTracking(True)

        self.shapes: List[Shape] = []
        self.undo_stack: List[Shape] = []
        self.current_tool = "line"
        self.stroke_width = 2

        self.grid_visible = True
        self.grid_size = 20
        self.snap_to_grid = False

        self.zoom = 1.0
        self.pan_offset = QPointF(0, 0)

        self.layers: Dict[str, Dict[str, object]] = {
            "Default": {"visible": True, "color": "#22c1ff"}
        }
        self.active_layer = "Default"

        self.drawing_shape: Optional[Shape] = None
        self.selected_shape: Optional[Shape] = None
        self.drag_origin: Optional[QPointF] = None
        self.panning = False
        self.pan_anchor = QPoint()

        self.on_status = None
        self.setStyleSheet("background-color: #1c1c1c;")

    def set_status_callback(self, callback) -> None:
        self.on_status = callback

    def emit_status(self, text: str) -> None:
        if self.on_status:
            self.on_status(text)

    def set_tool(self, tool: str) -> None:
        self.current_tool = tool
        self.clear_selection()
        self.update()

    def set_stroke_width(self, width: int) -> None:
        self.stroke_width = width
        self.update()

    def set_grid_size(self, size: int) -> None:
        self.grid_size = max(5, size)
        self.update()

    def toggle_grid(self, checked: bool) -> None:
        self.grid_visible = checked
        self.update()

    def toggle_snap(self, checked: bool) -> None:
        self.snap_to_grid = checked

    def set_active_layer(self, layer: str) -> None:
        if layer in self.layers:
            self.active_layer = layer
            self.emit_status(f"Active layer: {layer}")

    def add_layer(self, name: str, color: str = "#22c1ff") -> bool:
        if not name or name in self.layers:
            return False
        self.layers[name] = {"visible": True, "color": color}
        return True

    def toggle_layer_visibility(self, layer: str, visible: bool) -> None:
        if layer in self.layers:
            self.layers[layer]["visible"] = visible
            self.update()

    def set_layer_color(self, layer: str, color: str) -> None:
        if layer in self.layers:
            self.layers[layer]["color"] = color
            self.update()

    def clear_canvas(self) -> None:
        self.shapes.clear()
        self.undo_stack.clear()
        self.clear_selection()
        self.update()

    def undo_last(self) -> None:
        if self.shapes:
            self.undo_stack.append(self.shapes.pop())
            self.clear_selection()
            self.update()

    def redo_last(self) -> None:
        if self.undo_stack:
            self.shapes.append(self.undo_stack.pop())
            self.update()

    def delete_selected(self) -> None:
        if self.selected_shape and self.selected_shape in self.shapes:
            self.shapes.remove(self.selected_shape)
            self.selected_shape = None
            self.update()

    def duplicate_selected(self) -> None:
        if not self.selected_shape:
            return
        clone = Shape(**asdict(self.selected_shape))
        clone.move_by(15, 15)
        clone.selected = False
        self.shapes.append(clone)
        self.update()

    def zoom_in(self) -> None:
        self.zoom = min(4.0, self.zoom + 0.1)
        self.update()

    def zoom_out(self) -> None:
        self.zoom = max(0.2, self.zoom - 0.1)
        self.update()

    def zoom_reset(self) -> None:
        self.zoom = 1.0
        self.pan_offset = QPointF(0, 0)
        self.update()

    def world_from_screen(self, point: QPointF) -> QPointF:
        return QPointF(
            (point.x() - self.pan_offset.x()) / self.zoom,
            (point.y() - self.pan_offset.y()) / self.zoom,
        )

    def screen_from_world(self, point: QPointF) -> QPointF:
        return QPointF(
            point.x() * self.zoom + self.pan_offset.x(),
            point.y() * self.zoom + self.pan_offset.y(),
        )

    def quantize(self, point: QPointF) -> QPointF:
        if not self.snap_to_grid:
            return point
        x = round(point.x() / self.grid_size) * self.grid_size
        y = round(point.y() / self.grid_size) * self.grid_size
        return QPointF(x, y)

    def paintEvent(self, event) -> None:
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.grid_visible:
            self.draw_grid(painter)

        painter.translate(self.pan_offset)
        painter.scale(self.zoom, self.zoom)

        for shape in self.shapes:
            if not self.layers.get(shape.layer, {}).get("visible", True):
                continue
            self.draw_shape(painter, shape)

        if self.drawing_shape:
            self.draw_shape(painter, self.drawing_shape, preview=True)

    def draw_grid(self, painter: QPainter) -> None:
        pen = QPen(QColor("#2b2b2b"), 1)
        painter.setPen(pen)
        step = self.grid_size * self.zoom
        if step < 8:
            return
        x = self.pan_offset.x() % step
        while x < self.width():
            painter.drawLine(int(x), 0, int(x), self.height())
            x += step
        y = self.pan_offset.y() % step
        while y < self.height():
            painter.drawLine(0, int(y), self.width(), int(y))
            y += step

    def draw_shape(self, painter: QPainter, shape: Shape, preview: bool = False) -> None:
        layer_color = self.layers.get(shape.layer, {}).get("color", "#22c1ff")
        color = QColor("#b5f7ff") if preview else QColor(layer_color)
        if shape.selected:
            color = QColor("#ffd54f")
        pen = QPen(color, self.stroke_width / self.zoom)
        painter.setPen(pen)

        start, end = shape.start_point, shape.end_point
        if shape.shape_type == "line":
            painter.drawLine(start, end)
        elif shape.shape_type == "rectangle":
            painter.drawRect(shape.normalized_rect())
        elif shape.shape_type == "circle":
            painter.drawEllipse(shape.normalized_rect())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MiddleButton:
            self.panning = True
            self.pan_anchor = event.pos()
            return

        if event.button() != Qt.LeftButton:
            return

        world = self.quantize(self.world_from_screen(QPointF(event.pos())))
        if self.current_tool == "select":
            self.selected_shape = self.pick_shape(world)
            self.clear_selection()
            if self.selected_shape:
                self.selected_shape.selected = True
                self.drag_origin = world
                self.emit_properties(self.selected_shape)
            else:
                self.emit_status("No shape selected")
            self.update()
            return

        self.drawing_shape = Shape(self.current_tool, (world.x(), world.y()), (world.x(), world.y()), self.active_layer)
        self.undo_stack.clear()

    def mouseMoveEvent(self, event) -> None:
        if self.panning:
            delta = event.pos() - self.pan_anchor
            self.pan_offset = QPointF(self.pan_offset.x() + delta.x(), self.pan_offset.y() + delta.y())
            self.pan_anchor = event.pos()
            self.update()
            return

        world = self.quantize(self.world_from_screen(QPointF(event.pos())))

        if self.current_tool == "select" and self.selected_shape and self.drag_origin:
            dx = world.x() - self.drag_origin.x()
            dy = world.y() - self.drag_origin.y()
            self.selected_shape.move_by(dx, dy)
            self.drag_origin = world
            self.emit_properties(self.selected_shape)
            self.update()
            return

        if self.drawing_shape:
            self.drawing_shape.end = (world.x(), world.y())
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MiddleButton:
            self.panning = False
            return

        if event.button() != Qt.LeftButton:
            return

        if self.current_tool == "select":
            self.drag_origin = None
            return

        if self.drawing_shape:
            world = self.quantize(self.world_from_screen(QPointF(event.pos())))
            self.drawing_shape.end = (world.x(), world.y())
            self.shapes.append(self.drawing_shape)
            self.emit_properties(self.drawing_shape)
            self.drawing_shape = None
            self.update()

    def wheelEvent(self, event) -> None:
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Delete:
            self.delete_selected()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_C:
            self.duplicate_selected()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Z:
            self.undo_last()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Y:
            self.redo_last()

    def pick_shape(self, world_point: QPointF) -> Optional[Shape]:
        tol = 8 / self.zoom
        for shape in reversed(self.shapes):
            if not self.layers.get(shape.layer, {}).get("visible", True):
                continue
            if shape.contains_point(world_point, tol):
                return shape
        return None

    def clear_selection(self) -> None:
        for shape in self.shapes:
            shape.selected = False
        self.selected_shape = None

    def emit_properties(self, shape: Shape) -> None:
        length = shape.length()
        area = shape.area()
        self.emit_status(
            f"Layer={shape.layer} | Start={shape.start} End={shape.end} | Length={length:.1f} | Area={area:.1f}"
        )

    def save_project(self, filepath: str) -> None:
        payload = {
            "stroke_width": self.stroke_width,
            "grid_visible": self.grid_visible,
            "grid_size": self.grid_size,
            "snap_to_grid": self.snap_to_grid,
            "zoom": self.zoom,
            "pan_offset": (self.pan_offset.x(), self.pan_offset.y()),
            "layers": self.layers,
            "active_layer": self.active_layer,
            "shapes": [asdict(shape) for shape in self.shapes],
        }
        Path(filepath).write_text(json.dumps(payload, indent=2))

    def load_project(self, filepath: str) -> None:
        payload = json.loads(Path(filepath).read_text())
        self.stroke_width = int(payload.get("stroke_width", 2))
        self.grid_visible = bool(payload.get("grid_visible", True))
        self.grid_size = int(payload.get("grid_size", 20))
        self.snap_to_grid = bool(payload.get("snap_to_grid", False))
        self.zoom = float(payload.get("zoom", 1.0))
        px, py = payload.get("pan_offset", (0, 0))
        self.pan_offset = QPointF(px, py)
        self.layers = payload.get("layers", {"Default": {"visible": True, "color": "#22c1ff"}})
        self.active_layer = payload.get("active_layer", "Default")
        self.shapes = [Shape(**item) for item in payload.get("shapes", [])]
        self.clear_selection()
        self.update()


class AutoCADCloneWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AutoCAD Pro Clone App")
        self.resize(1320, 760)

        container = QWidget()
        self.outer_layout = QVBoxLayout()
        container.setLayout(self.outer_layout)

        self.canvas = CADCanvas()
        self.canvas.set_status_callback(self.update_status)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #f1f1f1; padding: 6px;")

        self.outer_layout.addWidget(self.build_toolbar())
        self.outer_layout.addWidget(self.canvas)
        self.outer_layout.addWidget(self.status_label)

        container.setStyleSheet(
            "QWidget { background-color: #252526; color: #f1f1f1; }"
            "QPushButton { background-color: #3a3a3a; border: 1px solid #585858; padding: 6px; }"
            "QPushButton:hover { background-color: #4c4c4c; }"
            "QComboBox, QSpinBox { background-color: #333; border: 1px solid #555; padding: 4px; }"
            "QCheckBox { padding: 4px; }"
        )

        self.setCentralWidget(container)

    def build_toolbar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout()
        bar.setLayout(row)

        self.tool_selector = QComboBox()
        self.tool_selector.addItems(["line", "rectangle", "circle", "select"])
        self.tool_selector.currentTextChanged.connect(self.on_tool_changed)

        self.stroke_selector = QSpinBox()
        self.stroke_selector.setRange(1, 14)
        self.stroke_selector.setValue(2)
        self.stroke_selector.valueChanged.connect(self.canvas.set_stroke_width)

        self.grid_selector = QSpinBox()
        self.grid_selector.setRange(5, 120)
        self.grid_selector.setValue(20)
        self.grid_selector.valueChanged.connect(self.canvas.set_grid_size)

        self.show_grid_chk = QCheckBox("Grid")
        self.show_grid_chk.setChecked(True)
        self.show_grid_chk.toggled.connect(self.canvas.toggle_grid)

        self.snap_chk = QCheckBox("Snap")
        self.snap_chk.toggled.connect(self.canvas.toggle_snap)

        self.layer_selector = QComboBox()
        self.layer_selector.addItems(["Default"])
        self.layer_selector.currentTextChanged.connect(self.canvas.set_active_layer)

        add_layer_btn = QPushButton("+Layer")
        add_layer_btn.clicked.connect(self.add_layer)

        layer_color_btn = QPushButton("Layer Color")
        layer_color_btn.clicked.connect(self.pick_layer_color)

        layer_vis_chk = QCheckBox("Layer Visible")
        layer_vis_chk.setChecked(True)
        layer_vis_chk.toggled.connect(self.toggle_layer_visibility)

        undo_btn = QPushButton("Undo")
        redo_btn = QPushButton("Redo")
        clear_btn = QPushButton("Clear")
        duplicate_btn = QPushButton("Duplicate")
        delete_btn = QPushButton("Delete")

        undo_btn.clicked.connect(self.canvas.undo_last)
        redo_btn.clicked.connect(self.canvas.redo_last)
        clear_btn.clicked.connect(self.canvas.clear_canvas)
        duplicate_btn.clicked.connect(self.canvas.duplicate_selected)
        delete_btn.clicked.connect(self.canvas.delete_selected)

        zoom_in = QPushButton("Zoom+")
        zoom_out = QPushButton("Zoom-")
        zoom_fit = QPushButton("Reset View")

        zoom_in.clicked.connect(self.canvas.zoom_in)
        zoom_out.clicked.connect(self.canvas.zoom_out)
        zoom_fit.clicked.connect(self.canvas.zoom_reset)

        save_btn = QPushButton("Save DWG*")
        load_btn = QPushButton("Load DWG*")
        save_btn.clicked.connect(self.save_project)
        load_btn.clicked.connect(self.load_project)

        row.addWidget(QLabel("Tool"))
        row.addWidget(self.tool_selector)
        row.addWidget(QLabel("Stroke"))
        row.addWidget(self.stroke_selector)
        row.addWidget(QLabel("Grid"))
        row.addWidget(self.grid_selector)
        row.addWidget(self.show_grid_chk)
        row.addWidget(self.snap_chk)
        row.addWidget(QLabel("Layer"))
        row.addWidget(self.layer_selector)
        row.addWidget(add_layer_btn)
        row.addWidget(layer_color_btn)
        row.addWidget(layer_vis_chk)
        row.addWidget(undo_btn)
        row.addWidget(redo_btn)
        row.addWidget(clear_btn)
        row.addWidget(duplicate_btn)
        row.addWidget(delete_btn)
        row.addWidget(zoom_in)
        row.addWidget(zoom_out)
        row.addWidget(zoom_fit)
        row.addWidget(save_btn)
        row.addWidget(load_btn)
        row.addStretch()

        self.layer_visibility_checkbox = layer_vis_chk
        return bar

    def on_tool_changed(self, tool: str) -> None:
        self.canvas.set_tool(tool)
        self.update_status(f"Tool: {tool}")

    def update_status(self, text: str) -> None:
        self.status_label.setText(text)

    def add_layer(self) -> None:
        name, ok = QInputDialog.getText(self, "New Layer", "Layer name:")
        if not ok:
            return
        if not self.canvas.add_layer(name, "#22c1ff"):
            QMessageBox.warning(self, "Layer", "Layer already exists or invalid name.")
            return
        self.layer_selector.addItem(name)
        self.layer_selector.setCurrentText(name)

    def pick_layer_color(self) -> None:
        layer = self.layer_selector.currentText()
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            self.canvas.set_layer_color(layer, color.name())

    def toggle_layer_visibility(self, visible: bool) -> None:
        layer = self.layer_selector.currentText()
        self.canvas.toggle_layer_visibility(layer, visible)

    def save_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "autocad_clone_project.json", "JSON (*.json)")
        if not path:
            return
        self.canvas.save_project(path)
        self.update_status(f"Saved: {path}")

    def load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "JSON (*.json)")
        if not path:
            return
        self.canvas.load_project(path)

        self.stroke_selector.setValue(self.canvas.stroke_width)
        self.grid_selector.setValue(self.canvas.grid_size)
        self.show_grid_chk.setChecked(self.canvas.grid_visible)
        self.snap_chk.setChecked(self.canvas.snap_to_grid)

        self.layer_selector.blockSignals(True)
        self.layer_selector.clear()
        self.layer_selector.addItems(list(self.canvas.layers.keys()))
        self.layer_selector.setCurrentText(self.canvas.active_layer)
        self.layer_selector.blockSignals(False)

        visible = bool(self.canvas.layers.get(self.canvas.active_layer, {}).get("visible", True))
        self.layer_visibility_checkbox.setChecked(visible)
        self.update_status(f"Loaded: {path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AutoCADCloneWindow()
    window.show()
    sys.exit(app.exec_())
