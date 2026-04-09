#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${VPS_ENV_FILE:-${REPO_ROOT}/.env.vps}"
ASKPASS_SCRIPT="${REPO_ROOT}/.gsd/runtime/ssh-askpass.sh"

load_env() {
  if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
  fi

  : "${VPS_HOST:=46.225.113.129}"
  : "${VPS_USER:=root}"
  : "${VPS_SSH_PORT:=22}"
  : "${VPS_SSH_KEY_PATH:=${HOME}/.ssh/id_ed25519}"
}

require_secret() {
  if [[ -z "${SSH_KEY_PASSPHRASE:-}" ]]; then
    printf 'SSH_KEY_PASSPHRASE is not set. Collect it into %s before using VPS commands.\n' "${ENV_FILE}" >&2
    exit 1
  fi
}

run_with_askpass() {
  local -a command=("$@")
  local -a prefix=(env \
    "SSH_KEY_PASSPHRASE=${SSH_KEY_PASSPHRASE}" \
    "SSH_ASKPASS=${ASKPASS_SCRIPT}" \
    "SSH_ASKPASS_REQUIRE=force" \
    "DISPLAY=${DISPLAY:-gsd}")

  if command -v setsid >/dev/null 2>&1; then
    "${prefix[@]}" setsid "${command[@]}"
  else
    "${prefix[@]}" "${command[@]}"
  fi
}

ssh_target() {
  printf '%s@%s' "${VPS_USER}" "${VPS_HOST}"
}

usage() {
  cat <<EOF
Usage:
  bash scripts/vpsctl.sh config
  bash scripts/vpsctl.sh exec -- 'remote command'
  bash scripts/vpsctl.sh get REMOTE_PATH LOCAL_PATH
  bash scripts/vpsctl.sh put LOCAL_PATH REMOTE_PATH

Environment:
  - Defaults are loaded from ${ENV_FILE} when it exists.
  - Required secret for exec/get/put: SSH_KEY_PASSPHRASE
  - Optional overrides: VPS_HOST, VPS_USER, VPS_SSH_PORT, VPS_SSH_KEY_PATH, VPS_ENV_FILE
EOF
}

load_env

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

subcommand="$1"
shift

ssh_args=(
  -o BatchMode=no
  -o PreferredAuthentications=publickey,password
  -o StrictHostKeyChecking=accept-new
  -p "${VPS_SSH_PORT}"
  -i "${VPS_SSH_KEY_PATH}"
)

case "${subcommand}" in
  config)
    cat <<EOF
VPS_HOST=${VPS_HOST}
VPS_USER=${VPS_USER}
VPS_SSH_PORT=${VPS_SSH_PORT}
VPS_SSH_KEY_PATH=${VPS_SSH_KEY_PATH}
VPS_ENV_FILE=${ENV_FILE}
SSH_KEY_PASSPHRASE_SET=$([[ -n "${SSH_KEY_PASSPHRASE:-}" ]] && printf true || printf false)
EOF
    ;;
  exec)
    require_secret
    if [[ $# -lt 2 || "$1" != "--" ]]; then
      printf 'Usage: bash scripts/vpsctl.sh exec -- '\''remote command'\''\n' >&2
      exit 1
    fi
    shift
    if [[ $# -lt 1 ]]; then
      printf 'Remote command is required.\n' >&2
      exit 1
    fi
    run_with_askpass ssh "${ssh_args[@]}" "$(ssh_target)" "$*"
    ;;
  get)
    require_secret
    if [[ $# -ne 2 ]]; then
      printf 'Usage: bash scripts/vpsctl.sh get REMOTE_PATH LOCAL_PATH\n' >&2
      exit 1
    fi
    run_with_askpass scp -P "${VPS_SSH_PORT}" -o BatchMode=no -o PreferredAuthentications=publickey,password -o StrictHostKeyChecking=accept-new -i "${VPS_SSH_KEY_PATH}" "$(ssh_target):$1" "$2"
    ;;
  put)
    require_secret
    if [[ $# -ne 2 ]]; then
      printf 'Usage: bash scripts/vpsctl.sh put LOCAL_PATH REMOTE_PATH\n' >&2
      exit 1
    fi
    run_with_askpass scp -P "${VPS_SSH_PORT}" -o BatchMode=no -o PreferredAuthentications=publickey,password -o StrictHostKeyChecking=accept-new -i "${VPS_SSH_KEY_PATH}" "$1" "$(ssh_target):$2"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    printf 'Unknown subcommand: %s\n\n' "${subcommand}" >&2
    usage >&2
    exit 1
    ;;
esac
