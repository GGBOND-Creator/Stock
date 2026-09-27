from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from stock_model.network_signal_view import (
    build_signal_report_model,
    render_signal_report,
    write_signal_report,
)


class NetworkSignalViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = pd.DataFrame(
            [
                self._state("listing", "LISTING_A", "lifecycle.change", 1.0),
                self._state("company", "COMPANY_A", "production.activity", 1.0),
                self._state("product", "PRODUCT_PIG", "production.activity", 0.0),
            ]
        )
        self.signal_types = pd.DataFrame(
            [
                {
                    "signal_type": "lifecycle.change",
                    "display_name": "生命周期变化",
                    "display_color": "#455A64",
                    "display_channel": "outline",
                },
                {
                    "signal_type": "production.activity",
                    "display_name": "生产活动",
                    "display_color": "#2E7D32",
                    "display_channel": "glow",
                },
            ]
        )
        self.events = pd.DataFrame(
            [
                self._event("life", "listing", "LISTING_A", "lifecycle.change"),
                self._event("prod", "company", "COMPANY_A", "production.activity"),
            ]
        )
        self.evidence = pd.DataFrame(
            [
                self._evidence(
                    "life-evidence", "life", "2026-01-03T00:00:00Z",
                    raw_unit="not_applicable", raw_text="示例股份"
                ),
                self._evidence(
                    "prod-evidence", "prod", "2026-01-02T00:00:00Z",
                    raw_unit="not_reported", raw_text="生猪的养殖与销售"
                ),
            ]
        )
        self.rules = pd.DataFrame(columns=["available_time", "valid_from", "valid_to"])
        self.companies = pd.DataFrame(
            [{"company_id": "COMPANY_A", "company_name": "示例食品股份有限公司"}]
        )
        self.listings = pd.DataFrame(
            [{
                "listing_id": "LISTING_A", "company_id": "COMPANY_A",
                "symbol": "000001.SZ", "exchange": "SZSE", "listing_date": "2010-01-01"
            }]
        )
        self.products = pd.DataFrame(
            [{"product_id": "PRODUCT_PIG", "canonical_name": "生猪"}]
        )
        self.mappings = pd.DataFrame(
            [{
                "company_id": "COMPANY_A", "product_id": "PRODUCT_PIG",
                "role": "producer", "review_status": "approved",
                "reviewed_at": "2026-01-02T00:00:00Z"
            }]
        )

    def test_model_labels_evidence_after_snapshot_without_backfilling(self) -> None:
        model = self._model()
        lifecycle = next(
            signal for signal in model["signals"]
            if signal["signal_type"] == "lifecycle.change"
        )
        production = next(
            signal for signal in model["signals"]
            if signal["signal_type"] == "production.activity"
        )
        self.assertFalse(lifecycle["evidence"][0]["available_at_snapshot"])
        self.assertEqual(lifecycle["later_evidence_count"], 1)
        self.assertTrue(production["evidence"][0]["available_at_snapshot"])
        self.assertEqual(
            production["evidence"][0]["raw_numeric_display"], "未披露"
        )
        self.assertEqual(model["transmission_rule_count"], 0)
        self.assertTrue(model["all_propagated_zero"])
        self.assertEqual(model["products"][0]["concentration"], 0.0)

    def test_event_available_after_snapshot_cannot_support_state(self) -> None:
        future = self.events.copy()
        future.loc[future["signal_event_id"] == "life", "available_time"] = (
            "2026-01-03T00:00:00Z"
        )
        with self.assertRaisesRegex(ValueError, "no event available at as_of"):
            build_signal_report_model(
                symbol="000001.SZ", snapshot=self.snapshot,
                signal_types=self.signal_types, events=future,
                evidence=self.evidence, rules=self.rules, companies=self.companies,
                listings=self.listings, products=self.products, mappings=self.mappings,
            )

    def test_render_escapes_inline_json_and_contains_no_remote_dependency(self) -> None:
        evidence = self.evidence.copy()
        evidence.loc[evidence["evidence_id"] == "prod-evidence", "raw_text"] = (
            "</script><script>alert(1)</script>"
        )
        model = build_signal_report_model(
            symbol="000001.SZ", snapshot=self.snapshot,
            signal_types=self.signal_types, events=self.events, evidence=evidence,
            rules=self.rules, companies=self.companies, listings=self.listings,
            products=self.products, mappings=self.mappings,
        )
        rendered = render_signal_report(model)
        self.assertNotIn("</script><script>alert(1)</script>", rendered)
        self.assertIn("\\u003c/script\\u003e", rendered)
        self.assertNotIn("https://", rendered)

    def test_writer_records_input_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.csv"
            source.write_text("a,b\n1,2\n", encoding="utf-8")
            output, metadata_path = write_signal_report(
                root / "report.html", self._model(), input_paths=[source]
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertTrue(output.exists())
            self.assertEqual(len(metadata["inputs"][0]["sha256"]), 64)
            self.assertEqual(metadata["later_evidence_count"], 1)

    def _model(self) -> dict:
        return build_signal_report_model(
            symbol="000001.SZ", snapshot=self.snapshot,
            signal_types=self.signal_types, events=self.events,
            evidence=self.evidence, rules=self.rules, companies=self.companies,
            listings=self.listings, products=self.products, mappings=self.mappings,
        )

    @staticmethod
    def _state(object_type: str, object_id: str, signal_type: str, value: float) -> dict:
        return {
            "as_of": "2026-01-02T12:00:00Z", "object_type": object_type,
            "object_id": object_id, "signal_type": signal_type,
            "concentration": value, "direct_contribution": value,
            "propagated_contribution": 0.0,
            "source_event_count": 1 if value else 0,
            "quality_status": "direct_signal_only" if value else "no_signal",
        }

    @staticmethod
    def _event(event_id: str, object_type: str, object_id: str, signal_type: str) -> dict:
        return {
            "signal_event_id": event_id, "emitter_object_type": object_type,
            "emitter_object_id": object_id, "signal_type": signal_type,
            "initial_strength": 1.0, "unit": "signal_unit",
            "available_time": "2026-01-02T00:00:00Z",
            "effective_time": "2026-01-02T00:00:00Z", "expires_time": pd.NaT,
            "source": "fixture source", "source_record_id": f"source-{event_id}",
            "evidence_kind": "observation", "quality_status": "fixture",
        }

    @staticmethod
    def _evidence(
        evidence_id: str, event_id: str, available_time: str,
        *, raw_unit: str, raw_text: str
    ) -> dict:
        return {
            "evidence_id": evidence_id, "signal_event_id": event_id,
            "source": "fixture evidence", "source_record_id": evidence_id,
            "raw_numeric_value": pd.NA, "raw_unit": raw_unit,
            "raw_text": raw_text, "available_time": available_time,
            "source_locator": "fixture.csv", "evidence_kind": "observation",
            "verification_method": "fixture verification",
            "quality_status": "fixture_quality", "dimension_type": "product",
            "dimension_id": "PRODUCT_PIG",
        }


if __name__ == "__main__":
    unittest.main()
