#!/usr/bin/env bash
# Operator-only CORE or FULL database backup/recovery acceptance gate.
# Remote Neon is READ ONLY. A private pg_dump is restored ONLY into an
# ephemeral --network none Docker container. Never upgrades, resets or merges.
set -Eeuo pipefail
umask 077

usage() {
  echo "Usage: bash $0 --url-file PRIVATE_FILE --expected-host EXACT_NEON_HOST --expected-database neondb --expected-role neondb_owner --backup-root PRIVATE_DIRECTORY [--expected-phase core|full]" >&2
  exit 2
}
url_file="" expected_host="" expected_database="" expected_role="" backup_root="" expected_phase="core"
while (( $# )); do
  case "$1" in
    --url-file|--expected-host|--expected-database|--expected-role|--backup-root|--expected-phase)
      (( $# >= 2 )) || usage
      case "$1" in
        --url-file) url_file="$2" ;;
        --expected-host) expected_host="$2" ;;
        --expected-database) expected_database="$2" ;;
        --expected-role) expected_role="$2" ;;
        --backup-root) backup_root="$2" ;;
        --expected-phase) expected_phase="$2" ;;
      esac
      shift 2 ;;
    *) usage ;;
  esac
done
[[ -n "$url_file" && -n "$expected_host" && -n "$expected_database" && -n "$expected_role" && -n "$backup_root" ]] || usage
[[ "$expected_phase" == "core" || "$expected_phase" == "full" ]] || {
  echo "RECOVERY_GATE=BLOCKED expected phase invalid" >&2
  exit 2
}
expected_revision="b5e4a019dc72"
expected_schema="MIGRATION_PENDING"
if [[ "$expected_phase" == "full" ]]; then
  expected_revision="d4ec2f9b7860"
  expected_schema="READY"
fi

