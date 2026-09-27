"""Normalize public-fund product, controller, and disclosed holding evidence."""

from __future__ import annotations

import hashlib
import re
from typing import Any

import pandas as pd

from stock_model.capital_control import (
    CAPITAL_POOL_COLUMNS,
    CONTROLLER_COLUMNS,
    CONTROL_RELATION_COLUMNS,
)


PUBLIC_FUND_PRODUCT_COLUMNS = [
    "fund_id",
    "fund_code",
    "fund_name",
    "full_name",
    "fund_type",
    "established_date",
    "net_assets",
    "net_assets_unit",
    "net_assets_report_date",
    "net_assets_scope",
    "manager_company",
    "custodian",
    "manager_names",
    "source",
    "source_record_id",
    "available_time",
    "availability_policy",
    "evidence_kind",
    "quality_status",
]

PUBLIC_FUND_HOLDING_COLUMNS = [
    "holding_id",
    "fund_id",
    "fund_code",
    "report_period_end",
    "instrument_id",
    "security_name",
    "portfolio_weight",
    "shares",
    "shares_unit",
    "market_value",
    "market_value_unit",
    "holding_scope",
    "available_time",
    "availability_policy",
    "source",
    "source_record_id",
    "evidence_kind",
    "quality_status",
]

PUBLIC_FUND_REPORT_COLUMNS = [
    "report_id",
    "fund_id",
    "fund_code",
    "announcement_title",
    "announcement_date",
    "report_period_end",
    "source",
    "source_record_id",
    "available_time",
    "availability_policy",
    "evidence_kind",
    "quality_status",
]

CAPITAL_POSITION_COLUMNS = [
    "position_id",
    "capital_pool_id",
    "instrument_id",
    "report_period_end",
    "position_amount",
    "amount_unit",
    "position_scope",
    "portfolio_weight",
    "available_time",
    "availability_policy",
    "source",
    "source_record_id",
    "evidence_kind",
    "quality_status",
]

PUBLIC_FUND_HOLDING_CHANGE_COLUMNS = [
    "change_id",
    "fund_id",
    "fund_code",
    "previous_period_end",
    "current_period_end",
    "instrument_id",
    "security_name",
    "comparison_status",
    "previous_shares",
    "current_shares",
    "share_change",
    "previous_market_value",
    "current_market_value",
    "market_value_change",
    "previous_portfolio_weight",
    "current_portfolio_weight",
    "portfolio_weight_change",
    "available_time",
    "availability_policy",
    "method",
    "evidence_kind",
    "source_record_ids",
    "quality_status",
]


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def _security_id(code: object) -> str:
    raw_value = str(code).strip()
    if re.fullmatch(r"\d{5}", raw_value):
        return f"{raw_value}.HK"
    value = raw_value.zfill(6)
    if value.startswith("6"):
        return f"{value}.SH"
    if value.startswith(("0", "3")):
        return f"{value}.SZ"
    if value.startswith(("4", "8", "9")):
        return f"{value}.BJ"
    return f"{value}.UNKNOWN"


def _quarter_end(label: object) -> str:
    match = re.search(r"(\d{4})年([1-4])季度", str(label))
    if not match:
        raise ValueError(f"Cannot parse fund holding quarter: {label}")
    year, quarter = int(match.group(1)), int(match.group(2))
    month_day = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}[quarter]
    return f"{year:04d}-{month_day}"


def report_period_end_from_title(title: object) -> str | None:
    """Parse a periodic-report title into its economic report period end."""

    text = str(title)
    year_match = re.search(r"(\d{4})年", text)
    if not year_match:
        return None
    year = int(year_match.group(1))
    quarter_match = re.search(r"第([1-4])季度报告", text)
    if quarter_match:
        return _quarter_end(f"{year}年{quarter_match.group(1)}季度")
    if "中期报告" in text:
        return f"{year:04d}-06-30"
    if "年度报告" in text:
        return f"{year:04d}-12-31"
    return None


