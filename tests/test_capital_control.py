from __future__ import annotations

import unittest

import pandas as pd

from stock_model.capital_control import (
    CAPITAL_CONTROL_SCHEMA_VERSION,
    DISTRIBUTION_COLUMNS,
    FLOW_EVENT_COLUMNS,
    distribution_as_of,
    expected_attribution,
    unknown_only_distribution,
    validate_distribution,
)


def make_flow_events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "schema_version": CAPITAL_CONTROL_SCHEMA_VERSION,
                "flow_event_id": "FLOW_1",
                "instrument_id": "002714.SZ",
                "market": "A-share",
                "event_time": "2026-08-17T10:00:00+08:00",
                "available_time": "2026-08-17T10:05:00+08:00",
                "availability_policy": "available_after_interval_end",
                "flow_measure": "buy_order_amount",
                "side": "buy",
                "observed_amount": 100.0,
                "amount_unit": "CNY",
                "source": "unit-test",
                "source_record_id": "fixture-1",
                "evidence_kind": "observation",
                "method": "fixture",
                "quality_status": "verified_fixture",
            }
        ],
        columns=FLOW_EVENT_COLUMNS,
    )


class CapitalControlTests(unittest.TestCase):
    def test_unknown_distribution_is_conservative_and_complete(self) -> None:
        distribution = unknown_only_distribution(make_flow_events())

        self.assertEqual(list(distribution.columns), DISTRIBUTION_COLUMNS)
        self.assertEqual(distribution.loc[0, "controller_id"], "CONTROLLER_UNKNOWN")
        self.assertEqual(distribution.loc[0, "probability"], 1.0)
        validate_distribution(distribution)

    def test_probabilities_must_sum_to_one_per_event(self) -> None:
        distribution = unknown_only_distribution(make_flow_events())
        distribution.loc[0, "probability"] = 0.8

        with self.assertRaisesRegex(ValueError, "sum to 1"):
            validate_distribution(distribution)

    def test_expected_amount_uses_side_and_probability(self) -> None:
        distribution = unknown_only_distribution(make_flow_events())
        attributed = expected_attribution(make_flow_events(), distribution)

        self.assertEqual(attributed.loc[0, "expected_signed_amount"], 100.0)

    def test_unknown_class_cannot_impersonate_named_controller(self) -> None:
        distribution = unknown_only_distribution(make_flow_events())
        distribution.loc[0, "controller_id"] = "PERSON_X"

        with self.assertRaisesRegex(ValueError, "CONTROLLER_UNKNOWN"):
            validate_distribution(distribution)

    def test_future_attribution_evidence_is_not_available_early(self) -> None:
        distribution = unknown_only_distribution(make_flow_events())

        early = distribution_as_of(distribution, as_of="2026-08-17T10:04:59+08:00")
        on_time = distribution_as_of(distribution, as_of="2026-08-17T10:05:00+08:00")

        self.assertTrue(early.empty)
        self.assertEqual(len(on_time), 1)


if __name__ == "__main__":
    unittest.main()
