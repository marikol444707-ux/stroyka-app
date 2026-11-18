#!/bin/bash
# Install or remove the on-server pull deploy timer. Run once as root.
# STROYKA_INSTALL_PREFIX redirects systemd paths for tests; production leaves it empty.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PREFIX="${STROYKA_INSTALL_PREFIX:-}"

if [[ -n "$PREFIX" ]]; then
  UNIT_DIR="$PREFIX/etc/systemd/system"
  STATE_DIR="$PREFIX/var/lib/stroyka-deploy"
else
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "Запустите от root: sudo bash scripts/install-pull-deploy.sh" >&2
    exit 1
  fi
  UNIT_DIR="/etc/systemd/system"
  STATE_DIR="/var/lib/stroyka-deploy"
fi

SERVICE_NAME="stroyka-pull-deploy.service"
TIMER_NAME="stroyka-pull-deploy.timer"
SERVICE_SRC="$REPO_ROOT/deploy/systemd/$SERVICE_NAME"
TIMER_SRC="$REPO_ROOT/deploy/systemd/$TIMER_NAME"

uninstall_units() {
  systemctl disable --now "$TIMER_NAME" || true
  rm -f -- "$UNIT_DIR/$SERVICE_NAME" "$UNIT_DIR/$TIMER_NAME"
  systemctl daemon-reload
  echo "Автовыкладка выключена. Каталог состояния оставлен: $STATE_DIR"
}

if [[ "${1:-}" == "--uninstall" || "${1:-}" == "uninstall" ]]; then
  uninstall_units
  exit 0
fi
if [[ -n "${1:-}" ]]; then
  echo "Неизвестный аргумент. Запуск без аргументов ставит таймер, --uninstall снимает его." >&2
  exit 2
fi
if [[ ! -f "$SERVICE_SRC" || ! -f "$TIMER_SRC" ]]; then
  echo "В репозитории нет файлов systemd для автовыкладки." >&2
  exit 1
fi

install -d -m 0755 "$UNIT_DIR"
install -m 0644 "$SERVICE_SRC" "$UNIT_DIR/$SERVICE_NAME"
install -m 0644 "$TIMER_SRC" "$UNIT_DIR/$TIMER_NAME"
install -d -m 0700 "$STATE_DIR"
systemctl daemon-reload
systemctl enable --now "$TIMER_NAME"
echo "Готово. Таймер $TIMER_NAME включён."
echo "Журнал: journalctl -u stroyka-pull-deploy -n 50"
echo "Пауза: systemctl disable --now $TIMER_NAME"
systemctl status "$TIMER_NAME" --no-pager --lines=12 || true