def normalize_fund_announcement_reports(
    reports: pd.DataFrame,
    *,
    fund_code: str,
    fetched_at: str,
) -> pd.DataFrame:
    """Normalize the report index and use its announcement date as availability."""

    required = {"基金代码", "公告标题", "公告日期", "报告ID"}
    missing = required - set(reports.columns)
    if missing:
        raise ValueError(f"Fund report index is missing columns: {sorted(missing)}")
    fund_code = str(fund_code).zfill(6)
    fund_id = f"PUBLIC_FUND_{fund_code}"
    rows = []
    for row in reports.itertuples(index=False):
        period_end = report_period_end_from_title(getattr(row, "公告标题"))
        announcement_date = pd.to_datetime(
            getattr(row, "公告日期"), errors="coerce"
        )
        if pd.isna(announcement_date):
            continue
        announcement_date_text = announcement_date.strftime("%Y-%m-%d")
        rows.append(
            {
                "report_id": _stable_id("FUND_REPORT", fund_id, getattr(row, "报告ID")),
                "fund_id": fund_id,
                "fund_code": fund_code,
                "announcement_title": str(getattr(row, "公告标题")).strip(),
                "announcement_date": announcement_date_text,
                "report_period_end": period_end,
                "source": "Eastmoney fund report index via AkShare fund_announcement_report_em",
                "source_record_id": str(getattr(row, "报告ID")),
                "available_time": f"{announcement_date_text}T23:59:59+08:00",
                "availability_policy": "available_after_announcement_date_end",
                "evidence_kind": "official_announcement_index",
                "quality_status": "third_party_index_date_unverified_pdf",
            }
        )
    result = pd.DataFrame(rows, columns=PUBLIC_FUND_REPORT_COLUMNS)
    if result["report_id"].duplicated().any():
        raise ValueError("Duplicate normalized public-fund report")
    return result.sort_values("announcement_date").reset_index(drop=True)


def _overview_assets(value: object) -> tuple[float | None, str, str | None]:
    text = str(value)
    amount_match = re.search(r"([\d.]+)亿元", text)
    date_match = re.search(r"截止至[：:]\s*(\d{4})年(\d{2})月(\d{2})日", text)
    amount = round(float(amount_match.group(1)) * 100_000_000, 2) if amount_match else None
    report_date = (
        f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        if date_match
        else None
    )
    return amount, "CNY", report_date


def _overview_date(value: object) -> str | None:
    match = re.search(r"(\d{4})年(\d{2})月(\d{2})日", str(value))
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}" if match else None


def normalize_fund_overview(
    overview: pd.DataFrame,
    *,
    fund_code: str,
    available_time: str,
) -> pd.DataFrame:
    """Normalize one Eastmoney fund overview row without inventing validity dates."""

    if len(overview) != 1:
        raise ValueError("Expected exactly one fund overview row")
    required = {
        "基金全称",
        "基金简称",
        "基金类型",
        "成立日期/规模",
        "净资产规模",
        "基金管理人",
        "基金托管人",
        "基金经理人",
    }
    missing = required - set(overview.columns)
    if missing:
        raise ValueError(f"Fund overview is missing columns: {sorted(missing)}")
    row = overview.iloc[0]
    assets, assets_unit, assets_date = _overview_assets(row["净资产规模"])
    fund_id = f"PUBLIC_FUND_{str(fund_code).zfill(6)}"
    record = {
        "fund_id": fund_id,
        "fund_code": str(fund_code).zfill(6),
        "fund_name": str(row["基金简称"]).strip(),
        "full_name": str(row["基金全称"]).strip(),
        "fund_type": str(row["基金类型"]).strip(),
        "established_date": _overview_date(row["成立日期/规模"]),
        "net_assets": assets,
        "net_assets_unit": assets_unit,
        "net_assets_report_date": assets_date,
        "net_assets_scope": "source_fund_code_share_class_or_unknown",
        "manager_company": str(row["基金管理人"]).strip(),
        "custodian": str(row["基金托管人"]).strip(),
        "manager_names": str(row["基金经理人"]).strip(),
        "source": "Eastmoney fund overview via AkShare fund_overview_em",
        "source_record_id": f"jbgk_{str(fund_code).zfill(6)}",
        "available_time": available_time,
        "availability_policy": "local_first_observation_not_official_announcement_time",
        "evidence_kind": "aggregated_observation",
        "quality_status": "third_party_aggregator_unverified",
    }
    return pd.DataFrame([record], columns=PUBLIC_FUND_PRODUCT_COLUMNS)


