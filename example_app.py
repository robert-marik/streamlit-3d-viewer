"""
Example Streamlit app: upload OBJ + texture, convert to GLB (+Draco),
show a conversion report, view the model and work with selected points.

Run:
    streamlit run example_app.py
"""

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from streamlit_3d_viewer import show_3d_viewer
from streamlit_3d_viewer.converter import convert

st.set_page_config(page_title="3D scan viewer", layout="wide")
st.title("3D scan viewer")

if "report" not in st.session_state:
    st.session_state.report = None

with st.sidebar:
    st.header("1. Upload")
    obj_file = st.file_uploader("OBJ file", type=["obj"])
    tex_file = st.file_uploader("Texture", type=["jpg", "jpeg", "png"])
    use_draco = st.checkbox("Use Draco compression (requires gltf-transform)", value=True)
    target_faces = st.number_input(
        "Simplify mesh to max. triangle count (0 = no change)",
        min_value=0, value=0, step=10000,
    )

    if st.button("Convert to GLB", disabled=obj_file is None):
        tmp_dir = Path(tempfile.mkdtemp())
        obj_path = tmp_dir / "model.obj"
        obj_path.write_bytes(obj_file.getvalue())

        texture_path = None
        if tex_file is not None:
            suffix = Path(tex_file.name).suffix or ".jpg"
            texture_path = tmp_dir / f"texture{suffix}"
            texture_path.write_bytes(tex_file.getvalue())

        glb_path = tmp_dir / "model.glb"
        with st.spinner("Converting..."):
            report = convert(
                obj_path,
                glb_path,
                texture_path=texture_path,
                use_draco=use_draco,
                target_faces=target_faces or None,
            )
        st.session_state.report = report

    st.header("2. Scene")
    bg_color = st.color_picker("Background color", "#1e1e1e")
    # Opacity is intentionally NOT configured here — the viewer below has
    # its own opacity slider right next to the scan; keeping a second one
    # here would just be a duplicate control that goes out of sync.

report = st.session_state.report

if report is not None:
    with st.expander("Conversion report", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Original size", f"{report.input_size_bytes / 1024:.1f} KB")
        c2.metric("GLB before Draco", f"{report.glb_size_before_draco_bytes / 1024:.1f} KB")
        c3.metric(
            "GLB final size",
            f"{report.glb_size_after_bytes / 1024:.1f} KB",
            delta=f"-{report.total_reduction_pct:.1f}% vs. original",
            delta_color="inverse",
        )
        c4.metric(
            "Draco reduction",
            f"{report.draco_reduction_pct:.1f}%" if report.draco_applied else "not applied",
        )

        st.caption(report.message)

        mesh_df = pd.DataFrame(
            {
                "": ["Vertices", "Triangles"],
                "Before decimation": [report.vertices_before, report.faces_before],
                "After decimation": [report.vertices_after, report.faces_after],
            }
        )
        st.dataframe(mesh_df, hide_index=True, width="stretch")
        if not report.decimation_applied:
            st.caption("No mesh decimation was applied (target_faces not set or mesh already smaller).")

    points = show_3d_viewer(
        report.output_path,
        background_color=bg_color,
        height=680,
        key="viewer",
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
        st.caption("No points selected yet.")
else:
    st.info("Upload an OBJ (and optionally a texture) in the sidebar, then click \"Convert to GLB\".")
