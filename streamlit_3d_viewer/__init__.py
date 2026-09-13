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


_EMPTY_VALUE = {"points": [], "clip_plane": None, "cross_section": None}


def show_3d_viewer(
    model_path=None,
    obj_path=None,
    texture_path=None,
    height=680,
    background_color="#1e1e1e",
    opacity=1.0,
    marker_size=1.0,
    enable_clipping=None,
    clip_plane_position=None,
    clip_plane_normal=None,
    show_both_clip_halves=False,
    show_cross_section=False,
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

    The clipping toggles (`enable_clipping`, `show_cross_section`) are
    optional. When omitted (`None`), the component keeps whatever state
    the frontend checkboxes currently have across Streamlit reruns. Pass
    explicit booleans to force a particular on/off state from Python.

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
    enable_clipping : bool | None
        Show the cutting-plane widget (a draggable/rotatable gizmo) and
        clip the model against it. Can also be turned on/off with the
        "Cutting plane" checkbox in the component itself. If left as
        ``None`` (default), the frontend checkbox controls this state.
    clip_plane_position : list[float] | tuple[float, float, float] | None
        `[x, y, z]` position to (re)apply to the cutting plane. This is
        read once per distinct value: the first time it's given it sets
        the plane's starting position (defaulting to the model's center
        otherwise); if you pass a *new* value on a later rerun (e.g. the
        user moved a Streamlit slider bound to this), the plane snaps to
        it, overriding whatever the mouse had set. As long as the value
        you pass doesn't change, dragging the on-screen gizmo is left
        alone.
    clip_plane_normal : list[float] | tuple[float, float, float] | None
        `[nx, ny, nz]` direction the plane faces (does not need to be
        unit length; it's normalized internally). Defaults to `[0, 1, 0]`
        (horizontal, like a water level) when not given.
        Follows the same "re-applied only when the value changes"
        convention as `clip_plane_position`.
    show_both_clip_halves : bool
        Keep both halves of the model visible while the cutting plane is
        enabled. If ``False`` (default), one half is clipped away.
    show_cross_section : bool | None
        Compute and draw the polygon(s) where the cutting plane
        intersects the model, and include them in the returned value.
        Can also be toggled with the "Show cross-section" checkbox. If
        left as ``None`` (default), the frontend checkbox controls this
        state.
    key : str | None
        Streamlit component key.

    Returns
    -------
    dict
        ``{"points": [...], "clip_plane": {...} | None, "cross_section": {...} | None}``

        - ``points``: list of clicked points, e.g.
          ``[{"point": [x, y, z], "uv": [u, v]}, ...]``.
        - ``clip_plane``: ``None`` if clipping is off, otherwise
          ``{"position": [x, y, z], "normal": [nx, ny, nz]}`` with the
          gizmo's current (possibly mouse-dragged) transform.
        - ``cross_section``: ``None`` unless "Show cross-section" is on,
          otherwise
          ``{"plane_basis": {...}, "loops": [{"closed": bool,
          "points_3d": [[x, y, z], ...], "points_2d": [[u, v], ...]}, ...]}``.
          ``points_2d`` are the same points flattened into the plane's own
          in-plane (u, v) axes (see ``plane_basis``), handy for exporting
          a flat cut profile.
    """
    kwargs = dict(
        opacity=float(opacity),
        marker_size=float(marker_size),
        background_color=background_color,
        clip_plane_position=(
            [float(v) for v in clip_plane_position] if clip_plane_position is not None else None
        ),
        clip_plane_normal=(
            [float(v) for v in clip_plane_normal] if clip_plane_normal is not None else None
        ),
        show_both_clip_halves=bool(show_both_clip_halves),
        show_cross_section=bool(show_cross_section),
        default=_EMPTY_VALUE,
        key=key,
    )
    if enable_clipping is not None:
        kwargs["enable_clipping"] = bool(enable_clipping)
    if show_cross_section is not None:
        kwargs["show_cross_section"] = bool(show_cross_section)

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

    return value or _EMPTY_VALUE
