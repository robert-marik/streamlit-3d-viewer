"""
Batch directory converter: point this page at a folder of scan files
(.obj / .mtl / .jpg / .png), pick which ones belong together, set
conversion parameters, preview the result, and only then save it (with
an optional cleanup of the original source files).
"""

import shutil
import tempfile
from pathlib import Path

import streamlit as st

from streamlit_3d_viewer import show_3d_viewer
from streamlit_3d_viewer.converter import (
    convert,
    delete_files,
    finalize_output,
    guess_texture_for_obj,
    list_scan_files,
)

st.set_page_config(page_title="Batch directory converter", layout="wide")
st.title("Batch directory converter")
st.caption("Convert OBJ + MTL + JPG/PNG scans found in a folder to GLB or glTF (optionally Draco-compressed).")

for key, default in {
    "batch_dir": "",
    "batch_files": None,
    "preview_report": None,
    "preview_tmp_dir": None,
    "saved_path": None,
    "saved_sources": None,
}.items():
    st.session_state.setdefault(key, default)

# --------------------------------------------------------------------- #
# 1. Pick a directory
# --------------------------------------------------------------------- #
st.subheader("1. Source directory")
col_dir, col_scan = st.columns([4, 1])
directory_input = col_dir.text_input("Directory with scan files", value=st.session_state.batch_dir)
if col_scan.button("Scan directory", width="stretch"):
    st.session_state.batch_dir = directory_input
    try:
        st.session_state.batch_files = list_scan_files(directory_input)
        st.session_state.preview_report = None
        st.session_state.saved_path = None
    except NotADirectoryError as exc:
        st.session_state.batch_files = None
        st.error(str(exc))

files = st.session_state.batch_files

if not files:
    st.info("Enter a folder path and click \"Scan directory\" to get started.")
    st.stop()

if not files["obj"]:
    st.warning("No .obj files found in this directory.")
    st.stop()

st.success(
    f"Found {len(files['obj'])} OBJ, {len(files['mtl'])} MTL, "
    f"{len(files['textures'])} texture file(s)."
)

# --------------------------------------------------------------------- #
# 2. Pick source files
# --------------------------------------------------------------------- #
st.subheader("2. Choose source files")
obj_path = Path(
    st.selectbox("OBJ file", options=files["obj"], format_func=lambda p: p.name)
)

auto_texture = guess_texture_for_obj(obj_path)
texture_options = ["Auto-detect from MTL", "None"] + [p.name for p in files["textures"]]
default_idx = 0 if auto_texture is not None else 1
texture_choice = st.selectbox("Texture", options=texture_options, index=default_idx)

if texture_choice == "Auto-detect from MTL":
    texture_path = auto_texture
    if texture_path is None:
        st.warning("Could not auto-detect a texture from the OBJ's MTL — pick one manually or choose \"None\".")
    else:
        st.caption(f"Using texture referenced by MTL: **{texture_path.name}**")
elif texture_choice == "None":
    texture_path = None
else:
    texture_path = obj_path.parent / texture_choice

mtl_guess = None
for m in files["mtl"]:
    if m.stem == obj_path.stem or m.name in obj_path.read_text(errors="ignore"):
        mtl_guess = m
        break

# --------------------------------------------------------------------- #
# 3. Conversion parameters
# --------------------------------------------------------------------- #
st.subheader("3. Conversion parameters")
p1, p2, p3 = st.columns(3)
output_name = p1.text_input("Output file name (no extension)", value=obj_path.stem)
output_format = p2.radio("Format", ["glb", "gltf"], horizontal=True,
                          help="glb = single binary file (recommended). gltf = JSON + separate asset files.")
use_draco = p3.checkbox("Draco compression", value=True,
                         help="Requires the Node.js CLI tool gltf-transform.")

p4, p5 = st.columns(2)
target_faces = p4.number_input("Simplify to max. triangle count (0 = no change)", min_value=0, value=0, step=10000)
max_texture_size = p5.number_input("Max texture size (px, 0 = no resize)", min_value=0, value=2048, step=256)

