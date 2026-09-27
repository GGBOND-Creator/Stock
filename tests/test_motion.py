from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from stock_model.industry_network import (
    business_activities_from_cninfo_profile,
    counterparty_concentrations_from_annual_report,
    product_mapping_candidates_from_activity,
    review_activity_product_candidates,
    tables_from_baostock,
)
from stock_model.motion import (
    MOTION_COLUMNS,
    UNRESOLVED_LATENT_CHANNELS,
    build_market_motion_stream,
    build_network_motion_stream,
    convert_ohlcv_file,
    merge_motion_streams,
    motion_stream_as_of,
    motion_stream_to_ohlcv,
)


def make_prices(rows: int = 90) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-02", periods=rows)
    close = pd.Series([10 + index * 0.02 + (index % 5) * 0.01 for index in range(rows)])
    return pd.DataFrame(
        {
            "date": dates,
            "open": close * 0.998,
            "high": close * 1.012,
            "low": close * 0.988,
            "close": close,
            "volume": [100_000 + index * 100 for index in range(rows)],
        }
    )


class MotionStreamTests(unittest.TestCase):
    def test_builds_long_form_stream_and_round_trips_observations(self) -> None:
        prices = make_prices()
        stream = build_market_motion_stream(
            prices,
            symbol="TEST.SZ",
            source="unit-test",
            market="A-share",
            adjustment="qfq",
            volume_unit="lots",
        )

        self.assertEqual(list(stream.columns), MOTION_COLUMNS)
        self.assertTrue(stream["event_id"].is_unique)
        self.assertIn("market.motion.return_1d", set(stream["channel"]))
        self.assertIn("proxy.directional_activity_pressure", set(stream["channel"]))
        for latent_channel in UNRESOLVED_LATENT_CHANNELS:
            self.assertNotIn(latent_channel, set(stream["channel"]))

        recovered = motion_stream_to_ohlcv(stream)
        pd.testing.assert_frame_equal(
            recovered.reset_index(drop=True),
            prices.reset_index(drop=True),
            check_dtype=False,
        )

    def test_future_change_does_not_change_past_motion_events(self) -> None:
        original = make_prices()
        changed = original.copy()
        changed.loc[changed.index[-1], ["open", "high", "low", "close", "volume"]] *= 5

        before = build_market_motion_stream(original, symbol="TEST.SZ")
        after = build_market_motion_stream(changed, symbol="TEST.SZ")
        cutoff = original.loc[original.index[-2], "date"].strftime("%Y-%m-%d")
        before_past = before[before["event_time"] <= cutoff].reset_index(drop=True)
        after_past = after[after["event_time"] <= cutoff].reset_index(drop=True)
        pd.testing.assert_frame_equal(before_past, after_past)

    def test_file_conversion_uses_source_metadata_and_writes_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            input_path = temp / "TEST.SZ.csv"
            output_path = temp / "TEST.SZ.motion.csv"
            make_prices().to_csv(input_path, index=False)
            Path(f"{input_path}.meta.json").write_text(
                '{"symbol":"TEST.SZ","source":"fixture","market":"A-share",'
                '"adjustment":"qfq","volume_unit":"lots"}',
                encoding="utf-8",
            )

            stream, metadata, audit_path = convert_ohlcv_file(input_path, output_path)

            self.assertTrue(output_path.exists())
            self.assertTrue(audit_path.exists())
            self.assertEqual(metadata["source"], "fixture")
            self.assertEqual(metadata["causality_policy"], "current_and_past_rows_only")
            self.assertGreater(len(stream), len(make_prices()))

    def test_reviewed_network_evidence_enters_only_after_available_time(self) -> None:
        basic = pd.DataFrame(
            [
                {
                    "code": "sz.000001",
                    "code_name": "测试公司",
                    "ipoDate": "2025-01-01",
                    "outDate": "",
                    "type": "1",
                    "status": "1",
                }
            ]
        )
        industry = pd.DataFrame(
            [
                {
                    "updateDate": "2026-01-01",
                    "code": "sz.000001",
                    "code_name": "测试公司",
                    "industry": "C13农副食品加工业",
                    "industryClassification": "证监会行业分类",
                }
            ]
        )
        tables = tables_from_baostock(
            basic, industry, fetched_at="2026-01-01T00:00:00Z"
        )
        company_id = tables.companies.iloc[0]["company_id"]
        activities = business_activities_from_cninfo_profile(
            pd.DataFrame(
                [{"主营业务": "生猪的养殖与销售。", "经营范围": "牲畜饲养。"}]
            ),
            company_id=company_id,
            issuer_id="fixture",
            security_code="000001",
            available_time="2026-02-01T00:00:00Z",
        )
        activity = activities.query(
            "activity_type == 'main_business_description'"
        ).iloc[0]
        product, candidates = product_mapping_candidates_from_activity(
            activity,
            canonical_name="生猪",
            roles=["producer", "seller"],
            available_time="2026-02-02T00:00:00Z",
            evidence_quote="生猪的养殖与销售",
        )
        reviewed = review_activity_product_candidates(
            candidates,
            activities,
            mapping_ids=candidates["mapping_id"].tolist(),
            decision="approved",
            reviewer="fixture-reviewer",
            reviewed_at="2026-02-03T00:00:00Z",
        )
        concentrations = counterparty_concentrations_from_annual_report(
            [
                {
                    "counterparty_side": "customer",
                    "aggregate_amount": 100.0,
                    "share_of_total": 0.08,
                    "related_party_share_of_total": 0.01,
                    "names_disclosed": False,
                    "evidence_pages": "30",
                    "evidence_quote": "匿名前五名客户。",
                },
                {
                    "counterparty_side": "supplier",
                    "aggregate_amount": 200.0,
                    "share_of_total": 0.19,
                    "related_party_share_of_total": 0.05,
                    "names_disclosed": False,
                    "evidence_pages": "30-31",
                    "evidence_quote": "匿名前五名供应商。",
                },
            ],
            company_id=company_id,
            report_period_start="2025-01-01",
            report_period_end="2025-12-31",
            announcement_time="2026-03-28T00:00:00+08:00",
            available_time="2026-08-17T00:00:00Z",
            source="fixture report",
            source_record_id="fixture-report",
        )
        tables.business_activities = activities
        tables.products = product
        tables.activity_product_candidates = reviewed
        tables.counterparty_concentrations = concentrations

        network = build_network_motion_stream(tables, symbol="000001.SZ")
        self.assertEqual(len(network), 6)
        product_events = network[
            network["channel"].str.startswith("production.activity")
        ]
        proxy_events = network[network["evidence_kind"].eq("proxy")]
        self.assertEqual(len(product_events), 2)
        self.assertEqual(set(product_events["dimension_name"]), {"生猪"})
        self.assertEqual(len(proxy_events), 4)
        self.assertTrue(
            motion_stream_as_of(network, as_of="2026-02-02T23:59:59Z").empty
        )
        at_review = motion_stream_as_of(network, as_of="2026-02-03T00:00:00Z")
        self.assertEqual(len(at_review), 2)
        all_known = motion_stream_as_of(network, as_of="2026-08-17T00:00:00Z")
        self.assertEqual(len(all_known), 6)

        market = build_market_motion_stream(make_prices(), symbol="000001.SZ")
        combined = merge_motion_streams(market, network)
        self.assertEqual(len(combined), len(market) + len(network))


if __name__ == "__main__":
    unittest.main()
