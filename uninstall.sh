#!/usr/bin/env bash
set -euo pipefail

APP_ID="org.juanton.messages-kde"
BIN_DIR="${HOME}/.local/bin"
DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
CACHE_HOME="${XDG_CACHE_HOME:-${HOME}/.cache}"

rm -f "${BIN_DIR}/messages-kde" "${HOME}/bin/messages-kde"
rm -rf "${DATA_HOME}/messages-kde"
rm -f "${DATA_HOME}/applications/${APP_ID}.desktop"
rm -f "${DATA_HOME}/icons/hicolor/"*"/apps/${APP_ID}.png"
rm -f "${DATA_HOME}/icons/hicolor/scalable/apps/${APP_ID}.svg"
rm -f "${CONFIG_HOME}/autostart/${APP_ID}.desktop"

if [[ "${1:-}" == "--purge" ]]; then
  rm -rf "${DATA_HOME}/messages-kde"
  rm -rf "${CONFIG_HOME}/messages-kde"
  rm -rf "${CACHE_HOME}/messages-kde"
  echo "Removed saved session, settings, and cache."
fi

if command -v update-desktop-database >/dev/null; then
  update-desktop-database "${DATA_HOME}/applications" >/dev/null 2>&1 || true
fi
if command -v kbuildsycoca6 >/dev/null; then
  kbuildsycoca6 >/dev/null 2>&1 || true
fi

echo "Google Messages for KDE has been uninstalled."
echo "Run uninstall.sh --purge to also delete login cookies and settings."
