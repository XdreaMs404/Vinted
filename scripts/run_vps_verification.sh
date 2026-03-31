#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH=".:${PYTHONPATH}"
else
  export PYTHONPATH="."
fi

MODE="short"
DB_PATH="${VINTED_RADAR_DB:-data/vinted-radar.db}"
BASE_URL="${VINTED_RADAR_BASE_URL:-}"
LISTING_ID="${VINTED_RADAR_LISTING_ID:-}"
TIMEOUT="${VINTED_RADAR_VERIFY_TIMEOUT:-30}"
EXPECTED_CUTOVER_MODE="${VINTED_RADAR_EXPECTED_CUTOVER_MODE:-polyglot-cutover}"
START_COMPOSE="false"
SKIP_BOOTSTRAP="false"
SKIP_BATCH="false"
SET_CUTOVER_FLAGS="false"
COMPOSE_FILE="infra/docker-compose.data-platform.yml"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_vps_verification.sh [options]

Runs the repo's VPS verification flow in either short or long mode.

Modes:
  --mode short    Fast smoke checks: doctor, audit, runtime-status, lifecycle dry-run, public serving check.
  --mode long     Stronger proof: optional compose start, bootstrap, reconcile, audit, narrow batch, full cutover proof.

Options:
  --mode short|long                Verification mode. Default: short.
  --db-path PATH                   SQLite DB path. Default: $VINTED_RADAR_DB or data/vinted-radar.db.
  --base-url URL                   Public/base URL for serving verification. Required in short mode.
  --listing-id ID                  Representative listing ID. Required in short mode, optional in long mode.
  --timeout SECONDS                Per-request timeout. Default: $VINTED_RADAR_VERIFY_TIMEOUT or 30.
  --expected-cutover-mode MODE     Expected mode for HTTP / cutover checks. Default: polyglot-cutover.
  --start-compose                  In long mode, run 'docker compose -f infra/docker-compose.data-platform.yml up -d' first.
  --skip-bootstrap                 In long mode, skip platform-bootstrap.
  --skip-batch                     In long mode, skip the narrow batch cycle.
  --set-cutover-flags              Export the four cutover env flags=true in this shell before long-mode checks.
  --compose-file PATH              Override the compose file used by --start-compose.
  -h, --help                       Show this help text.

Environment shortcuts:
  VINTED_RADAR_DB
  VINTED_RADAR_BASE_URL
  VINTED_RADAR_LISTING_ID
  VINTED_RADAR_VERIFY_TIMEOUT
  VINTED_RADAR_EXPECTED_CUTOVER_MODE

Examples:
  scripts/run_vps_verification.sh \
    --mode short \
    --base-url https://radar.example.com/radar \
    --listing-id 1234567890

  scripts/run_vps_verification.sh \
    --mode long \
    --db-path data/vinted-radar.db \
    --base-url https://radar.example.com/radar \
    --set-cutover-flags \
    --start-compose
EOF
}

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

