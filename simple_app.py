"""
Minimal demo: upload a model directly — GLB/glTF, or OBJ with an optional
JPG/PNG texture — and try out the component's behavior flags (show/hide
controls, immediate vs. deferred point sending, ...) with a few checkboxes.

No conversion step here (see example_app.py for the OBJ -> GLB + Draco
conversion pipeline): this just forwards the uploaded file straight to
show_3d_viewer(), which can render OBJ+texture or GLB as-is.

Run:
    streamlit run simple_app.py
"""

import tempfile
from pathlib import Path

import streamlit as st

from streamlit_3d_viewer import show_3d_viewer

st.set_page_config(page_title="3D viewer — quick test", layout="wide")
st.title("3D viewer — quick test")
st.caption(
    "Upload a model directly (GLB/glTF, or OBJ + optional JPG/PNG texture) "
    "and toggle behavior flags to try them out — no conversion step."
)

with st.sidebar:
    st.header("1. Model")
    model_file = st.file_uploader("GLB / glTF / OBJ", type=["glb", "gltf", "obj"])

    texture_file = None
    if model_file is not None and Path(model_file.name).suffix.lower() == ".obj":
        texture_file = st.file_uploader(
            "Texture for the OBJ (optional)", type=["jpg", "jpeg", "png"]
        )

    st.header("2. Behavior")
    show_controls = st.checkbox(
        "Show controls",
        value=True,
        help="Sliders, buttons, cutting-plane handle. Mouse orbit/zoom/pan "
        "and Shift+Click to place a point still work either way.",
    )
    defer_points = st.checkbox(
        "Defer point sending (adds a 'Confirm points' button)",
        value=False,
        help='point_submit_mode="confirm" instead of the default '
        '"immediate" — placed/moved/cleared points stay local until you '
        "press the component's own Confirm button, instead of triggering "
        "a rerun on every click.",
    )

    with st.expander("More options"):
        enable_clipping = st.checkbox("Enable cutting plane", value=False)
        show_cross_section = st.checkbox(
            "Show cross-section", value=False, disabled=not enable_clipping
        )

if model_file is None:
    st.info("Upload a GLB/glTF or OBJ file in the sidebar to get started.")
    st.stop()

# Stash the uploaded bytes on disk — the component needs real file paths.
tmp_dir = Path(tempfile.mkdtemp())
suffix = Path(model_file.name).suffix.lower()
model_path, obj_path, texture_path = None, None, None

if suffix == ".obj":
    obj_path = tmp_dir / f"model{suffix}"
    obj_path.write_bytes(model_file.getvalue())
    if texture_file is not None:
        tex_suffix = Path(texture_file.name).suffix or ".jpg"
        texture_path = tmp_dir / f"texture{tex_suffix}"
        texture_path.write_bytes(texture_file.getvalue())
else:
    model_path = tmp_dir / f"model{suffix}"
    model_path.write_bytes(model_file.getvalue())

result = show_3d_viewer(
    model_path=model_path,
    obj_path=obj_path,
    texture_path=texture_path,
    show_controls=show_controls,
    point_submit_mode="confirm" if defer_points else "immediate",
    enable_clipping=enable_clipping,
    show_cross_section=show_cross_section,
    height=650,
    key="viewer",
)

points = result["points"]

st.subheader(f"Selected points ({len(points)})")
if points:
    st.dataframe(
        [
            {
                "x": p["point"][0] if p["point"] else None,
                "y": p["point"][1] if p["point"] else None,
                "z": p["point"][2] if p["point"] else None,
                "u": p["uv"][0] if p["uv"] else None,
                "v": p["uv"][1] if p["uv"] else None,
            }
            for p in points
        ],
        width="stretch",
    )
else:
    st.caption("Shift + click on the model to add a point.")
