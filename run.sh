#!/usr/bin/env bash
set -euo pipefail

# ENV-06: MSYS2 (Git Bash) rewrites POSIX-looking path arguments into Windows
# paths before invoking docker.exe, corrupting container-side paths. Disable
# that rewriting for this script's docker invocations. This is a no-op on
# Linux and macOS, where OSTYPE never matches msys*/cygwin*.
case "${OSTYPE:-}" in
  msys*|cygwin*)
    export MSYS_NO_PATHCONV=1
    ;;
esac

# env_value NAME — read a value out of .env without sourcing it. Selects the
# last line matching ^NAME=, strips the key and the "=", and prints the
# remainder. .env is never sourced: a config file should not be able to run
# arbitrary shell.
env_value() {
  local name="$1"
  local line=""
  line="$(grep -E "^${name}=" .env 2>/dev/null | tail -n1 || true)"
  printf '%s' "${line#*=}"
}

# require_file PATH MESSAGE — exit 1 with MESSAGE on stderr when PATH does
# not exist. Called before any docker invocation for subcommands whose
# target does not exist yet in this phase, so a Phase 1 clone fails instantly
# instead of triggering an unwanted image pull.
require_file() {
  local path="$1"
  local message="$2"
  if [ ! -e "$path" ]; then
    echo "$message" >&2
    exit 1
  fi
}

# run_step LABEL COMMAND... — lean output with full detail on failure (D-12).
# Captures combined stdout/stderr of COMMAND into a temp file. On success,
# prints one status line. On failure, prints a failure status line followed
# by the entire captured output on stderr, then returns COMMAND's exit
# status.
run_step() {
  local label="$1"
  shift
  local tmp status
  tmp="$(mktemp)"
  if "$@" >"$tmp" 2>&1; then
    echo "[ok]   ${label}"
    rm -f "$tmp"
    return 0
  else
    status=$?
    echo "[FAIL] ${label}" >&2
    cat "$tmp" >&2
    rm -f "$tmp"
    return "$status"
  fi
}

# preflight — six ordered checks with an actionable remedy for each failure
# (D-13). Never creates .env; check 6 is the mitigation for T-01-03.
preflight() {
  if ! docker info >/dev/null 2>&1; then
    echo "Docker does not appear to be running. Start Docker Desktop (or the docker daemon) and retry." >&2
    exit 1
  fi

  if ! docker compose version >/dev/null 2>&1; then
    echo "docker compose is not available. Install the Docker Compose v2 plugin." >&2
    exit 1
  fi

  if ! docker compose up --help 2>&1 | grep -q -- '--wait'; then
    echo "Your docker compose does not support --wait. Upgrade to Docker Compose v2.1.1 or newer." >&2
    exit 1
  fi

  if [ ! -f .env ]; then
    echo "No .env file found. Run: cp .env.example .env" >&2
    exit 1
  fi

  local var value
  for var in PROJECT_NAME AWS_ENDPOINT_URL AWS_DEFAULT_REGION AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; do
    value="$(env_value "$var")"
    if [ -z "$value" ]; then
      echo "${var} is missing or empty in .env. Check .env.example for the expected variables." >&2
      exit 1
    fi
  done

  local endpoint
  endpoint="$(env_value AWS_ENDPOINT_URL)"
  case "$endpoint" in
    *amazonaws.com*)
      echo "AWS_ENDPOINT_URL (${endpoint}) points at a real AWS endpoint. run.sh drives the local emulator only; refusing to continue." >&2
      exit 1
      ;;
  esac
}

# usage — fixed block listing all eight subcommands in a fixed order, one per
# line with a description. A literal heredoc, not a loop over an unordered
# structure, so two invocations are byte-identical.
usage() {
  cat <<'EOF'
Usage: ./run.sh <subcommand>

  up         Start the emulator, then bootstrap the catalog and seed sample data
  down       Stop the emulator and remove volumes
  bootstrap  Create or update the Glue database, table, and partitions in the catalog
  seed       Upload sample CSV data to the emulated S3 bucket
  job        Run the csv_to_parquet Glue job
  test       Run the pytest suite inside the Glue container
  lint       Run ruff check and ruff format --check inside the tools container
  demo       Run up, then job, then test, then print a summary
EOF
}

