from __future__ import annotations

from dataclasses import dataclass

POSTGRES_MUTABLE_SCHEMA_VERSION = 3


@dataclass(frozen=True, slots=True)
class PostgresTableContract:
    name: str
    purpose: str
    key_columns: tuple[str, ...]
    index_names: tuple[str, ...]


POSTGRES_MUTABLE_TABLE_CONTRACTS = (
    PostgresTableContract(
        name="platform_mutable_manifests",
        purpose="Tracks mutable-truth manifest batches and their projection status for replay-safe projectors.",
        key_columns=("manifest_id",),
        index_names=(
            "idx_platform_mutable_manifests_status_time",
            "idx_platform_mutable_manifests_aggregate_time",
        ),
    ),
    PostgresTableContract(
        name="platform_discovery_runs",
        purpose="Stores current PostgreSQL-backed discovery bookkeeping instead of SQLite-only mutation rows.",
        key_columns=("run_id",),
        index_names=(
            "idx_platform_discovery_runs_status_time",
            "idx_platform_discovery_runs_finished_time",
        ),
    ),
    PostgresTableContract(
        name="platform_runtime_cycles",
        purpose="Stores runtime cycle history and per-cycle refresh counters for operator/runtime reads.",
        key_columns=("cycle_id",),
        index_names=(
            "idx_platform_runtime_cycles_started_at",
            "idx_platform_runtime_cycles_status_time",
            "idx_platform_runtime_cycles_discovery_run",
        ),
    ),
    PostgresTableContract(
        name="platform_runtime_controller_state",
        purpose="Stores the singleton runtime controller truth for pause/resume/status cutover.",
        key_columns=("controller_id",),
        index_names=(
            "idx_platform_runtime_controller_status_time",
            "idx_platform_runtime_controller_requested_action",
        ),
    ),
    PostgresTableContract(
        name="platform_catalogs",
        purpose="Stores mutable catalog metadata and projector provenance for discovery/runtime queries.",
        key_columns=("catalog_id",),
        index_names=(
            "idx_platform_catalogs_root_leaf",
            "idx_platform_catalogs_parent_order",
            "idx_platform_catalogs_synced_time",
        ),
    ),
    PostgresTableContract(
        name="platform_listing_identity",
        purpose="Stores normalized listing identity and latest normalized listing-card truth.",
        key_columns=("listing_id",),
        index_names=(
            "idx_platform_listing_identity_last_seen",
            "idx_platform_listing_identity_catalog_last_seen",
            "idx_platform_listing_identity_brand",
            "idx_platform_listing_identity_condition",
        ),
    ),
    PostgresTableContract(
        name="platform_listing_current_state",
        purpose="Stores the current listing state-machine output and latest probe/scan evidence summary.",
        key_columns=("listing_id",),
        index_names=(
            "idx_platform_listing_current_state_state_confidence",
            "idx_platform_listing_current_state_basis_state",
            "idx_platform_listing_current_state_probe_outcome",
        ),
    ),
    PostgresTableContract(
        name="platform_listing_presence_summary",
        purpose="Stores recent-presence rollups used by freshness, explorer, and runtime summaries.",
        key_columns=("listing_id",),
        index_names=(
            "idx_platform_listing_presence_summary_bucket_time",
            "idx_platform_listing_presence_summary_price_band",
            "idx_platform_listing_presence_summary_run",
        ),
    ),
    PostgresTableContract(
        name="platform_outbox_checkpoints",
        purpose="Stores projector checkpoint and lag state keyed by consumer and sink for idempotent delivery.",
        key_columns=("consumer_name", "sink"),
        index_names=(
            "idx_platform_outbox_checkpoints_status_time",
            "idx_platform_outbox_checkpoints_sink_time",
            "idx_platform_outbox_checkpoints_outbox_id",
        ),
    ),
)

POSTGRES_MUTABLE_TABLE_CONTRACTS_BY_NAME = {
    contract.name: contract for contract in POSTGRES_MUTABLE_TABLE_CONTRACTS
}
POSTGRES_MUTABLE_TABLES = tuple(contract.name for contract in POSTGRES_MUTABLE_TABLE_CONTRACTS)
POSTGRES_MUTABLE_INDEXES = tuple(
    index_name
    for contract in POSTGRES_MUTABLE_TABLE_CONTRACTS
    for index_name in contract.index_names
)

__all__ = [
    "POSTGRES_MUTABLE_INDEXES",
    "POSTGRES_MUTABLE_SCHEMA_VERSION",
    "POSTGRES_MUTABLE_TABLE_CONTRACTS",
    "POSTGRES_MUTABLE_TABLE_CONTRACTS_BY_NAME",
    "POSTGRES_MUTABLE_TABLES",
    "PostgresTableContract",
]
