# streamlit_3d_viewer

A Streamlit component for processing and viewing 3D scans (OBJ + MTL +
JPG/PNG texture) with three.js, including conversion to a leaner
**glTF/GLB** format (optionally with **Draco** geometry compression).

Every visual aspect of the viewer — camera angle, background, opacity,
brightness, cutting plane, checkboxes, pre-placed points — can be driven
entirely from Python, and the whole control UI can be hidden to embed a
clean, read-only 3D view.

## Features

**Conversion**
- Load an `.obj` model (+ `.mtl` and/or explicit texture) and convert it
  to **GLB** (single binary file) or **glTF** (JSON + separate asset
  files).
- Auto-detects the texture referenced by an OBJ's `.mtl` (`map_Kd`) if no
  explicit texture is given.
- Optional Draco geometry compression (via the Node.js CLI tool
  `gltf-transform`).
- Optional mesh decimation (simplify to a target triangle count).
- A detailed conversion report: original file size, output size
  before/after Draco, size reduction %, vertex/triangle count before and
  after decimation.
- **Direct OBJ + JPG/PNG rendering**, no GLB conversion required: pass
  `obj_path`/`texture_path` to `show_3d_viewer` to preview a raw scan
  as-is. Useful for quick looks or small files; for large scans, convert
  to GLB first (smaller, faster to load).
- **Batch directory converter page**: point it at a folder, pick which
  OBJ/MTL/texture files belong together, set conversion parameters,
  preview the result, and only then save it — with an optional cleanup
  step to delete the original source files.

**Viewing**
- 3D viewing with three.js (`GLTFLoader` + `DRACOLoader`).
- Zoom with the mouse wheel, rotate/pan by dragging (`OrbitControls`) —
  always available, even in read-only mode (see below).
- Sliders for **elevation** and **view angle** that drive the camera
  directly (independent of mouse dragging), plus **opacity**,
  **brightness**, and **point size** sliders.
- "Full scene" button (fit-to-view) and "Zoom to selected points" button
  (frames the camera so all currently selected points are visible).
- Click on the model to add a point (3D position + UV); a red marker is
  shown at that spot. Points are returned to Python as a list.
- Control panel has its own solid dark background with light text, so
  the legend stays readable regardless of Streamlit's light/dark theme
  or page background color.

