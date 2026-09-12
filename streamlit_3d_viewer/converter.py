"""
Convert an OBJ mesh (+ MTL + JPG/PNG texture) into a leaner GLB or glTF,
optionally with Draco geometry compression, and report detailed stats
about the process.

Draco compression requires the Node.js CLI tool `@gltf-transform/cli`:

    npm install -g @gltf-transform/cli

If the tool is not available, compression is skipped and a plain (but
still much smaller than the original OBJ+MTL+texture) binary GLB is
produced.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import trimesh
from PIL import Image
from scipy.spatial import cKDTree

TEXTURE_EXTENSIONS = (".jpg", ".jpeg", ".png")


# --------------------------------------------------------------------------- #
# Directory / file discovery helpers (used by the batch-converter UI)
# --------------------------------------------------------------------------- #

def list_scan_files(directory) -> dict:
    """
    List files relevant to 3D scan conversion in a directory.

    Returns {"obj": [...], "mtl": [...], "textures": [...]} with sorted
    Path lists (non-recursive).
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    obj_files = sorted(directory.glob("*.obj"))
    mtl_files = sorted(directory.glob("*.mtl"))
    texture_files = sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in TEXTURE_EXTENSIONS
    )
    return {"obj": obj_files, "mtl": mtl_files, "textures": texture_files}


def guess_texture_for_obj(obj_path) -> Path | None:
    """
    Best-effort: follow `mtllib` in the OBJ to its .mtl file, then read
    `map_Kd` from it to find the referenced diffuse texture. Returns the
    resolved Path if the file exists on disk, else None.
    """
    obj_path = Path(obj_path)
    try:
        obj_text = obj_path.read_text(errors="ignore")
    except OSError:
        return None

    mtl_name = None
    for line in obj_text.splitlines():
        line = line.strip()
        if line.lower().startswith("mtllib"):
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                mtl_name = parts[1].strip().split()[0]
            break
    if not mtl_name:
        return None

    mtl_path = obj_path.parent / mtl_name
    if not mtl_path.exists():
        return None

    try:
        mtl_text = mtl_path.read_text(errors="ignore")
    except OSError:
        return None

    for line in mtl_text.splitlines():
        line = line.strip()
        if line.lower().startswith("map_kd"):
            parts = line.split()
            if len(parts) >= 2:
                tex_path = obj_path.parent / parts[-1]
                if tex_path.exists():
                    return tex_path
    return None


def delete_files(paths) -> list[str]:
    """Delete a list of files. Returns a list of error messages (empty = all OK)."""
    errors = []
    for p in paths:
        p = Path(p)
        try:
            if p.exists():
                p.unlink()
        except OSError as exc:
            errors.append(f"{p.name}: {exc}")
    return errors


# --------------------------------------------------------------------------- #
# Conversion
# --------------------------------------------------------------------------- #

@dataclass
class ConversionReport:
    """Summary of an OBJ -> GLB/glTF (+Draco) conversion."""

    output_path: Path
    output_format: str
    draco_applied: bool
    message: str

    vertices_before: int
    faces_before: int
    vertices_after: int
    faces_after: int

    input_size_bytes: int              # original .obj + .mtl + texture combined
    glb_size_before_draco_bytes: int   # main output file size right after export, pre-Draco
    glb_size_after_bytes: int          # final size of the main output file on disk

    extra_files: list = field(default_factory=list)  # sibling files for non-binary gltf

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

    @property
    def all_output_files(self) -> list:
        return [self.output_path, *self.extra_files]


def _mesh_stats(mesh) -> dict:
    return {"vertices": int(len(mesh.vertices)), "faces": int(len(mesh.faces))}


def _existing_material_image(mesh):
    """Best-effort extraction of a diffuse image already attached to a mesh
    (e.g. auto-loaded by trimesh from an OBJ's MTL)."""
    material = getattr(mesh.visual, "material", None)
    if material is None:
        return None
    image = getattr(material, "image", None)
    if image is not None:
        return image
    return getattr(material, "baseColorTexture", None)


