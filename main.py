import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QPoint, QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QKeySequence, QPainter, QPen
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSpinBox,
    QSplitter,
    QToolBar,
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
        return QPointF(*self.start)

    @property
    def end_point(self) -> QPointF:
        return QPointF(*self.end)

    def normalized_rect(self) -> QRectF:
        return QRectF(self.start_point, self.end_point).normalized()

    def move_by(self, dx: float, dy: float) -> None:
        self.start = (self.start[0] + dx, self.start[1] + dy)
        self.end = (self.end[0] + dx, self.end[1] + dy)

    def length(self) -> float:
        return math.hypot(self.end[0] - self.start[0], self.end[1] - self.start[1])

    def area(self) -> float:
        rect = self.normalized_rect()
        if self.shape_type == "rectangle":
            return rect.width() * rect.height()
        if self.shape_type == "circle":
            radius = min(rect.width(), rect.height()) / 2
            return math.pi * radius * radius
        return 0.0

    def contains_point(self, point: QPointF, tolerance: float = 8.0) -> bool:
        if self.shape_type == "line":
            return self._distance_to_line(point) <= tolerance
        return self.normalized_rect().adjusted(-tolerance, -tolerance, tolerance, tolerance).contains(point)

    def _distance_to_line(self, point: QPointF) -> float:
        x1, y1 = self.start
        x2, y2 = self.end
        px, py = point.x(), point.y()
        line_len_sq = (x2 - x1) ** 2 + (y2 - y1) ** 2
        if line_len_sq == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0.0, min(1.0, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / line_len_sq))
        cx = x1 + t * (x2 - x1)
        cy = y1 + t * (y2 - y1)
        return math.hypot(px - cx, py - cy)


