#!/usr/bin/env python3
"""Batch convert molecules from CSV rows into FBX files."""

import argparse
import csv
import os
import re
import subprocess
import sys
from pathlib import Path


COLUMN_ALIASES = {
    "name": ("name", "compound", "compound_name", "molecule", "molecule_name", "名前"),
    "smiles": ("smiles",),
    "feature": ("feature", "features", "note", "notes", "category", "特徴"),
}


def fail(message):
    print(f"[ERROR] {message}", file=sys.stderr)
    raise SystemExit(1)


def slugify(value):
    # Keep multibyte text intact and only replace filesystem-hostile characters.
    slug = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value.strip())
    slug = slug.strip("._- ")
    return slug


def resolve_column(fieldnames, explicit_name, aliases, required):
    if explicit_name:
        if explicit_name not in fieldnames:
            fail(f"CSV column not found: {explicit_name}")
        return explicit_name

    field_lookup = {name.lower(): name for name in fieldnames}
    for alias in aliases:
        actual = field_lookup.get(alias.lower())
        if actual is not None:
            return actual

    if required:
        fail(
            f"Required CSV column was not found. Tried: {', '.join(aliases)}. "
            f"Available columns: {', '.join(fieldnames)}"
        )
    return None


def build_output_path(outdir, row_number, name_value, feature_value, used_paths, overwrite):
    parts = []
    for value in (name_value, feature_value):
        if value:
            slug = slugify(value)
            if slug:
                parts.append(slug)

    stem = "__".join(parts) if parts else f"row_{row_number:04d}"
    candidate = outdir / f"{stem}.fbx"

    if overwrite:
        return candidate

    suffix = 2
    while candidate in used_paths or candidate.exists():
        candidate = outdir / f"{stem}_{suffix}.fbx"
        suffix += 1
    return candidate


def parse_args():
    parser = argparse.ArgumentParser(
        description="Batch convert CSV rows (name/smiles/feature) into FBX files."
    )
    parser.add_argument("csv_path", help="Input CSV path")
    parser.add_argument("outdir", help="Directory for generated FBX files")
    parser.add_argument("--name-column", help="CSV column name for the molecule name")
    parser.add_argument("--smiles-column", help="CSV column name for the SMILES string")
    parser.add_argument("--feature-column", help="CSV column name for the feature/note")
    parser.add_argument(
        "--results-csv",
        help="Optional path for a results CSV. Defaults to <outdir>/batch_results.csv",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output filenames instead of suffixing them",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop the batch as soon as one row fails",
    )
    parser.add_argument(
        "converter_args",
        nargs=argparse.REMAINDER,
        help="Pass-through options for smiles2fbx.sh after '--'",
    )
    return parser.parse_args()


def main():
    raw_argv = sys.argv[1:]
    args = parse_args()
    converter_args = list(args.converter_args)
    if converter_args and converter_args[0] == "--":
        converter_args = converter_args[1:]
    elif converter_args and converter_args[0].startswith("-") and "--" not in raw_argv:
        print(
            "[WARN] Pass-through converter options are usually placed after '--' "
            "to avoid future option-name collisions.",
            file=sys.stderr,
        )

    repo_dir = Path(__file__).resolve().parent
    converter = repo_dir / "smiles2fbx.sh"
    csv_path = Path(args.csv_path).expanduser().resolve()
    outdir = Path(args.outdir).expanduser().resolve()
    results_csv = (
        Path(args.results_csv).expanduser().resolve()
        if args.results_csv
        else outdir / "batch_results.csv"
    )

    if not csv_path.exists():
        fail(f"CSV file not found: {csv_path}")
    if not converter.exists():
        fail(f"Converter script not found: {converter}")

    outdir.mkdir(parents=True, exist_ok=True)

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            fail("CSV must have a header row")

        fieldnames = reader.fieldnames
        name_column = resolve_column(
            fieldnames, args.name_column, COLUMN_ALIASES["name"], required=False
        )
        smiles_column = resolve_column(
            fieldnames, args.smiles_column, COLUMN_ALIASES["smiles"], required=True
        )
        feature_column = resolve_column(
            fieldnames, args.feature_column, COLUMN_ALIASES["feature"], required=False
        )

        rows = list(reader)

    used_paths = set()
    results = []
    success_count = 0

    for row_number, row in enumerate(rows, start=1):
        smiles_value = (row.get(smiles_column) or "").strip()
        name_value = (row.get(name_column) or "").strip() if name_column else ""
        feature_value = (row.get(feature_column) or "").strip() if feature_column else ""

        if not smiles_value:
            result = {
                "row": row_number,
                "status": "error",
                "name": name_value,
                "feature": feature_value,
                "smiles": smiles_value,
                "output_path": str(
                    build_output_path(
                        outdir,
                        row_number,
                        name_value,
                        feature_value,
                        used_paths,
                        args.overwrite,
                    )
                ),
                "message": f"Missing SMILES in column '{smiles_column}'",
            }
            results.append(result)
            print(f"[ERROR] row {row_number}: missing SMILES", file=sys.stderr)
            if args.stop_on_error:
                break
            continue

        output_path = build_output_path(
            outdir, row_number, name_value, feature_value, used_paths, args.overwrite
        )
        used_paths.add(output_path)

        command = [str(converter), smiles_value, str(output_path), *converter_args]
        completed = subprocess.run(
            command,
            cwd=str(repo_dir),
            env=os.environ.copy(),
            text=True,
            capture_output=True,
        )

        if completed.returncode == 0:
            success_count += 1
            print(
                f"[OK] row {row_number}: "
                f"{name_value or output_path.stem} -> {output_path.name}"
            )
            message = completed.stdout.strip()
            status = "ok"
        else:
            print(
                f"[ERROR] row {row_number}: "
                f"{name_value or output_path.stem} failed",
                file=sys.stderr,
            )
            message = (completed.stderr or completed.stdout).strip()
            status = "error"

        results.append(
            {
                "row": row_number,
                "status": status,
                "name": name_value,
                "feature": feature_value,
                "smiles": smiles_value,
                "output_path": str(output_path),
                "message": message,
            }
        )

        if completed.returncode != 0 and args.stop_on_error:
            break

    with results_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=("row", "status", "name", "feature", "smiles", "output_path", "message"),
        )
        writer.writeheader()
        writer.writerows(results)

    print(
        f"[SUMMARY] {success_count}/{len(rows)} row(s) succeeded. "
        f"Results CSV: {results_csv}"
    )

    if success_count != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