def obj_to_model(
    obj_path,
    output_path,
    texture_path=None,
    output_format: str = "glb",
    max_texture_size: int | None = 2048,
    target_faces: int | None = None,
):
    """
    Load an OBJ (+ MTL / explicit JPG-PNG texture) and export it as GLB or
    glTF.

    texture_path : explicit texture to use. If None, the texture referenced
        by the OBJ's MTL (already parsed by trimesh on load) is used
        instead, if present.
    output_format : "glb" (single binary file, recommended) or "gltf"
        (JSON + separate .bin/image files, written into a subfolder named
        after the output file's stem to avoid collisions).
    max_texture_size : downscale the texture so its longest side is at most
        this many pixels. None = no resizing.
    target_faces : if given and the mesh has more faces than this, the mesh
        is simplified (decimated) to roughly this many triangles before
        export. Requires `pip install fast-simplification`.

    Returns (output_path, extra_files, stats).
    """
    obj_path = Path(obj_path)
    output_path = Path(output_path)
    output_format = output_format.lower()
    if output_format not in ("glb", "gltf"):
        raise ValueError("output_format must be 'glb' or 'gltf'")

    mesh = trimesh.load(obj_path, force="mesh", process=False)
    before = _mesh_stats(mesh)

    original_uv = getattr(mesh.visual, "uv", None)
    original_image = _existing_material_image(mesh)

    if target_faces and len(mesh.faces) > target_faces:
        original_vertices = mesh.vertices.copy()
        try:
            # `face_count` must be passed as a keyword: current trimesh
            # versions changed the first positional argument to `percent`
            # (a 0-1 target reduction ratio, not a face count).
            simplified = mesh.simplify_quadric_decimation(face_count=int(target_faces))
        except Exception as exc:  # e.g. fast-simplification not installed
            raise RuntimeError(
                "Mesh simplification failed (try `pip install fast-simplification`): "
                f"{exc}"
            ) from exc

        if original_uv is not None:
            # simplify_quadric_decimation returns a bare Trimesh with only
            # vertices/faces (no visual/UV data). Recover an approximate
            # per-vertex UV for the simplified mesh via nearest-neighbor
            # lookup against the original (pre-decimation) vertices.
            tree = cKDTree(original_vertices)
            _, nn_idx = tree.query(simplified.vertices)
            original_uv = original_uv[nn_idx]

        mesh = simplified

    after = _mesh_stats(mesh)

    # Pick the texture: explicit override wins, otherwise whatever was
    # already attached to the mesh (typically from the OBJ's MTL).
    final_image = None
    if texture_path is not None:
        raw = Image.open(texture_path)
        source_format = raw.format  # e.g. "JPEG" — capture before .convert() wipes it
        final_image = raw.convert("RGB")
    elif original_image is not None:
        source_format = getattr(original_image, "format", None)
        final_image = original_image.convert("RGB") if hasattr(original_image, "convert") else original_image
    else:
        source_format = None

    if final_image is not None:
        # PIL's .convert() (and possibly .thumbnail()) return/mutate an
        # image whose `.format` attribute is None. trimesh's glTF exporter
        # uses `.format` to decide whether to keep a texture as JPEG or
        # re-encode it as PNG — without restoring it here, every JPEG
        # texture gets silently re-encoded as lossless PNG, which can
        # inflate a compressed photo texture by 5-10x. Re-apply it after
        # any operation that might have cleared it.
        final_image.format = source_format
        if max_texture_size and hasattr(final_image, "thumbnail"):
            final_image.thumbnail((max_texture_size, max_texture_size), Image.LANCZOS)
            final_image.format = source_format
        if original_uv is None:
            raise ValueError("The mesh has no UV coordinates — the texture cannot be mapped.")
        # Explicitly non-metallic/diffuse material: trimesh/OBJ materials
        # otherwise often end up with metallicFactor=1, which looks almost
        # black without an environment map.
        material = trimesh.visual.material.PBRMaterial(
            baseColorTexture=final_image,
            metallicFactor=0.0,
            roughnessFactor=1.0,
        )
        mesh.visual = trimesh.visual.TextureVisuals(uv=original_uv, image=final_image, material=material)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    extra_files: list[Path] = []

    if output_format == "glb":
        mesh.export(str(output_path.with_suffix(".glb")), file_type="glb")
        final_path = output_path.with_suffix(".glb")
    else:
        # Non-binary glTF writes several sibling files with generic names
        # (buffer .bin, material .png, ...) — isolate them in a subfolder
        # named after the output stem so repeated conversions don't clash.
        out_dir = output_path.parent / output_path.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        final_path = out_dir / (output_path.stem + ".gltf")
        before_files = set(out_dir.iterdir())
        mesh.export(str(final_path), file_type="gltf")
        after_files = set(out_dir.iterdir())
        extra_files = sorted(p for p in (after_files - before_files) if p != final_path)

    stats = {
        "vertices_before": before["vertices"],
        "faces_before": before["faces"],
        "vertices_after": after["vertices"],
        "faces_after": after["faces"],
    }
    return final_path, extra_files, stats