class CADCanvas(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(1024, 720)
        self.setMouseTracking(True)

        self.shapes: List[Shape] = []
        self.undo_stack: List[Shape] = []
        self.layers: Dict[str, Dict[str, object]] = {
            "Default": {"visible": True, "color": "#22c1ff"}
        }
        self.active_layer = "Default"

        self.current_tool = "line"
        self.stroke_width = 2
        self.grid_visible = True
        self.grid_size = 20
        self.snap_to_grid = False

        self.zoom = 1.0
        self.pan_offset = QPointF(0, 0)
        self.panning = False
        self.pan_anchor = QPoint()

        self.drawing_shape: Optional[Shape] = None
        self.selected_shape: Optional[Shape] = None
        self.drag_origin: Optional[QPointF] = None

        self.status_callback = None
        self.modified_callback = None
        self.selection_callback = None

    def set_callbacks(self, status_cb=None, modified_cb=None, selection_cb=None) -> None:
        self.status_callback = status_cb
        self.modified_callback = modified_cb
        self.selection_callback = selection_cb

    def emit_status(self, text: str) -> None:
        if self.status_callback:
            self.status_callback(text)

    def emit_modified(self) -> None:
        if self.modified_callback:
            self.modified_callback()

    def emit_selection(self, shape: Optional[Shape]) -> None:
        if self.selection_callback:
            self.selection_callback(shape)

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
            self.emit_status(f"Layer: {layer}")

    def add_layer(self, name: str, color: str = "#22c1ff") -> bool:
        if not name.strip() or name in self.layers:
            return False
        self.layers[name] = {"visible": True, "color": color}
        return True

    def remove_layer(self, name: str) -> bool:
        if name == "Default" or name not in self.layers:
            return False
        for shape in self.shapes:
            if shape.layer == name:
                shape.layer = "Default"
        self.layers.pop(name)
        self.active_layer = "Default"
        self.emit_modified()
        self.update()
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
        self.emit_modified()
        self.update()

    def undo_last(self) -> None:
        if self.shapes:
            self.undo_stack.append(self.shapes.pop())
            self.clear_selection()
            self.emit_modified()
            self.update()

    def redo_last(self) -> None:
        if self.undo_stack:
            self.shapes.append(self.undo_stack.pop())
            self.emit_modified()
            self.update()

    def delete_selected(self) -> None:
        if self.selected_shape and self.selected_shape in self.shapes:
            self.shapes.remove(self.selected_shape)
            self.clear_selection()
            self.emit_modified()
            self.update()

    def duplicate_selected(self) -> None:
        if not self.selected_shape:
            return
        clone = Shape(**asdict(self.selected_shape))
        clone.selected = False
        clone.move_by(15, 15)
        self.shapes.append(clone)
        self.emit_modified()
        self.update()

    def zoom_in(self) -> None:
        self.zoom = min(5.0, self.zoom + 0.1)
        self.update()

    def zoom_out(self) -> None:
        self.zoom = max(0.2, self.zoom - 0.1)
        self.update()

    def zoom_reset(self) -> None:
        self.zoom = 1.0
        self.pan_offset = QPointF(0, 0)
        self.update()

    def world_from_screen(self, point: QPointF) -> QPointF:
        return QPointF((point.x() - self.pan_offset.x()) / self.zoom, (point.y() - self.pan_offset.y()) / self.zoom)

    def quantize(self, point: QPointF) -> QPointF:
        if not self.snap_to_grid:
            return point
        return QPointF(round(point.x() / self.grid_size) * self.grid_size, round(point.y() / self.grid_size) * self.grid_size)

    def paintEvent(self, event) -> None:
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.grid_visible:
            self._draw_grid(painter)

        painter.translate(self.pan_offset)
        painter.scale(self.zoom, self.zoom)

        for shape in self.shapes:
            if self.layers.get(shape.layer, {}).get("visible", True):
                self._draw_shape(painter, shape)

        if self.drawing_shape:
            self._draw_shape(painter, self.drawing_shape, preview=True)

    def _draw_grid(self, painter: QPainter) -> None:
        step = self.grid_size * self.zoom
        if step < 8:
            return
        painter.setPen(QPen(QColor("#2d2d2d"), 1))
        x = self.pan_offset.x() % step
        while x < self.width():
            painter.drawLine(int(x), 0, int(x), self.height())
            x += step
        y = self.pan_offset.y() % step
        while y < self.height():
            painter.drawLine(0, int(y), self.width(), int(y))
            y += step

    def _draw_shape(self, painter: QPainter, shape: Shape, preview: bool = False) -> None:
        color = QColor(self.layers.get(shape.layer, {}).get("color", "#22c1ff"))
        if preview:
            color = QColor("#7be6ff")
        if shape.selected:
            color = QColor("#ffd54f")
        painter.setPen(QPen(color, self.stroke_width / self.zoom))

        if shape.shape_type == "line":
            painter.drawLine(shape.start_point, shape.end_point)
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
            self.selected_shape = self._pick_shape(world)
            self.clear_selection()
            if self.selected_shape:
                self.selected_shape.selected = True
                self.drag_origin = world
                self._emit_shape_properties(self.selected_shape)
                self.emit_selection(self.selected_shape)
            else:
                self.emit_status("No object selected")
                self.emit_selection(None)
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
            self._emit_shape_properties(self.selected_shape)
            self.emit_selection(self.selected_shape)
            self.emit_modified()
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
            self._emit_shape_properties(self.drawing_shape)
            self.emit_selection(self.drawing_shape)
            self.drawing_shape = None
            self.emit_modified()
            self.update()

    def wheelEvent(self, event) -> None:
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def _pick_shape(self, world: QPointF) -> Optional[Shape]:
        tolerance = 8 / self.zoom
        for shape in reversed(self.shapes):
            if self.layers.get(shape.layer, {}).get("visible", True) and shape.contains_point(world, tolerance):
                return shape
        return None

    def clear_selection(self) -> None:
        for shape in self.shapes:
            shape.selected = False
        self.selected_shape = None

    def _emit_shape_properties(self, shape: Shape) -> None:
        self.emit_status(
            f"{shape.shape_type.upper()} | Layer={shape.layer} | Start={shape.start} End={shape.end} | Length={shape.length():.2f} | Area={shape.area():.2f}"
        )

    def export_png(self, path: str) -> None:
        pixmap = self.grab()
        pixmap.save(path, "PNG")

    def to_payload(self) -> dict:
        return {
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

    def from_payload(self, data: dict) -> None:
        self.stroke_width = int(data.get("stroke_width", 2))
        self.grid_visible = bool(data.get("grid_visible", True))
        self.grid_size = int(data.get("grid_size", 20))
        self.snap_to_grid = bool(data.get("snap_to_grid", False))
        self.zoom = float(data.get("zoom", 1.0))
        px, py = data.get("pan_offset", (0, 0))
        self.pan_offset = QPointF(px, py)
        self.layers = data.get("layers", {"Default": {"visible": True, "color": "#22c1ff"}})
        if "Default" not in self.layers:
            self.layers["Default"] = {"visible": True, "color": "#22c1ff"}
        self.active_layer = data.get("active_layer", "Default")
        if self.active_layer not in self.layers:
            self.active_layer = "Default"
        self.shapes = [Shape(**item) for item in data.get("shapes", [])]
        self.clear_selection()
        self.update()


class PropertiesPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QFormLayout(self)
        self.type_label = QLabel("-")
        self.layer_label = QLabel("-")
        self.start_label = QLabel("-")
        self.end_label = QLabel("-")
        self.length_label = QLabel("-")
        self.area_label = QLabel("-")

        layout.addRow("Type", self.type_label)
        layout.addRow("Layer", self.layer_label)
        layout.addRow("Start", self.start_label)
        layout.addRow("End", self.end_label)
        layout.addRow("Length", self.length_label)
        layout.addRow("Area", self.area_label)

    def set_shape(self, shape: Optional[Shape]) -> None:
        if not shape:
            self.type_label.setText("-")
            self.layer_label.setText("-")
            self.start_label.setText("-")
            self.end_label.setText("-")
            self.length_label.setText("-")
            self.area_label.setText("-")
            return

        self.type_label.setText(shape.shape_type)
        self.layer_label.setText(shape.layer)
        self.start_label.setText(f"{shape.start}")
        self.end_label.setText(f"{shape.end}")
        self.length_label.setText(f"{shape.length():.2f}")
        self.area_label.setText(f"{shape.area():.2f}")


class AutoCADCloneWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AutoCAD Pro Clone Desktop")
        self.resize(1480, 900)

        self.current_file: Optional[str] = None
        self.is_dirty = False

        self.canvas = CADCanvas()
        self.canvas.set_callbacks(status_cb=self.set_status, modified_cb=self.mark_dirty, selection_cb=self.on_selection_changed)

        self.setCentralWidget(self._build_central_layout())
        self.addToolBar(self._build_toolbar())
        self._build_menus()
        self._setup_shortcuts()
        self.statusBar().showMessage("Ready")
        self.refresh_layer_list()

    def _build_central_layout(self) -> QWidget:
        root = QWidget()
        layout = QHBoxLayout(root)

        splitter = QSplitter()
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self.canvas)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 1100])

        layout.addWidget(splitter)
        return root

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setMinimumWidth(280)
        side_layout = QVBoxLayout(sidebar)

        self.layer_list = QListWidget()
        self.layer_list.itemClicked.connect(self.on_layer_clicked)

        add_layer_btn = QPushButton("Add Layer")
        remove_layer_btn = QPushButton("Remove Layer")
        toggle_visibility_btn = QPushButton("Toggle Visibility")
        color_btn = QPushButton("Layer Color")

        add_layer_btn.clicked.connect(self.add_layer)
        remove_layer_btn.clicked.connect(self.remove_layer)
        toggle_visibility_btn.clicked.connect(self.toggle_selected_layer_visibility)
        color_btn.clicked.connect(self.pick_selected_layer_color)

        side_layout.addWidget(QLabel("Layers"))
        side_layout.addWidget(self.layer_list)

        side_layout.addWidget(add_layer_btn)
        side_layout.addWidget(remove_layer_btn)
        side_layout.addWidget(toggle_visibility_btn)
        side_layout.addWidget(color_btn)

        side_layout.addSpacing(12)
        side_layout.addWidget(QLabel("Selected Object Properties"))
        self.properties_panel = PropertiesPanel()
        side_layout.addWidget(self.properties_panel)
        side_layout.addStretch()

        return sidebar

    def _build_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)

        self.tool_selector = QComboBox()
        self.tool_selector.addItems(["line", "rectangle", "circle", "select"])
        self.tool_selector.currentTextChanged.connect(self.canvas.set_tool)

        self.stroke_selector = QSpinBox()
        self.stroke_selector.setRange(1, 20)
        self.stroke_selector.setValue(2)
        self.stroke_selector.valueChanged.connect(self.canvas.set_stroke_width)

        self.grid_selector = QSpinBox()
        self.grid_selector.setRange(5, 120)
        self.grid_selector.setValue(20)
        self.grid_selector.valueChanged.connect(self.canvas.set_grid_size)

        self.grid_check = QCheckBox("Grid")
        self.grid_check.setChecked(True)
        self.grid_check.toggled.connect(self.canvas.toggle_grid)

        self.snap_check = QCheckBox("Snap")
        self.snap_check.toggled.connect(self.canvas.toggle_snap)

        toolbar.addWidget(QLabel("Tool"))
        toolbar.addWidget(self.tool_selector)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Stroke"))
        toolbar.addWidget(self.stroke_selector)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Grid"))
        toolbar.addWidget(self.grid_selector)
        toolbar.addWidget(self.grid_check)
        toolbar.addWidget(self.snap_check)

        zoom_in = QPushButton("Zoom+")
        zoom_out = QPushButton("Zoom-")
        zoom_reset = QPushButton("Reset View")

        zoom_in.clicked.connect(self.canvas.zoom_in)
        zoom_out.clicked.connect(self.canvas.zoom_out)
        zoom_reset.clicked.connect(self.canvas.zoom_reset)

        toolbar.addSeparator()
        toolbar.addWidget(zoom_in)
        toolbar.addWidget(zoom_out)
        toolbar.addWidget(zoom_reset)

        return toolbar

    def _build_menus(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("File")
        edit_menu = menu.addMenu("Edit")
        view_menu = menu.addMenu("View")

        self.new_action = QAction("New", self)
        self.open_action = QAction("Open", self)
        self.save_action = QAction("Save", self)
        self.save_as_action = QAction("Save As", self)
        self.export_action = QAction("Export PNG", self)
        self.exit_action = QAction("Exit", self)

        self.new_action.triggered.connect(self.new_file)
        self.open_action.triggered.connect(self.open_file)
        self.save_action.triggered.connect(self.save_file)
        self.save_as_action.triggered.connect(self.save_file_as)
        self.export_action.triggered.connect(self.export_png)
        self.exit_action.triggered.connect(self.close)

        file_menu.addActions([self.new_action, self.open_action, self.save_action, self.save_as_action, self.export_action])
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        undo_action = QAction("Undo", self)
        redo_action = QAction("Redo", self)
        duplicate_action = QAction("Duplicate", self)
        delete_action = QAction("Delete", self)
        clear_action = QAction("Clear Canvas", self)

        undo_action.triggered.connect(self.canvas.undo_last)
        redo_action.triggered.connect(self.canvas.redo_last)
        duplicate_action.triggered.connect(self.canvas.duplicate_selected)
        delete_action.triggered.connect(self.canvas.delete_selected)
        clear_action.triggered.connect(self.canvas.clear_canvas)

        edit_menu.addActions([undo_action, redo_action, duplicate_action, delete_action, clear_action])

        toggle_grid_action = QAction("Toggle Grid", self)
        toggle_grid_action.triggered.connect(lambda: self.grid_check.setChecked(not self.grid_check.isChecked()))
        view_menu.addAction(toggle_grid_action)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_file)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.open_file)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_file)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.save_file_as)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.canvas.undo_last)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.canvas.redo_last)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self.canvas.duplicate_selected)
        QShortcut(QKeySequence("Delete"), self, activated=self.canvas.delete_selected)

    def set_status(self, msg: str) -> None:
        self.statusBar().showMessage(msg, 5000)

    def mark_dirty(self) -> None:
        self.is_dirty = True
        self._update_window_title()

    def _update_window_title(self) -> None:
        file_name = Path(self.current_file).name if self.current_file else "Untitled"
        dirty_marker = " *" if self.is_dirty else ""
        self.setWindowTitle(f"AutoCAD Pro Clone Desktop - {file_name}{dirty_marker}")

    def confirm_discard_changes(self) -> bool:
        if not self.is_dirty:
            return True
        choice = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Continue without saving?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return choice == QMessageBox.Yes

    def new_file(self) -> None:
        if not self.confirm_discard_changes():
            return
        self.canvas = CADCanvas()
        self.canvas.set_callbacks(status_cb=self.set_status, modified_cb=self.mark_dirty, selection_cb=self.on_selection_changed)
        self.setCentralWidget(self._build_central_layout())
        self.current_file = None
        self.is_dirty = False
        self.refresh_layer_list()
        self._update_window_title()

    def open_file(self) -> None:
        if not self.confirm_discard_changes():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "JSON (*.json)")
        if not path:
            return
        data = json.loads(Path(path).read_text())
        self.canvas.from_payload(data)
        self.stroke_selector.setValue(self.canvas.stroke_width)
        self.grid_selector.setValue(self.canvas.grid_size)
        self.grid_check.setChecked(self.canvas.grid_visible)
        self.snap_check.setChecked(self.canvas.snap_to_grid)
        self.current_file = path
        self.is_dirty = False
        self.refresh_layer_list()
        self._update_window_title()
        self.set_status(f"Opened {path}")

    def save_file(self) -> None:
        if self.current_file:
            Path(self.current_file).write_text(json.dumps(self.canvas.to_payload(), indent=2))
            self.is_dirty = False
            self._update_window_title()
            self.set_status(f"Saved {self.current_file}")
            return
        self.save_file_as()

    def save_file_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "drawing_project.json", "JSON (*.json)")
        if not path:
            return
        self.current_file = path
        self.save_file()

    def export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "drawing.png", "PNG (*.png)")
        if not path:
            return
        self.canvas.export_png(path)
        self.set_status(f"Exported {path}")

    def closeEvent(self, event) -> None:
        if self.confirm_discard_changes():
            event.accept()
        else:
            event.ignore()

    def refresh_layer_list(self) -> None:
        self.layer_list.clear()
        for name, meta in self.canvas.layers.items():
            prefix = "👁" if meta.get("visible", True) else "🚫"
            item = QListWidgetItem(f"{prefix} {name}")
            item.setData(Qt.UserRole, name)
            if name == self.canvas.active_layer:
                item.setSelected(True)
            self.layer_list.addItem(item)

    def on_layer_clicked(self, item: QListWidgetItem) -> None:
        layer_name = item.data(Qt.UserRole)
        self.canvas.set_active_layer(layer_name)
        self.refresh_layer_list()

    def add_layer(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Layer", "Layer name")
        if not ok:
            return
        if not self.canvas.add_layer(name, "#22c1ff"):
            QMessageBox.warning(self, "Layer", "Layer name is invalid or already exists.")
            return
        self.canvas.set_active_layer(name)
        self.mark_dirty()
        self.refresh_layer_list()

    def remove_layer(self) -> None:
        item = self.layer_list.currentItem()
        if not item:
            return
        layer_name = item.data(Qt.UserRole)
        if not self.canvas.remove_layer(layer_name):
            QMessageBox.information(self, "Layer", "Default layer cannot be removed.")
            return
        self.mark_dirty()
        self.refresh_layer_list()

    def toggle_selected_layer_visibility(self) -> None:
        item = self.layer_list.currentItem()
        if not item:
            return
        layer = item.data(Qt.UserRole)
        current = bool(self.canvas.layers[layer].get("visible", True))
        self.canvas.toggle_layer_visibility(layer, not current)
        self.mark_dirty()
        self.refresh_layer_list()

    def pick_selected_layer_color(self) -> None:
        item = self.layer_list.currentItem()
        if not item:
            return
        layer = item.data(Qt.UserRole)
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            self.canvas.set_layer_color(layer, color.name())
            self.mark_dirty()

    def on_selection_changed(self, shape: Optional[Shape]) -> None:
        self.properties_panel.set_shape(shape)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = AutoCADCloneWindow()
    window.show()
    sys.exit(app.exec_())
