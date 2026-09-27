from __future__ import annotations

"""Human-need/resource-first production network contract.

The network deliberately stops before financial interpretation.  A need is a
root node; companies and securities are optional carrier mappings downstream.
All rows carry an availability time so a later observation cannot alter an
earlier snapshot.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd


SCHEMA_VERSION = "human_need_resource_network_v2"
APPROVED_STRUCTURE = "accepted_model_structure"
CANDIDATE_EVIDENCE = "candidate_needs_evidence"
VERIFIED_STATUSES = {"verified", "imported", APPROVED_STRUCTURE}
SOURCE_CANDIDATE = "candidate_source"

NEED_COLUMNS = [
    "need_id", "parent_need_id", "need_name", "need_level", "need_domain",
    "need_nature", "population_scope", "biological_basis",
    "deprivation_response", "cultural_variability", "description", "event_time",
    "available_time", "evidence_kind", "source_status", "confidence", "source",
    "notes",
]
FUNCTION_COLUMNS = [
    "function_id", "parent_function_id", "function_name", "function_kind",
    "description", "event_time", "available_time", "evidence_kind",
    "source_status", "confidence", "source", "notes",
]
PROCESS_COLUMNS = [
    "process_id", "process_name", "process_kind", "description",
    "event_time", "available_time", "evidence_kind", "source_status",
    "confidence", "source", "notes",
]
RESOURCE_COLUMNS = [
    "resource_id", "resource_name", "resource_kind", "resource_class",
    "renewability", "description", "event_time", "available_time",
    "evidence_kind", "source_status", "confidence", "source", "notes",
]
NEED_FUNCTION_EDGE_COLUMNS = [
    "edge_id", "source_need_id", "target_function_id", "relation_type",
    "event_time", "available_time", "valid_from", "valid_to",
    "evidence_kind", "source_status", "confidence", "source",
    "evidence_quote", "review_status", "notes",
]
FUNCTION_PROCESS_EDGE_COLUMNS = [
    "edge_id", "source_function_id", "target_process_id", "relation_type",
    "event_time", "available_time", "valid_from", "valid_to",
    "evidence_kind", "source_status", "confidence", "source",
    "evidence_quote", "review_status", "notes",
]
PROCESS_RESOURCE_COLUMNS = [
    "dependency_id", "process_id", "resource_id", "dependency_role",
    "quantity", "unit", "measurement_scope", "geographic_scope",
    "event_time", "available_time", "valid_from", "valid_to",
    "evidence_kind", "source_status", "confidence", "source",
    "evidence_quote", "review_status", "notes",
]
ENDOWMENT_COLUMNS = [
    "observation_id", "resource_id", "geographic_unit_id",
    "geographic_unit_name", "observation_time", "available_time", "quantity",
    "unit", "measurement_scope", "renewability", "accessibility",
    "quality_status", "source", "evidence_kind", "source_status",
    "confidence", "notes",
]
CARRIER_COLUMNS = [
    "mapping_id", "process_id", "carrier_type", "carrier_id", "carrier_name",
    "role", "event_time", "available_time", "valid_from", "valid_to",
    "evidence_kind", "source_status", "confidence", "source",
    "review_status", "notes",
]
SOURCE_COLUMNS = [
    "source_id", "source_name", "publisher", "dataset_name", "official_url",
    "access_method", "license_status", "intended_resource_id", "geography_level",
    "frequency", "observation_time_field", "available_time_rule", "source_status",
    "evidence_kind", "confidence", "notes",
]
SOURCE_OBSERVATION_COLUMNS = [
    "source_id", "source_record_id", "resource_id", "geographic_unit_id",
    "geographic_unit_name", "observation_time", "available_time", "quantity",
    "unit", "measurement_scope", "renewability", "accessibility", "quality_status",
    "evidence_kind", "confidence", "notes",
]


@dataclass
class HumanNeedNetworkTables:
    needs: pd.DataFrame
    satisfaction_functions: pd.DataFrame
    transformation_processes: pd.DataFrame
    material_resources: pd.DataFrame
    need_function_edges: pd.DataFrame
    function_process_edges: pd.DataFrame
    process_resource_dependencies: pd.DataFrame
    resource_endowment_observations: pd.DataFrame
    process_carrier_mappings: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=CARRIER_COLUMNS)
    )


@dataclass
class HumanNeedNetworkSnapshot:
    needs: pd.DataFrame
    satisfaction_functions: pd.DataFrame
    transformation_processes: pd.DataFrame
    material_resources: pd.DataFrame
    need_function_edges: pd.DataFrame
    function_process_edges: pd.DataFrame
    process_resource_dependencies: pd.DataFrame
    resource_endowment_observations: pd.DataFrame
    process_carrier_mappings: pd.DataFrame


TABLE_SPECS = {
    "needs": ("needs.csv", NEED_COLUMNS),
    "satisfaction_functions": ("satisfaction_functions.csv", FUNCTION_COLUMNS),
    "transformation_processes": ("transformation_processes.csv", PROCESS_COLUMNS),
    "material_resources": ("material_resources.csv", RESOURCE_COLUMNS),
    "need_function_edges": ("need_function_edges.csv", NEED_FUNCTION_EDGE_COLUMNS),
    "function_process_edges": ("function_process_edges.csv", FUNCTION_PROCESS_EDGE_COLUMNS),
    "process_resource_dependencies": ("process_resource_dependencies.csv", PROCESS_RESOURCE_COLUMNS),
    "resource_endowment_observations": ("resource_endowment_observations.csv", ENDOWMENT_COLUMNS),
    "process_carrier_mappings": ("process_carrier_mappings.csv", CARRIER_COLUMNS),
}


def validate_source_registry(registry: pd.DataFrame, *, material_resource_ids: set[str] | None = None) -> None:
    """Validate source metadata without treating a source candidate as an observation."""
    _require_columns(registry, SOURCE_COLUMNS, "source_registry")
    _unique_ids(registry, "source_id", "source_registry")
    if material_resource_ids is not None:
        unknown = set(registry["intended_resource_id"]) - set(material_resource_ids)
        if unknown:
            raise ValueError(f"source_registry references unknown resource: {sorted(unknown)}")
    if registry["source_status"].isin({"imported", "verified"}).any():
        rows = registry[registry["source_status"].isin({"imported", "verified"})]
        if (rows["official_url"].astype(str).str.strip() == "").any():
            raise ValueError("verified source must preserve official_url")


def observations_from_source_rows(
    rows: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    as_of: str | pd.Timestamp,
    material_resource_ids: set[str],
) -> pd.DataFrame:
    """Normalize a supplied source extract; never invent missing measurements.

    The function is intentionally offline. A caller must provide the downloaded
    or manually archived rows and a source registry entry. Candidate sources may
    be inspected, but only imported/verified sources can produce observations.
    """
    _require_columns(rows, SOURCE_OBSERVATION_COLUMNS, "source_observations")
    validate_source_registry(registry, material_resource_ids=material_resource_ids)
    allowed = registry[registry["source_status"].isin({"imported", "verified"})]
    allowed_ids = set(allowed["source_id"])
    if not set(rows["source_id"]).issubset(allowed_ids):
        raise ValueError("source observations require an imported or verified source")
    if not set(rows["resource_id"]).issubset(material_resource_ids):
        raise ValueError("source observations reference unknown resource")
    result = rows.copy()
    result["observation_id"] = result.apply(
        lambda row: f"OBS_{row['source_id']}_{row['source_record_id']}", axis=1
    )
    if result["observation_id"].duplicated().any():
        raise ValueError("source observations must have unique source_id/source_record_id")
    cutoff = _as_utc(as_of)
    available = pd.to_datetime(result["available_time"], errors="coerce", utc=True, format="mixed")
    observed = pd.to_datetime(result["observation_time"], errors="coerce", utc=True, format="mixed")
    if available.isna().any() or observed.isna().any():
        raise ValueError("source observations require valid observation_time and available_time")
    if (available < observed).any():
        raise ValueError("available_time cannot be earlier than observation_time")
    if (available > cutoff).any():
        result = result.loc[available <= cutoff].copy()
    for column in ["quantity", "unit", "geographic_unit_id", "measurement_scope"]:
        if (result[column].astype(str).str.strip() == "").any():
            raise ValueError(f"source observations require {column}")
    result["source"] = result["source_id"]
    result["source_status"] = "imported"
    result["renewability"] = result["renewability"].replace("", "unknown")
    result["quality_status"] = result["quality_status"].replace("", "observed")
    return result[ENDOWMENT_COLUMNS].reset_index(drop=True)


def _as_utc(value: str | pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _available(df: pd.DataFrame, as_of: str | pd.Timestamp) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    cutoff = _as_utc(as_of)
    times = pd.to_datetime(df["available_time"], errors="coerce", utc=True, format="mixed")
    if times.isna().any():
        raise ValueError("available_time must be a valid timestamp")
    return df.loc[times <= cutoff].copy()


def _temporal_edges(df: pd.DataFrame, as_of: str | pd.Timestamp) -> pd.DataFrame:
    rows = _available(df, as_of)
    if rows.empty or "valid_from" not in rows:
        return rows
    cutoff = _as_utc(as_of)
    start = pd.to_datetime(rows["valid_from"], errors="coerce", utc=True, format="mixed")
    end = pd.to_datetime(rows["valid_to"], errors="coerce", utc=True, format="mixed")
    if start.isna().any():
        raise ValueError("valid_from must be a valid timestamp")
    return rows.loc[(start <= cutoff) & (end.isna() | (end > cutoff))].copy()


def _require_columns(df: pd.DataFrame, columns: Iterable[str], name: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{name} missing columns: {', '.join(missing)}")


def _unique_ids(df: pd.DataFrame, column: str, name: str) -> None:
    if df[column].duplicated().any():
        raise ValueError(f"{name}.{column} must be unique")


def _validate_node(df: pd.DataFrame, columns: list[str], name: str, id_column: str) -> None:
    _require_columns(df, columns, name)
    _unique_ids(df, id_column, name)
    if df[id_column].isna().any() or (df[id_column].astype(str).str.strip() == "").any():
        raise ValueError(f"{name}.{id_column} must be non-empty")


def validate_network_tables(tables: HumanNeedNetworkTables) -> None:
    _validate_node(tables.needs, NEED_COLUMNS, "needs", "need_id")
    _validate_node(tables.satisfaction_functions, FUNCTION_COLUMNS, "satisfaction_functions", "function_id")
    _validate_node(tables.transformation_processes, PROCESS_COLUMNS, "transformation_processes", "process_id")
    _validate_node(tables.material_resources, RESOURCE_COLUMNS, "material_resources", "resource_id")
    for df, columns, name in [
        (tables.need_function_edges, NEED_FUNCTION_EDGE_COLUMNS, "need_function_edges"),
        (tables.function_process_edges, FUNCTION_PROCESS_EDGE_COLUMNS, "function_process_edges"),
        (tables.process_resource_dependencies, PROCESS_RESOURCE_COLUMNS, "process_resource_dependencies"),
        (tables.resource_endowment_observations, ENDOWMENT_COLUMNS, "resource_endowment_observations"),
        (tables.process_carrier_mappings, CARRIER_COLUMNS, "process_carrier_mappings"),
    ]:
        _require_columns(df, columns, name)

    need_ids = set(tables.needs["need_id"])
    function_ids = set(tables.satisfaction_functions["function_id"])
    process_ids = set(tables.transformation_processes["process_id"])
    resource_ids = set(tables.material_resources["resource_id"])
    need_parent_ids = set(
        tables.needs.loc[
            tables.needs["parent_need_id"].astype(str).str.strip() != "",
            "parent_need_id",
        ]
    )
    if not need_parent_ids.issubset(need_ids):
        raise ValueError("needs references unknown parent_need_id")
    root_count = (tables.needs["parent_need_id"].astype(str).str.strip() == "").sum()
    if root_count != 1:
        raise ValueError("needs must contain exactly one biological population root")
    if not set(tables.need_function_edges["source_need_id"]).issubset(need_ids):
        raise ValueError("need_function_edges references unknown need")
    if not set(tables.need_function_edges["target_function_id"]).issubset(function_ids):
        raise ValueError("need_function_edges references unknown function")
    if not set(tables.function_process_edges["source_function_id"]).issubset(function_ids):
        raise ValueError("function_process_edges references unknown function")
    if not set(tables.function_process_edges["target_process_id"]).issubset(process_ids):
        raise ValueError("function_process_edges references unknown process")
    if not set(tables.process_resource_dependencies["process_id"]).issubset(process_ids):
        raise ValueError("process_resource_dependencies references unknown process")
    if not set(tables.process_resource_dependencies["resource_id"]).issubset(resource_ids):
        raise ValueError("process_resource_dependencies references unknown resource")
    if not set(tables.resource_endowment_observations["resource_id"]).issubset(resource_ids):
        raise ValueError("resource_endowment_observations references unknown resource")
    if (tables.needs["need_id"].astype(str) == tables.needs["parent_need_id"].astype(str)).any():
        raise ValueError("needs cannot parent themselves")
    if (
        tables.satisfaction_functions["function_id"].astype(str)
        == tables.satisfaction_functions["parent_function_id"].astype(str)
    ).any():
        raise ValueError("satisfaction_functions cannot parent themselves")

    parent_by_need = dict(zip(tables.needs["need_id"], tables.needs["parent_need_id"]))
    for need_id in parent_by_need:
        seen: set[str] = set()
        current = need_id
        while current:
            if current in seen:
                raise ValueError("needs hierarchy must be acyclic")
            seen.add(current)
            current = str(parent_by_need.get(current, "")).strip()
    if (tables.needs["population_scope"].astype(str).str.strip() == "").any():
        raise ValueError("every need must declare a population_scope")
    non_root = tables.needs["parent_need_id"].astype(str).str.strip() != ""
    if (non_root & (tables.needs["biological_basis"].astype(str).str.strip() == "")).any():
        raise ValueError("every non-root need must declare a biological_basis")

    # A blank quantity is allowed only when explicitly marked not observed.
    deps = tables.process_resource_dependencies
    missing_quantity = deps["quantity"].isna() | (deps["quantity"].astype(str).str.strip() == "")
    if (missing_quantity & ~deps["source_status"].isin({CANDIDATE_EVIDENCE, "not_yet_observed"})).any():
        raise ValueError("empty dependency quantity must remain candidate_needs_evidence or not_yet_observed")
    obs = tables.resource_endowment_observations
    missing_obs_quantity = obs["quantity"].isna() | (obs["quantity"].astype(str).str.strip() == "")
    if (missing_obs_quantity & ~obs["quality_status"].isin({"not_yet_observed", "not_reported"})).any():
        raise ValueError("empty resource quantity must be marked not_yet_observed or not_reported")

    # Carriers are mappings only; they cannot be roots or add a need/function fact.
    if not tables.process_carrier_mappings.empty:
        carriers = tables.process_carrier_mappings
        if carriers["carrier_type"].isin({"need", "satisfaction_function"}).any():
            raise ValueError("carrier mappings cannot point to need roots or satisfaction functions")


def load_network(directory: str | Path) -> HumanNeedNetworkTables:
    directory = Path(directory)
    frames: dict[str, pd.DataFrame] = {}
    for name, (filename, columns) in TABLE_SPECS.items():
        path = directory / filename
        if path.exists():
            frames[name] = pd.read_csv(path, dtype=str, keep_default_na=False)
        else:
            frames[name] = pd.DataFrame(columns=columns)
    tables = HumanNeedNetworkTables(**frames)
    validate_network_tables(tables)
    return tables


def build_snapshot(
    tables: HumanNeedNetworkTables,
    *,
    as_of: str | pd.Timestamp,
    include_candidates: bool = False,
) -> HumanNeedNetworkSnapshot:
    validate_network_tables(tables)
    needs = _available(tables.needs, as_of)
    functions = _available(tables.satisfaction_functions, as_of)
    processes = _available(tables.transformation_processes, as_of)
    resources = _available(tables.material_resources, as_of)
    need_edges = _temporal_edges(tables.need_function_edges, as_of)
    function_edges = _temporal_edges(tables.function_process_edges, as_of)
    dependencies = _temporal_edges(tables.process_resource_dependencies, as_of)
    observations = _available(tables.resource_endowment_observations, as_of)
    carriers = _temporal_edges(tables.process_carrier_mappings, as_of)
    if not include_candidates:
        dependencies = dependencies[dependencies["review_status"].isin(VERIFIED_STATUSES)]
        carriers = carriers[carriers["review_status"].isin(VERIFIED_STATUSES)]
    return HumanNeedNetworkSnapshot(
        needs=needs.reset_index(drop=True),
        satisfaction_functions=functions.reset_index(drop=True),
        transformation_processes=processes.reset_index(drop=True),
        material_resources=resources.reset_index(drop=True),
        need_function_edges=need_edges.reset_index(drop=True),
        function_process_edges=function_edges.reset_index(drop=True),
        process_resource_dependencies=dependencies.reset_index(drop=True),
        resource_endowment_observations=observations.reset_index(drop=True),
        process_carrier_mappings=carriers.reset_index(drop=True),
    )


def graph_records(snapshot: HumanNeedNetworkSnapshot) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return compact node/edge records for a renderer; no financial inference."""
    nodes: list[dict[str, str]] = []
    for df, id_column, label_column, node_type in [
        (snapshot.needs, "need_id", "need_name", "need"),
        (snapshot.satisfaction_functions, "function_id", "function_name", "function"),
        (snapshot.transformation_processes, "process_id", "process_name", "process"),
        (snapshot.material_resources, "resource_id", "resource_name", "resource"),
    ]:
        for _, row in df.iterrows():
            node = {"id": str(row[id_column]), "label": str(row[label_column]), "type": node_type}
            if node_type == "need":
                node.update(
                    {
                        "parent_id": str(row.get("parent_need_id", "")),
                        "level": str(row.get("need_level", "")),
                        "domain": str(row.get("need_domain", "")),
                        "nature": str(row.get("need_nature", "")),
                        "population_scope": str(row.get("population_scope", "")),
                        "biological_basis": str(row.get("biological_basis", "")),
                        "deprivation_response": str(row.get("deprivation_response", "")),
                        "description": str(row.get("description", "")),
                    }
                )
            nodes.append(node)
    edges: list[dict[str, str]] = []
    for _, row in snapshot.needs.iterrows():
        parent_id = str(row.get("parent_need_id", "")).strip()
        if parent_id:
            edges.append(
                {
                    "source": parent_id,
                    "target": str(row["need_id"]),
                    "label": "contains",
                    "status": APPROVED_STRUCTURE,
                }
            )
    for df, source, target, relation, default_status in [
        (snapshot.need_function_edges, "source_need_id", "target_function_id", "relation_type", APPROVED_STRUCTURE),
        (snapshot.function_process_edges, "source_function_id", "target_process_id", "relation_type", APPROVED_STRUCTURE),
        (snapshot.process_resource_dependencies, "process_id", "resource_id", "dependency_role", CANDIDATE_EVIDENCE),
    ]:
        for _, row in df.iterrows():
            edges.append(
                {
                    "source": str(row[source]),
                    "target": str(row[target]),
                    "label": str(row[relation]) if relation in row else "",
                    "status": str(row.get("review_status", row.get("source_status", default_status))),
                }
            )
    return nodes, edges