def compress_with_draco(model_path, output_path=None):
    """
    Compress a GLB/glTF's geometry with Draco (via the gltf-transform CLI).

    Returns (success: bool, message: str).
    """
    model_path = Path(model_path)
    output_path = Path(output_path) if output_path else model_path

    if shutil.which("gltf-transform") is None:
        return False, (
            "The 'gltf-transform' CLI was not found on PATH. "
            "Install it with: npm install -g @gltf-transform/cli"
        )

    tmp_out = output_path.with_name(output_path.stem + ".draco.tmp" + output_path.suffix)
    try:
        subprocess.run(
            [
                "gltf-transform",
                "draco",
                str(model_path),
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


def finalize_output(report: ConversionReport, dest_dir, dest_stem: str) -> Path:
    """
    Move a (typically temp-location) conversion result to its final
    destination directory, renaming the main file to `dest_stem`.

    For "glb" this just moves/renames the single file. For "gltf" the
    whole sibling-files subfolder is moved and the main .gltf file inside
    it is renamed (buffer/image filenames are left untouched since the
    glTF JSON references them by their existing names).
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    if report.output_format == "glb":
        dest_path = dest_dir / f"{dest_stem}.glb"
        shutil.move(str(report.output_path), str(dest_path))
        return dest_path

    src_dir = report.output_path.parent
    dest_subdir = dest_dir / dest_stem
    if dest_subdir.exists():
        shutil.rmtree(dest_subdir)
    shutil.move(str(src_dir), str(dest_subdir))
    new_main = dest_subdir / f"{dest_stem}.gltf"
    old_main = dest_subdir / report.output_path.name
    if old_main != new_main:
        old_main.rename(new_main)
    return new_main


def convert(
    obj_path,
    output_path,
    texture_path=None,
    mtl_path=None,
    output_format: str = "glb",
    use_draco: bool = True,
    max_texture_size: int | None = 2048,
    target_faces: int | None = None,
) -> ConversionReport:
    """
    Full OBJ (+MTL / JPG-PNG) -> GLB or glTF (+Draco) conversion.

    mtl_path is only used to include its size in the reported input size
    (trimesh follows the OBJ's own `mtllib` reference automatically when
    loading, so this does not need to point trimesh anywhere).

    Returns a ConversionReport.
    """
    obj_path = Path(obj_path)
    texture_path = Path(texture_path) if texture_path else None
    mtl_path = Path(mtl_path) if mtl_path else None

    input_size = obj_path.stat().st_size
    if texture_path is not None and texture_path.exists():
        input_size += texture_path.stat().st_size
    if mtl_path is not None and mtl_path.exists():
        input_size += mtl_path.stat().st_size

    final_path, extra_files, stats = obj_to_model(
        obj_path,
        output_path,
        texture_path=texture_path,
        output_format=output_format,
        max_texture_size=max_texture_size,
        target_faces=target_faces,
    )
    size_before_draco = final_path.stat().st_size

    draco_applied = False
    message = "Draco compression not requested."
    if use_draco:
        draco_applied, message = compress_with_draco(final_path)

    size_after = final_path.stat().st_size

    return ConversionReport(
        output_path=final_path,
        output_format=output_format,
        draco_applied=draco_applied,
        message=message,
        vertices_before=stats["vertices_before"],
        faces_before=stats["faces_before"],
        vertices_after=stats["vertices_after"],
        faces_after=stats["faces_after"],
        input_size_bytes=input_size,
        glb_size_before_draco_bytes=size_before_draco,
        glb_size_after_bytes=size_after,
        extra_files=extra_files,
    )
