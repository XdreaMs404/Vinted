from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vinted_radar.price_filter_benchmark import (
    PriceFilterBenchmarkOptions,
    run_price_filter_benchmark,
    write_price_filter_benchmark_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark Vinted API native price bounds by comparing bounded and "
            "unbounded requests on the same catalog/page window."
        )
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Where to write the benchmark JSON report.",
    )
    parser.add_argument(
        "--output-markdown",
        help="Optional Markdown summary path.",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=3,
        help="Maximum page window to request per catalog.",
    )
    parser.add_argument(
        "--max-leaf-categories",
        type=int,
        default=10,
        help="Maximum number of leaf catalogs to benchmark when --target-catalogs is not used.",
    )
    parser.add_argument(
        "--root-scope",
        default="both",
        help="Which root catalogs to benchmark: both, women, or men.",
    )
    parser.add_argument(
        "--min-price",
        type=float,
        default=30.0,
        help="Local acceptance lower bound in euros. In bounded mode it is also sent to the API.",
    )
    parser.add_argument(
        "--max-price",
        type=float,
        default=0.0,
        help="Local acceptance upper bound in euros. 0 disables the upper bound. In bounded mode it is also sent to the API.",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=3.0,
        help="Minimum delay between HTTP requests in seconds.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="HTTP timeout per request in seconds.",
    )
    parser.add_argument(
        "--http-max-retries",
        type=int,
        default=1,
        help=(
            "How many transport-layer attempts to allow per request. "
            "Default 1 keeps 403/429/challenge friction visible in the benchmark."
        ),
    )
    parser.add_argument(
        "--target-catalogs",
        action="append",
        type=int,
        default=None,
        help="Catalog ID to benchmark. Repeatable.",
    )
    parser.add_argument(
        "--proxy",
        action="append",
        default=None,
        help="Proxy URL (http://user:pass@host:port). Repeatable for a proxy pool.",
    )
    parser.add_argument(
        "--mode-order",
        choices=("alternate", "bounded-first", "unbounded-first"),
        default="alternate",
        help="How to order bounded/unbounded requests inside each catalog/page pair.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    options = PriceFilterBenchmarkOptions(
        page_limit=args.page_limit,
        max_leaf_categories=args.max_leaf_categories,
        root_scope=args.root_scope,
        request_delay=args.request_delay,
        timeout_seconds=args.timeout_seconds,
        http_max_retries=args.http_max_retries,
        min_price=args.min_price,
        max_price=args.max_price,
        target_catalogs=tuple(args.target_catalogs or ()),
        proxies=tuple(args.proxy or ()),
        mode_order=args.mode_order,
    )
    report = run_price_filter_benchmark(options)
    written = write_price_filter_benchmark_report(
        report,
        json_path=Path(args.output_json),
        markdown_path=None if not args.output_markdown else Path(args.output_markdown),
    )

    by_mode = dict(report.get("aggregates", {}).get("by_mode", {}))
    delta = dict(report.get("aggregates", {}).get("delta", {}))
    print(f"Benchmark: {report['benchmark_id']}")
    print(f"JSON: {written['json']}")
    if "markdown" in written:
        print(f"Markdown: {written['markdown']}")
    print(f"Catalogs: {len(report.get('catalogs', []))}")
    print(f"Page records: {len(report.get('pages', []))}")
    for mode in ("bounded", "unbounded"):
        summary = dict(by_mode.get(mode) or {})
        print(
            "{mode}: requests={requests} success={success} failures={failures} "
            "challenge_suspects={challenges} accepted/request={per_request} "
            "weighted_ratio={weighted_ratio}".format(
                mode=mode,
                requests=summary.get("request_count", 0),
                success=summary.get("success_count", 0),
                failures=summary.get("failure_count", 0),
                challenges=summary.get("challenge_suspected_count", 0),
                per_request=_fmt(summary.get("accepted_listings_per_request")),
                weighted_ratio=_fmt(summary.get("accepted_ratio_weighted")),
            )
        )
    print(
        "delta: accepted/request={per_request_delta} weighted_ratio={ratio_delta} "
        "requests/100 accepted={requests_delta}".format(
            per_request_delta=_fmt(delta.get("accepted_listings_per_request_delta")),
            ratio_delta=_fmt(delta.get("accepted_ratio_weighted_delta")),
            requests_delta=_fmt(
                delta.get("estimated_requests_per_100_accepted_listings_delta")
            ),
        )
    )
    return 0


def _fmt(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.4f}"


if __name__ == "__main__":
    raise SystemExit(main())