run() {
  printf '\n==> %s\n' "$*"
  "$@"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      [[ $# -ge 2 ]] || fail "--mode requires a value"
      MODE="$2"
      shift 2
      ;;
    --db-path)
      [[ $# -ge 2 ]] || fail "--db-path requires a value"
      DB_PATH="$2"
      shift 2
      ;;
    --base-url)
      [[ $# -ge 2 ]] || fail "--base-url requires a value"
      BASE_URL="$2"
      shift 2
      ;;
    --listing-id)
      [[ $# -ge 2 ]] || fail "--listing-id requires a value"
      LISTING_ID="$2"
      shift 2
      ;;
    --timeout)
      [[ $# -ge 2 ]] || fail "--timeout requires a value"
      TIMEOUT="$2"
      shift 2
      ;;
    --expected-cutover-mode)
      [[ $# -ge 2 ]] || fail "--expected-cutover-mode requires a value"
      EXPECTED_CUTOVER_MODE="$2"
      shift 2
      ;;
    --start-compose)
      START_COMPOSE="true"
      shift
      ;;
    --skip-bootstrap)
      SKIP_BOOTSTRAP="true"
      shift
      ;;
    --skip-batch)
      SKIP_BATCH="true"
      shift
      ;;
    --set-cutover-flags)
      SET_CUTOVER_FLAGS="true"
      shift
      ;;
    --compose-file)
      [[ $# -ge 2 ]] || fail "--compose-file requires a value"
      COMPOSE_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

case "$MODE" in
  short|long) ;;
  *) fail "--mode must be 'short' or 'long'" ;;
esac

require_command python3

printf 'Repo root: %s\n' "$REPO_ROOT"
printf 'Mode: %s\n' "$MODE"
printf 'DB path: %s\n' "$DB_PATH"
printf 'Base URL: %s\n' "${BASE_URL:-<none>}"
printf 'Listing ID: %s\n' "${LISTING_ID:-<none>}"
printf 'Expected cutover mode: %s\n' "$EXPECTED_CUTOVER_MODE"

if [[ "$MODE" == "short" ]]; then
  [[ -n "$BASE_URL" ]] || fail "short mode requires --base-url or VINTED_RADAR_BASE_URL"
  [[ -n "$LISTING_ID" ]] || fail "short mode requires --listing-id or VINTED_RADAR_LISTING_ID"

  run python3 -m vinted_radar.cli platform-doctor
  run python3 -m vinted_radar.cli platform-audit --db "$DB_PATH" --format json
  run python3 -m vinted_radar.cli runtime-status --db "$DB_PATH" --format json
  run python3 -m vinted_radar.cli platform-lifecycle --dry-run
  run python3 scripts/verify_vps_serving.py \
    --base-url "$BASE_URL" \
    --listing-id "$LISTING_ID" \
    --timeout "$TIMEOUT" \
    --expected-cutover-mode "$EXPECTED_CUTOVER_MODE"

  printf '\nShort VPS verification passed.\n'
  exit 0
fi

if [[ "$SET_CUTOVER_FLAGS" == "true" ]]; then
  export VINTED_RADAR_PLATFORM_ENABLE_POSTGRES_WRITES=true
  export VINTED_RADAR_PLATFORM_ENABLE_CLICKHOUSE_WRITES=true
  export VINTED_RADAR_PLATFORM_ENABLE_OBJECT_STORAGE_WRITES=true
  export VINTED_RADAR_PLATFORM_ENABLE_POLYGLOT_READS=true
  printf 'Cutover flags exported in current shell.\n'
else
  printf 'Cutover flags not modified by the script; using current shell environment as-is.\n'
fi

if [[ "$START_COMPOSE" == "true" ]]; then
  require_command docker
  run docker compose -f "$COMPOSE_FILE" up -d
fi

if [[ "$SKIP_BOOTSTRAP" != "true" ]]; then
  run python3 -m vinted_radar.cli platform-bootstrap
fi
run python3 -m vinted_radar.cli platform-doctor
run python3 -m vinted_radar.cli platform-reconcile --db "$DB_PATH"
run python3 -m vinted_radar.cli platform-audit --db "$DB_PATH" --format json

if [[ "$SKIP_BATCH" != "true" ]]; then
  run python3 -m vinted_radar.cli batch \
    --db "$DB_PATH" \
    --page-limit 1 \
    --max-leaf-categories 1 \
    --state-refresh-limit 2
fi

VERIFY_ARGS=(
  python3 scripts/verify_cutover_stack.py
  --db-path "$DB_PATH"
  --timeout "$TIMEOUT"
  --expected-cutover-mode "$EXPECTED_CUTOVER_MODE"
  --json
)

if [[ -n "$BASE_URL" ]]; then
  VERIFY_ARGS+=(--base-url "$BASE_URL")
fi

if [[ -n "$LISTING_ID" ]]; then
  VERIFY_ARGS+=(--listing-id "$LISTING_ID")
fi

run "${VERIFY_ARGS[@]}"

printf '\nLong VPS verification passed.\n'
