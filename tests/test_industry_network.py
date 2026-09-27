from __future__ import annotations

import unittest
from io import StringIO

import pandas as pd

from stock_model.industry_network import (
    EVENT_COLUMNS,
    NetworkTables,
    apply_cninfo_issuer_identity,
    apply_lifecycle_events,
    audit_counterparty_relation_eligibility,
    business_activities_from_cninfo_profile,
    build_market_impact_stream,
    build_network_snapshot,
    company_relations_from_named_counterparty_evidence,
    counterparty_concentrations_from_annual_report,
    merge_incremental_network_refresh,
    named_relation_corroborations_from_records,
    product_mapping_candidates_from_activity,
    review_activity_product_candidates,
    tables_from_baostock,
)


def named_relation_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "reporting_company_id": "COMPANY_REPORTER",
        "reporting_symbol": "600741.SH",
        "reporting_legal_name": "报告公司股份有限公司",
        "counterparty_company_id": "COMPANY_COUNTERPARTY",
        "counterparty_symbol": "600104.SH",
        "counterparty_legal_name": "交易对手股份有限公司",
        "counterparty_name_in_filing": "交易对手",
        "report_period_start": "2025-01-01",
        "report_period_end": "2025-12-31",
        "transaction_direction": "purchase_from",
        "relation_type": "supplies",
        "product_or_service": "商品及材料",
        "transaction_amount": 153169367.40,
        "currency": "CNY",
        "announcement_time": "2026-03-31T00:00:00+08:00",
        "source_available_time": "2026-08-18T07:23:51Z",
        "identity_announcement_time": "2026-04-02T00:00:00+08:00",
        "identity_available_time": "2026-08-18T07:24:33Z",
        "relation_available_time": "2026-08-18T07:28:24Z",
        "source": "official annual report",
        "source_record_id": "report-1",
        "source_url": "https://example.invalid/report-1.pdf",
        "evidence_page": "178",
        "evidence_quote": "交易对手 商品及材料采购 协商确定 153,169,367.40",
        "reporting_identity_evidence_page": "4",
        "reporting_identity_evidence_quote": "报告公司股份有限公司 2025年年度报告",
        "identity_source": "independent official annual report",
        "identity_source_record_id": "identity-report-1",
        "identity_source_url": "https://example.invalid/identity-report-1.pdf",
        "identity_evidence_page": "1",
        "identity_evidence_quote": "公司代码：600104 交易对手股份有限公司",
        "extraction_method": "text_plus_visual_review",
        "review_status": "visually_verified_and_identity_confirmed",
        "reviewed_at": "2026-08-18T07:28:24Z",
        "confidence": "high",
        "source_status": "official_filing_archived_and_reviewed",
    }
    record.update(overrides)
    return record


def named_relation_companies() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "company_id": ["COMPANY_REPORTER", "COMPANY_COUNTERPARTY"],
            "company_name": ["报告公司", "交易对手"],
        }
    )


def named_corroboration_record(evidence_id: str, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "evidence_id": evidence_id,
        "corroboration_kind": "issuer_report_identity_and_control_link",
        "source_company_id": "COMPANY_COUNTERPARTY",
        "subject_company_id": "COMPANY_REPORTER",
        "subject_symbol": "600741.SH",
        "subject_legal_name": "报告公司股份有限公司",
        "reported_control_label": "下属控股子公司",
        "reported_direct_ownership_share": 0.5832,
        "source": "counterparty official annual report",
        "source_record_id": "identity-report-1",
        "source_url": "https://example.invalid/identity-report-1.pdf",
        "source_announcement_time": "2026-04-02T00:00:00+08:00",
        "source_available_time": "2026-08-18T07:24:33Z",
        "evidence_pages": "17;170",
        "evidence_quote": (
            "下属控股子公司报告公司股份有限公司（股票代码：600741）；"
            "报告公司股份有限公司直接持股比例58.32%"
        ),
        "reviewed_at": "2026-08-18T07:55:10Z",
        "available_time": "2026-08-18T07:55:10Z",
        "extraction_method": "text_plus_visual_review",
        "review_status": "visually_verified",
        "conclusion": (
            "corroborates_identity_and_control_link_not_transaction_amount_or_direction"
        ),
        "confidence": "high",
        "source_status": "official_filing_archived_and_reviewed",
    }
    record.update(overrides)
    return record


