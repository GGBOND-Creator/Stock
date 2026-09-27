from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from stock_model.human_need_network import (
    CARRIER_COLUMNS,
    ENDOWMENT_COLUMNS,
    HumanNeedNetworkTables,
    SCHEMA_VERSION,
    build_snapshot,
    graph_records,
    load_network,
    observations_from_source_rows,
    validate_source_registry,
    validate_network_tables,
)


ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "data" / "human_need_network"


class HumanNeedNetworkTests(unittest.TestCase):
    def test_seed_has_human_need_root_and_no_carrier_root(self) -> None:
        tables = load_network(SEED_DIR)
        self.assertEqual(SCHEMA_VERSION, "human_need_resource_network_v2")
        roots = tables.needs[tables.needs["parent_need_id"] == ""]
        self.assertEqual(list(roots["need_id"]), ["NEED_HUMAN_BIOLOGICAL_CONTINUITY"])
        self.assertIn("NEED_BASIC_NUTRITION", set(tables.needs["need_id"]))
        self.assertTrue(tables.process_carrier_mappings.empty)
        nodes, edges = graph_records(build_snapshot(tables, as_of="2026-08-18T12:00:00Z", include_candidates=True))
        self.assertIn("need", {node["type"] for node in nodes})
        self.assertTrue(any(edge["source"] == "NEED_HUMAN_BIOLOGICAL_CONTINUITY" for edge in edges))

    def test_taxonomy_covers_material_and_spiritual_biological_domains(self) -> None:
        tables = load_network(SEED_DIR)
        domains = set(tables.needs["need_domain"])
        natures = set(tables.needs["need_nature"])
        self.assertIn("material_homeostasis", domains)
        self.assertIn("symbolic_spiritual", domains)
        self.assertIn("material", natures)
        self.assertIn("spiritual_emergent", natures)
        self.assertGreaterEqual(len(tables.needs), 40)
        self.assertFalse((tables.needs["population_scope"] == "").any())

    def test_every_need_is_connected_to_population_root(self) -> None:
        tables = load_network(SEED_DIR)
        parent = dict(zip(tables.needs["need_id"], tables.needs["parent_need_id"]))
        root = "NEED_HUMAN_BIOLOGICAL_CONTINUITY"
        for need_id in parent:
            current = need_id
            for _ in range(len(parent) + 1):
                if current == root:
                    break
                current = parent[current]
            self.assertEqual(current, root, need_id)

    def test_candidate_dependencies_are_not_verified_by_default(self) -> None:
        tables = load_network(SEED_DIR)
        snapshot = build_snapshot(tables, as_of="2026-08-18T12:00:00Z")
        self.assertTrue(snapshot.process_resource_dependencies.empty)
        with_candidates = build_snapshot(tables, as_of="2026-08-18T12:00:00Z", include_candidates=True)
        self.assertEqual(len(with_candidates.process_resource_dependencies), 6)

    def test_future_resource_observation_does_not_leak(self) -> None:
        tables = load_network(SEED_DIR)
        future = tables.resource_endowment_observations.iloc[0].copy()
        future["observation_id"] = "future"
        future["available_time"] = "2026-08-20T00:00:00Z"
        future["quantity"] = "10"
        future["unit"] = "million tonnes"
        future["quality_status"] = "observed"
        future["source_status"] = "imported"
        tables.resource_endowment_observations = pd.concat(
            [tables.resource_endowment_observations, pd.DataFrame([future], columns=ENDOWMENT_COLUMNS)],
            ignore_index=True,
        )
        before = build_snapshot(tables, as_of="2026-08-19T00:00:00Z", include_candidates=True)
        after = build_snapshot(tables, as_of="2026-08-21T00:00:00Z", include_candidates=True)
        self.assertNotIn("future", set(before.resource_endowment_observations["observation_id"]))
        self.assertIn("future", set(after.resource_endowment_observations["observation_id"]))

    def test_empty_quantity_cannot_become_zero(self) -> None:
        tables = load_network(SEED_DIR)
        bad = tables.resource_endowment_observations.copy()
        bad.loc[0, "quality_status"] = "observed"
        with self.assertRaisesRegex(ValueError, "empty resource quantity"):
            validate_network_tables(
                HumanNeedNetworkTables(
                    tables.needs,
                    tables.satisfaction_functions,
                    tables.transformation_processes,
                    tables.material_resources,
                    tables.need_function_edges,
                    tables.function_process_edges,
                    tables.process_resource_dependencies,
                    bad,
                    tables.process_carrier_mappings,
                )
            )

    def test_carrier_mapping_cannot_point_to_need_root(self) -> None:
        tables = load_network(SEED_DIR)
        row = {
            column: "" for column in CARRIER_COLUMNS
        }
        row.update({
            "mapping_id": "MAP_BAD",
            "process_id": "PROCESS_PIG_PRODUCTION",
            "carrier_type": "need",
            "carrier_id": "NEED_BASIC_NUTRITION",
            "carrier_name": "基本营养需求",
            "available_time": "2026-08-18T00:00:00Z",
            "event_time": "2026-08-18T00:00:00Z",
            "valid_from": "2026-08-18T00:00:00Z",
            "source_status": "candidate_needs_evidence",
        })
        tables.process_carrier_mappings = pd.DataFrame([row], columns=CARRIER_COLUMNS)
        with self.assertRaisesRegex(ValueError, "carrier mappings"):
            validate_network_tables(tables)

    def test_candidate_source_cannot_create_observation(self) -> None:
        tables = load_network(SEED_DIR)
        registry = pd.read_csv(SEED_DIR / "source_registry.csv", dtype=str, keep_default_na=False)
        rows = pd.DataFrame([
            {
                "source_id": "SRC_FEED_GRAIN_FAOSTAT",
                "source_record_id": "fixture-1",
                "resource_id": "RES_FEED_GRAINS",
                "geographic_unit_id": "CN",
                "geographic_unit_name": "China",
                "observation_time": "2025-12-31T00:00:00Z",
                "available_time": "2026-08-19T00:00:00Z",
                "quantity": "100",
                "unit": "million tonnes",
                "measurement_scope": "production",
                "renewability": "partly_renewable",
                "accessibility": "unknown",
                "quality_status": "observed",
                "evidence_kind": "official_table",
                "confidence": "source_import_pending",
                "notes": "fixture",
            }
        ])
        with self.assertRaisesRegex(ValueError, "imported or verified"):
            observations_from_source_rows(
                rows, registry, as_of="2026-08-20T00:00:00Z",
                material_resource_ids=set(tables.material_resources["resource_id"]),
            )

    def test_imported_source_observation_preserves_time_and_unit(self) -> None:
        tables = load_network(SEED_DIR)
        registry = pd.read_csv(SEED_DIR / "source_registry.csv", dtype=str, keep_default_na=False)
        registry.loc[registry["source_id"] == "SRC_FEED_GRAIN_FAOSTAT", "source_status"] = "imported"
        rows = pd.DataFrame([
            {
                "source_id": "SRC_FEED_GRAIN_FAOSTAT", "source_record_id": "fixture-2",
                "resource_id": "RES_FEED_GRAINS", "geographic_unit_id": "CN",
                "geographic_unit_name": "China", "observation_time": "2025-12-31T00:00:00Z",
                "available_time": "2026-08-19T00:00:00Z", "quantity": "100",
                "unit": "million tonnes", "measurement_scope": "production",
                "renewability": "partly_renewable", "accessibility": "unknown",
                "quality_status": "observed", "evidence_kind": "official_table",
                "confidence": "imported", "notes": "fixture",
            }
        ])
        result = observations_from_source_rows(
            rows, registry, as_of="2026-08-20T00:00:00Z",
            material_resource_ids=set(tables.material_resources["resource_id"]),
        )
        self.assertEqual(result.iloc[0]["quantity"], "100")
        self.assertEqual(result.iloc[0]["unit"], "million tonnes")
        self.assertEqual(result.iloc[0]["source_status"], "imported")

    def test_observation_cannot_be_available_before_observation(self) -> None:
        tables = load_network(SEED_DIR)
        registry = pd.read_csv(SEED_DIR / "source_registry.csv", dtype=str, keep_default_na=False)
        registry.loc[registry["source_id"] == "SRC_FEED_GRAIN_FAOSTAT", "source_status"] = "imported"
        rows = pd.DataFrame([{
            "source_id": "SRC_FEED_GRAIN_FAOSTAT", "source_record_id": "fixture-3",
            "resource_id": "RES_FEED_GRAINS", "geographic_unit_id": "CN", "geographic_unit_name": "China",
            "observation_time": "2026-08-20T00:00:00Z", "available_time": "2026-08-19T00:00:00Z",
            "quantity": "100", "unit": "million tonnes", "measurement_scope": "production",
            "renewability": "partly_renewable", "accessibility": "unknown", "quality_status": "observed",
            "evidence_kind": "official_table", "confidence": "imported", "notes": "fixture",
        }])
        with self.assertRaisesRegex(ValueError, "earlier than observation"):
            observations_from_source_rows(
                rows, registry, as_of="2026-08-21T00:00:00Z",
                material_resource_ids=set(tables.material_resources["resource_id"]),
            )


if __name__ == "__main__":
    unittest.main()
