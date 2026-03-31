from __future__ import annotations

from contextlib import closing

from vinted_radar.domain.events import build_listing_observed_event
from vinted_radar.domain.manifests import EvidenceManifest, EvidenceManifestEntry
from vinted_radar.models import ListingCard
from vinted_radar.platform import (
    PostgresOutbox,
    doctor_data_platform,
    render_platform_report_text,
    summarize_platform_health,
)


def test_data_platform_smoke(
    data_platform_stack,
    postgres_connect,
    clickhouse_client_factory,
    object_storage_client_factory,
) -> None:
    config = data_platform_stack.config

    bootstrap = data_platform_stack.run_cli("platform-bootstrap")
    assert bootstrap.returncode == 0, _format_process_failure(
        "platform-bootstrap",
        bootstrap.stdout,
        bootstrap.stderr,
        data_platform_stack.compose_ps(),
    )
    assert "Mode: bootstrap" in bootstrap.stdout
    assert "PostgreSQL: ok" in bootstrap.stdout
    assert "ClickHouse: ok" in bootstrap.stdout
    assert "Object storage: ok" in bootstrap.stdout
    assert "Healthy: yes" in bootstrap.stdout
    assert "- bucket state: exists yes | created yes" in bootstrap.stdout
    assert "- applied this run: V001, V002, V003" in bootstrap.stdout

    with closing(postgres_connect()) as postgres_connection:
        applied_versions = [
            int(row[0])
            for row in postgres_connection.execute(
                "SELECT version FROM platform_schema_migrations ORDER BY version"
            ).fetchall()
        ]
        assert applied_versions == [1, 2, 3]

        event, manifest = _sample_event_and_manifest(config.storage.raw_events, config.object_storage.bucket)
        publish_result = PostgresOutbox(postgres_connection).publish(
            event,
            sinks=["clickhouse", "parquet"],
            manifest=manifest,
        )

        assert publish_result.event_created is True
        assert publish_result.manifest_created is True
        assert publish_result.delivery_rows_created == 2
        assert publish_result.delivery_rows_existing == 0

        stored_event_count = int(
            postgres_connection.execute(
                "SELECT COUNT(*) FROM platform_events WHERE event_id = %s",
                (event.event_id,),
            ).fetchone()[0]
        )
        stored_manifest_count = int(
            postgres_connection.execute(
                "SELECT COUNT(*) FROM platform_evidence_manifests WHERE manifest_id = %s",
                (manifest.manifest_id,),
            ).fetchone()[0]
        )
        outbox_rows = postgres_connection.execute(
            "SELECT sink, status, manifest_id FROM platform_outbox WHERE event_id = %s ORDER BY sink",
            (event.event_id,),
        ).fetchall()

        assert stored_event_count == 1
        assert stored_manifest_count == 1
        assert outbox_rows == [
            ("clickhouse", "pending", manifest.manifest_id),
            ("parquet", "pending", manifest.manifest_id),
        ]

    clickhouse_client = clickhouse_client_factory(database=config.clickhouse.database)
    try:
        clickhouse_versions = [
            int(row[0])
            for row in clickhouse_client.query(
                "SELECT version FROM platform_schema_migrations ORDER BY version"
            ).result_rows
        ]
        assert clickhouse_versions == [1]
    finally:
        close = getattr(clickhouse_client, "close", None)
        if callable(close):
            close()

    object_storage_client = object_storage_client_factory()
    manifest_key = manifest.object_key(config.storage.manifests)
    manifest_payload = manifest.to_json().encode("utf-8")
    object_storage_client.put_object(
        Bucket=config.object_storage.bucket,
        Key=manifest_key,
        Body=manifest_payload,
        ContentType="application/json",
    )
    for marker_key in (
        f"{config.storage.raw_events}/.prefix",
        f"{config.storage.manifests}/.prefix",
        f"{config.storage.parquet}/.prefix",
    ):
        object_storage_client.head_object(Bucket=config.object_storage.bucket, Key=marker_key)
    stored_manifest = object_storage_client.get_object(
        Bucket=config.object_storage.bucket,
        Key=manifest_key,
    )
    try:
        assert stored_manifest["Body"].read() == manifest_payload
    finally:
        stored_manifest["Body"].close()

    doctor = data_platform_stack.run_cli("platform-doctor")
    assert doctor.returncode == 0, _format_process_failure(
        "platform-doctor",
        doctor.stdout,
        doctor.stderr,
        data_platform_stack.compose_ps(),
    )
    assert "Mode: doctor" in doctor.stdout
    assert "PostgreSQL: ok" in doctor.stdout
    assert "ClickHouse: ok" in doctor.stdout
    assert "Object storage: ok" in doctor.stdout
    assert "Healthy: yes" in doctor.stdout
    assert "- write probes: raw_events, manifests, parquet" in doctor.stdout

    doctor_report = doctor_data_platform(config=config)
    health_snapshot = summarize_platform_health(doctor_report)
    rendered_health = render_platform_report_text(doctor_report)

    assert health_snapshot.ok is True
    assert health_snapshot.postgres_ok is True
    assert health_snapshot.clickhouse_ok is True
    assert health_snapshot.object_storage_ok is True
    assert doctor_report.postgres.current_version == 3
    assert doctor_report.clickhouse.current_version == 2
    assert sorted(doctor_report.object_storage.write_checked_prefixes) == [
        "manifests",
        "parquet",
        "raw_events",
    ]
    assert "PostgreSQL: ok" in rendered_health
    assert "ClickHouse: ok" in rendered_health
    assert "Object storage: ok" in rendered_health
    assert "Healthy: yes" in rendered_health



def _sample_event_and_manifest(raw_events_prefix: str, bucket: str):
    listing = ListingCard(
        listing_id=904,
        source_url="https://www.vinted.fr/items/904-robe?referrer=catalog",
        canonical_url="https://www.vinted.fr/items/904-robe",
        title="Robe de smoke test",
        brand="Sézane",
        size_label="S",
        condition_label="Très bon état",
        price_amount_cents=9900,
        price_currency="€",
        total_price_amount_cents=10450,
        total_price_currency="€",
        image_url="https://images1.vinted.net/t/robe.webp",
        favourite_count=17,
        view_count=223,
        user_id=41,
        user_login="alice",
        user_profile_url="https://www.vinted.fr/member/41",
        created_at_ts=1711092000,
        source_catalog_id=2001,
        source_root_catalog_id=1904,
        raw_card={"id": 904, "title": "Robe de smoke test"},
    )
    event = build_listing_observed_event(
        listing,
        run_id="run-platform-smoke",
        observed_at="2026-03-28T19:40:00+00:00",
        source_page_number=1,
        card_position=1,
    )
    event_entry = EvidenceManifestEntry.from_bytes(
        logical_name="event-envelope",
        object_key=event.object_key(raw_events_prefix),
        data=event.to_json().encode("utf-8"),
        content_type="application/json",
    )
    manifest = EvidenceManifest.from_event(
        event,
        bucket=bucket,
        entries=[event_entry],
        metadata={"projection": "platform-smoke"},
    )
    return event, manifest



def _format_process_failure(command: str, stdout: str, stderr: str, compose_ps: str) -> str:
    return (
        f"{command} failed.\n\n"
        f"stdout:\n{stdout}\n\n"
        f"stderr:\n{stderr}\n\n"
        f"docker compose ps:\n{compose_ps}"
    )
 )
