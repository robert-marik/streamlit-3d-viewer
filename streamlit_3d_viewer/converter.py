"""
Convert an OBJ mesh + texture (JPG/PNG) into a leaner GLB, optionally with
Draco geometry compression, and report detailed stats about the process.

Draco compression requires the Node.js CLI tool `@gltf-transform/cli`:

    npm install -g @gltf-transform/cli

If the tool is not available, compression is skipped and a plain (but
still much smaller than the original OBJ+MTL+texture) binary GLB is
produced.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import trimesh
from PIL import Image


@dataclass
class ConversionReport:
    """Summary of an OBJ -> GLB(+Draco) conversion."""

    output_path: Path
    draco_applied: bool
    message: str

    vertices_before: int
    faces_before: int
    vertices_after: int
    faces_after: int

    input_size_bytes: int              # original .obj + texture combined
    glb_size_before_draco_bytes: int   # GLB right after export, pre-Draco
    glb_size_after_bytes: int          # final size on disk

    @property
    def total_reduction_pct(self) -> float:
        if self.input_size_bytes == 0:
            return 0.0
        return (1 - self.glb_size_after_bytes / self.input_size_bytes) * 100

    @property
    def draco_reduction_pct(self) -> float:
        if self.glb_size_before_draco_bytes == 0:
            return 0.0
        return (1 - self.glb_size_after_bytes / self.glb_size_before_draco_bytes) * 100

    @property
    def decimation_applied(self) -> bool:
        return self.faces_after < self.faces_before


def _mesh_stats(mesh) -> dict:
    return {"vertices": int(len(mesh.vertices)), "faces": int(len(mesh.faces))}


def obj_to_glb(
    obj_path,
    output_path,
    texture_path=None,
    max_texture_size: int | None = 2048,
    target_faces: int | None = None,
):
    """
    Load an OBJ (+ optional JPG/PNG texture) and export it as a binary GLB.

    max_texture_size : downscale the texture so its longest side is at most
        this many pixels (faster load, smaller file). None = no resizing.
    target_faces : if given and the mesh has more faces than this, the mesh
        is simplified (decimated) to roughly this many triangles before
        export. Requires `pip install fast-simplification`.

    Returns (output_path, stats) where stats has keys:
        vertices_before, faces_before, vertices_after, faces_after
    """
    obj_path = Path(obj_path)
    output_path = Path(output_path)

    mesh = trimesh.load(obj_path, force="mesh", process=False)
    before = _mesh_stats(mesh)

    if target_faces and len(mesh.faces) > target_faces:
        try:
            mesh = mesh.simplify_quadric_decimation(target_faces)
        except Exception as exc:  # e.g. fast-simplification not installed
            raise RuntimeError(
                "Mesh simplification failed (try `pip install fast-simplification`): "
                f"{exc}"
            ) from exc

    after = _mesh_stats(mesh)

    if texture_path is not None:
        # PIL detects the actual format from content, so the extension
        # (jpg/png/...) doesn't matter.
        image = Image.open(texture_path).convert("RGB")
        if max_texture_size:
            image.thumbnail((max_texture_size, max_texture_size), Image.LANCZOS)

        uv = getattr(mesh.visual, "uv", None)
        if uv is None:
            raise ValueError("The OBJ file has no UV coordinates — the texture cannot be mapped.")

        # Explicitly non-metallic/diffuse material: trimesh otherwise exports
        # metallicFactor=1 by default, which looks almost black without an
        # environment map.
        material = trimesh.visual.material.PBRMaterial(
            baseColorTexture=image,
            metallicFactor=0.0,
            roughnessFactor=1.0,
        )
        mesh.visual = trimesh.visual.TextureVisuals(uv=uv, image=image, material=material)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(output_path, file_type="glb")

    stats = {
        "vertices_before": before["vertices"],
        "faces_before": before["faces"],
        "vertices_after": after["vertices"],
        "faces_after": after["faces"],
    }
    return output_path, stats


def compress_with_draco(glb_path, output_path=None):
    """
    Compress a GLB's geometry with Draco (via the gltf-transform CLI).

    Returns (success: bool, message: str).
    """
    glb_path = Path(glb_path)
    output_path = Path(output_path) if output_path else glb_path

    if shutil.which("gltf-transform") is None:
        return False, (
            "The 'gltf-transform' CLI was not found on PATH. "
            "Install it with: npm install -g @gltf-transform/cli"
        )

    tmp_out = output_path.with_suffix(".draco.tmp.glb")
    try:
        subprocess.run(
            [
                "gltf-transform",
                "draco",
                str(glb_path),
                str(tmp_out),
                "--method",
                "edgebreaker",
                "--quantize-position",
                "14",
                "--quantize-texcoord",
                "12",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        shutil.move(str(tmp_out), str(output_path))
        return True, "Draco compression applied successfully."
    except subprocess.CalledProcessError as exc:
        return False, f"Draco compression failed: {exc.stderr}"
    finally:
        if tmp_out.exists():
            tmp_out.unlink(missing_ok=True)


def convert(
    obj_path,
    output_path,
    texture_path=None,
    use_draco: bool = True,
    max_texture_size: int | None = 2048,
    target_faces: int | None = None,
) -> ConversionReport:
    """Full OBJ (+JPG/PNG) -> GLB (+Draco) conversion. Returns a ConversionReport."""
    obj_path = Path(obj_path)
    texture_path = Path(texture_path) if texture_path else None

    input_size = obj_path.stat().st_size
    if texture_path is not None:
        input_size += texture_path.stat().st_size

    glb_path, stats = obj_to_glb(
        obj_path,
        output_path,
        texture_path,
        max_texture_size=max_texture_size,
        target_faces=target_faces,
    )
    glb_size_before_draco = glb_path.stat().st_size

    draco_applied = False
    message = "Draco compression not requested."
    if use_draco:
        draco_applied, message = compress_with_draco(glb_path)

    glb_size_after = glb_path.stat().st_size

    return ConversionReport(
        output_path=glb_path,
        draco_applied=draco_applied,
        message=message,
        vertices_before=stats["vertices_before"],
        faces_before=stats["faces_before"],
        vertices_after=stats["vertices_after"],
        faces_after=stats["faces_after"],
        input_size_bytes=input_size,
        glb_size_before_draco_bytes=glb_size_before_draco,
        glb_size_after_bytes=glb_size_after,
    )