def normalize_fund_holdings(
    holdings: pd.DataFrame,
    *,
    fund_code: str,
    available_time: str,
    report_available_times: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Normalize disclosed holdings; source units are 万股 and 万元."""

    required = {"股票代码", "股票名称", "占净值比例", "持股数", "持仓市值", "季度"}
    missing = required - set(holdings.columns)
    if missing:
        raise ValueError(f"Fund holdings are missing columns: {sorted(missing)}")
    fund_code = str(fund_code).zfill(6)
    fund_id = f"PUBLIC_FUND_{fund_code}"
    rows = []
    report_available_times = report_available_times or {}
    for row in holdings.itertuples(index=False):
        quarter = getattr(row, "季度")
        report_period_end = _quarter_end(quarter)
        holding_available_time = report_available_times.get(report_period_end, available_time)
        holding_availability_policy = (
            "available_after_announcement_date_end"
            if report_period_end in report_available_times
            else "local_first_observation_not_official_announcement_time"
        )
        instrument_id = _security_id(getattr(row, "股票代码"))
        weight = round(float(getattr(row, "占净值比例")) / 100.0, 10)
        shares = round(float(getattr(row, "持股数")) * 10_000, 4)
        market_value = round(float(getattr(row, "持仓市值")) * 10_000, 2)
        rows.append(
            {
                "holding_id": _stable_id(
                    "FUND_HOLDING", fund_id, report_period_end, instrument_id
                ),
                "fund_id": fund_id,
                "fund_code": fund_code,
                "report_period_end": report_period_end,
                "instrument_id": instrument_id,
                "security_name": str(getattr(row, "股票名称")).strip(),
                "portfolio_weight": weight,
                "shares": shares,
                "shares_unit": "share",
                "market_value": market_value,
                "market_value_unit": "CNY",
                "holding_scope": "source_fund_portfolio_scope_unknown",
                "available_time": holding_available_time,
                "availability_policy": holding_availability_policy,
                "source": "Eastmoney fund holdings via AkShare fund_portfolio_hold_em",
                "source_record_id": f"ccmx_{fund_code}|{quarter}|{instrument_id}",
                "evidence_kind": "aggregated_observation",
                "quality_status": "third_party_aggregator_unverified",
            }
        )
    result = pd.DataFrame(rows, columns=PUBLIC_FUND_HOLDING_COLUMNS)
    if result["holding_id"].duplicated().any():
        raise ValueError("Duplicate normalized public-fund holding")
    return result.sort_values(["report_period_end", "portfolio_weight"], ascending=[True, False]).reset_index(drop=True)


def capital_control_tables_from_fund(
    product: pd.Series,
    holdings: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Map explicit product metadata and positions into capital-control tables.

    Manager validity start dates are not supplied by the overview source, so
    relations are only available from local first observation and are not
    backfilled to the holding report dates.
    """

    fund_id = str(product["fund_id"])
    available_time = str(product["available_time"])
    manager_company = str(product["manager_company"])
    custodian = str(product["custodian"])
    managers = [
        item.strip()
        for item in re.split(r"[、,，\s]+", str(product["manager_names"]))
        if item.strip()
    ]
    company_id = _stable_id("CONTROLLER_ORG", manager_company)
    custodian_id = _stable_id("CONTROLLER_CUSTODIAN", custodian)
    controllers = [
        {
            "controller_id": company_id,
            "controller_class": "fund_management_company",
            "display_name": manager_company,
            "identity_scope": "named_organization",
            "identity_basis": "third_party_fund_overview",
            "source": product["source"],
            "source_record_id": product["source_record_id"],
            "available_time": available_time,
            "quality_status": product["quality_status"],
        },
        {
            "controller_id": custodian_id,
            "controller_class": "custodian_nominee",
            "display_name": custodian,
            "identity_scope": "named_organization",
            "identity_basis": "third_party_fund_overview",
            "source": product["source"],
            "source_record_id": product["source_record_id"],
            "available_time": available_time,
            "quality_status": product["quality_status"],
        },
    ]
    manager_ids = []
    for manager in managers:
        manager_id = _stable_id("CONTROLLER_PERSON", manager_company, manager)
        manager_ids.append(manager_id)
        controllers.append(
            {
                "controller_id": manager_id,
                "controller_class": "fund_manager",
                "display_name": manager,
                "identity_scope": "named_person_unverified_identity",
                "identity_basis": "third_party_fund_overview_name_only",
                "source": product["source"],
                "source_record_id": product["source_record_id"],
                "available_time": available_time,
                "quality_status": product["quality_status"],
            }
        )
    controller_frame = pd.DataFrame(controllers, columns=CONTROLLER_COLUMNS)
    pool = pd.DataFrame(
        [
            {
                "capital_pool_id": fund_id,
                "pool_type": "public_fund_product",
                "display_name": product["full_name"],
                "currency": "CNY",
                "source": product["source"],
                "source_record_id": product["source_record_id"],
                "available_time": available_time,
                "quality_status": product["quality_status"],
            }
        ],
        columns=CAPITAL_POOL_COLUMNS,
    )
    relations = []
    for controller_id, role in [
        (company_id, "mandate_decision_maker"),
        (custodian_id, "custodian_nominee"),
        *[(manager_id, "mandate_decision_maker") for manager_id in manager_ids],
    ]:
        relations.append(
            {
                "relation_id": _stable_id("CONTROL_RELATION", fund_id, controller_id, role),
                "capital_pool_id": fund_id,
                "controller_id": controller_id,
                "control_role": role,
                "valid_from": pd.NA,
                "valid_to": pd.NA,
                "control_share": pd.NA,
                "available_time": available_time,
                "evidence_kind": "aggregated_observation",
                "source": product["source"],
                "source_record_id": product["source_record_id"],
                "confidence": "medium_unverified",
                "quality_status": product["quality_status"],
            }
        )
    relation_frame = pd.DataFrame(relations, columns=CONTROL_RELATION_COLUMNS)
    positions = pd.DataFrame(
        [
            {
                "position_id": row.holding_id,
                "capital_pool_id": fund_id,
                "instrument_id": row.instrument_id,
                "report_period_end": row.report_period_end,
                "position_amount": row.market_value,
                "amount_unit": row.market_value_unit,
                "position_scope": row.holding_scope,
                "portfolio_weight": row.portfolio_weight,
                "available_time": row.available_time,
                "availability_policy": row.availability_policy,
                "source": row.source,
                "source_record_id": row.source_record_id,
                "evidence_kind": row.evidence_kind,
                "quality_status": row.quality_status,
            }
            for row in holdings.itertuples(index=False)
        ],
        columns=CAPITAL_POSITION_COLUMNS,
    )
    return controller_frame, pool, relation_frame, positions


def build_reported_holding_changes(holdings: pd.DataFrame) -> pd.DataFrame:
    """Compare adjacent disclosed holding sets without treating absence as zero.

    Only securities present in both adjacent disclosure sets receive numeric
    changes.  Entering or leaving the disclosed top-holdings set is a coverage
    event, not proof of a purchase or full sale.
    """

    missing = set(PUBLIC_FUND_HOLDING_COLUMNS) - set(holdings.columns)
    if missing:
        raise ValueError(f"Fund holdings are missing columns: {sorted(missing)}")
    rows = []
    for fund_id, fund_holdings in holdings.groupby("fund_id", sort=True):
        periods = sorted(fund_holdings["report_period_end"].dropna().unique())
        for previous_period, current_period in zip(periods, periods[1:]):
            previous = fund_holdings[
                fund_holdings["report_period_end"].eq(previous_period)
            ].set_index("instrument_id")
            current = fund_holdings[
                fund_holdings["report_period_end"].eq(current_period)
            ].set_index("instrument_id")
            instruments = sorted(set(previous.index) | set(current.index))
            for instrument_id in instruments:
                in_previous = instrument_id in previous.index
                in_current = instrument_id in current.index
                previous_row = previous.loc[instrument_id] if in_previous else None
                current_row = current.loc[instrument_id] if in_current else None
                if in_previous and in_current:
                    status = "present_in_both_disclosures"
                    share_change = float(current_row["shares"]) - float(previous_row["shares"])
                    market_value_change = float(current_row["market_value"]) - float(previous_row["market_value"])
                    weight_change = float(current_row["portfolio_weight"]) - float(previous_row["portfolio_weight"])
                elif in_current:
                    status = "entered_disclosed_set_actual_prior_position_unknown"
                    share_change = None
                    market_value_change = None
                    weight_change = None
                else:
                    status = "left_disclosed_set_actual_current_position_unknown"
                    share_change = None
                    market_value_change = None
                    weight_change = None
                reference = current_row if in_current else previous_row
                current_available = (
                    str(current_row["available_time"])
                    if in_current
                    else str(
                        current["available_time"].dropna().iloc[0]
                        if not current.empty
                        else reference["available_time"]
                    )
                )
                source_ids = [
                    str(row["holding_id"])
                    for row in [previous_row, current_row]
                    if row is not None
                ]
                rows.append(
                    {
                        "change_id": _stable_id(
                            "FUND_HOLDING_CHANGE",
                            fund_id,
                            previous_period,
                            current_period,
                            instrument_id,
                        ),
                        "fund_id": fund_id,
                        "fund_code": str(reference["fund_code"]).zfill(6),
                        "previous_period_end": previous_period,
                        "current_period_end": current_period,
                        "instrument_id": instrument_id,
                        "security_name": str(reference["security_name"]),
                        "comparison_status": status,
                        "previous_shares": float(previous_row["shares"]) if in_previous else None,
                        "current_shares": float(current_row["shares"]) if in_current else None,
                        "share_change": share_change,
                        "previous_market_value": float(previous_row["market_value"]) if in_previous else None,
                        "current_market_value": float(current_row["market_value"]) if in_current else None,
                        "market_value_change": market_value_change,
                        "previous_portfolio_weight": float(previous_row["portfolio_weight"]) if in_previous else None,
                        "current_portfolio_weight": float(current_row["portfolio_weight"]) if in_current else None,
                        "portfolio_weight_change": weight_change,
                        "available_time": current_available,
                        "availability_policy": "available_after_current_report_announcement_date_end",
                        "method": "adjacent_disclosed_holding_set_comparison_no_trade_attribution",
                        "evidence_kind": "derived_interval_observation",
                        "source_record_ids": "|".join(source_ids),
                        "quality_status": "top_holdings_only_absence_is_not_zero_position",
                    }
                )
    result = pd.DataFrame(rows, columns=PUBLIC_FUND_HOLDING_CHANGE_COLUMNS)
    if not result.empty and result["change_id"].duplicated().any():
        raise ValueError("Duplicate reported holding change")
    return result
