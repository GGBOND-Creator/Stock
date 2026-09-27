from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from stock_model.network_signals import (
    DEFAULT_SIGNAL_TYPES,
    EDGE_COLUMNS,
    EVIDENCE_COLUMNS,
    EVENT_COLUMNS,
    RULE_COLUMNS,
    SIGNAL_TYPE_COLUMNS,
    approved_production_mappings_to_signal_bundle,
    build_signal_snapshot,
    initialize_signal_store,
    lifecycle_status_observations_to_signal_events,
    merge_signal_evidence,
    merge_signal_events,
    merge_lifecycle_status_signals,
    szse_a_share_list_evidence,
)


SIGNAL_TYPES = pd.DataFrame(
    [
        {
            "signal_type": "risk.warning",
            "display_name": "风险",
            "description": "fixture",
            "default_unit": "signal_unit",
            "polarity": "nonnegative",
            "display_color": "#c00",
            "display_channel": "halo",
            "default_half_life_days": pd.NA,
            "evidence_status": "fixture",
            "quality_status": "fixture",
        }
    ],
    columns=SIGNAL_TYPE_COLUMNS,
)


def event(**overrides: object) -> pd.DataFrame:
    row = {
        "signal_event_id": "e1",
        "emitter_object_type": "company",
        "emitter_object_id": "A",
        "signal_type": "risk.warning",
        "initial_strength": 8.0,
        "unit": "signal_unit",
        "event_time": "2026-01-01T00:00:00Z",
        "available_time": "2026-01-01T00:00:00Z",
        "effective_time": "2026-01-01T00:00:00Z",
        "expires_time": pd.NaT,
        "half_life_days": 2.0,
        "decay_method": "exponential_half_life",
        "source": "fixture",
        "source_record_id": "fixture",
        "evidence_kind": "observation",
        "confidence": 1.0,
        "quality_status": "verified_fixture",
    }
    row.update(overrides)
    return pd.DataFrame([row], columns=EVENT_COLUMNS)


def edges(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=EDGE_COLUMNS)


def rule(**overrides: object) -> pd.DataFrame:
    row = {
        "rule_id": "r1",
        "signal_type": "risk.warning",
        "relation_type": "supplier",
        "direction": "forward",
        "attenuation": 0.5,
        "delay_days": 1.0,
        "max_hops": 2,
        "valid_from": "2026-01-01T00:00:00Z",
        "valid_to": pd.NaT,
        "available_time": "2026-01-01T00:00:00Z",
        "evidence_kind": "assumption",
        "method": "fixture",
        "quality_status": "hypothesis",
    }
    row.update(overrides)
    return pd.DataFrame([row], columns=RULE_COLUMNS)


