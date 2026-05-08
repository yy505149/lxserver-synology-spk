#!/bin/sh

echo "Content-Type: application/json"
echo ""

VAR_DIR="/var/packages/lxserver/target/var"
PORT_FILE="${VAR_DIR}/port"
BIND_IP_FILE="${VAR_DIR}/bind_ip"
PASSWORD_FILE="${VAR_DIR}/admin_password"
RESTART_LOG="${VAR_DIR}/apply-restart.log"

read_file_trim() {
  f="$1"
  if [ -f "$f" ]; then
    tr -d ' \t\r\n' <"$f" 2>/dev/null || true
  else
    printf ''
  fi
}

if [ "${REQUEST_METHOD}" = "GET" ]; then
  PORT_VALUE="$(read_file_trim "${PORT_FILE}")"
  BIND_IP_VALUE="$(read_file_trim "${BIND_IP_FILE}")"
  if [ -z "${PORT_VALUE}" ]; then PORT_VALUE="9527"; fi
  if [ -z "${BIND_IP_VALUE}" ]; then BIND_IP_VALUE="::"; fi
  if [ -f "${PASSWORD_FILE}" ]; then
    HAS_PASSWORD="true"
  else
    HAS_PASSWORD="false"
  fi
  echo "{\"success\":true,\"port\":\"${PORT_VALUE}\",\"bind_ip\":\"${BIND_IP_VALUE}\",\"has_password\":${HAS_PASSWORD}}"
  exit 0
fi

if [ "${REQUEST_METHOD}" != "POST" ]; then
  echo '{"success":false,"error":"Method Not Allowed"}'
  exit 0
fi

read_post_data() {
  length="${CONTENT_LENGTH:-0}"
  if [ -z "${length}" ] || [ "${length}" -le 0 ] 2>/dev/null; then
    printf ''
    return
  fi
  dd bs=1 count="${length}" 2>/dev/null
}

urldecode() {
  data="$(echo "$1" | sed 's/+/ /g')"
  printf '%b' "${data//%/\\x}"
}

get_form_value() {
  key="$1"
  body="$2"
  raw="$(printf '%s' "$body" | tr '&' '\n' | awk -F= -v k="$key" '$1==k {print substr($0, index($0, "=")+1); exit}')"
  urldecode "$raw"
}

BODY="$(read_post_data)"
PORT="$(get_form_value port "$BODY" | tr -d ' \t\r\n')"
BIND_IP="$(get_form_value bind_ip "$BODY" | tr -d ' \t\r\n')"
PASSWORD="$(get_form_value password "$BODY")"

case "${PORT}" in
  ''|*[!0-9]*)
    echo '{"success":false,"error":"Invalid port"}'
    exit 0
    ;;
esac
if [ "${PORT}" -lt 1 ] || [ "${PORT}" -gt 65535 ]; then
  echo '{"success":false,"error":"Port out of range"}'
  exit 0
fi

case "${BIND_IP}" in
  '')
    BIND_IP='::'
    ;;
  '0.0.0.0'|'::') ;;
  *)
    echo '{"success":false,"error":"Invalid bind_ip"}'
    exit 0
    ;;
esac

mkdir -p "${VAR_DIR}" || {
  echo '{"success":false,"error":"Failed to create var directory"}'
  exit 0
}

echo "${PORT}" > "${PORT_FILE}" || {
  echo '{"success":false,"error":"Failed to write port"}'
  exit 0
}

echo "${BIND_IP}" > "${BIND_IP_FILE}" || {
  echo '{"success":false,"error":"Failed to write bind_ip"}'
  exit 0
}

if [ -n "${PASSWORD}" ]; then
  printf '%s' "${PASSWORD}" > "${PASSWORD_FILE}" || {
    echo '{"success":false,"error":"Failed to write password"}'
    exit 0
  }
  chmod 600 "${PASSWORD_FILE}" >/dev/null 2>&1
fi

SYNOPKG_PKGNAME="lxserver"
SYNOPKG_PKGDEST="/var/packages/${SYNOPKG_PKGNAME}/target"
CTL_SCRIPT="/var/packages/${SYNOPKG_PKGNAME}/scripts/start-stop-status"
export SYNOPKG_PKGNAME SYNOPKG_PKGDEST
{
  echo "[$(date '+%F %T')] apply.cgi: requested restart (port=${PORT}, bind_ip=${BIND_IP})"
} >>"${RESTART_LOG}" 2>&1

nohup sh -c "echo '[`date '+%F %T'`]' apply.cgi: stop && ${CTL_SCRIPT} stop && echo '[`date '+%F %T'`]' apply.cgi: start && ${CTL_SCRIPT} start && echo '[`date '+%F %T'`]' apply.cgi: done" >>"${RESTART_LOG}" 2>&1 &

echo '{"success":true}'
exit 0
