#!/bin/sh
set -eu

ACTION=${1:-verify}
shift || true

MYSQL_HOST=${MYSQL_HOST:-mysql}
MYSQL_PORT=${MYSQL_PORT:-3306}
MYSQL_USER=${MYSQL_USER:-root}
MYSQL_DATABASE=${MYSQL_DATABASE:-ai_homework}
BACKUP_DIR=${BACKUP_DIR:-/backup/mysql}
BACKUP_BUCKET=${BACKUP_BUCKET:-ai-homework-backups}
RESTORE_SOURCE=${RESTORE_SOURCE:-minio}
MINIO_ENDPOINT=${MINIO_ENDPOINT:-http://minio:9000}
MC_ALIAS=${MC_ALIAS:-backup-minio}
MC_CONFIG_DIR=${MC_CONFIG_DIR:-/tmp/mc}

export MC_CONFIG_DIR
export MYSQL_PWD=${MYSQL_PASSWORD:?MYSQL_PASSWORD is required}
: "${MINIO_ACCESS_KEY:?MINIO_ACCESS_KEY is required}"
: "${MINIO_SECRET_KEY:?MINIO_SECRET_KEY is required}"

WORK_DIR=$(mktemp -d /tmp/mysql-restore.XXXXXX)
VERIFY_DATABASE=""

cleanup() {
    if [ -n "$VERIFY_DATABASE" ]; then
        mysql --host="$MYSQL_HOST" --port="$MYSQL_PORT" --user="$MYSQL_USER" \
            -e "DROP DATABASE IF EXISTS \`$VERIFY_DATABASE\`" >/dev/null 2>&1 || true
    fi
    rm -rf "$WORK_DIR"
}

trap cleanup EXIT INT TERM

configure_minio() {
    mkdir -p "$MC_CONFIG_DIR"
    mc alias set "$MC_ALIAS" "$MINIO_ENDPOINT" \
        "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" --api S3v4 >/dev/null
}

validate_filename() {
    case "$1" in
        full_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9].sql.gz) ;;
        *) echo "invalid backup filename: $1" >&2; exit 2 ;;
    esac
}

resolve_filename() {
    requested=${1:-}
    if [ -n "$requested" ]; then
        validate_filename "$requested"
        echo "$requested"
        return
    fi

    if [ "$RESTORE_SOURCE" = "local" ]; then
        latest=$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'full_*.sql.gz' \
            -printf '%f\n' | sort | tail -n 1)
    else
        configure_minio
        latest=$(mc find "$MC_ALIAS/$BACKUP_BUCKET/mysql" \
            --name 'full_*.sql.gz' | sort | tail -n 1)
        latest=${latest##*/}
    fi

    if [ -z "$latest" ]; then
        echo "no backup archive found" >&2
        exit 1
    fi
    validate_filename "$latest"
    echo "$latest"
}

fetch_archive() {
    filename=$1
    if [ "$RESTORE_SOURCE" = "local" ]; then
        cp "$BACKUP_DIR/$filename" "$WORK_DIR/$filename"
        cp "$BACKUP_DIR/$filename.sha256" "$WORK_DIR/$filename.sha256"
    elif [ "$RESTORE_SOURCE" = "minio" ]; then
        configure_minio
        mc cp --quiet "$MC_ALIAS/$BACKUP_BUCKET/mysql/$filename" "$WORK_DIR/$filename"
        mc cp --quiet "$MC_ALIAS/$BACKUP_BUCKET/mysql/$filename.sha256" \
            "$WORK_DIR/$filename.sha256"
    else
        echo "RESTORE_SOURCE must be local or minio" >&2
        exit 2
    fi

    (cd "$WORK_DIR" && sha256sum -c "$filename.sha256" >/dev/null)
    gzip -t "$WORK_DIR/$filename"
}

validate_database_name() {
    case "$1" in
        ''|*[!A-Za-z0-9_]*) echo "invalid restore database name" >&2; exit 2 ;;
    esac
    if [ "$1" = "$MYSQL_DATABASE" ] && [ "${RESTORE_ALLOW_PRIMARY:-false}" != "true" ]; then
        echo "refusing to overwrite primary database without RESTORE_ALLOW_PRIMARY=true" >&2
        exit 2
    fi
}

restore_database() {
    archive=$1
    target_database=$2
    validate_database_name "$target_database"

    exists=$(mysql --host="$MYSQL_HOST" --port="$MYSQL_PORT" --user="$MYSQL_USER" \
        --batch --skip-column-names \
        -e "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='$target_database'")
    if [ "$exists" -ne 0 ]; then
        if [ "${RESTORE_REPLACE:-false}" != "true" ]; then
            echo "target database already exists; set RESTORE_REPLACE=true to replace it" >&2
            exit 2
        fi
        mysql --host="$MYSQL_HOST" --port="$MYSQL_PORT" --user="$MYSQL_USER" \
            -e "DROP DATABASE \`$target_database\`"
    fi

    mysql --host="$MYSQL_HOST" --port="$MYSQL_PORT" --user="$MYSQL_USER" \
        -e "CREATE DATABASE \`$target_database\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    gzip -dc "$archive" | mysql --host="$MYSQL_HOST" --port="$MYSQL_PORT" \
        --user="$MYSQL_USER" "$target_database"
}

case "$ACTION" in
    verify)
        filename=$(resolve_filename "${1:-}")
        fetch_archive "$filename"
        VERIFY_DATABASE="ai_homework_restore_verify_$(date +%Y%m%d%H%M%S)_$$"
        restore_database "$WORK_DIR/$filename" "$VERIFY_DATABASE"

        table_count=$(mysql --host="$MYSQL_HOST" --port="$MYSQL_PORT" --user="$MYSQL_USER" \
            --batch --skip-column-names \
            -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$VERIFY_DATABASE'")
        required_count=$(mysql --host="$MYSQL_HOST" --port="$MYSQL_PORT" --user="$MYSQL_USER" \
            --batch --skip-column-names \
            -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$VERIFY_DATABASE' AND table_name IN ('users','submissions','grading_attempts','audit_logs')")
        if [ "$table_count" -lt 14 ] || [ "$required_count" -ne 4 ]; then
            echo "restored schema is incomplete: tables=$table_count required=$required_count" >&2
            exit 1
        fi
        mysql --host="$MYSQL_HOST" --port="$MYSQL_PORT" --user="$MYSQL_USER" \
            -e "DROP DATABASE \`$VERIFY_DATABASE\`"
        remaining=$(mysql --host="$MYSQL_HOST" --port="$MYSQL_PORT" --user="$MYSQL_USER" \
            --batch --skip-column-names \
            -e "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='$VERIFY_DATABASE'")
        if [ "$remaining" -ne 0 ]; then
            echo "restore verification database was not cleaned up" >&2
            exit 1
        fi
        VERIFY_DATABASE=""
        echo "RESTORE_VERIFY_SUCCESS file=$filename tables=$table_count source=$RESTORE_SOURCE cleanup=confirmed"
        ;;
    restore)
        filename=$(resolve_filename "${1:-}")
        target_database=${2:-${RESTORE_TARGET_DATABASE:-}}
        if [ -z "$target_database" ]; then
            echo "usage: restore.sh restore [backup-file] target_database" >&2
            exit 2
        fi
        fetch_archive "$filename"
        restore_database "$WORK_DIR/$filename" "$target_database"
        echo "RESTORE_SUCCESS file=$filename database=$target_database source=$RESTORE_SOURCE"
        ;;
    *)
        echo "usage: restore.sh [verify|restore] [backup-file] [target_database]" >&2
        exit 2
        ;;
esac
