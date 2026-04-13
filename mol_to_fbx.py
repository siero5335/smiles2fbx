"""
Blender Python script: molecule JSON → FBX (Stick / Ball-and-Stick model)
Usage: blender --background --python mol_to_fbx.py -- input.json output.fbx [options]

Options:
  --segments N     cylinder vertex count (default: 8)
  --scale F        global scale (default: 1.0)
  --radius F       stick radius (default: 0.06)
  --mode MODE      stick (default) | ball-and-stick
  --no-hydrogen    hide hydrogen atoms and their bonds
  --mono [HEX]     monochrome output (default: C0C0C0 silver)
  --metallic F     PBR metallic value 0.0-1.0 (default: 0.1, mono default: 0.9)
  --roughness F    PBR roughness value 0.0-1.0 (default: 0.4, mono default: 0.15)
"""

import bpy
import json
import sys
from mathutils import Vector


def fail(message):
    raise SystemExit(f"[ERROR] {message}")


# ---------- CLI args ----------
argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
else:
    argv = []

data_path = argv[0] if len(argv) > 0 else "molecule.json"
fbx_path = argv[1] if len(argv) > 1 else "molecule.fbx"

segments = 8
scale = 1.0
bond_radius = 0.06
mode = "stick"
show_hydrogen = True
mono_color = None       # None = CPK coloring, set to (r,g,b,a) for monochrome
metallic = None         # None = use defaults per mode
roughness = None


def parse_int(name, value, minimum):
    try:
        parsed = int(value)
    except ValueError as exc:
        fail(f"{name} must be an integer: {value}")
    if parsed < minimum:
        fail(f"{name} must be >= {minimum}: {value}")
    return parsed


def parse_float(name, value, minimum=None, maximum=None, inclusive_min=True):
    try:
        parsed = float(value)
    except ValueError as exc:
        fail(f"{name} must be a number: {value}")

    if minimum is not None:
        too_small = parsed < minimum if inclusive_min else parsed <= minimum
        if too_small:
            op = ">=" if inclusive_min else ">"
            fail(f"{name} must be {op} {minimum}: {value}")

    if maximum is not None and parsed > maximum:
        fail(f"{name} must be <= {maximum}: {value}")

    return parsed


def hex_to_rgba(h):
    """Convert hex string like 'C0C0C0' or '#C0C0C0' to (r,g,b,a) tuple."""
    h = h.lstrip("#")
    if len(h) != 6 or any(c not in "0123456789abcdefABCDEF" for c in h):
        fail(f"--mono expects a 6-digit hex color, got: {h}")
    return (int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255, 1.0)

i = 2
while i < len(argv):
    if argv[i] == "--segments" and i + 1 < len(argv):
        segments = parse_int("--segments", argv[i + 1], 3); i += 2
    elif argv[i] == "--scale" and i + 1 < len(argv):
        scale = parse_float("--scale", argv[i + 1], minimum=0.0, inclusive_min=False); i += 2
    elif argv[i] == "--radius" and i + 1 < len(argv):
        bond_radius = parse_float("--radius", argv[i + 1], minimum=0.0, inclusive_min=False); i += 2
    elif argv[i] == "--mode" and i + 1 < len(argv):
        mode = argv[i + 1]
        if mode not in {"stick", "ball-and-stick"}:
            fail(f"--mode must be 'stick' or 'ball-and-stick', got: {mode}")
        i += 2
    elif argv[i] == "--no-hydrogen":
        show_hydrogen = False; i += 1
    elif argv[i] == "--mono":
        # --mono with optional hex color
        if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            mono_color = hex_to_rgba(argv[i + 1]); i += 2
        else:
            mono_color = hex_to_rgba("C0C0C0"); i += 1  # silver default
    elif argv[i] == "--metallic" and i + 1 < len(argv):
        metallic = parse_float("--metallic", argv[i + 1], minimum=0.0, maximum=1.0); i += 2
    elif argv[i] == "--roughness" and i + 1 < len(argv):
        roughness = parse_float("--roughness", argv[i + 1], minimum=0.0, maximum=1.0); i += 2
    else:
        fail(f"Unknown or incomplete option: {argv[i]}")

