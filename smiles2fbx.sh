#!/usr/bin/env bash
# smiles2fbx.sh — SMILES → FBX one-shot converter
# 依存: python3 + rdkit, blender (3.x / 4.x)
#
# Usage:
#   ./smiles2fbx.sh "CCO" ethanol.fbx
#   ./smiles2fbx.sh "c1ccccc1" benzene.fbx --no-hydrogen --scale 0.5
#   ./smiles2fbx.sh "CCO" ethanol.fbx --mode ball-and-stick
#
# Options (Blender側に渡される):
#   --segments N   シリンダーの分割数 (default: 8)
#   --scale F      全体スケール (default: 1.0)
#   --radius F     棒の太さ (default: 0.06)
#   --mode MODE    stick (default) | ball-and-stick
#   --no-hydrogen  水素を非表示
#   --mono [HEX]   モノクローム出力 (default: C0C0C0 シルバー)
#   --metallic F   PBR metallic 0.0-1.0
#   --roughness F  PBR roughness 0.0-1.0

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

resolve_blender() {
  if [[ -n "${BLENDER_PATH:-}" ]]; then
    if [[ -x "${BLENDER_PATH}" ]]; then
      printf '%s\n' "${BLENDER_PATH}"
      return 0
    fi
    echo "BLENDER_PATH is set but not executable: ${BLENDER_PATH}" >&2
    exit 1
  fi

  if command -v blender >/dev/null 2>&1; then
    command -v blender
    return 0
  fi

  if [[ -x "/Applications/Blender.app/Contents/MacOS/Blender" ]]; then
    printf '%s\n' "/Applications/Blender.app/Contents/MacOS/Blender"
    return 0
  fi

  cat >&2 <<'EOF'
Blender executable was not found.

Try one of these:
  export BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/Blender
  export PATH="/Applications/Blender.app/Contents/MacOS:$PATH"

Cut-down diagnostic:
  blender --background --python-expr "print('headless ok')"
EOF
  exit 1
}

BLENDER="$(resolve_blender)"

SMILES="${1:?Usage: $0 SMILES output.fbx [--segments N] [--scale F]}"
FBX_OUT="${2:?Usage: $0 SMILES output.fbx [--segments N] [--scale F]}"
shift 2

# temp dir
TMPDIR="$(mktemp -d)"
MOLECULE_JSON="${TMPDIR}/molecule.json"
trap 'rm -rf "$TMPDIR"' EXIT

# 1) SMILES → molecule JSON (RDKit)
python3 - "$SMILES" "$MOLECULE_JSON" <<'PY'
from rdkit import Chem
from rdkit.Chem import AllChem
import json
import sys

smiles = sys.argv[1]
json_path = sys.argv[2]

mol = Chem.MolFromSmiles(smiles)
if mol is None:
    raise ValueError(f"Invalid SMILES: {smiles}")

mol = Chem.AddHs(mol)
params = AllChem.ETKDGv3()
params.randomSeed = 0xF00D

embed_status = AllChem.EmbedMolecule(mol, params)
if embed_status != 0:
    raise RuntimeError(f"3D embedding failed for SMILES: {smiles}")

if AllChem.MMFFHasAllMoleculeParams(mol):
    optimize_status = AllChem.MMFFOptimizeMolecule(mol)
    if optimize_status == -1:
        raise RuntimeError(f"MMFF optimization failed for SMILES: {smiles}")
else:
    optimize_status = AllChem.UFFOptimizeMolecule(mol)
    if optimize_status == -1:
        raise RuntimeError(f"UFF optimization failed for SMILES: {smiles}")

conf = mol.GetConformer()
atoms = []
for atom in mol.GetAtoms():
    pos = conf.GetAtomPosition(atom.GetIdx())
    atoms.append(
        {
            "element": atom.GetSymbol(),
            "pos": [pos.x, pos.y, pos.z],
        }
    )

bonds = []
for bond in mol.GetBonds():
    bonds.append(
        {
            "a1": bond.GetBeginAtomIdx(),
            "a2": bond.GetEndAtomIdx(),
            "order": int(bond.GetBondTypeAsDouble()),
        }
    )

with open(json_path, "w", encoding="utf-8") as f:
    json.dump({"atoms": atoms, "bonds": bonds}, f)

print(f"[OK] Molecule data generated: {json_path}")
PY

# 2) Molecule JSON → FBX (Blender headless)
echo "[INFO] Using Blender: ${BLENDER}"
set +e
"$BLENDER" --background --python "${SCRIPT_DIR}/mol_to_fbx.py" -- "$MOLECULE_JSON" "$FBX_OUT" "$@"
blender_status=$?
set -e

if [[ ${blender_status} -ne 0 ]]; then
  cat >&2 <<EOF
[ERROR] Blender headless execution failed with exit code ${blender_status}.

Quick checks:
  ${BLENDER} --background --python-expr "print('headless ok')"

If that command also crashes, the issue is Blender itself rather than smiles2fbx.
On macOS, using an LTS build is the safest workaround for automation:
  https://www.blender.org/download/lts/

You can point this script at another Blender build explicitly:
  BLENDER_PATH="/path/to/Blender.app/Contents/MacOS/Blender" bash smiles2fbx.sh "CCO" out.fbx
EOF
  exit "${blender_status}"
fi

echo "=== Done: ${FBX_OUT} ==="
