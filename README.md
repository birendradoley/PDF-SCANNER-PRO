# AutoCAD Pro Clone App (PyQt5)

A desktop CAD-style app inspired by premium AutoCAD workflows.

## Included Pro-Style Features
- Draw **lines**, **rectangles**, and **circles**.
- **Selection & transform**: select, drag, duplicate, delete.
- **Layer system**: create layers, switch active layer, set layer color, toggle layer visibility.
- **Precision tools**: snap-to-grid, adjustable grid size, optional grid overlay.
- **Navigation**: mouse-wheel zoom, zoom in/out buttons, reset view, middle-mouse pan.
- **Editing history**: undo/redo.
- **Properties/status feedback**: live start/end points, length, area, active layer.
- **Project persistence**: save/load complete drawings to JSON project files (`*.json`) through DWG-labeled UI actions.

## Run
```bash
pip install -r requirements.txt
python main.py
```

## Controls
- Tool dropdown: `line`, `rectangle`, `circle`, `select`.
- Select mode:
  - Click shape to select.
  - Drag to move.
  - `Delete` key to remove selected shape.
  - `Ctrl+C` to duplicate selected shape.
- History shortcuts:
  - `Ctrl+Z` undo
  - `Ctrl+Y` redo
- Navigation:
  - Mouse wheel to zoom
  - Middle mouse button to pan

## Important Note
This project emulates many premium CAD-style interactions but is still not a full AutoCAD replacement.
