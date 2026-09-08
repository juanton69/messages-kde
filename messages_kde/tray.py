from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRectF, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from messages_kde import APP_DISPLAY_NAME
from messages_kde.config import icon_path


def badge_icon(base: QIcon, count: int, size: int = 64) -> QIcon:
    pixmap = base.pixmap(size, size)
    if pixmap.isNull():
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor("#1A73E8"))
    if count <= 0:
        return QIcon(pixmap)
    canvas = pixmap.copy()
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    badge = min(size * 0.48, 30)
    rect = QRectF(size - badge - 1, 1, badge, badge)
    painter.setBrush(QColor("#E23E3E"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(rect)
    painter.setPen(QColor("white"))
    font = QFont()
    font.setBold(True)
    font.setPixelSize(int(badge * 0.55))
    painter.setFont(font)
    label = "9+" if count > 9 else str(count)
    painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), label)
    painter.end()
    return QIcon(canvas)


class TrayController(QObject):
    def __init__(
        self,
        window: QWidget,
        *,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
        on_settings: Callable[[], None],
        on_reload: Callable[[], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._base_icon = QIcon(str(icon_path()))
        self._window = window
        self.icon = QSystemTrayIcon(self._base_icon, window)
        self.icon.setToolTip(APP_DISPLAY_NAME)
        menu = QMenu(window)
        show_action = QAction("Show Messages", menu)
        show_action.triggered.connect(on_show)
        reload_action = QAction("Reload", menu)
        reload_action.triggered.connect(on_reload)
        settings_action = QAction("Settings…", menu)
        settings_action.triggered.connect(on_settings)
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(on_quit)
        menu.addAction(show_action)
        menu.addAction(reload_action)
        menu.addSeparator()
        menu.addAction(settings_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.icon.setContextMenu(menu)
        self.icon.activated.connect(self._activated)
        self._on_show = on_show
        self.icon.show()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._on_show()

    def set_unread(self, count: int) -> None:
        self.icon.setIcon(badge_icon(self._base_icon, count))
        if count:
            self.icon.setToolTip(f"{APP_DISPLAY_NAME} ({count} unread)")
        else:
            self.icon.setToolTip(APP_DISPLAY_NAME)
