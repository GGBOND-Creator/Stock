from __future__ import annotations

import unittest

import pandas as pd

from stock_model.public_fund import (
    build_reported_holding_changes,
    normalize_fund_announcement_reports,
    normalize_fund_holdings,
    normalize_fund_overview,
)


class PublicFundEvidenceTests(unittest.TestCase):
    def test_holding_changes_do_not_turn_missing_top_ten_rows_into_zero(self) -> None:
        holdings = pd.DataFrame(
            [
                {
                    "holding_id": "H1",
                    "fund_id": "PUBLIC_FUND_000001",
                    "fund_code": "000001",
                    "report_period_end": "2026-03-31",
                    "instrument_id": "000001.SZ",
                    "security_name": "旧股",
                    "portfolio_weight": 0.04,
                    "shares": 100.0,
                    "shares_unit": "share",
                    "market_value": 1000.0,
                    "market_value_unit": "CNY",
                    "holding_scope": "unknown",
                    "available_time": "2026-04-22T23:59:59+08:00",
                    "availability_policy": "available_after_announcement_date_end",
                    "source": "fixture",
                    "source_record_id": "H1",
                    "evidence_kind": "aggregated_observation",
                    "quality_status": "fixture",
                },
                {
                    "holding_id": "H2",
                    "fund_id": "PUBLIC_FUND_000001",
                    "fund_code": "000001",
                    "report_period_end": "2026-03-31",
                    "instrument_id": "000002.SZ",
                    "security_name": "退出候选",
                    "portfolio_weight": 0.02,
                    "shares": 50.0,
                    "shares_unit": "share",
                    "market_value": 500.0,
                    "market_value_unit": "CNY",
                    "holding_scope": "unknown",
                    "available_time": "2026-04-22T23:59:59+08:00",
                    "availability_policy": "available_after_announcement_date_end",
                    "source": "fixture",
                    "source_record_id": "H2",
                    "evidence_kind": "aggregated_observation",
                    "quality_status": "fixture",
                },
                {
                    "holding_id": "H3",
                    "fund_id": "PUBLIC_FUND_000001",
                    "fund_code": "000001",
                    "report_period_end": "2026-06-30",
                    "instrument_id": "000001.SZ",
                    "security_name": "旧股",
                    "portfolio_weight": 0.05,
                    "shares": 120.0,
                    "shares_unit": "share",
                    "market_value": 1300.0,
                    "market_value_unit": "CNY",
                    "holding_scope": "unknown",
                    "available_time": "2026-07-21T23:59:59+08:00",
                    "availability_policy": "available_after_announcement_date_end",
                    "source": "fixture",
                    "source_record_id": "H3",
                    "evidence_kind": "aggregated_observation",
                    "quality_status": "fixture",
                },
                {
                    "holding_id": "H4",
                    "fund_id": "PUBLIC_FUND_000001",
                    "fund_code": "000001",
                    "report_period_end": "2026-06-30",
                    "instrument_id": "000003.SZ",
                    "security_name": "新股",
                    "portfolio_weight": 0.03,
                    "shares": 70.0,
                    "shares_unit": "share",
                    "market_value": 700.0,
                    "market_value_unit": "CNY",
                    "holding_scope": "unknown",
                    "available_time": "2026-07-21T23:59:59+08:00",
                    "availability_policy": "available_after_announcement_date_end",
                    "source": "fixture",
                    "source_record_id": "H4",
                    "evidence_kind": "aggregated_observation",
                    "quality_status": "fixture",
                },
            ]
        )
        result = build_reported_holding_changes(holdings)

        common = result[result.instrument_id.eq("000001.SZ")].iloc[0]
        self.assertEqual(common.comparison_status, "present_in_both_disclosures")
        self.assertEqual(common.share_change, 20.0)
        exited = result[result.instrument_id.eq("000002.SZ")].iloc[0]
        self.assertEqual(
            exited.comparison_status,
            "left_disclosed_set_actual_current_position_unknown",
        )
        self.assertTrue(pd.isna(exited.share_change))
    def test_report_index_gives_historical_availability_date(self) -> None:
        reports = pd.DataFrame(
            [
                {
                    "基金代码": "000001",
                    "公告标题": "示例基金2026年第2季度报告",
                    "基金名称": "示例基金",
                    "公告日期": "2026-07-21",
                    "报告ID": "AN-1",
                }
            ]
        )
        result = normalize_fund_announcement_reports(
            reports,
            fund_code="000001",
            fetched_at="2026-08-17T10:00:00+08:00",
        )

        self.assertEqual(result.loc[0, "report_period_end"], "2026-06-30")
        self.assertEqual(result.loc[0, "available_time"], "2026-07-21T23:59:59+08:00")

    def test_normalizes_overview_and_preserves_conservative_availability(self) -> None:
        overview = pd.DataFrame(
            [
                {
                    "基金全称": "示例成长证券投资基金",
                    "基金简称": "示例成长混合",
                    "基金代码": "000001",
                    "基金类型": "混合型-灵活",
                    "发行日期": "2020年01月01日",
                    "成立日期/规模": "2020年01月10日 / 1亿份",
                    "净资产规模": "2.50亿元（截止至：2026年06月30日）",
                    "份额规模": "1亿份",
                    "基金管理人": "示例基金",
                    "基金托管人": "示例银行",
                    "基金经理人": "甲、乙",
                }
            ]
        )
        result = normalize_fund_overview(
            overview,
            fund_code="000001",
            available_time="2026-08-17T10:00:00+08:00",
        )

        self.assertEqual(result.loc[0, "net_assets"], 250_000_000)
        self.assertEqual(result.loc[0, "net_assets_report_date"], "2026-06-30")
        self.assertEqual(
            result.loc[0, "net_assets_scope"],
            "source_fund_code_share_class_or_unknown",
        )
        self.assertEqual(
            result.loc[0, "availability_policy"],
            "local_first_observation_not_official_announcement_time",
        )

    def test_normalizes_quarter_holdings_to_positions(self) -> None:
        holdings = pd.DataFrame(
            [
                {
                    "序号": 1,
                    "股票代码": "002714",
                    "股票名称": "牧原股份",
                    "占净值比例": 4.2,
                    "持股数": 10.5,
                    "持仓市值": 123.4,
                    "季度": "2026年2季度股票投资明细",
                }
            ]
        )
        result = normalize_fund_holdings(
            holdings,
            fund_code="000001",
            available_time="2026-08-17T10:00:00+08:00",
            report_available_times={"2026-06-30": "2026-07-21T23:59:59+08:00"},
        )

        self.assertEqual(result.loc[0, "instrument_id"], "002714.SZ")
        self.assertEqual(result.loc[0, "report_period_end"], "2026-06-30")
        self.assertEqual(result.loc[0, "shares"], 105_000)
        self.assertEqual(result.loc[0, "market_value"], 1_234_000)
        self.assertEqual(result.loc[0, "portfolio_weight"], 0.042)
        self.assertEqual(
            result.loc[0, "holding_scope"], "source_fund_portfolio_scope_unknown"
        )
        self.assertEqual(result.loc[0, "available_time"], "2026-07-21T23:59:59+08:00")

    def test_five_digit_hong_kong_code_is_not_misclassified_as_shenzhen(self) -> None:
        holdings = pd.DataFrame(
            [
                {
                    "序号": 1,
                    "股票代码": "00700",
                    "股票名称": "腾讯控股",
                    "占净值比例": 9.0,
                    "持股数": 1.0,
                    "持仓市值": 100.0,
                    "季度": "2026年2季度股票投资明细",
                }
            ]
        )
        result = normalize_fund_holdings(
            holdings,
            fund_code="005827",
            available_time="2026-08-17T10:00:00+08:00",
        )

        self.assertEqual(result.loc[0, "instrument_id"], "00700.HK")


if __name__ == "__main__":
    unittest.main()