**Everything configurable from Python**
- Every slider/checkbox/toggle in the viewer has a matching
  `show_3d_viewer()` parameter to set its **initial** value — background
  color, opacity, brightness, point size, initial camera elevation/
  azimuth, cutting-plane on/off + position/normal/gizmo mode, "show both
  halves", "show cross-section", and points pre-placed on the model. See
  [Initial state from Python](#initial-state-from-python) below.
- **`show_controls=False`**: hide the entire UI (all sliders, buttons,
  checkboxes, text hints, and the draggable cutting-plane handle) and
  display *only* the bare 3D scan — for embedding a clean, read-only
  viewer. Mouse orbit/zoom/pan and Shift+Click to place a point keep
  working, and a cutting plane configured from Python keeps clipping the
  geometry, just without a visible handle. See
  [Read-only / embed mode](#read-only--embed-mode) below.
- **Round-trips back to Python**: `show_3d_viewer()` returns a live
  `settings` snapshot (camera angle, opacity, brightness, point size,
  cutting-plane state) alongside `points` and `clip_plane`, so you can
  read back exactly what's on screen and pass it straight into the next
  call to reproduce it. See
  [Reproducing the current view](#reproducing-the-current-view) below.

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
is simply skipped (the resulting file is still much smaller than the
original OBJ + MTL + texture, since it's binary and the texture is
compressed).

For **mesh decimation** (`target_faces`), install:

```bash
pip install fast-simplification
```

The frontend (three.js, GLTFLoader, DRACOLoader, OBJLoader, OrbitControls,
and the Draco WASM decoder) is **vendored locally** in
`streamlit_3d_viewer/frontend/vendor/` — no CDN and no internet access is
required at runtime, either for the Python side or for the browser
displaying the viewer. (Earlier versions loaded these from `unpkg.com`
and `gstatic.com`; see `vendor/three/LICENSE` for attribution/licensing
of the bundled files.)

## Project layout

```
streamlit_3d_viewer/
├── __init__.py        # show_3d_viewer() – component's Python API
├── converter.py         # convert(), obj_to_model(), compress_with_draco(),
│                         #   list_scan_files(), guess_texture_for_obj(),
│                         #   finalize_output(), delete_files(), ConversionReport
└── frontend/
    ├── index.html          # three.js viewer (plain JS, no npm build)
    └── vendor/three/       # vendored three.js + loaders + Draco decoder
                            #   (fully offline, no CDN needed)
example_app.py                  # single-file upload demo: OBJ -> GLB conversion ("Home" page)
example_obj_texture_demo.py     # direct OBJ+JPG rendering demo (no conversion step)
demo_assets/
└── obj_texture_demo/            # bundled sample OBJ+JPG for the demo above
pages/
└── 1_Batch_Directory_Converter.py   # folder-based batch converter page
requirements.txt
```

## Usage

### Single-file demo

```bash
streamlit run example_app.py
```

Uploads an OBJ + texture, converts, previews, shows selected points.

### Direct OBJ + JPG demo (no conversion)

```bash
streamlit run example_obj_texture_demo.py
```

Renders a raw `.obj` + `.jpg` straight in the viewer, skipping the GLB
conversion step entirely. Ships with a bundled procedurally-generated
sample (a textured sphere in `demo_assets/obj_texture_demo/`) so it runs
out of the box; uncheck "Use bundled sample" in the sidebar to upload
your own OBJ/texture instead.

### Batch directory converter

The same command (`streamlit run example_app.py`) also gives you the
"Batch Directory Converter" page in the sidebar navigation (Streamlit
multi-page app, driven by the `pages/` folder). Workflow:

1. Enter a folder path and click **Scan directory** — it lists the
   `.obj`, `.mtl`, and `.jpg`/`.png` files found there.
2. Pick the OBJ file; the texture is auto-detected from its `.mtl`
   (or pick one manually / choose "None").
3. Set conversion parameters: output file name, format (`glb`/`gltf`),
   Draco on/off, mesh simplification target, max texture size, and
   output location (defaults to the same folder as the source files).
4. Click **Convert & preview** — the result is written to a temporary
   location first and shown in the 3D viewer with a full conversion
   report.
5. If you're happy with it, click **Looks good — save here** to move
   the result to its final location.
6. Optionally select the original source files and delete them (an
   explicit confirmation checkbox is required).

### Library usage

```python
from streamlit_3d_viewer import show_3d_viewer
from streamlit_3d_viewer.converter import convert

# 1) convert (texture auto-detected from scan.obj's MTL if omitted)
report = convert("scan.obj", "scan_out", output_format="glb", use_draco=True)
print(report.total_reduction_pct, report.draco_reduction_pct)

# 2) display (GLB — recommended for large scans)
points = show_3d_viewer(report.output_path, opacity=0.9, marker_size=1.2, height=680)

# ...or, skip conversion entirely and render the raw OBJ + texture directly:
points = show_3d_viewer(obj_path="scan.obj", texture_path="scan.jpg")
```

`enable_clipping` and `show_cross_section` are optional. If you omit them,
the in-component checkboxes keep their current frontend state across reruns.
If you pass `False` explicitly, Python forces the corresponding feature off.

### Initial state from Python

Every control in the viewer accepts an initial value as a
`show_3d_viewer()` keyword argument:

| Parameter | Controls | Default |
|---|---|---|
| `background_color` | Scene background color (hex) | `"#1e1e1e"` |
| `opacity` | Opacity slider | `1.0` |
| `brightness` | Brightness slider (rendering exposure) | `1.3` |
| `marker_size` | Point-size slider | `1.0` |
| `camera_elevation` | Elevation slider (°, 1–179) | `None` = auto fit-to-model |
| `camera_azimuth` | View-angle slider (°, 0–360) | `None` = auto fit-to-model |
| `enable_clipping` | "Cutting plane" checkbox | `None` = frontend keeps its state |
| `clip_plane_position` | `[x, y, z]` of the cutting plane | `None` = model center |
| `clip_plane_normal` | `[nx, ny, nz]` of the cutting plane | `None` = `[0, 1, 0]` (horizontal) |
| `clip_gizmo_mode` | Gizmo "Move" / "Rotate" toggle | `None` = `"translate"` |
| `show_both_clip_halves` | "Show both halves" checkbox | `None` = frontend keeps its state |
| `show_cross_section` | "Show cross-section" checkbox | `False` |
| `unit_scale` | Meters per one model unit (for the m² area table) | `1.0` |
| `initial_points` | Points pre-placed on the model | `None` |
| `show_controls` | Show/hide the entire UI (see below) | `True` |

```python
points = show_3d_viewer(
    "scan.glb",
    background_color="#0b0f1a",
    opacity=0.9,
    brightness=1.1,
    marker_size=1.2,
    camera_elevation=55,
    camera_azimuth=210,
    enable_clipping=True,
    clip_plane_position=[0, 0.4, 0],
    clip_plane_normal=[0, 1, 0],
    clip_gizmo_mode="rotate",
    show_both_clip_halves=True,
    show_cross_section=True,
    unit_scale=0.001,   # model authored in millimeters
    initial_points=[{"point": [0.1, 0.2, 0.0], "uv": None}],
)
```

`camera_elevation`, `camera_azimuth`, `clip_plane_position`,
`clip_plane_normal`, `clip_gizmo_mode`, and `initial_points` are all
**re-applied only when the value you pass actually changes** on a later
Streamlit rerun — so setting them once doesn't fight the user's mouse
(orbiting the camera, dragging the cutting-plane gizmo, moving a marker),
but moving a Streamlit slider bound to one of them does snap the viewer
to the new value.

### Read-only / embed mode

Pass `show_controls=False` to hide every on-screen control — sliders,
buttons, checkboxes, the mesh-info/points-info text, the keyboard-shortcut
hint, and the draggable cutting-plane handle/quad — leaving only the bare
3D scan:

```python
show_3d_viewer(
    "scan.glb",
    show_controls=False,
    enable_clipping=True,             # still clips the geometry...
    clip_plane_position=[0, 0.4, 0],  # ...at this fixed position...
    clip_plane_normal=[0, 1, 0],      # ...on this fixed plane,
    camera_elevation=60,              # from this fixed starting angle,
    camera_azimuth=30,
)
```

Mouse orbit/zoom/pan and Shift+Click to place a point keep working in
this mode — only the on-screen widgets and the cutting-plane's visible
handle disappear. This is meant for dashboards or reports where you want
a clean picture of the scan (optionally pre-cut and pre-angled from
Python) without any Streamlit-independent UI cluttering the page.

### Reproducing the current view

`show_3d_viewer()` returns everything needed to reproduce, in a later
call, exactly what's currently on screen — camera angle, brightness,
opacity, point size, cutting-plane state, and placed points:

```python
result = show_3d_viewer("scan.glb", key="viewer")

result["points"]         # -> [{"point": [x, y, z], "uv": [u, v] | None}, ...]
result["clip_plane"]     # -> {"position": [x, y, z], "normal": [nx, ny, nz]} | None
result["cross_section"]  # -> {"plane_basis": {...}, "loops": [...]} | None
result["settings"]       # -> {"background_color": "#1e1e1e", "opacity": 1.0,
                          #     "brightness": 1.3, "marker_size": 1.0,
                          #     "camera_elevation": 55.0, "camera_azimuth": 210.0,
                          #     "enable_clipping": True, "clip_gizmo_mode": "rotate",
                          #     "show_both_clip_halves": False,
                          #     "show_cross_section": True, "unit_scale": 1.0}
```

`settings` updates whenever you release a slider, toggle a checkbox, or
finish an orbit/drag with the mouse (not on every intermediate tick while
dragging, to avoid triggering a Streamlit rerun per pixel). Whatever it
holds — together with `clip_plane` (as `clip_plane_position` /
`clip_plane_normal`) and `points` (as `initial_points`) — can be fed
straight back into `show_3d_viewer()`:

```python
s = result["settings"]
show_3d_viewer(
    "scan.glb",
    background_color=s["background_color"],
    opacity=s["opacity"],
    brightness=s["brightness"],
    marker_size=s["marker_size"],
    camera_elevation=s["camera_elevation"],
    camera_azimuth=s["camera_azimuth"],
    enable_clipping=s["enable_clipping"],
    clip_gizmo_mode=s["clip_gizmo_mode"],
    show_both_clip_halves=s["show_both_clip_halves"],
    show_cross_section=s["show_cross_section"],
    unit_scale=s["unit_scale"],
    clip_plane_position=result["clip_plane"]["position"] if result["clip_plane"] else None,
    clip_plane_normal=result["clip_plane"]["normal"] if result["clip_plane"] else None,
    initial_points=result["points"],
)
```

`example_app.py` does exactly this in a "🔁 Current settings — reproduce
this exact view" expander below the viewer, which shows the raw
`settings` dict and a ready-to-copy Python snippet built from it.

## Cutting-plane fixes (local patch)

- **Keyboard shortcuts** for the cutting plane, once you've clicked inside
  the 3D view: `C` toggle clipping, `1`/`2`/`3` snap the normal to X/Y/Z,
  `Up`/`Down` nudge the plane along its normal (hold `Shift` for a bigger
  step), `G` switch the gizmo between move/rotate, `F` flip the side,
  `B` toggle "show both halves", `S` toggle the cross-section, `R` reset
  the plane to the model's center.
- **"Show both halves" actually shows both halves now.** It used to
  disable clipping entirely (`clippingPlanes = []`), showing the whole
  uncut model. It now renders a second, oppositely-clipped copy of the
  model, nudged apart along the plane's normal so both cut faces are
  visible at once.
- **Cross-section + both halves can be shown together.** Enabling "Show
  both halves" no longer force-disables/hides "Show cross-section" — the
  cut outline, fill, and the polygon-area table stay available regardless
  of which halves are visible (the slice is computed from the original,
  unclipped geometry either way).
- **Cross-section area table** sorts polygons largest-first and always
  shows areas in **m²** (there is no unit switcher in the UI). Pass
  `unit_scale` to `show_3d_viewer()` (meters per one model unit; default
  `1.0` = model already in meters) if your scan was authored in mm/cm,
  so the displayed m² values are correct.

## Notes / limitations

- The OBJ file (or its MTL) must provide UV coordinates for a texture to
  be mapped.
- The material is exported as non-metallic/diffuse (`metallicFactor=0`) —
  otherwise a scan would look dark/black without an environment map.
- If the model is still slow after Draco compression, try `target_faces`
  (mesh decimation, requires `pip install fast-simplification`) and/or a
  lower `max_texture_size`.
- Opacity, brightness, and point size are each configured in exactly one
  place: their respective slider inside the viewer component (`opacity`,
  `brightness`, `marker_size` only set the *starting* value). There is
  intentionally no separate Streamlit-level control for any of them, to
  avoid two out-of-sync settings.
- There is no unit switcher for the cross-section area table — areas are
  always reported in m² (scaled by `unit_scale`).
- Direct OBJ+JPG rendering (`obj_path`/`texture_path`) sends the raw,
  uncompressed files to the browser and ignores any `.mtl` the OBJ
  references — the texture you pass in (if any) is what gets applied.
  The OBJ must already contain UV coordinates for the texture to map
  correctly. For large scans, prefer converting to GLB first.
- `gltf` (non-binary) output writes several sibling files (buffers,
  images) into a subfolder named after the output file — this avoids
  filename collisions between repeated conversions in the same directory.
- Deleting source files is permanent — there's no undo, hence the
  explicit confirmation checkbox before the delete button is enabled.
- JPEG textures are kept as JPEG inside the GLB/glTF (not re-encoded to
  PNG) whenever possible. This matters a lot: PIL's `.convert()` clears
  an image's `.format` tag, and trimesh's exporter uses that tag to
  decide whether to keep JPEG compression or fall back to lossless PNG —
  losing the tag silently turns a compressed photo texture into a much
  larger PNG (5-10x is common). If you convert an image yourself before
  passing it in, remember to restore `image.format` afterward.
