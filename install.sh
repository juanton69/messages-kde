#!/usr/bin/env bash
set -euo pipefail

APP_ID="org.juanton.messages-kde"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
APP_DIR="${DATA_HOME}/messages-kde"
ICON_DIR="${DATA_HOME}/icons/hicolor"
DESKTOP_DIR="${DATA_HOME}/applications"

mkdir -p "${BIN_DIR}" "${APP_DIR}" "${DESKTOP_DIR}" \
  "${ICON_DIR}/scalable/apps" \
  "${ICON_DIR}/256x256/apps" \
  "${ICON_DIR}/128x128/apps" \
  "${ICON_DIR}/64x64/apps" \
  "${ICON_DIR}/48x48/apps" \
  "${ICON_DIR}/32x32/apps" \
  "${ICON_DIR}/24x24/apps" \
  "${ICON_DIR}/16x16/apps"

echo "Installing Google Messages for KDE from ${ROOT}"
mkdir -p "${APP_DIR}/messages_kde"
rsync -a --delete \
  --exclude '.git/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "${ROOT}/messages_kde/" "${APP_DIR}/messages_kde/"
install -m 0755 "${ROOT}/messages-kde" "${APP_DIR}/messages-kde"

cat > "${BIN_DIR}/messages-kde" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${APP_DIR}\${PYTHONPATH:+:\${PYTHONPATH}}"
exec /usr/bin/python3 "${APP_DIR}/messages-kde" "\$@"
EOF
chmod 0755 "${BIN_DIR}/messages-kde"

if [[ -d "${HOME}/bin" ]]; then
  ln -sfn "${BIN_DIR}/messages-kde" "${HOME}/bin/messages-kde"
fi

install -m 0644 "${ROOT}/messages_kde/resources/${APP_ID}.svg" \
  "${ICON_DIR}/scalable/apps/${APP_ID}.svg"

python3 - "${ROOT}/messages_kde/resources/${APP_ID}.svg" "${ICON_DIR}" "${APP_ID}" <<'PY'
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

svg, icon_dir, app_id = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
app = QGuiApplication([])
renderer = QSvgRenderer(str(svg))
for size in (16, 24, 32, 48, 64, 128, 256):
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    target = icon_dir / f"{size}x{size}" / "apps" / f"{app_id}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(target))
PY

desktop_src="${ROOT}/data/${APP_ID}.desktop"
desktop_dst="${DESKTOP_DIR}/${APP_ID}.desktop"
sed "s|Exec=messages-kde|Exec=${BIN_DIR}/messages-kde|g; s|TryExec=messages-kde|TryExec=${BIN_DIR}/messages-kde|" \
  "${desktop_src}" > "${desktop_dst}"
chmod 0644 "${desktop_dst}"

if command -v update-desktop-database >/dev/null; then
  update-desktop-database "${DESKTOP_DIR}" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null; then
  gtk-update-icon-cache -f -t "${ICON_DIR}" >/dev/null 2>&1 || true
fi
if command -v kbuildsycoca6 >/dev/null; then
  kbuildsycoca6 >/dev/null 2>&1 || true
fi
if command -v xdg-mime >/dev/null; then
  xdg-mime default "${APP_ID}.desktop" x-scheme-handler/sms || true
fi

echo
echo "Installed Google Messages (KDE wrapper)"
echo "  Launcher : ${BIN_DIR}/messages-kde"
echo "  Desktop  : ${desktop_dst}"
echo "  App files: ${APP_DIR}"
echo
echo "Open it from Kickoff, KRunner, or by running: messages-kde"
echo "Sign in as juanton@wahcha.com and confirm this computer on your phone."