# resolve PBR defaults based on mode
if mono_color is not None:
    if metallic is None: metallic = 0.9
    if roughness is None: roughness = 0.15
else:
    if metallic is None: metallic = 0.1
    if roughness is None: roughness = 0.4

# ---------- CPK colors ----------
ELEMENT_DATA = {
    "C":  {"radius": 0.30, "color": (0.20, 0.20, 0.20, 1.0)},
    "N":  {"radius": 0.28, "color": (0.12, 0.31, 0.94, 1.0)},
    "O":  {"radius": 0.27, "color": (0.90, 0.05, 0.05, 1.0)},
    "H":  {"radius": 0.18, "color": (0.90, 0.90, 0.90, 1.0)},
    "S":  {"radius": 0.35, "color": (0.90, 0.78, 0.13, 1.0)},
    "P":  {"radius": 0.33, "color": (1.00, 0.50, 0.00, 1.0)},
    "F":  {"radius": 0.25, "color": (0.56, 0.88, 0.31, 1.0)},
    "Cl": {"radius": 0.30, "color": (0.12, 0.94, 0.12, 1.0)},
    "Br": {"radius": 0.33, "color": (0.65, 0.16, 0.16, 1.0)},
    "I":  {"radius": 0.36, "color": (0.58, 0.00, 0.58, 1.0)},
}
DEFAULT_ELEM = {"radius": 0.30, "color": (0.75, 0.40, 0.75, 1.0)}


def load_molecule_data(path):
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        fail(f"Input file not found: {path}")
    except json.JSONDecodeError as exc:
        fail(f"Input file is not valid JSON: {path}")

    atoms = payload.get("atoms")
    bonds = payload.get("bonds")
    if not isinstance(atoms, list) or not isinstance(bonds, list):
        fail("Input JSON must contain 'atoms' and 'bonds' arrays")

    parsed_atoms = []
    for index, atom in enumerate(atoms):
        if not isinstance(atom, dict):
            fail(f"Atom entry {index} must be an object")
        element = atom.get("element")
        pos = atom.get("pos")
        if not isinstance(element, str) or not element:
            fail(f"Atom entry {index} has an invalid element")
        if not isinstance(pos, list) or len(pos) != 3:
            fail(f"Atom entry {index} must have a 3D 'pos' array")
        try:
            coords = tuple(float(value) for value in pos)
        except (TypeError, ValueError):
            fail(f"Atom entry {index} has non-numeric coordinates")
        parsed_atoms.append({"element": element, "pos": coords})

    parsed_bonds = []
    atom_count = len(parsed_atoms)
    for index, bond in enumerate(bonds):
        if not isinstance(bond, dict):
            fail(f"Bond entry {index} must be an object")
        try:
            a1 = int(bond["a1"])
            a2 = int(bond["a2"])
            order = int(bond["order"])
        except (KeyError, TypeError, ValueError):
            fail(f"Bond entry {index} must contain integer a1/a2/order fields")
        if not (0 <= a1 < atom_count and 0 <= a2 < atom_count):
            fail(f"Bond entry {index} references an atom index out of range")
        if order < 1:
            fail(f"Bond entry {index} must have order >= 1")
        parsed_bonds.append({"a1": a1, "a2": a2, "order": order})

    return parsed_atoms, parsed_bonds


# ---------- Blender helpers ----------
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)


def get_or_create_material(name, color):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def get_element_color(element):
    """Return element color, or mono_color if monochrome mode."""
    if mono_color is not None:
        return mono_color
    return ELEMENT_DATA.get(element, DEFAULT_ELEM)["color"]