# Explicit expected identity is mandatory; do not silently guess or select
# the default branch. A second target database must be reviewed separately.
[[ "$expected_database" == "neondb" && "$expected_role" == "neondb_owner" ]] || {
  echo "RECOVERY_GATE=BLOCKED unexpected database or role" >&2
  exit 2
}
for tool in python3 pg_dump pg_restore docker; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "RECOVERY_GATE=BLOCKED required local dependency unavailable" >&2
    exit 2
  }
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
# Never place connection files or raw backups under the Git working tree.
# A chmod-600 secret inside the repo can still be accidentally committed.
url_parent="$(cd "$(dirname "$url_file")" 2>/dev/null && pwd -P)" || {
  echo "RECOVERY_GATE=BLOCKED private URL file directory unavailable" >&2
  exit 2
}
case "$url_parent/$(basename "$url_file")" in
  "$ROOT"/*) echo "RECOVERY_GATE=BLOCKED URL file cannot be under the Git repository" >&2; exit 2 ;;
esac
backup_script="$ROOT/scripts/ops/neon_remote_backup.py"
restore_script="$ROOT/scripts/ops/neon_restore_rehearsal.sh"
[[ -f "$backup_script" && -f "$restore_script" ]] || {
  echo "RECOVERY_GATE=BLOCKED missing reviewed Aqlyra recovery scripts" >&2
  exit 2
}
# Before any backup exists, confirm the actual database/role and exact
# selected Core or Full schema using a read-only PostgreSQL session.
preflight="$(python3 "$backup_script" \
  --url-file "$url_file" --expected-host "$expected_host" \
  --expected-database "$expected_database" --expected-role "$expected_role")" || {
  echo "RECOVERY_GATE=BLOCKED Neon read-only preflight failed" >&2
  exit 2
}
[[ "$preflight" == *"NEON_TARGET_AND_TLS=PASS"* &&
   "$preflight" == *"NEON_SCHEMA=PASS"* &&
   "$preflight" == *"ALEMBIC_REVISION=$expected_revision"* &&
   "$preflight" == *"FULL_RELEASE_SCHEMA=$expected_schema"* ]] || {
  echo "RECOVERY_GATE=BLOCKED unexpected schema head; do not run a migration" >&2
  exit 2
}

# Validate exact migrated table, index, owner-FK and primary-key catalog
# before generating a dump; this also enforces a read-only session.
if [[ "$expected_phase" == "full" ]]; then
  python3 "$ROOT/scripts/ops/neon_study_schema_audit.py" \
    --url-file "$url_file" --expected-host "$expected_host" \
    --expected-database "$expected_database" --expected-role "$expected_role" \
    --expected-phase full >/dev/null || {
    echo "RECOVERY_GATE=BLOCKED Full schema catalog preflight failed" >&2
    exit 2
  }
fi

# Refuse symlinks and broad permissions on private backup root.
[[ ! -L "$backup_root" ]] || {
  echo "RECOVERY_GATE=BLOCKED backup root cannot be a symlink" >&2
  exit 2
}
mkdir -p "$backup_root"
backup_root="$(cd "$backup_root" && pwd -P)"
case "$backup_root" in
  "$ROOT"|"$ROOT"/*)
    echo "RECOVERY_GATE=BLOCKED backups cannot be stored under the Git repository" >&2
    exit 2 ;;
esac
[[ -d "$backup_root" && ! -L "$backup_root" ]] || {
  echo "RECOVERY_GATE=BLOCKED invalid backup directory" >&2
  exit 2
}
# Existing private directory must already have owner-only permissions;
# do not silently chmod a shared directory with unrelated files.
python3 - "$backup_root" <<'PY'
import os, pathlib, stat, sys
path = pathlib.Path(sys.argv[1])
mode = path.stat().st_mode
if (not stat.S_ISDIR(mode) or mode & 0o077 or
        (hasattr(os, "getuid") and path.stat().st_uid != os.getuid())):
    raise SystemExit("RECOVERY_GATE=BLOCKED private directory ownership or mode")
PY

# Each run gets an isolated non-overwriting private folder. Never log the
# URL or contents. Preserve the backup on failure for operator inspection.
run_dir="$(mktemp -d "$backup_root/aqlyra-$expected_phase-recovery.XXXXXXXX")"
[[ -d "$run_dir" && ! -L "$run_dir" ]] || {
  echo "RECOVERY_GATE=BLOCKED private run directory could not be created" >&2
  exit 2
}

python3 "$backup_script" \
  --url-file "$url_file" --expected-host "$expected_host" \
  --expected-database "$expected_database" --expected-role "$expected_role" \
  --backup-dir "$run_dir" || {
  echo "RECOVERY_GATE=BLOCKED private pg_dump failed" >&2
  exit 2
}
shopt -s nullglob
manifests=("$run_dir"/*.json)
dumps=("$run_dir"/*.dump)
(( ${#manifests[@]} == 1 && ${#dumps[@]} == 1 )) || {
  echo "RECOVERY_GATE=BLOCKED unexpected archive or manifest count" >&2
  exit 2
}
[[ "${manifests[0]%.json}" == "${dumps[0]%.dump}" ]] || {
  echo "RECOVERY_GATE=BLOCKED archive and manifest do not match" >&2
  exit 2
}
# The restoration process checks SHA256, pgvector, tables, revision and
# removes its own disposable network-isolated PostgreSQL container.
bash "$restore_script" "${dumps[0]}" "${manifests[0]}" || {
  echo "RECOVERY_GATE=BLOCKED isolated restore failed" >&2
  exit 2
}
# Recheck the database revision after the dump to detect a concurrent
# migration or stale operator session; fail closed if the source changed.
postflight="$(python3 "$backup_script" \
  --url-file "$url_file" --expected-host "$expected_host" \
  --expected-database "$expected_database" --expected-role "$expected_role")" || {
  echo "RECOVERY_GATE=BLOCKED post-backup Neon check failed" >&2
  exit 2
}
[[ "$postflight" == *"ALEMBIC_REVISION=$expected_revision"* &&
   "$postflight" == *"FULL_RELEASE_SCHEMA=$expected_schema"* ]] || {
  echo "RECOVERY_GATE=BLOCKED Neon revision changed during backup" >&2
  exit 2
}
if [[ "$expected_phase" == "full" ]]; then
  python3 "$ROOT/scripts/ops/neon_study_schema_audit.py" \
    --url-file "$url_file" --expected-host "$expected_host" \
    --expected-database "$expected_database" --expected-role "$expected_role" \
    --expected-phase full >/dev/null || {
    echo "RECOVERY_GATE=BLOCKED Full schema catalog postflight failed" >&2
    exit 2
  }
fi
echo "NEON_PRIVATE_BACKUP=PASS"
echo "NEON_ISOLATED_RESTORE=PASS"
if [[ "$expected_phase" == "full" ]]; then
  echo "NEON_FULL_SCHEMA_HEAD=PASS"
  echo "FULL_RELEASE_DATABASE_MIGRATION=ALREADY_APPLIED_NOT_RUN_BY_GATE"
else
  echo "NEON_CORE_SCHEMA_HEAD=PASS"
  echo "FULL_RELEASE_DATABASE_MIGRATION=NOT_RUN"
  echo "OWNER_APPROVAL_REQUIRED_FOR_MIGRATION=true"
fi
echo "PRIVATE_BACKUP_LOCATION=$run_dir"
