#!/usr/bin/env bash
# Executar na VM como usuario com acesso ao Docker.
set -euo pipefail
umask 077

APP_DIR="${APP_DIR:-/opt/pli-hazardtrack}"
DB_CONTAINER="${DB_CONTAINER:-sigma_pli_db}"
DB_NAME=pli_hazardtrack
DB_USER=hazardtrack_app
ENV_FILE="${APP_DIR}/.env"
SQL_FILE="${APP_DIR}/scripts/sql/001_alertas.sql"
ADMIN_SQL_FILE="${APP_DIR}/scripts/sql/002_administracao.sql"
OPERATION_SQL_FILE="${APP_DIR}/scripts/sql/003_gestao_institucional.sql"
PASSWORD=""
test -f "${ENV_FILE}"
test -f "${SQL_FILE}"
test -f "${ADMIN_SQL_FILE}"
test -f "${OPERATION_SQL_FILE}"

admin_sql() {
    docker exec -i "${DB_CONTAINER}" \
        psql -X -v ON_ERROR_STOP=1 -U postgres -d postgres "$@"
}

role_exists="$(admin_sql -Atc \
    "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'")"
if [ "${role_exists}" != 1 ]; then
    PASSWORD="$(openssl rand -hex 32)"
    printf "CREATE ROLE %s LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '%s';\n" \
        "${DB_USER}" "${PASSWORD}" | admin_sql >/dev/null
elif ! grep -q '^HAZARDTRACK_DATABASE_URL=.' "${ENV_FILE}"; then
    echo "Role ja existe sem DSN local; recupere a credencial antes de continuar." >&2
    exit 1
fi

db_owner="$(admin_sql -Atc \
    "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='${DB_NAME}'")"
if [ -z "${db_owner}" ]; then
    admin_sql -c \
        "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER} ENCODING 'UTF8' TEMPLATE template0" \
        >/dev/null
elif [ "${db_owner}" != "${DB_USER}" ]; then
    echo "Banco existente tem outro proprietario; nenhuma alteracao aplicada." >&2
    exit 1
fi
admin_sql -c \
    "REVOKE CONNECT ON DATABASE ${DB_NAME} FROM PUBLIC; GRANT CONNECT ON DATABASE ${DB_NAME} TO ${DB_USER}" \
    >/dev/null

if [ "${role_exists}" = 1 ] && [ "${ROTATE_PASSWORD:-0}" = 1 ]; then
    PASSWORD="$(openssl rand -hex 32)"
    printf "ALTER ROLE %s PASSWORD '%s';\n" "${DB_USER}" "${PASSWORD}" \
        | admin_sql >/dev/null
fi

if [ -n "${PASSWORD:-}" ]; then
    tmp="$(mktemp "${APP_DIR}/.env.XXXXXX")"
    trap 'rm -f "${tmp}"' EXIT
    grep -Ev '^HAZARDTRACK_DATABASE_(URL|REQUIRED)=' "${ENV_FILE}" > "${tmp}" || true
    printf '\nHAZARDTRACK_DATABASE_URL=postgresql://%s:%s@%s:5432/%s\nHAZARDTRACK_DATABASE_REQUIRED=1\n' \
        "${DB_USER}" "${PASSWORD}" "${DB_CONTAINER}" "${DB_NAME}" >> "${tmp}"
    chmod 600 "${tmp}"
    mv "${tmp}" "${ENV_FILE}"
    trap - EXIT
fi

# O esquema e criado com o proprietario da aplicacao, nao com postgres.
{
    printf 'BEGIN;\nSET LOCAL ROLE %s;\n' "${DB_USER}"
    cat "${SQL_FILE}"
    printf '\n'
    cat "${ADMIN_SQL_FILE}"
    printf '\n'
    cat "${OPERATION_SQL_FILE}"
    printf '\nCOMMIT;\n'
} | docker exec -i "${DB_CONTAINER}" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d "${DB_NAME}" >/dev/null
echo "Banco ${DB_NAME}, esquema e conexao provisionados; credencial em .env."