def fixture_tables() -> NetworkTables:
    basic = pd.DataFrame(
        [
            {
                "code": "sz.000001",
                "code_name": "测试公司",
                "ipoDate": "2026-01-10",
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
    return tables_from_baostock(
        basic, industry, fetched_at="2026-01-01T00:00:00+00:00"
    )


class IndustryNetworkTests(unittest.TestCase):
    def test_counterparty_filing_corroborates_identity_without_changing_relation(self) -> None:
        evidence, relations = company_relations_from_named_counterparty_evidence(
            [named_relation_record()],
            companies=named_relation_companies(),
            as_of="2026-08-18T07:28:24Z",
        )
        normalized, available = named_relation_corroborations_from_records(
            [named_corroboration_record(evidence.iloc[0]["evidence_id"])],
            named_evidence=evidence,
            as_of="2026-08-18T07:55:10Z",
        )
        self.assertEqual(len(normalized), 1)
        self.assertEqual(len(available), 1)
        self.assertEqual(normalized.iloc[0]["relation_id"], relations.iloc[0]["relation_id"])
        self.assertAlmostEqual(
            normalized.iloc[0]["reported_direct_ownership_share"], 0.5832
        )

    def test_counterparty_filing_corroboration_cannot_leak_before_review(self) -> None:
        evidence, _ = company_relations_from_named_counterparty_evidence(
            [named_relation_record()],
            companies=named_relation_companies(),
            as_of="2026-08-18T07:28:24Z",
        )
        normalized, available = named_relation_corroborations_from_records(
            [named_corroboration_record(evidence.iloc[0]["evidence_id"])],
            named_evidence=evidence,
            as_of="2026-08-18T07:55:09Z",
        )
        self.assertEqual(len(normalized), 1)
        self.assertTrue(available.empty)

    def test_counterparty_filing_corroboration_preserves_transaction_limit(self) -> None:
        evidence, _ = company_relations_from_named_counterparty_evidence(
            [named_relation_record()],
            companies=named_relation_companies(),
            as_of="2026-08-18T07:28:24Z",
        )
        with self.assertRaisesRegex(ValueError, "transaction limit"):
            named_relation_corroborations_from_records(
                [
                    named_corroboration_record(
                        evidence.iloc[0]["evidence_id"],
                        conclusion="confirms_transaction_amount",
                    )
                ],
                named_evidence=evidence,
                as_of="2026-08-18T07:55:10Z",
            )
    def test_named_counterparty_evidence_builds_period_bounded_supply_edge(self) -> None:
        evidence, relations = company_relations_from_named_counterparty_evidence(
            [named_relation_record()],
            companies=named_relation_companies(),
            as_of="2026-08-18T07:28:24Z",
        )
        self.assertEqual(len(evidence), 1)
        self.assertEqual(len(relations), 1)
        relation = relations.iloc[0]
        self.assertEqual(relation["source_company_id"], "COMPANY_COUNTERPARTY")
        self.assertEqual(relation["target_company_id"], "COMPANY_REPORTER")
        self.assertEqual(relation["valid_from"], "2025-01-01")
        self.assertEqual(relation["valid_to"], "2026-01-01")
        self.assertEqual(relation["available_time"], "2026-08-18T07:28:24+00:00")

    def test_named_counterparty_evidence_cannot_leak_before_review(self) -> None:
        evidence, relations = company_relations_from_named_counterparty_evidence(
            [named_relation_record()],
            companies=named_relation_companies(),
            as_of="2026-08-18T07:28:23Z",
        )
        self.assertEqual(len(evidence), 1)
        self.assertTrue(relations.empty)

    def test_named_counterparty_evidence_rejects_identity_or_quote_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "legal name"):
            company_relations_from_named_counterparty_evidence(
                [named_relation_record(identity_evidence_quote="公司代码：600104")],
                companies=named_relation_companies(),
                as_of="2026-08-18T07:28:24Z",
            )
        with self.assertRaisesRegex(ValueError, "disclosed amount"):
            company_relations_from_named_counterparty_evidence(
                [named_relation_record(evidence_quote="交易对手 商品及材料采购")],
                companies=named_relation_companies(),
                as_of="2026-08-18T07:28:24Z",
            )

    def test_named_counterparty_evidence_ids_are_idempotent(self) -> None:
        first = company_relations_from_named_counterparty_evidence(
            [named_relation_record()],
            companies=named_relation_companies(),
            as_of="2026-08-18T07:28:24Z",
        )
        second = company_relations_from_named_counterparty_evidence(
            [named_relation_record()],
            companies=named_relation_companies(),
            as_of="2026-08-18T07:28:24Z",
        )
        self.assertEqual(first[0].iloc[0]["evidence_id"], second[0].iloc[0]["evidence_id"])
        self.assertEqual(first[1].iloc[0]["relation_id"], second[1].iloc[0]["relation_id"])

    def test_cninfo_org_id_replaces_symbol_proxy_across_tables(self) -> None:
        tables = fixture_tables()
        registry = pd.DataFrame(
            [
                {
                    "code": "000001",
                    "orgId": "gssz0000001",
                    "zwjc": "测试公司",
                    "category": "A股",
                }
            ]
        )
        mapped, audit = apply_cninfo_issuer_identity(
            tables,
            registry,
            available_time="2026-02-01T00:00:00Z",
        )
        expected_id = "CNINFO_ORG_gssz0000001"
        self.assertEqual(mapped.companies.iloc[0]["company_id"], expected_id)
        self.assertEqual(mapped.listings.iloc[0]["company_id"], expected_id)
        self.assertEqual(mapped.memberships.iloc[0]["company_id"], expected_id)
        self.assertEqual(mapped.lifecycle_events.iloc[0]["company_id"], expected_id)
        self.assertEqual(audit.iloc[0]["match_method"], "security_code_to_cninfo_org_id")

    def test_cninfo_profile_is_preserved_as_verbatim_business_evidence(self) -> None:
        profile = pd.DataFrame(
            [{"主营业务": "生猪养殖与销售。", "经营范围": "牲畜饲养；粮食收购。"}]
        )
        activities = business_activities_from_cninfo_profile(
            profile,
            company_id="CNINFO_ORG_1",
            issuer_id="1",
            security_code="002714",
            available_time="2026-02-01T00:00:00Z",
        )
        self.assertEqual(len(activities), 2)
        self.assertEqual(set(activities["product_or_service"]), {"unparsed"})
        self.assertEqual(set(activities["extraction_method"]), {"verbatim_profile_field"})

    def test_product_mapping_is_pending_and_requires_a_verbatim_quote(self) -> None:
        profile = pd.DataFrame(
            [{"主营业务": "生猪的养殖与销售。", "经营范围": "牲畜饲养；粮食收购。"}]
        )
        activities = business_activities_from_cninfo_profile(
            profile,
            company_id="CNINFO_ORG_1",
            issuer_id="1",
            security_code="002714",
            available_time="2026-02-01T00:00:00Z",
        )
        activity = activities.query(
            "activity_type == 'main_business_description'"
        ).iloc[0]
        product, mappings = product_mapping_candidates_from_activity(
            activity,
            canonical_name="生猪",
            roles=["producer", "seller"],
            available_time="2026-02-02T00:00:00Z",
            evidence_quote="生猪的养殖与销售",
        )
        self.assertEqual(product.iloc[0]["canonical_name"], "生猪")
        self.assertEqual(set(mappings["role"]), {"producer", "seller"})
        self.assertEqual(set(mappings["review_status"]), {"pending_human_review"})
        with self.assertRaises(ValueError):
            product_mapping_candidates_from_activity(
                activity,
                canonical_name="饲料",
                roles=["producer"],
                available_time="2026-02-02T00:00:00Z",
                evidence_quote="饲料生产",
            )

        reviewed = review_activity_product_candidates(
            mappings,
            activities,
            mapping_ids=mappings["mapping_id"].tolist(),
            decision="approved",
            reviewer="project_user_authorized_review",
            reviewed_at="2026-02-03T00:00:00Z",
            review_note="Exact main-business quote; no business-scope inference.",
        )
        self.assertEqual(set(reviewed["review_status"]), {"approved"})
        self.assertEqual(
            set(reviewed["confidence"]), {"human_reviewed_exact_text_match"}
        )
        reloaded = pd.read_csv(StringIO(mappings.to_csv(index=False)))
        reviewed_after_csv = review_activity_product_candidates(
            reloaded,
            activities,
            mapping_ids=reloaded["mapping_id"].tolist(),
            decision="approved",
            reviewer="project_user_authorized_review",
            reviewed_at="2026-02-03T00:00:00Z",
        )
        self.assertEqual(set(reviewed_after_csv["review_status"]), {"approved"})

    def test_anonymous_counterparty_disclosure_is_concentration_not_edge(self) -> None:
        tables = fixture_tables()
        company_id = tables.companies.iloc[0]["company_id"]
        concentration = counterparty_concentrations_from_annual_report(
            [
                {
                    "counterparty_side": "customer",
                    "aggregate_amount": 100.0,
                    "share_of_total": 0.08,
                    "related_party_share_of_total": 0.01,
                    "names_disclosed": False,
                    "evidence_pages": "30",
                    "evidence_quote": "客户名称仅披露为第一名至第五名。",
                }
            ],
            company_id=company_id,
            report_period_start="2025-01-01",
            report_period_end="2025-12-31",
            announcement_time="2026-03-28T00:00:00+08:00",
            available_time="2026-08-17T00:00:00Z",
            source="fixture annual report",
            source_record_id="fixture-report",
        )
        tables.counterparty_concentrations = concentration
        before = build_network_snapshot(tables, as_of="2026-08-16T23:59:59Z")
        after = build_network_snapshot(tables, as_of="2026-08-17T00:00:00Z")
        self.assertTrue(before.counterparty_concentrations.empty)
        self.assertEqual(len(after.counterparty_concentrations), 1)
        self.assertTrue(tables.relations.empty)

    def test_anonymous_counterparty_fails_company_relation_gate(self) -> None:
        concentration = counterparty_concentrations_from_annual_report(
            [
                {
                    "counterparty_side": "supplier",
                    "aggregate_amount": 100.0,
                    "share_of_total": 0.1,
                    "related_party_share_of_total": 0.0,
                    "names_disclosed": False,
                    "evidence_pages": "31",
                    "evidence_quote": "供应商名称仅披露为第一名至第五名。",
                }
            ],
            company_id="COMPANY_A",
            report_period_start="2025-01-01",
            report_period_end="2025-12-31",
            announcement_time="2026-03-28T00:00:00+08:00",
            available_time="2026-08-17T00:00:00Z",
            source="fixture annual report",
            source_record_id="fixture-report",
        )
        audit = audit_counterparty_relation_eligibility(
            concentration, as_of="2026-08-18T00:00:00Z"
        )
        self.assertEqual(audit.iloc[0]["decision"], "rejected")
        self.assertEqual(audit.iloc[0]["reason_code"], "anonymous_aggregate_only")
        self.assertFalse(audit.iloc[0]["eligible_for_company_relation"])
        self.assertEqual(audit.iloc[0]["relation_rows_created"], 0)

    def test_counterparty_gate_filters_records_not_yet_available(self) -> None:
        concentration = counterparty_concentrations_from_annual_report(
            [
                {
                    "counterparty_side": "customer",
                    "aggregate_amount": 100.0,
                    "share_of_total": 0.1,
                    "related_party_share_of_total": 0.0,
                    "names_disclosed": False,
                    "evidence_pages": "30",
                    "evidence_quote": "客户名称仅披露为第一名至第五名。",
                }
            ],
            company_id="COMPANY_A",
            report_period_start="2025-01-01",
            report_period_end="2025-12-31",
            announcement_time="2026-03-28T00:00:00+08:00",
            available_time="2026-08-17T00:00:00Z",
            source="fixture annual report",
            source_record_id="fixture-report",
        )
        audit = audit_counterparty_relation_eligibility(
            concentration, as_of="2026-08-16T23:59:59Z"
        )
        self.assertTrue(audit.empty)

    def test_listing_and_delisting_change_listing_not_company_identity(self) -> None:
        tables = fixture_tables()
        listing = tables.listings.iloc[0]
        extra = pd.DataFrame(
            [
                {
                    "event_id": "announce-delisting",
                    "listing_id": listing["listing_id"],
                    "company_id": listing["company_id"],
                    "event_type": "delisting_announced",
                    "event_time": "2026-02-01T00:00:00+00:00",
                    "available_time": "2026-02-01T00:00:00+00:00",
                    "effective_time": "2026-02-01T00:00:00+00:00",
                    "industry_id": pd.NA,
                    "fundraising_amount": pd.NA,
                    "free_float_market_value": 1_000_000.0,
                    "reason": "fixture",
                    "source": "fixture",
                    "evidence_kind": "observation",
                    "availability_quality": "verified",
                    "source_status": "verified_fixture",
                },
                {
                    "event_id": "delisted",
                    "listing_id": listing["listing_id"],
                    "company_id": listing["company_id"],
                    "event_type": "delisted",
                    "event_time": "2026-02-10T00:00:00+00:00",
                    "available_time": "2026-02-01T00:00:00+00:00",
                    "effective_time": "2026-02-10T00:00:00+00:00",
                    "industry_id": pd.NA,
                    "fundraising_amount": pd.NA,
                    "free_float_market_value": 1_000_000.0,
                    "reason": "fixture",
                    "source": "fixture",
                    "evidence_kind": "observation",
                    "availability_quality": "verified",
                    "source_status": "verified_fixture",
                },
            ],
            columns=EVENT_COLUMNS,
        )
        tables.lifecycle_events = pd.concat(
            [tables.lifecycle_events, extra], ignore_index=True
        )

        announced = build_network_snapshot(tables, as_of="2026-02-05T00:00:00Z")
        self.assertEqual(announced.listings.iloc[0]["lifecycle_status"], "delisting_announced")
        self.assertEqual(len(announced.pending_events), 1)
        self.assertEqual(len(announced.companies), 1)
        self.assertTrue(announced.companies.iloc[0]["network_included"])

        after = build_network_snapshot(tables, as_of="2026-02-11T00:00:00Z")
        self.assertEqual(after.listings.iloc[0]["lifecycle_status"], "delisted")
        self.assertEqual(len(after.companies), 1)
        self.assertFalse(after.companies.iloc[0]["network_included"])

    def test_event_not_yet_available_does_not_leak_into_snapshot(self) -> None:
        tables = fixture_tables()
        listing = tables.listings.iloc[0]
        late = pd.DataFrame(
            [
                {
                    "event_id": "late-delisting-record",
                    "listing_id": listing["listing_id"],
                    "company_id": listing["company_id"],
                    "event_type": "delisted",
                    "event_time": "2026-01-20T00:00:00Z",
                    "available_time": "2026-02-01T00:00:00Z",
                    "effective_time": "2026-01-20T00:00:00Z",
                    "industry_id": pd.NA,
                    "fundraising_amount": pd.NA,
                    "free_float_market_value": pd.NA,
                    "reason": "late archival record",
                    "source": "fixture",
                    "evidence_kind": "observation",
                    "availability_quality": "verified",
                    "source_status": "verified_fixture",
                }
            ],
            columns=EVENT_COLUMNS,
        )
        tables.lifecycle_events = pd.concat(
            [tables.lifecycle_events, late], ignore_index=True
        )
        before_available, _ = apply_lifecycle_events(
            tables.listings,
            tables.lifecycle_events,
            as_of="2026-01-25T00:00:00Z",
        )
        self.assertEqual(before_available.iloc[0]["lifecycle_status"], "active")

    def test_market_impact_separates_structural_change_and_proxy(self) -> None:
        tables = fixture_tables()
        listing = tables.listings.iloc[0]
        delisted = pd.DataFrame(
            [
                {
                    "event_id": "delisted-impact",
                    "listing_id": listing["listing_id"],
                    "company_id": listing["company_id"],
                    "event_type": "delisted",
                    "event_time": "2026-02-10T00:00:00Z",
                    "available_time": "2026-02-10T00:00:00Z",
                    "effective_time": "2026-02-10T00:00:00Z",
                    "industry_id": tables.industries.iloc[0]["industry_id"],
                    "fundraising_amount": pd.NA,
                    "free_float_market_value": 2_000_000.0,
                    "reason": "fixture",
                    "source": "fixture",
                    "evidence_kind": "observation",
                    "availability_quality": "verified",
                    "source_status": "verified_fixture",
                }
            ],
            columns=EVENT_COLUMNS,
        )
        impacts = build_market_impact_stream(
            delisted,
            listings=tables.listings,
            as_of="2026-02-11T00:00:00Z",
        )
        count = impacts.loc[
            impacts["impact_channel"] == "market.structure.listed_security_count_change",
            "value",
        ].iloc[0]
        self.assertEqual(count, -1.0)
        proxy = impacts[
            impacts["impact_channel"] == "proxy.market.forced_reallocation_exposure"
        ]
        self.assertEqual(proxy.iloc[0]["evidence_kind"], "proxy")

    def test_incremental_refresh_marks_new_delisting_at_first_observation(self) -> None:
        previous = fixture_tables()
        current_basic = pd.DataFrame(
            [
                {
                    "code": "sz.000001",
                    "code_name": "测试公司",
                    "ipoDate": "2026-01-10",
                    "outDate": "2026-02-01",
                    "type": "1",
                    "status": "0",
                }
            ]
        )
        current_industry = pd.DataFrame(
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
        current = tables_from_baostock(
            current_basic,
            current_industry,
            fetched_at="2026-02-02T00:00:00Z",
        )
        merged = merge_incremental_network_refresh(
            previous,
            current,
            previous_refresh_time="2026-01-15T00:00:00Z",
            current_refresh_time="2026-02-02T00:00:00Z",
        )
        new_delisting = merged.lifecycle_events[
            merged.lifecycle_events["event_type"] == "delisted"
        ].iloc[0]
        self.assertEqual(
            new_delisting["availability_quality"],
            "first_observed_after_previous_refresh",
        )
        impacts = build_market_impact_stream(
            merged.lifecycle_events,
            listings=merged.listings,
            as_of="2026-02-03T00:00:00Z",
        )
        delisting_count = impacts[
            impacts["impact_channel"]
            == "market.structure.listed_security_count_change"
        ]
        self.assertEqual(delisting_count.iloc[-1]["value"], -1.0)


if __name__ == "__main__":
    unittest.main()
