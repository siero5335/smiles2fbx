#!/usr/bin/env bash
# Export the bundled chemical CSV datasets into FBX batches.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BATCH_SCRIPT="${SCRIPT_DIR}/smiles2fbx_batch.py"

OUTPUT_ROOT="${1:-/Users/a_eguchi/Documents/GitHub/exported_fbx }"
STICK_RADIUS="${2:-0.2}"

DATASETS=(
  "toxic_environmental_chemicals.csv"
  "famous_poisons.csv"
)

if [[ ! -f "${BATCH_SCRIPT}" ]]; then
  echo "[ERROR] Batch script not found: ${BATCH_SCRIPT}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_ROOT}"

overall_status=0
for dataset in "${DATASETS[@]}"; do
  csv_path="${SCRIPT_DIR}/${dataset}"
  if [[ ! -f "${csv_path}" ]]; then
    echo "[ERROR] CSV not found: ${csv_path}" >&2
    exit 1
  fi

  dataset_name="${dataset%.csv}"
  outdir="${OUTPUT_ROOT%/}/${dataset_name}"

  echo "[INFO] Exporting ${dataset} -> ${outdir} (radius=${STICK_RADIUS})"
  set +e
  python3 "${BATCH_SCRIPT}" "${csv_path}" "${outdir}" -- --radius "${STICK_RADIUS}"
  batch_status=$?
  set -e
  if [[ ${batch_status} -ne 0 ]]; then
    overall_status=1
    echo "[WARN] ${dataset} completed with some failed rows. See ${outdir}/batch_results.csv" >&2
  fi
done

echo "[OK] All exports completed under: ${OUTPUT_ROOT}"
exit "${overall_status}"
