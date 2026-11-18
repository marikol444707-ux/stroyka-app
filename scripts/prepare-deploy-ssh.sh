#!/bin/bash
# Write the deploy key to a 600 file. Never print the key, the host, or known_hosts.
# DEPLOY_HOST, DEPLOY_USER and DEPLOY_PORT are cleaned before the strict check.
# Cleaning drops pasted whitespace and invisible characters, and also an accidental
# ssh://, http(s)://, user@ prefix, trailing slash or :port on the host.
# When the host carries a port and DEPLOY_PORT is set, DEPLOY_PORT wins.
# The cleaned values are appended to GITHUB_ENV for the later deploy steps.
set -euo pipefail

if [[ -z "${GITHUB_ENV:-}" || -z "${RUNNER_TEMP:-}" ]]; then
  echo "ОШИБКА: подготовка SSH запускается только внутри GitHub Actions." >&2
  exit 1
fi

missing=0
for name in DEPLOY_HOST DEPLOY_USER DEPLOY_SSH_KEY DEPLOY_PORT; do
  if [[ -z "${!name:-}" ]]; then
    echo "ОШИБКА: не задан секрет ${name}." >&2
    missing=1
  fi
done
if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

install -d -m 700 "$RUNNER_TEMP/stroyka-ssh"
NORM_FILE="$RUNNER_TEMP/stroyka-ssh/normalized.env"
trap 'rm -f "$NORM_FILE"' EXIT
umask 077

if ! STROYKA_NORM_OUT="$NORM_FILE" PYTHONUTF8=1 python3 - <<'PY'
import base64
import os
import re
import sys

EDGE_EXTRA = "\u200b\u200c\u200d\ufeff"


def is_edge(char):
    return char.isspace() or char in EDGE_EXTRA


def strip_edges(value):
    start = 0
    end = len(value)
    while start < end and is_edge(value[start]):
        start += 1
    while end > start and is_edge(value[end - 1]):
        end -= 1
    return value[start:end]


def normalize_host(value):
    value = strip_edges(value)
    embedded_port = None
    for _ in range(4):
        updated = re.sub(r"(?i)^(?:ssh|https?)://", "", value)
        updated = strip_edges(updated)
        matched = re.fullmatch(r"([A-Za-z0-9._-]+)@([^@]+)", updated)
        if matched:
            updated = strip_edges(matched.group(2))
        updated = re.sub(r"/+$", "", updated)
        updated = strip_edges(updated)
        port_match = re.fullmatch(r"([^:/]+):([0-9]{1,5})", updated)
        if port_match:
            embedded_port = port_match.group(2)
            updated = strip_edges(port_match.group(1))
        if updated == value:
            break
        value = updated
    return value, embedded_port


def canonicalize_port(value):
    if re.fullmatch(r"[0-9]{1,5}", value):
        return str(int(value))
    return value


def ports_differ(embedded, port):
    if not embedded or not re.fullmatch(r"[0-9]{1,5}", embedded):
        return False
    if not re.fullmatch(r"[0-9]{1,5}", port):
        return False
    port_number = int(port)
    if not 1 <= port_number <= 65535:
        return False
    return int(embedded) != port_number


def encode(value):
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def main():
    host, embedded_port = normalize_host(os.environ.get("DEPLOY_HOST", ""))
    user = strip_edges(os.environ.get("DEPLOY_USER", ""))
    port = canonicalize_port(strip_edges(os.environ.get("DEPLOY_PORT", "")))
    if ports_differ(embedded_port, port):
        print("В адресе сервера указан другой порт. Берётся порт из секрета DEPLOY_PORT.")
    destination = os.environ["STROYKA_NORM_OUT"]
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write("DEPLOY_HOST=%s\n" % encode(host))
        handle.write("DEPLOY_USER=%s\n" % encode(user))
        handle.write("DEPLOY_PORT=%s\n" % encode(port))


try:
    main()
except Exception:
    print("ОШИБКА: не удалось очистить адрес, пользователя или порт.", file=sys.stderr)
    sys.exit(1)
PY
then
  exit 1
fi

read_norm() {
  local key="$1"
  local payload decoded
  if ! grep -q "^${key}=" "$NORM_FILE"; then
    echo "ОШИБКА: не удалось прочитать очищенное значение ${key}." >&2
    exit 1
  fi
  payload=$(sed -n "s/^${key}=//p" "$NORM_FILE")
  decoded=$(printf '%s' "$payload" | base64 -d && printf 'X')
  printf '%s' "${decoded%X}"
}

DEPLOY_HOST=$(read_norm DEPLOY_HOST)
DEPLOY_USER=$(read_norm DEPLOY_USER)
DEPLOY_PORT=$(read_norm DEPLOY_PORT)
export DEPLOY_HOST DEPLOY_USER DEPLOY_PORT
rm -f "$NORM_FILE"

blank=0
for name in DEPLOY_HOST DEPLOY_USER DEPLOY_PORT; do
  if [[ -z "${!name}" ]]; then
    echo "ОШИБКА: секрет ${name} пустой: в нём только пробелы или невидимые символы." >&2
    blank=1
  fi
done
if [[ "$blank" -ne 0 ]]; then
  exit 1
fi

