"""
Demo: render a raw OBJ + JPG texture directly, with NO conversion step.

This is the lightweight alternative to example_app.py's "upload -> convert
to GLB -> view" flow: pass `obj_path`/`texture_path` straight to
`show_3d_viewer` and the component loads the OBJ as-is in the browser,
applying the given JPG texture to it. Handy for quick previews or small
scans where a GLB conversion isn't worth the extra step — for large scans
prefer the GLB path in example_app.py, since OBJ+JPG is transferred
uncompressed.

A small procedurally-generated sample (a textured sphere) is bundled in
demo_assets/obj_texture_demo/ so this script runs out of the box; swap in
your own .obj/.jpg via the sidebar upload to try it with real data.

Run:
    streamlit run example_obj_texture_demo.py
"""

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from streamlit_3d_viewer import show_3d_viewer

st.set_page_config(page_title="3D scan viewer — OBJ+JPG demo", layout="wide")
st.title("3D scan viewer — direct OBJ + JPG rendering")
st.caption(
    "No GLB conversion here: the OBJ and its JPG texture are sent to the "
    "browser and rendered as-is."
)

SAMPLE_DIR = Path(__file__).parent / "demo_assets" / "obj_texture_demo"
SAMPLE_OBJ = SAMPLE_DIR / "sphere.obj"
SAMPLE_TEX = SAMPLE_DIR / "sphere.jpg"

with st.sidebar:
    st.header("1. Model")
    use_sample = st.checkbox("Use bundled sample (textured sphere)", value=True)

    obj_path, texture_path = None, None
    if use_sample:
        obj_path, texture_path = SAMPLE_OBJ, SAMPLE_TEX
    else:
        obj_file = st.file_uploader("OBJ file", type=["obj"])
        tex_file = st.file_uploader("Texture", type=["jpg", "jpeg", "png"])
        if obj_file is not None:
            tmp_dir = Path(tempfile.mkdtemp())
            obj_path = tmp_dir / "model.obj"
            obj_path.write_bytes(obj_file.getvalue())
            if tex_file is not None:
                suffix = Path(tex_file.name).suffix or ".jpg"
                texture_path = tmp_dir / f"texture{suffix}"
                texture_path.write_bytes(tex_file.getvalue())

    st.header("2. Scene")
    bg_color = st.color_picker("Background color", "#1e1e1e")
    # Opacity and point size are intentionally NOT configured here — the
    # viewer below has its own sliders right next to the scan, which are
    # the single source of truth once rendered.

if obj_path is not None:
    points = show_3d_viewer(
        obj_path=obj_path,
        texture_path=texture_path,
        background_color=bg_color,
        height=680,
        key="viewer-objtex",
    )

    st.subheader("Selected points")
    if points:
        df = pd.DataFrame(
            [
                {
                    "x": p["point"][0] if p["point"] else None,
                    "y": p["point"][1] if p["point"] else None,
                    "z": p["point"][2] if p["point"] else None,
                    "u": p["uv"][0] if p["uv"] else None,
                    "v": p["uv"][1] if p["uv"] else None,
                }
                for p in points
            ]
        )
        st.dataframe(df, width="stretch")
    else:
        st.caption("Shift + click on the model to add a point.")
else:
    st.info("Upload an OBJ (and optionally a texture) in the sidebar, or keep the bundled sample checked.")