class NetworkSignalTests(unittest.TestCase):
    def test_approved_producer_mapping_separates_raw_fact_and_display_strength(self) -> None:
        activities = pd.DataFrame(
            [
                {
                    "activity_id": "activity-1",
                    "company_id": "COMPANY_A",
                    "activity_text": "生猪的养殖与销售。",
                    "available_time": "2026-02-01T00:00:00Z",
                    "source": "CNINFO profile",
                    "source_record_id": "profile-1",
                }
            ]
        )
        products = pd.DataFrame(
            [{"product_id": "PRODUCT_PIG", "canonical_name": "生猪"}]
        )
        mappings = pd.DataFrame(
            [
                {
                    "mapping_id": "mapping-producer",
                    "activity_id": "activity-1",
                    "company_id": "COMPANY_A",
                    "product_id": "PRODUCT_PIG",
                    "role": "producer",
                    "evidence_quote": "生猪的养殖与销售",
                    "available_time": "2026-02-02T00:00:00Z",
                    "review_status": "approved",
                    "reviewer": "fixture-reviewer",
                    "reviewed_at": "2026-02-03T00:00:00Z",
                    "confidence": "human_reviewed_exact_text_match",
                }
            ]
        )
        events, evidence = approved_production_mappings_to_signal_bundle(
            activities, products, mappings, mapping_ids=["mapping-producer"]
        )
        self.assertEqual(events.iloc[0]["initial_strength"], 1.0)
        self.assertEqual(events.iloc[0]["available_time"], "2026-02-03T00:00:00+00:00")
        self.assertTrue(pd.isna(evidence.iloc[0]["raw_numeric_value"]))
        self.assertEqual(evidence.iloc[0]["raw_unit"], "not_reported")
        self.assertEqual(evidence.iloc[0]["raw_text"], "生猪的养殖与销售")

        signal_types = pd.DataFrame(DEFAULT_SIGNAL_TYPES, columns=SIGNAL_TYPE_COLUMNS)
        objects = pd.DataFrame([{"object_type": "company", "object_id": "COMPANY_A"}])
        before = build_signal_snapshot(
            events,
            pd.DataFrame(columns=RULE_COLUMNS),
            pd.DataFrame(columns=EDGE_COLUMNS),
            as_of="2026-02-02T23:59:59Z",
            signal_types=signal_types,
            objects=objects,
        )
        after = build_signal_snapshot(
            events,
            pd.DataFrame(columns=RULE_COLUMNS),
            pd.DataFrame(columns=EDGE_COLUMNS),
            as_of="2026-02-03T00:00:00Z",
            signal_types=signal_types,
            objects=objects,
        )
        before_value = before.loc[
            before["signal_type"] == "production.activity", "concentration"
        ].iloc[0]
        after_value = after.loc[
            after["signal_type"] == "production.activity", "concentration"
        ].iloc[0]
        self.assertEqual(before_value, 0.0)
        self.assertEqual(after_value, 1.0)

    def test_unapproved_or_non_producer_mapping_cannot_emit_production_signal(self) -> None:
        activities = pd.DataFrame(
            [
                {
                    "activity_id": "activity-1",
                    "company_id": "COMPANY_A",
                    "activity_text": "生猪的养殖与销售。",
                    "available_time": "2026-02-01T00:00:00Z",
                    "source": "CNINFO profile",
                    "source_record_id": "profile-1",
                }
            ]
        )
        products = pd.DataFrame(
            [{"product_id": "PRODUCT_PIG", "canonical_name": "生猪"}]
        )
        base = {
            "mapping_id": "mapping-1",
            "activity_id": "activity-1",
            "company_id": "COMPANY_A",
            "product_id": "PRODUCT_PIG",
            "role": "producer",
            "evidence_quote": "生猪的养殖与销售",
            "available_time": "2026-02-02T00:00:00Z",
            "review_status": "pending_human_review",
            "reviewer": pd.NA,
            "reviewed_at": pd.NA,
            "confidence": "candidate",
        }
        with self.assertRaises(ValueError):
            approved_production_mappings_to_signal_bundle(
                activities, products, pd.DataFrame([base]), mapping_ids=["mapping-1"]
            )
        seller = dict(base, role="seller", review_status="approved", reviewed_at="2026-02-03T00:00:00Z")
        with self.assertRaises(ValueError):
            approved_production_mappings_to_signal_bundle(
                activities, products, pd.DataFrame([seller]), mapping_ids=["mapping-1"]
            )

    def test_signal_store_initialization_does_not_overwrite_existing_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            initialize_signal_store(directory)
            meta_path = directory / "signal_store.meta.json"
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            metadata["verification_marker"] = "preserve"
            meta_path.write_text(
                json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
            )
            store = initialize_signal_store(directory)
            reloaded = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(reloaded["verification_marker"], "preserve")
            self.assertTrue(store.evidence.empty)

    def test_szse_a_share_list_requires_exact_code_and_name(self) -> None:
        signal_id = "SIGNAL_LIFECYCLE_fixture"
        payload = [
            {
                "metadata": {"subname": "2026-08-18 ", "recordcount": 1},
                "data": [
                    {
                        "bk": "主板",
                        "agdm": "002714",
                        "agjc": "<a><u>牧原股份</u></a>",
                        "agssrq": "2014-01-28",
                    }
                ],
            }
        ]
        evidence = szse_a_share_list_evidence(
            payload,
            signal_event_id=signal_id,
            symbol="002714",
            expected_name="牧原股份",
            fetched_at="2026-08-18T06:00:00Z",
            source_locator="fixture.json",
        )
        self.assertEqual(evidence.iloc[0]["claim_value"], "listed_on_a_share_list")
        self.assertEqual(
            evidence.iloc[0]["quality_status"],
            "official_source_exact_code_and_name_match",
        )
        with self.assertRaises(ValueError):
            szse_a_share_list_evidence(
                payload,
                signal_event_id=signal_id,
                symbol="002714",
                expected_name="错误名称",
                fetched_at="2026-08-18T06:00:00Z",
                source_locator="fixture.json",
            )

    def test_official_evidence_merge_is_idempotent_and_marks_signal(self) -> None:
        signals = lifecycle_status_observations_to_signal_events(
            pd.DataFrame(
                [
                    {
                        "event_id": "active",
                        "listing_id": "LISTING_A",
                        "event_type": "status_observed_active",
                        "event_time": "2026-08-16T00:00:00Z",
                        "available_time": "2026-08-16T00:00:00Z",
                        "effective_time": "2026-08-16T00:00:00Z",
                        "source": "fixture",
                        "evidence_kind": "observation",
                        "availability_quality": "observed_at_fetch_time",
                        "source_status": "imported_unverified",
                    }
                ]
            )
        )
        signal_id = signals.iloc[0]["signal_event_id"]
        evidence = pd.DataFrame(
            [
                {
                    "evidence_id": "official-1",
                    "signal_event_id": signal_id,
                    "source": "SZSE",
                    "source_record_id": "record-1",
                    "claim_type": "official_listing_presence",
                    "claim_value": "listed_on_a_share_list",
                    "event_time": "2026-08-18T00:00:00+08:00",
                    "available_time": "2026-08-18T06:00:00Z",
                    "source_locator": "fixture.json",
                    "evidence_kind": "official_observation",
                    "verification_method": "exact fixture match",
                    "quality_status": "official_source_exact_code_and_name_match",
                }
            ],
            columns=EVIDENCE_COLUMNS,
        )
        merged, updated = merge_signal_evidence(
            pd.DataFrame(columns=EVIDENCE_COLUMNS), evidence, signals
        )
        repeated, updated_again = merge_signal_evidence(merged, evidence, updated)
        self.assertEqual(len(repeated), 1)
        self.assertIn(
            "official_listing_presence_confirmed",
            updated_again.iloc[0]["quality_status"],
        )
        self.assertEqual(
            updated_again.iloc[0]["quality_status"].count(
                "official_listing_presence_confirmed"
            ),
            1,
        )

    def test_fetch_time_lifecycle_observation_becomes_direct_listing_signal(self) -> None:
        source = pd.DataFrame(
            [
                {
                    "event_id": "status-a",
                    "listing_id": "LISTING_A",
                    "event_type": "status_observed_active",
                    "event_time": "2026-01-01T00:00:00Z",
                    "available_time": "2026-01-03T00:00:00Z",
                    "effective_time": "2026-01-01T00:00:00Z",
                    "source": "fixture source",
                    "evidence_kind": "observation",
                    "availability_quality": "observed_at_fetch_time",
                    "source_status": "imported_unverified",
                }
            ]
        )
        signals = lifecycle_status_observations_to_signal_events(source)
        row = signals.iloc[0]
        self.assertEqual(row["emitter_object_type"], "listing")
        self.assertEqual(row["signal_type"], "lifecycle.change")
        self.assertEqual(row["initial_strength"], 1.0)
        self.assertEqual(row["effective_time"], "2026-01-03T00:00:00+00:00")
        self.assertIn("imported_unverified", row["quality_status"])

        snapshot = build_signal_snapshot(
            signals,
            pd.DataFrame(columns=RULE_COLUMNS),
            pd.DataFrame(columns=EDGE_COLUMNS),
            as_of="2026-01-03T00:00:00Z",
            signal_types=pd.DataFrame(DEFAULT_SIGNAL_TYPES, columns=SIGNAL_TYPE_COLUMNS),
            objects=pd.DataFrame([{"object_type": "listing", "object_id": "LISTING_A"}]),
        )
        lifecycle = snapshot[snapshot["signal_type"] == "lifecycle.change"].iloc[0]
        self.assertEqual(lifecycle["direct_contribution"], 1.0)
        self.assertEqual(lifecycle["propagated_contribution"], 0.0)

    def test_lifecycle_import_rejects_unknown_historical_availability(self) -> None:
        source = pd.DataFrame(
            [
                {
                    "event_id": "historical",
                    "listing_id": "LISTING_A",
                    "event_type": "status_observed_delisted",
                    "event_time": "2020-01-01",
                    "available_time": "2026-01-03T00:00:00Z",
                    "effective_time": "2020-01-01",
                    "source": "fixture source",
                    "evidence_kind": "observation",
                    "availability_quality": "historical_availability_unknown",
                    "source_status": "imported_unverified",
                }
            ]
        )
        with self.assertRaises(ValueError):
            lifecycle_status_observations_to_signal_events(source)

    def test_lifecycle_merge_is_idempotent_and_closes_previous_state(self) -> None:
        active = lifecycle_status_observations_to_signal_events(
            pd.DataFrame(
                [
                    {
                        "event_id": "active",
                        "listing_id": "LISTING_A",
                        "event_type": "status_observed_active",
                        "event_time": "2026-01-01T00:00:00Z",
                        "available_time": "2026-01-01T00:00:00Z",
                        "effective_time": "2026-01-01T00:00:00Z",
                        "source": "fixture",
                        "evidence_kind": "observation",
                        "availability_quality": "observed_at_fetch_time",
                        "source_status": "imported_unverified",
                    }
                ]
            )
        )
        first = merge_lifecycle_status_signals(pd.DataFrame(columns=EVENT_COLUMNS), active)
        repeated = merge_lifecycle_status_signals(first, active)
        self.assertEqual(len(repeated), 1)

        delisted_source = pd.DataFrame(
            [
                {
                    "event_id": "delisted",
                    "listing_id": "LISTING_A",
                    "event_type": "status_observed_delisted",
                    "event_time": "2026-02-01T00:00:00Z",
                    "available_time": "2026-02-01T00:00:00Z",
                    "effective_time": "2026-02-01T00:00:00Z",
                    "source": "fixture",
                    "evidence_kind": "observation",
                    "availability_quality": "observed_at_fetch_time",
                    "source_status": "imported_unverified",
                }
            ]
        )
        delisted = lifecycle_status_observations_to_signal_events(delisted_source)
        merged = merge_lifecycle_status_signals(repeated, delisted)
        self.assertEqual(len(merged), 2)
        old = merged[merged["source_record_id"] == "active"].iloc[0]
        self.assertEqual(pd.Timestamp(old["expires_time"]), pd.Timestamp("2026-02-01T00:00:00Z"))

    def test_exponential_half_life_is_applied_to_direct_signal(self) -> None:
        result = build_signal_snapshot(
            event(), pd.DataFrame(columns=RULE_COLUMNS), pd.DataFrame(columns=EDGE_COLUMNS),
            as_of="2026-01-03T00:00:00Z", signal_types=SIGNAL_TYPES,
            objects=pd.DataFrame([{"object_type": "company", "object_id": "A"}]),
        )
        row = result.iloc[0]
        self.assertAlmostEqual(row["concentration"], 4.0)
        self.assertEqual(row["direct_contribution"], 4.0)
        self.assertEqual(row["propagated_contribution"], 0.0)
        self.assertEqual(row["quality_status"], "direct_signal_only")

    def test_available_time_blocks_signal_before_record_is_known(self) -> None:
        result = build_signal_snapshot(
            event(available_time="2026-01-05T00:00:00Z"),
            pd.DataFrame(columns=RULE_COLUMNS), pd.DataFrame(columns=EDGE_COLUMNS),
            as_of="2026-01-03T00:00:00Z", signal_types=SIGNAL_TYPES,
        )
        self.assertTrue(result.empty)

    def test_rule_and_edge_control_delayed_attenuated_propagation(self) -> None:
        network_edges = edges([
            {
                "edge_id": "ab", "source_object_type": "company", "source_object_id": "A",
                "target_object_type": "company", "target_object_id": "B", "relation_type": "supplier",
                "valid_from": "2026-01-01T00:00:00Z", "valid_to": pd.NaT,
                "available_time": "2026-01-01T00:00:00Z", "quality_status": "fixture",
            },
            {
                "edge_id": "bc", "source_object_type": "company", "source_object_id": "B",
                "target_object_type": "company", "target_object_id": "C", "relation_type": "supplier",
                "valid_from": "2026-01-01T00:00:00Z", "valid_to": pd.NaT,
                "available_time": "2026-01-01T00:00:00Z", "quality_status": "fixture",
            },
        ])
        result = build_signal_snapshot(
            event(half_life_days=100.0), rule(), network_edges,
            as_of="2026-01-03T00:00:00Z", signal_types=SIGNAL_TYPES,
            objects=pd.DataFrame([{"object_type": "company", "object_id": x} for x in "ABC"]),
        )
        values = result.set_index("object_id")["concentration"]
        self.assertAlmostEqual(values["B"], 8.0 * 0.5 * (0.5 ** (2 / 100)), places=6)
        self.assertAlmostEqual(values["C"], 8.0 * 0.25 * (0.5 ** (2 / 100)), places=6)
        self.assertEqual(result.set_index("object_id").loc["C", "quality_status"], "includes_propagated_signal")

    def test_no_rule_means_no_propagation(self) -> None:
        network_edges = edges([{
            "edge_id": "ab", "source_object_type": "company", "source_object_id": "A",
            "target_object_type": "company", "target_object_id": "B", "relation_type": "supplier",
            "valid_from": "2026-01-01T00:00:00Z", "valid_to": pd.NaT,
            "available_time": "2026-01-01T00:00:00Z", "quality_status": "fixture",
        }])
        result = build_signal_snapshot(
            event(decay_method="none"), pd.DataFrame(columns=RULE_COLUMNS), network_edges,
            as_of="2026-01-02T00:00:00Z", signal_types=SIGNAL_TYPES,
            objects=pd.DataFrame([{"object_type": "company", "object_id": x} for x in "AB"]),
        ).set_index("object_id")
        self.assertEqual(result.loc["A", "concentration"], 8.0)
        self.assertEqual(result.loc["B", "concentration"], 0.0)
        self.assertEqual(result.loc["B", "quality_status"], "no_signal")

    def test_cycle_does_not_amplify_or_loop_forever(self) -> None:
        network_edges = edges([
            {
                "edge_id": edge_id, "source_object_type": "company", "source_object_id": source,
                "target_object_type": "company", "target_object_id": target, "relation_type": "supplier",
                "valid_from": "2026-01-01T00:00:00Z", "valid_to": pd.NaT,
                "available_time": "2026-01-01T00:00:00Z", "quality_status": "fixture",
            }
            for edge_id, source, target in [("ab", "A", "B"), ("ba", "B", "A")]
        ])
        result = build_signal_snapshot(
            event(decay_method="none"), rule(attenuation=1.0, max_hops=10), network_edges,
            as_of="2026-01-02T00:00:00Z", signal_types=SIGNAL_TYPES,
            objects=pd.DataFrame([{"object_type": "company", "object_id": x} for x in "AB"]),
        ).set_index("object_id")
        self.assertEqual(result.loc["A", "concentration"], 8.0)
        self.assertEqual(result.loc["A", "source_event_count"], 1)
        self.assertEqual(result.loc["B", "concentration"], 8.0)


if __name__ == "__main__":
    unittest.main()
