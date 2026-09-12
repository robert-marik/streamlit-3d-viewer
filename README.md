# streamlit_3d_viewer

A Streamlit component for processing and viewing 3D scans (OBJ + MTL +
JPG/PNG texture) with three.js, including conversion to a leaner
**glTF/GLB** format (optionally with **Draco** geometry compression).

## Features

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
- 3D viewing with three.js (`GLTFLoader` + `DRACOLoader`).
- Zoom with the mouse wheel, rotate/pan by dragging (`OrbitControls`).
- Sliders for **elevation** and **view angle** that drive the camera
  directly (independent of mouse dragging).
- "Full scene" button (fit-to-view) and "Zoom to selected points" button
  (frames the camera so all currently selected points are visible).
- A single **opacity** slider, live in the viewer next to the scan.
- Click on the model to add a point (3D position + UV); a red marker is
  shown at that spot. Points are returned to Python as a list.
- A **point size** slider to control how big the click-to-add markers are
  drawn — it resizes markers already placed too, not just new ones.
- Control panel has its own solid dark background with light text, so
  the legend stays readable regardless of Streamlit's light/dark theme
  or page background color.
- **Direct OBJ + JPG/PNG rendering**, no GLB conversion required: pass
  `obj_path`/`texture_path` to `show_3d_viewer` to preview a raw scan
  as-is. Useful for quick looks or small files; for large scans, convert
  to GLB first (smaller, faster to load).
- **Batch directory converter page**: point it at a folder, pick which
  OBJ/MTL/texture files belong together, set conversion parameters,
  preview the result, and only then save it — with an optional cleanup
  step to delete the original source files.

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

## Notes / limitations

- The OBJ file (or its MTL) must provide UV coordinates for a texture to
  be mapped.
- The material is exported as non-metallic/diffuse (`metallicFactor=0`) —
  otherwise a scan would look dark/black without an environment map.
- If the model is still slow after Draco compression, try `target_faces`
  (mesh decimation, requires `pip install fast-simplification`) and/or a
  lower `max_texture_size`.
- Opacity and point size are each configured in exactly one place: their
  respective slider inside the viewer component. There is intentionally
  no separate Streamlit-level control for either, to avoid two
  out-of-sync settings.
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
