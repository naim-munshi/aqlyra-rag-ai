#!/usr/bin/env bash
# Operator-only CORE database backup/recovery acceptance gate.
# Remote Neon is READ ONLY. A private pg_dump is restored ONLY into an
# ephemeral --network none Docker container. Never upgrades, resets or merges.
set -Eeuo pipefail
umask 077

usage() {
  echo "Usage: bash $0 --url-file PRIVATE_FILE --expected-host EXACT_NEON_HOST --expected-database neondb --expected-role neondb_owner --backup-root PRIVATE_DIRECTORY" >&2
  exit 2
}
url_file="" expected_host="" expected_database="" expected_role="" backup_root=""
while (( $# )); do
  case "$1" in
    --url-file|--expected-host|--expected-database|--expected-role|--backup-root)
      (( $# >= 2 )) || usage
      case "$1" in
        --url-file) url_file="$2" ;;
        --expected-host) expected_host="$2" ;;
        --expected-database) expected_database="$2" ;;
        --expected-role) expected_role="$2" ;;
        --backup-root) backup_root="$2" ;;
      esac
      shift 2 ;;
    *) usage ;;
  esac
done
[[ -n "$url_file" && -n "$expected_host" && -n "$expected_database" && -n "$expected_role" && -n "$backup_root" ]] || usage

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
backup_script="$ROOT/scripts/ops/neon_remote_backup.py"
restore_script="$ROOT/scripts/ops/neon_restore_rehearsal.sh"
[[ -f "$backup_script" && -f "$restore_script" ]] || {
  echo "RECOVERY_GATE=BLOCKED missing reviewed Aqlyra recovery scripts" >&2
  exit 2
}
# Before any backup exists, confirm the actual database/role and migrated
# CORE schema using a read-only PostgreSQL session.
preflight="$(python3 "$backup_script" \
  --url-file "$url_file" --expected-host "$expected_host" \
  --expected-database "$expected_database" --expected-role "$expected_role")" || {
  echo "RECOVERY_GATE=BLOCKED Neon read-only preflight failed" >&2
  exit 2
}
[[ "$preflight" == *"NEON_TARGET_AND_TLS=PASS"* &&
   "$preflight" == *"NEON_SCHEMA=PASS"* &&
   "$preflight" == *"ALEMBIC_REVISION=b5e4a019dc72"* &&
   "$preflight" == *"FULL_RELEASE_SCHEMA=MIGRATION_PENDING"* ]] || {
  echo "RECOVERY_GATE=BLOCKED unexpected schema head; do not run a migration" >&2
  exit 2
}

# Refuse symlinks and broad permissions on private backup root.
[[ ! -L "$backup_root" ]] || {
  echo "RECOVERY_GATE=BLOCKED backup root cannot be a symlink" >&2
  exit 2
}
mkdir -p "$backup_root"
backup_root="$(cd "$backup_root" && pwd -P)"
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
run_dir="$(mktemp -d "$backup_root/aqlyra-core-recovery.XXXXXXXX")"
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
[[ "$postflight" == *"ALEMBIC_REVISION=b5e4a019dc72"* ]] || {
  echo "RECOVERY_GATE=BLOCKED Neon revision changed during backup" >&2
  exit 2
}
echo "NEON_PRIVATE_BACKUP=PASS"
echo "NEON_ISOLATED_RESTORE=PASS"
echo "NEON_CORE_SCHEMA_HEAD=PASS"
echo "FULL_RELEASE_DATABASE_MIGRATION=NOT_RUN"
echo "OWNER_APPROVAL_REQUIRED_FOR_MIGRATION=true"
echo "PRIVATE_BACKUP_LOCATION=$run_dir"
