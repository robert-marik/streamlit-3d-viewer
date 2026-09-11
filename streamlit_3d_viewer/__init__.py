"""
streamlit_3d_viewer
====================

Streamlit component for viewing 3D scans (OBJ + texture) with three.js,
including conversion to a leaner glTF/GLB format (optionally Draco
compressed).

Usage:

    from streamlit_3d_viewer import show_3d_viewer
    from streamlit_3d_viewer.converter import convert

    report = convert("scan.obj", "scan.glb", texture_path="scan.jpg")
    points = show_3d_viewer(report.output_path, opacity=0.8)
"""

import base64
from pathlib import Path

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).parent / "frontend"

_component_func = components.declare_component(
    "streamlit_3d_viewer",
    path=str(_COMPONENT_DIR),
)


def _file_to_data_url(path, mime):
    data = Path(path).read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def show_3d_viewer(
    model_path,
    height=680,
    background_color="#1e1e1e",
    opacity=1.0,
    key=None,
):
    """
    Display a 3D model (GLB/GLTF) in Streamlit using three.js.

    Parameters
    ----------
    model_path : str | Path
        Path to a .glb (or .gltf) file.
    height : int
        Component height in px.
    background_color : str
        Scene background color (hex).
    opacity : float
        Initial model opacity (0.0 - 1.0). This is only the starting
        value — the component has its own opacity slider next to the
        scan, which is the single source of truth once rendered.
    key : str | None
        Streamlit component key.

    Returns
    -------
    list[dict]
        Points the user clicked on the model, e.g.:
        [{"point": [x, y, z], "uv": [u, v]}, ...]
    """
    model_path = Path(model_path)
    model_url = _file_to_data_url(model_path, "model/gltf-binary")
    model_size_kb = round(model_path.stat().st_size / 1024, 1)

    value = _component_func(
        model_url=model_url,
        model_size_kb=model_size_kb,
        opacity=float(opacity),
        background_color=background_color,
        default=[],
        key=key,
    )
    return value or []
