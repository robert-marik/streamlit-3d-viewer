"""
streamlit_3d_viewer
====================

Streamlit component for viewing 3D scans (OBJ + texture) with three.js,
including conversion to a leaner glTF/GLB format (optionally Draco
compressed).

Usage (GLB/glTF, the recommended, lightweight path):

    from streamlit_3d_viewer import show_3d_viewer
    from streamlit_3d_viewer.converter import convert

    report = convert("scan.obj", "scan.glb", texture_path="scan.jpg")
    points = show_3d_viewer(report.output_path, opacity=0.8)

Usage (render a raw OBJ + JPG/PNG texture directly, no conversion step):

    points = show_3d_viewer(obj_path="scan.obj", texture_path="scan.jpg")
"""

import base64
import mimetypes
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
    model_path=None,
    obj_path=None,
    texture_path=None,
    height=680,
    background_color="#1e1e1e",
    opacity=1.0,
    marker_size=1.0,
    key=None,
):
    """
    Display a 3D model in Streamlit using three.js.

    Two mutually exclusive input modes are supported:

    1. GLB/glTF (recommended): pass `model_path`. This is the compact,
       fast-loading format produced by `streamlit_3d_viewer.converter.convert`.
    2. Raw OBJ + texture (no conversion needed): pass `obj_path` and,
       optionally, `texture_path`. The OBJ is loaded as-is (with its own
       UV coordinates) and the given JPG/PNG is applied directly as the
       diffuse texture. This is handy for quick previews or small scans
       where the GLB conversion step isn't worth it, but the file is
       transferred uncompressed, so prefer the GLB path for large scans.

    Parameters
    ----------
    model_path : str | Path | None
        Path to a .glb (or .gltf) file. Ignored if `obj_path` is given.
    obj_path : str | Path | None
        Path to a .obj file to render directly, without any GLB
        conversion. If given, takes precedence over `model_path`.
    texture_path : str | Path | None
        Path to a .jpg/.jpeg/.png texture to apply to `obj_path`. The
        OBJ must have UV coordinates for the texture to map correctly.
        Optional — the OBJ is shown untextured (plain material) if
        omitted.
    height : int
        Component height in px.
    background_color : str
        Scene background color (hex).
    opacity : float
        Initial model opacity (0.0 - 1.0). This is only the starting
        value — the component has its own opacity slider next to the
        scan, which is the single source of truth once rendered.
    marker_size : float
        Initial relative size of the point markers (1.0 = 100%, the
        default size). This is only the starting value — the component
        has its own "Point size" slider, which is the single source of
        truth once rendered and also lets the user resize markers
        already placed.
    key : str | None
        Streamlit component key.

    Returns
    -------
    list[dict]
        Points the user clicked on the model, e.g.:
        [{"point": [x, y, z], "uv": [u, v]}, ...]
    """
    kwargs = dict(
        opacity=float(opacity),
        marker_size=float(marker_size),
        background_color=background_color,
        default=[],
        key=key,
    )

    if obj_path is not None:
        obj_path = Path(obj_path)
        obj_url = _file_to_data_url(obj_path, "text/plain")

        texture_url = None
        if texture_path is not None:
            texture_path = Path(texture_path)
            tex_mime = mimetypes.guess_type(str(texture_path))[0] or "image/jpeg"
            texture_url = _file_to_data_url(texture_path, tex_mime)

        value = _component_func(
            model_type="objtex",
            obj_url=obj_url,
            texture_url=texture_url,
            model_size_kb=round(
                (obj_path.stat().st_size
                 + (texture_path.stat().st_size if texture_path else 0)) / 1024,
                1,
            ),
            **kwargs,
        )
    else:
        if model_path is None:
            raise ValueError("Either model_path or obj_path must be given.")
        model_path = Path(model_path)
        model_url = _file_to_data_url(model_path, "model/gltf-binary")
        model_size_kb = round(model_path.stat().st_size / 1024, 1)

        value = _component_func(
            model_type="glb",
            model_url=model_url,
            model_size_kb=model_size_kb,
            **kwargs,
        )

    return value or []