# cmd_up — bring up the emulator, then bootstrap the catalog, then seed sample
# data (D-09). Fixed order: compose-up, then bootstrap, then seed. run_step
# propagates the first failing step's exit status and aborts the chain.
cmd_up() {
  preflight
  run_step "start emulator" docker compose up -d --wait floci
  cmd_bootstrap
  cmd_seed
  echo "Environment is up: floci emulator healthy, catalog bootstrapped, sample data seeded."
}

# cmd_down — stop the emulator and remove volumes/orphans so nothing lingers
# from a memory-mode emulator or an anonymous volume left by run --rm.
cmd_down() {
  preflight
  run_step "stop emulator" docker compose down -v --remove-orphans
}

# cmd_bootstrap — create or update the Glue database, table, and partitions
# (D-05). Runs in the tools service, never the Glue image.
cmd_bootstrap() {
  preflight
  run_step "bootstrap catalog" docker compose --profile tools run --rm tools python catalog/bootstrap.py
}

# cmd_seed — upload sample CSV data to the emulated S3 bucket.
cmd_seed() {
  preflight
  run_step "seed sample data" docker compose --profile tools run --rm tools python catalog/seed.py
}

# cmd_job — run the csv_to_parquet Glue job (D-07). require_file runs before
# any docker invocation so a Phase 1 clone fails instantly instead of
# triggering an unwanted ~4.77 GB Glue image pull.
cmd_job() {
  require_file jobs/csv_to_parquet/job.py "jobs/csv_to_parquet/job.py not found. This subcommand is wired in Phase 1 but only functional from Phase 2 onward."
  preflight
  echo "First run downloads the AWS Glue image (~4.8 GB). This may take a while."
  run_step "run csv_to_parquet job" docker compose --profile glue run --rm glue spark-submit jobs/csv_to_parquet/job.py --JOB_NAME csv_to_parquet
}

# cmd_test — run the pytest suite inside the Glue container. require_file
# runs before any docker invocation for the same reason as cmd_job.
cmd_test() {
  require_file tests "tests not found. This subcommand is wired in Phase 1 but only functional from Phase 2 onward."
  preflight
  run_step "run pytest suite" docker compose --profile glue run --rm glue -c "python3 -m pytest --disable-warnings"
}

# cmd_lint — ruff check, then ruff format --check, both against the tools
# service. Must exit 0 on a clean clone (no Python files yet) and continue to
# do so once plan 01-03 adds them.
cmd_lint() {
  preflight
  run_step "ruff check" docker compose --profile tools run --rm tools ruff check .
  run_step "ruff format --check" docker compose --profile tools run --rm tools ruff format --check .
}

# cmd_demo — up, then job, then test, then a summary (D-10). The single
# command the README leads with. On a Phase 1 clone this stops at cmd_job
# with a non-zero exit, which is correct: the job script does not exist yet.
cmd_demo() {
  cmd_up
  cmd_job
  cmd_test
  echo "Demo complete: environment up, csv_to_parquet job ran, pytest suite passed."
}

main() {
  local cmd="${1:-}"

  case "$cmd" in
    -h|--help)
      usage
      exit 0
      ;;
    "")
      usage >&2
      exit 2
      ;;
    up|down|bootstrap|seed|job|test|lint|demo)
      ;;
    *)
      echo "Unknown subcommand: ${cmd}" >&2
      usage >&2
      exit 2
      ;;
  esac

  if [ "$#" -gt 1 ]; then
    echo "Unexpected extra argument: ${2}" >&2
    exit 2
  fi

  case "$cmd" in
    up) cmd_up ;;
    down) cmd_down ;;
    bootstrap) cmd_bootstrap ;;
    seed) cmd_seed ;;
    job) cmd_job ;;
    test) cmd_test ;;
    lint) cmd_lint ;;
    demo) cmd_demo ;;
  esac
}

main "$@"