def make_cylinder(p1, p2, radius, mat, offset=None):
    """Create a cylinder from p1 to p2 with given material."""
    if offset is None:
        offset = Vector((0, 0, 0))
    v1, v2 = Vector(p1) + offset, Vector(p2) + offset
    mid = (v1 + v2) / 2
    diff = v2 - v1
    length = diff.length
    if length < 1e-6:
        return None

    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius,
        depth=length,
        vertices=segments,
        location=mid,
    )
    obj = bpy.context.active_object
    direction = diff.normalized()
    rot_quat = Vector((0, 0, 1)).rotation_difference(direction)
    obj.rotation_euler = rot_quat.to_euler()
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return obj


def compute_bond_offsets(diff, order):
    """Return list of offset vectors for single/double/triple bonds."""
    if order == 1:
        return [Vector((0, 0, 0))]
    perp = diff.cross(Vector((0, 0, 1)))
    if perp.length < 1e-6:
        perp = diff.cross(Vector((0, 1, 0)))
    perp.normalize()
    if order == 2:
        d = perp * 0.10 * scale
        return [d, -d]
    elif order >= 3:
        d = perp * 0.13 * scale
        return [Vector((0, 0, 0)), d, -d]
    return [Vector((0, 0, 0))]


# ---------- Main ----------
def main():
    clear_scene()
    atoms, bonds = load_molecule_data(data_path)
    all_objects = []

    # -- Atoms (ball-and-stick mode only) --
    if mode == "ball-and-stick":
        for atom in atoms:
            if not show_hydrogen and atom["element"] == "H":
                continue
            info = ELEMENT_DATA.get(atom["element"], DEFAULT_ELEM)
            r = info["radius"] * scale
            pos = tuple(c * scale for c in atom["pos"])
            bpy.ops.mesh.primitive_uv_sphere_add(
                radius=r, segments=segments, ring_count=segments // 2, location=pos
            )
            obj = bpy.context.active_object
            obj.name = f"Atom_{atom['element']}"
            color = get_element_color(atom["element"])
            mat_name = "Mat_Mono" if mono_color else f"Mat_{atom['element']}"
            mat = get_or_create_material(mat_name, color)
            obj.data.materials.append(mat)
            bpy.ops.object.shade_smooth()
            all_objects.append(obj)

    # -- Bonds --
    for bond in bonds:
        elem1 = atoms[bond["a1"]]["element"]
        elem2 = atoms[bond["a2"]]["element"]

        if not show_hydrogen and (elem1 == "H" or elem2 == "H"):
            continue

        p1 = Vector(tuple(c * scale for c in atoms[bond["a1"]]["pos"]))
        p2 = Vector(tuple(c * scale for c in atoms[bond["a2"]]["pos"]))
        mid = (p1 + p2) / 2
        diff = p2 - p1
        offsets = compute_bond_offsets(diff, bond["order"])
        r = bond_radius * scale

        if mono_color is not None:
            # monochrome: single cylinder per bond (no midpoint split)
            mat = get_or_create_material("Mat_Mono", mono_color)
            for off in offsets:
                obj = make_cylinder(p1, p2, r, mat, off)
                if obj:
                    obj.name = "Bond"
                    all_objects.append(obj)
        else:
            # CPK half-bond coloring
            color1 = get_element_color(elem1)
            color2 = get_element_color(elem2)
            mat1 = get_or_create_material(f"Mat_{elem1}", color1)
            mat2 = get_or_create_material(f"Mat_{elem2}", color2)
            for off in offsets:
                obj = make_cylinder(p1, mid, r, mat1, off)
                if obj:
                    obj.name = f"Bond_{elem1}"
                    all_objects.append(obj)
                obj = make_cylinder(mid, p2, r, mat2, off)
                if obj:
                    obj.name = f"Bond_{elem2}"
                    all_objects.append(obj)

    if not all_objects:
        print("[WARN] No geometry created")
        return

    # -- Join all into single mesh --
    bpy.ops.object.select_all(action="DESELECT")
    for obj in all_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = all_objects[0]
    bpy.ops.object.join()
    bpy.context.active_object.name = "Molecule"
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # -- Export FBX --
    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=True,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        mesh_smooth_type="FACE",
    )
    print(f"[OK] Exported: {fbx_path}")


main()
