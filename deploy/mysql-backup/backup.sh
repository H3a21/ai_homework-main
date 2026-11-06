#!/bin/sh
set -eu

MYSQL_HOST=${MYSQL_HOST:-mysql}
MYSQL_PORT=${MYSQL_PORT:-3306}
MYSQL_USER=${MYSQL_USER:-root}
MYSQL_DATABASE=${MYSQL_DATABASE:-ai_homework}
BACKUP_DIR=${BACKUP_DIR:-/backup/mysql}
BACKUP_BUCKET=${BACKUP_BUCKET:-ai-homework-backups}
BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}
BACKUP_TIME=${BACKUP_TIME:-03:00}
BACKUP_RUN_ON_STARTUP=${BACKUP_RUN_ON_STARTUP:-true}
MINIO_ENDPOINT=${MINIO_ENDPOINT:-http://minio:9000}
MC_ALIAS=${MC_ALIAS:-backup-minio}
MC_CONFIG_DIR=${MC_CONFIG_DIR:-/tmp/mc}

export MC_CONFIG_DIR
export MYSQL_PWD=${MYSQL_PASSWORD:?MYSQL_PASSWORD is required}
: "${MINIO_ACCESS_KEY:?MINIO_ACCESS_KEY is required}"
: "${MINIO_SECRET_KEY:?MINIO_SECRET_KEY is required}"

CURRENT_DUMP=""
CURRENT_ARCHIVE=""

cleanup_partial_files() {
    [ -z "$CURRENT_DUMP" ] || rm -f "$CURRENT_DUMP"
    [ -z "$CURRENT_ARCHIVE" ] || rm -f "$CURRENT_ARCHIVE"
}

trap cleanup_partial_files EXIT INT TERM

validate_settings() {
    case "$BACKUP_RETENTION_DAYS" in
        ''|*[!0-9]*) echo "BACKUP_RETENTION_DAYS must be a non-negative integer" >&2; exit 2 ;;
    esac
    if ! date -d "today $BACKUP_TIME" +%s >/dev/null 2>&1; then
        echo "BACKUP_TIME must be a valid HH:MM value" >&2
        exit 2
    fi
}

configure_minio() {
    mkdir -p "$MC_CONFIG_DIR"
    mc alias set "$MC_ALIAS" "$MINIO_ENDPOINT" \
        "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" --api S3v4 >/dev/null
    mc mb --ignore-existing "$MC_ALIAS/$BACKUP_BUCKET" >/dev/null
}

prune_expired_backups() {
    find "$BACKUP_DIR" -type f \
        \( -name 'full_*.sql.gz' -o -name 'full_*.sql.gz.sha256' \) \
        -mtime "+$BACKUP_RETENTION_DAYS" -delete

    if [ "$BACKUP_RETENTION_DAYS" -gt 0 ]; then
        mc rm --recursive --force --older-than "${BACKUP_RETENTION_DAYS}d" \
            "$MC_ALIAS/$BACKUP_BUCKET/mysql" >/dev/null
    fi
}

backup_once() {
    configure_minio
    mkdir -p "$BACKUP_DIR"

    timestamp=$(date +%Y%m%d_%H%M%S)
    filename="full_${timestamp}.sql.gz"
    final_archive="$BACKUP_DIR/$filename"
    checksum_file="$final_archive.sha256"
    CURRENT_DUMP="$BACKUP_DIR/.full_${timestamp}.sql.partial"
    CURRENT_ARCHIVE="$BACKUP_DIR/.$filename.partial"

    mysqldump \
        --host="$MYSQL_HOST" \
        --port="$MYSQL_PORT" \
        --user="$MYSQL_USER" \
        --single-transaction \
        --quick \
        --routines \
        --triggers \
        --events \
        --hex-blob \
        --no-tablespaces \
        --set-gtid-purged=OFF \
        "$MYSQL_DATABASE" > "$CURRENT_DUMP"

    gzip -c "$CURRENT_DUMP" > "$CURRENT_ARCHIVE"
    gzip -t "$CURRENT_ARCHIVE"
    mv "$CURRENT_ARCHIVE" "$final_archive"
    CURRENT_ARCHIVE=""
    rm -f "$CURRENT_DUMP"
    CURRENT_DUMP=""

    (cd "$BACKUP_DIR" && sha256sum "$filename" > "$filename.sha256")
    mc cp --quiet "$final_archive" "$MC_ALIAS/$BACKUP_BUCKET/mysql/$filename"
    mc cp --quiet "$checksum_file" \
        "$MC_ALIAS/$BACKUP_BUCKET/mysql/$filename.sha256"

    prune_expired_backups
    date -u +%Y-%m-%dT%H:%M:%SZ > "$BACKUP_DIR/.last-success"
    echo "BACKUP_SUCCESS file=$filename bucket=$BACKUP_BUCKET"
}

seconds_until_next_run() {
    now=$(date +%s)
    target=$(date -d "today $BACKUP_TIME" +%s)
    if [ "$target" -le "$now" ]; then
        target=$(date -d "tomorrow $BACKUP_TIME" +%s)
    fi
    echo $((target - now))
}

run_schedule() {
    configure_minio
    touch /tmp/mysql-backup-ready

    if [ "$BACKUP_RUN_ON_STARTUP" = "true" ]; then
        backup_once
    fi

    while true; do
        delay=$(seconds_until_next_run)
        echo "NEXT_BACKUP seconds=$delay time=$BACKUP_TIME"
        sleep "$delay"
        backup_once
    done
}

validate_settings

case "${1:-schedule}" in
    schedule) run_schedule ;;
    once) backup_once ;;
    restore|verify)
        action=$1
        shift
        exec /usr/local/bin/restore.sh "$action" "$@"
        ;;
    *)
        echo "usage: backup.sh [schedule|once|restore|verify]" >&2
        exit 2
        ;;
esac
