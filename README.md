# AutoCAD Pro Clone Desktop App (PyQt5)

A complete desktop CAD-style application built with PyQt5.

## What this app now includes
- Full desktop shell with **menu bar**, **toolbar**, **sidebar**, and **status bar**.
- Drafting tools: **line**, **rectangle**, **circle**, and **select** mode.
- Layer workflow:
  - Add/remove layers
  - Active layer switching
  - Layer color changes
  - Layer visibility toggling
- Precision controls:
  - Configurable grid
  - Grid show/hide
  - Snap to grid
- Navigation:
  - Mouse-wheel zoom
  - Zoom in/out/reset buttons
  - Middle-mouse pan
- Editing:
  - Select/move objects
  - Duplicate and delete selected objects
  - Undo/redo
  - Clear canvas
- File operations:
  - New/Open/Save/Save As project files (`.json`)
  - Export canvas to PNG
  - Unsaved changes warning on close/new/open
- Object inspector panel with type, layer, points, length, and area.

## Run
```bash
pip install -r requirements.txt
python main.py
```

## Keyboard shortcuts
- `Ctrl+N` New project
- `Ctrl+O` Open project
- `Ctrl+S` Save
- `Ctrl+Shift+S` Save As
- `Ctrl+Z` Undo
- `Ctrl+Y` Redo
- `Ctrl+D` Duplicate selected shape
- `Delete` Delete selected shape

## Notes
- Project files are stored as JSON for portability.
- This is a robust desktop CAD clone for learning/prototyping, not Autodesk AutoCAD itself.