st.markdown("**Output location**")
same_dir = st.checkbox("Save in the same directory as the source files", value=True)
custom_out_dir = None
if not same_dir:
    custom_out_dir = st.text_input("Custom output directory", value=str(obj_path.parent))

final_out_dir = Path(custom_out_dir) if custom_out_dir else obj_path.parent

# --------------------------------------------------------------------- #
# 4. Convert & preview (written to a temp location first)
# --------------------------------------------------------------------- #
st.subheader("4. Convert & preview")
if st.button("Convert & preview", type="primary"):
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        with st.spinner("Converting..."):
            report = convert(
                obj_path,
                tmp_dir / output_name,
                texture_path=texture_path,
                mtl_path=mtl_guess,
                output_format=output_format,
                use_draco=use_draco,
                max_texture_size=max_texture_size or None,
                target_faces=target_faces or None,
            )
        st.session_state.preview_report = report
        st.session_state.preview_tmp_dir = tmp_dir
        st.session_state.saved_path = None
    except Exception as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        st.error(f"Conversion failed: {exc}")

report = st.session_state.preview_report

if report is not None:
    with st.expander("Conversion report", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Original size", f"{report.input_size_bytes / 1024:.1f} KB")
        c2.metric("Before Draco", f"{report.glb_size_before_draco_bytes / 1024:.1f} KB")
        c3.metric(
            "Final size",
            f"{report.glb_size_after_bytes / 1024:.1f} KB",
            delta=f"-{report.total_reduction_pct:.1f}% vs. original",
            delta_color="inverse",
        )
        c4.metric("Draco reduction", f"{report.draco_reduction_pct:.1f}%" if report.draco_applied else "not applied")
        st.caption(report.message)

        import pandas as pd
        mesh_df = pd.DataFrame({
            "": ["Vertices", "Triangles"],
            "Before decimation": [report.vertices_before, report.faces_before],
            "After decimation": [report.vertices_after, report.faces_after],
        })
        st.dataframe(mesh_df, hide_index=True, width="stretch")

    st.markdown("**Preview**")
    show_3d_viewer(report.output_path, height=600, key="batch_preview_viewer")

    # ------------------------------------------------------------- #
    # 5. Save (only once the user is happy with the preview)
    # ------------------------------------------------------------- #
    st.subheader("5. Save result")
    st.caption(f"Will be written to: `{final_out_dir / output_name}` ({output_format})")

    if st.button("Looks good — save here"):
        saved_path = finalize_output(report, final_out_dir, output_name)
        shutil.rmtree(st.session_state.preview_tmp_dir, ignore_errors=True)
        st.session_state.saved_path = saved_path
        st.session_state.saved_sources = {
            "obj_path": obj_path,
            "mtl_guess": mtl_guess,
            "texture_path": texture_path,
        }
        st.session_state.preview_report = None
        st.rerun()

# ------------------------------------------------------------- #
# 6. Clean up source files (shown once something has been saved,
#    independent of the (now cleared) preview/report state above)
# ------------------------------------------------------------- #
if st.session_state.saved_path is not None:
    st.success(f"Saved: {st.session_state.saved_path}")

    st.subheader("6. Clean up source files (optional)")
    sources = st.session_state.get("saved_sources", {})
    candidates = [sources.get("obj_path")] + [sources.get("mtl_guess")] + [sources.get("texture_path")]
    candidates = [c for c in candidates if c is not None]
    chosen = st.multiselect(
        "Select source files to delete",
        options=candidates,
        default=candidates,
        format_func=lambda p: p.name,
    )
    confirm = st.checkbox("I understand this permanently deletes the selected file(s).")
    if st.button("Delete selected source files", disabled=not (chosen and confirm)):
        errors = delete_files(chosen)
        if errors:
            st.error("Some files could not be deleted:\n" + "\n".join(errors))
        else:
            st.success("Source files deleted.")
            st.session_state.batch_files = list_scan_files(st.session_state.batch_dir)
            st.session_state.saved_path = None

