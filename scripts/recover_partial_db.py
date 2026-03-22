from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vinted_radar.db_recovery import recover_partial_database, write_recovery_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recover a structurally healthy partial SQLite database by copying only source tables that still pass health probes.",
    )
    parser.add_argument("--source", default="data/vinted-radar.db", help="Corrupted source SQLite database")
    parser.add_argument("--destination", default="data/vinted-radar.recovered.db", help="Recovered destination SQLite database")
    parser.add_argument(
        "--report",
        default="data/vinted-radar.recovered.report.json",
        help="Where to write the JSON recovery report",
    )
    parser.add_argument("--integrity", action="store_true", help="Run source integrity_check in addition to quick_check before deciding what to copy")
    parser.add_argument("--force", action="store_true", help="Overwrite the destination if it already exists")
    parser.add_argument("--batch-size", type=int, default=1000, help="Row batch size for streaming table copies")
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    report = recover_partial_database(
        args.source,
        args.destination,
        include_integrity_check=args.integrity,
        force=args.force,
        batch_size=args.batch_size,
    )
    report_path = write_recovery_report(report, args.report)

    print(f"Source: {report['source_db']}")
    print(f"Destination: {report['destination_db']}")
    print(f"Report: {report_path}")
    print(f"Promoted: {report['promoted']}")
    print("Recovered tables:")
    for table in report["recovered_tables"]:
        print(f"- {table['table']}: {table['imported_rows']} rows")
    print("Skipped tables:")
    for table in report["skipped_tables"]:
        print(f"- {table['table']}: {table['reason']}")
    health = report["destination_health"]
    print(f"Recovered DB healthy: {health['healthy']}")

    return 0 if report["promoted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
