# streamlit_3d_viewer

A Streamlit component for processing and viewing 3D scans (OBJ + JPG/PNG
texture) with three.js, including conversion to a leaner **glTF/GLB**
format (optionally with **Draco** geometry compression).

## Features

- Load an `.obj` model + texture (`.jpg` or `.png`) and convert it to a
  binary `.glb`.
- Optional Draco geometry compression (via the Node.js CLI tool
  `gltf-transform`).
- Optional mesh decimation (simplify to a target triangle count).
- A detailed conversion report: original file size, GLB size before/after
  Draco, size reduction %, vertex/triangle count before and after
  decimation.
- 3D viewing with three.js (`GLTFLoader` + `DRACOLoader`).
- Zoom with the mouse wheel, rotate/pan by dragging (`OrbitControls`).
- Sliders for **elevation** and **view angle** that drive the camera
  directly (independent of mouse dragging).
- "Full scene" button (fit-to-view) and "Zoom to selected points" button
  (frames the camera so all currently selected points are visible).
- A single **opacity** slider, live in the viewer next to the scan.
- Click on the model to add a point (3D position + UV); a red marker is
  shown at that spot. Points are returned to Python as a list.

## Installation

```bash
pip install -r requirements.txt
```

For **Draco compression**, install Node.js and the `@gltf-transform/cli`
tool globally:

```bash
npm install -g @gltf-transform/cli
```

If this tool isn't available, conversion still works — Draco compression
is simply skipped (the resulting `.glb` is still much smaller than the
original `.obj` + `.mtl` + texture, since it's binary and the texture is
compressed).

For **mesh decimation** (`target_faces`), install:

```bash
pip install fast-simplification
```

The frontend (three.js, GLTFLoader, DRACOLoader, OrbitControls) is loaded
from a CDN (`unpkg.com`, `gstatic.com`), so the browser running the
Streamlit app needs internet access.

## Project layout

```
streamlit_3d_viewer/
├── __init__.py        # show_3d_viewer() – component's Python API
├── converter.py        # obj_to_glb(), compress_with_draco(), convert(), ConversionReport
└── frontend/
    └── index.html       # three.js viewer (plain JS, no npm build)
example_app.py           # example app
requirements.txt
```

## Usage

```python
from streamlit_3d_viewer import show_3d_viewer
from streamlit_3d_viewer.converter import convert

# 1) convert
report = convert(
    "scan.obj", "scan.glb", texture_path="scan.jpg", use_draco=True
)
print(report.total_reduction_pct, report.draco_reduction_pct)

# 2) display
points = show_3d_viewer(
    report.output_path,
    opacity=0.9,
    background_color="#1e1e1e",
    height=680,
)

st.write(points)
```

Full example in `example_app.py`:

```bash
streamlit run example_app.py
```

## Notes / limitations

- The OBJ file must contain UV coordinates, otherwise the texture cannot
  be mapped.
- The material is exported as non-metallic/diffuse (`metallicFactor=0`) —
  otherwise a scan would look dark/black without an environment map.
- If the model is still slow after Draco compression, try the
  `target_faces` parameter in `convert()` (mesh decimation, requires
  `pip install fast-simplification`) and/or a lower `max_texture_size`.
- Opacity is configured in exactly one place: the slider inside the
  viewer component. There is intentionally no separate Streamlit-level
  opacity control, to avoid two out-of-sync settings.