reject_deploy_value() {
  local name="$1"
  STROYKA_DIAG_NAME="$name" PYTHONUTF8=1 python3 - <<'PY'
import os
import re
import sys

name = os.environ.get("STROYKA_DIAG_NAME", "")
summaries = {
    "DEPLOY_HOST": "DEPLOY_HOST должен быть именем сервера или IPv4, без пробелов.",
    "DEPLOY_USER": "DEPLOY_USER должен содержать только буквы, цифры, точку, _ и -.",
    "DEPLOY_PORT": "DEPLOY_PORT должен быть числом от 1 до 65535.",
}
if name not in summaries:
    print("ОШИБКА: внутренняя ошибка проверки секрета.", file=sys.stderr)
    sys.exit(1)
value = os.environ.get(name, "")
print("ОШИБКА: %s" % summaries[name], file=sys.stderr)
print("Длина после очистки: %s." % len(value), file=sys.stderr)
non_ascii = any(ord(char) > 127 for char in value)
has_space = any(char.isspace() for char in value)
print("Есть символы не из ASCII: %s." % ("да" if non_ascii else "нет"), file=sys.stderr)
print("Есть пробелы или переводы строк: %s." % ("да" if has_space else "нет"), file=sys.stderr)
notes = []
if non_ascii:
    notes.append("найден не-ASCII символ")
if any(char.isspace() and char not in "\r\n" for char in value):
    notes.append("найден пробел внутри")
if any(char in "\r\n" for char in value):
    notes.append("найден перевод строки")
if "@" in value:
    notes.append("найден символ @")
if ":" in value:
    notes.append("найден символ :")
if "/" in value:
    notes.append("найден символ /")
if name == "DEPLOY_PORT" and any(char.isalpha() for char in value):
    notes.append("найдены буквы")
if name == "DEPLOY_PORT" and re.fullmatch(r"[0-9]+", value):
    number = int(value)
    if number < 1 or number > 65535 or not re.fullmatch(r"[0-9]{1,5}", value):
        notes.append("число вне диапазона от 1 до 65535")
allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
if name == "DEPLOY_PORT":
    allowed = set("0123456789")
other = False
for char in value:
    if char in allowed or char.isspace() or ord(char) > 127 or char in "@/:":
        continue
    if name == "DEPLOY_PORT" and char.isalpha():
        continue
    other = True
    break
if other or not notes:
    notes.append("найден недопустимый символ")
seen = []
for note in notes:
    if note not in seen:
        seen.append(note)
for note in seen:
    print(note, file=sys.stderr)
PY
  exit 1
}

if [[ ! "$DEPLOY_HOST" =~ ^[A-Za-z0-9._-]+$ ]]; then
  reject_deploy_value DEPLOY_HOST
fi
if [[ ! "$DEPLOY_USER" =~ ^[A-Za-z0-9._-]+$ ]]; then
  reject_deploy_value DEPLOY_USER
fi
if [[ ! "$DEPLOY_PORT" =~ ^[0-9]{1,5}$ ]] || [[ "$DEPLOY_PORT" -lt 1 || "$DEPLOY_PORT" -gt 65535 ]]; then
  reject_deploy_value DEPLOY_PORT
fi

key="$RUNNER_TEMP/stroyka-ssh/id"
known="$RUNNER_TEMP/stroyka-ssh/known_hosts"
umask 077
printf '%s\n' "$DEPLOY_SSH_KEY" > "$key"
chmod 600 "$key"
if ! grep -q "PRIVATE KEY" "$key"; then
  rm -f "$key"
  echo "ОШИБКА: DEPLOY_SSH_KEY не похож на приватный ключ. Вставьте весь ключ, включая строки BEGIN и END." >&2
  exit 1
fi

if [[ -n "${DEPLOY_KNOWN_HOSTS:-}" ]]; then
  printf '%s\n' "$DEPLOY_KNOWN_HOSTS" > "$known"
  echo "Ключ сервера взят из секрета DEPLOY_KNOWN_HOSTS."
else
  echo "Секрет DEPLOY_KNOWN_HOSTS не задан. Ключ сервера будет получен через ssh-keyscan."
  echo "Так проще, но при подмене сети можно довериться чужому серверу. Лучше задать DEPLOY_KNOWN_HOSTS."
  if ! ssh-keyscan -p "$DEPLOY_PORT" -T 10 -H "$DEPLOY_HOST" > "$known" 2>"$RUNNER_TEMP/stroyka-ssh/keyscan.err"; then
    rm -f "$known" "$RUNNER_TEMP/stroyka-ssh/keyscan.err"
    echo "ОШИБКА: не удалось получить ключ сервера через ssh-keyscan." >&2
    exit 1
  fi
  rm -f "$RUNNER_TEMP/stroyka-ssh/keyscan.err"
fi
chmod 600 "$known"
if [[ ! -s "$known" ]]; then
  rm -f "$known"
  echo "ОШИБКА: файл ключа сервера пустой." >&2
  exit 1
fi

{
  printf 'DEPLOY_HOST=%s\n' "$DEPLOY_HOST"
  printf 'DEPLOY_USER=%s\n' "$DEPLOY_USER"
  printf 'DEPLOY_PORT=%s\n' "$DEPLOY_PORT"
  printf 'SSH_KEY=%s\n' "$key"
  printf 'SSH_KNOWN_HOSTS=%s\n' "$known"
  printf 'SSH_PORT=%s\n' "$DEPLOY_PORT"
  printf 'SSH_USER=%s\n' "$DEPLOY_USER"
  printf 'SSH_HOST=%s\n' "$DEPLOY_HOST"
} >> "$GITHUB_ENV"
