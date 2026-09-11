from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QObject, Slot
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
from PySide6.QtGui import QIcon
from PySide6.QtWebEngineCore import QWebEngineNotification
from PySide6.QtWidgets import QSystemTrayIcon

from messages_kde import APP_DISPLAY_NAME, APP_ID


class NotificationService(QObject):
    """Show Messages web notifications through the Plasma notification server."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._active: dict[int, QWebEngineNotification] = {}
        self._tags: dict[str, int] = {}
        self._on_click: Callable[[], None] | None = None
        self._tray: QSystemTrayIcon | None = None
        self._next_fallback_id = 1
        bus = QDBusConnection.sessionBus()
        self._iface = QDBusInterface(
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
            bus,
            self,
        )
        bus.connect(
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
            "ActionInvoked",
            self,
            "_on_action",
        )
        bus.connect(
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
            "NotificationClosed",
            self,
            "_on_closed",
        )

    def set_click_handler(self, handler: Callable[[], None]) -> None:
        self._on_click = handler

    def set_tray(self, tray: QSystemTrayIcon) -> None:
        self._tray = tray
        tray.messageClicked.connect(self._on_tray_clicked)

    @staticmethod
    def _forward_otp(title: str, body: str) -> None:
        def work() -> None:
            try:
                from messages_kde.otp_forward import forward_sms

                forward_sms(title, body)
            except Exception:
                return

        threading.Thread(target=work, daemon=True, name="otp-forward").start()

    def present(self, notification: QWebEngineNotification) -> None:
        self._forward_otp(notification.title() or "", notification.message() or "")
        notification.show()
        replaces = 0
        tag = notification.tag()
        if tag and tag in self._tags:
            replaces = self._tags[tag]
        nid = self._notify_dbus(notification, replaces)
        if nid:
            self._active[nid] = notification
            if tag:
                self._tags[tag] = nid
            notification.closed.connect(lambda n=notification, i=nid: self._forget(i, n))
            return
        self._notify_tray(notification)
        fid = -self._next_fallback_id
        self._next_fallback_id += 1
        self._active[fid] = notification

    def _notify_dbus(self, notification: QWebEngineNotification, replaces: int) -> int:
        if not self._iface.isValid():
            return 0
        hints = {
            "desktop-entry": APP_ID,
            "urgency": 1,
            "category": "im.received",
        }
        args = [
            APP_DISPLAY_NAME,
            replaces,
            APP_ID,
            notification.title() or APP_DISPLAY_NAME,
            notification.message(),
            ["default", "Open"],
            hints,
            8000,
        ]
        reply = self._iface.call("Notify", *args)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            return 0
        values = reply.arguments()
        try:
            return int(values[0]) if values else 0
        except (TypeError, ValueError):
            return 0

    def _notify_tray(self, notification: QWebEngineNotification) -> None:
        if self._tray is None:
            return
        icon = QIcon(notification.icon()) if not notification.icon().isNull() else QIcon.fromTheme(APP_ID)
        self._tray.showMessage(
            notification.title() or APP_DISPLAY_NAME,
            notification.message(),
            icon,
            8000,
        )

    def _forget(self, nid: int, notification: QWebEngineNotification) -> None:
        current = self._active.get(nid)
        if current is notification:
            self._active.pop(nid, None)
        tag = notification.tag()
        if tag and self._tags.get(tag) == nid:
            self._tags.pop(tag, None)

    @Slot(int, str)
    def _on_action(self, nid: int, action: str) -> None:
        notification = self._active.get(nid)
        if notification is not None:
            notification.click()
        if self._on_click:
            self._on_click()

    @Slot(int, int)
    def _on_closed(self, nid: int, _reason: int) -> None:
        notification = self._active.pop(nid, None)
        if notification is not None:
            notification.close()

    def _on_tray_clicked(self) -> None:
        if self._active:
            newest = list(self._active.values())[-1]
            newest.click()
        if self._on_click:
            self._on_click()
