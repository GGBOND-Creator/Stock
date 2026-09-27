from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_model.human_need_network import load_network, observations_from_source_rows


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "data" / "human_need_network" / "source_registry.csv"
DEFAULT_OUTPUT = ROOT / "data" / "human_need_network" / "resource_endowment_observations_imported.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import archived resource observations after source admission checks.")
    parser.add_argument("--input", required=True, help="Archived CSV with SOURCE_OBSERVATION_COLUMNS.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()

    input_path = Path(args.input)
    registry = pd.read_csv(args.registry, dtype=str, keep_default_na=False)
    rows = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    tables = load_network(ROOT / "data" / "human_need_network")
    imported = observations_from_source_rows(
        rows,
        registry,
        as_of=args.as_of,
        material_resource_ids=set(tables.material_resources["resource_id"]),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    imported.to_csv(output, index=False, encoding="utf-8-sig")
    metadata = {
        "schema_version": "resource_observation_source_v1",
        "input": str(input_path),
        "input_sha256": sha256(input_path),
        "registry": str(Path(args.registry)),
        "as_of": args.as_of,
        "rows_written": int(len(imported)),
        "status": "imported",
    }
    output.with_suffix(output.suffix + ".meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(imported)} resource observations to {output}")


if __name__ == "__main__":
    main()
