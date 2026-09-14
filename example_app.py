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


def _reproduce_snippet(settings, clip_plane, points):
    """Turn the component's returned `settings` (+ `clip_plane` + `points`)
    into a ready-to-paste `show_3d_viewer(...)` call that reproduces
    exactly what's currently on screen."""
    lines = ["show_3d_viewer(", "    report.output_path,"]
    for py_key in (
        "background_color",
        "opacity",
        "brightness",
        "marker_size",
        "camera_elevation",
        "camera_azimuth",
        "enable_clipping",
        "clip_gizmo_mode",
        "show_both_clip_halves",
        "show_cross_section",
        "unit_scale",
    ):
        if py_key in settings:
            lines.append(f"    {py_key}={settings[py_key]!r},")
    if clip_plane is not None:
        pos = [round(v, 4) for v in clip_plane["position"]]
        nrm = [round(v, 4) for v in clip_plane["normal"]]
        lines.append(f"    clip_plane_position={pos!r},")
        lines.append(f"    clip_plane_normal={nrm!r},")
    if points:
        pts_repr = [{"point": p["point"], "uv": p["uv"]} for p in points]
        lines.append(f"    initial_points={pts_repr!r},")
    lines.append(")")
    return "\n".join(lines)


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

    show_controls = st.checkbox(
        "Show controls",
        value=True,
        help=(
            "Turn off to display only the bare 3D scan (no sliders, "
            "buttons, checkboxes, or cutting-plane handle). Mouse "
            "orbit/zoom/pan and Shift+Click to place a point still work."
        ),
    )

    with st.expander("Initial camera / view"):
        camera_elevation = st.slider("Initial elevation (°)", 1, 179, 60)
        camera_azimuth = st.slider("Initial view angle (°)", 0, 360, 0)
        brightness = st.slider("Initial brightness (%)", 30, 300, 130) / 100.0

    st.header("3. Cutting plane")
    enable_clipping = st.checkbox("Enable cutting plane", value=False)
    clip_plane_position = None
    clip_plane_normal = None
    show_both_clip_halves = False
    show_cross_section = False
    if enable_clipping:
        st.caption(
            "Starting position/tilt for the plane. Drag the gizmo in the "
            "viewer to fine-tune it; moving a slider here snaps the plane "
            "back to that exact value."
        )
        # -2..2 is a generic default; adjust to your model's actual scale.
        px = st.slider("Position X", -2.0, 2.0, 0.0, 0.01)
        py = st.slider("Position Y", -2.0, 2.0, 0.0, 0.01)
        pz = st.slider("Position Z", -2.0, 2.0, 0.0, 0.01)
        clip_plane_position = [px, py, pz]

        tilt = st.slider("Tilt from horizontal (°)", 0, 180, 0)
        rotate = st.slider("Rotation around vertical axis (°)", 0, 360, 0)
        import math
        t, r = math.radians(tilt), math.radians(rotate)
        # tilt=0 -> horizontal plane, normal points straight up (+Y)
        clip_plane_normal = [
            math.sin(t) * math.cos(r),
            math.cos(t),
            math.sin(t) * math.sin(r),
        ]

        show_both_clip_halves = st.checkbox("Show both halves", value=False)
        show_cross_section = st.checkbox("Show cross-section", value=False)
        clip_gizmo_mode = st.radio("Gizmo mode", ["translate", "rotate"], horizontal=True)
    else:
        clip_gizmo_mode = None

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

    result = show_3d_viewer(
        report.output_path,
        background_color=bg_color,
        height=680,
        show_controls=show_controls,
        camera_elevation=camera_elevation,
        camera_azimuth=camera_azimuth,
        brightness=brightness,
        enable_clipping=enable_clipping,
        clip_plane_position=clip_plane_position,
        clip_plane_normal=clip_plane_normal,
        clip_gizmo_mode=clip_gizmo_mode,
        show_both_clip_halves=show_both_clip_halves,
        show_cross_section=show_cross_section,
        key="viewer",
    )
    points = result["points"]
    clip_plane = result["clip_plane"]
    cross_section = result["cross_section"]
    settings = result.get("settings", {})

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

    with st.expander("🔁 Current settings — reproduce this exact view"):
        st.caption(
            "Reflects the sliders/checkboxes/camera angle/cutting plane as "
            "they currently are on screen (updates once you release a "
            "slider, toggle a checkbox, or finish dragging/orbiting)."
        )
        st.json(settings)
        st.code(_reproduce_snippet(settings, clip_plane, points), language="python")

    if clip_plane is not None:
        st.subheader("Cutting plane")
        st.caption(
            f"Position: {[round(v, 4) for v in clip_plane['position']]} · "
            f"Normal: {[round(v, 4) for v in clip_plane['normal']]}"
        )

        if cross_section is not None:
            n_loops = len(cross_section["loops"])
            n_pts = sum(len(l["points_3d"]) for l in cross_section["loops"])
            st.caption(f"Cross-section: {n_loops} loop(s), {n_pts} point(s) total.")

            if cross_section["loops"] and st.button("Render cross-section in detail (matplotlib)"):
                import matplotlib.pyplot as plt

                fig, ax = plt.subplots(figsize=(6, 6))
                for i, loop in enumerate(cross_section["loops"]):
                    pts = loop["points_2d"]
                    if loop["closed"]:
                        pts = pts + [pts[0]]
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    ax.plot(xs, ys, marker="o", markersize=2, label=f"Loop {i + 1}")
                    if loop["closed"]:
                        ax.fill(xs, ys, alpha=0.2)
                ax.set_aspect("equal")
                ax.set_xlabel("u")
                ax.set_ylabel("v")
                ax.set_title("Cross-section polygon(s)")
                ax.legend()
                st.pyplot(fig)

            for i, loop in enumerate(cross_section["loops"]):
                loop_df = pd.DataFrame(
                    loop["points_3d"], columns=["x", "y", "z"]
                )
                loop_df[["u", "v"]] = pd.DataFrame(loop["points_2d"])
                with st.expander(
                    f"Loop {i + 1} ({'closed' if loop['closed'] else 'open'}, "
                    f"{len(loop['points_3d'])} points)"
                ):
                    st.dataframe(loop_df, width="stretch")
                    st.download_button(
                        f"Download loop {i + 1} as CSV",
                        loop_df.to_csv(index=False).encode("utf-8"),
                        file_name=f"cross_section_loop_{i + 1}.csv",
                        mime="text/csv",
                        key=f"dl_loop_{i}",
                    )
else:
    st.info("Upload an OBJ (and optionally a texture) in the sidebar, then click \"Convert to GLB\".")
