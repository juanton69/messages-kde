from __future__ import annotations

import argparse
import json
import os
import signal
import sys

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from messages_kde import APP_DISPLAY_NAME, APP_ID, APP_NAME, ORG_NAME, __version__
from messages_kde.config import Config, icon_path
from messages_kde.constants import SOCKET_NAME


def _chromium_flags(hardware_acceleration: bool) -> str:
    flags = [
        "--disable-blink-features=AutomationControlled",
        "--enable-features=VaapiVideoDecoder,VaapiVideoEncoder,AcceleratedVideoDecodeLinuxGL",
        "--autoplay-policy=no-user-gesture-required",
        "--enable-gpu-rasterization",
        "--enable-zero-copy",
        "--ignore-gpu-blocklist",
        "--enable-accelerated-video-decode",
    ]
    if not hardware_acceleration:
        flags = ["--disable-gpu", "--disable-gpu-compositing"]
    extra = os.environ.get("MESSAGES_KDE_CHROMIUM_FLAGS", "").strip()
    if extra:
        flags.append(extra)
    return " ".join(flags)


def apply_runtime_environment(config: Config) -> None:
    if "QTWEBENGINE_CHROMIUM_FLAGS" not in os.environ:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _chromium_flags(config.hardware_acceleration)
    os.environ.setdefault("QT_WAYLAND_DISABLE_WINDOWDECORATION", "0")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="messages-kde",
        description="Unofficial Google Messages client for KDE Plasma",
    )
    parser.add_argument("urls", nargs="*", help="Messages URL or sms: link")
    parser.add_argument("--minimized", action="store_true", help="Start in the system tray")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


class SingleInstance(QObject):
    message_received = Signal(list)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_connection)

    @staticmethod
    def socket_name() -> str:
        return f"{SOCKET_NAME}-{os.getuid()}"

    def listen(self) -> None:
        name = self.socket_name()
        QLocalServer.removeServer(name)
        if not self._server.listen(name):
            print(
                f"messages-kde: could not claim single-instance socket: {self._server.errorString()}",
                file=sys.stderr,
            )

    def _on_connection(self) -> None:
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        socket.readyRead.connect(lambda s=socket: self._read(s))

    def _read(self, socket: QLocalSocket) -> None:
        raw = bytes(socket.readAll())
        socket.disconnectFromServer()
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        urls = payload.get("urls") or []
        if isinstance(urls, str):
            urls = [urls]
        self.message_received.emit(list(urls))

    @classmethod
    def forward(cls, urls: list[str], minimized: bool) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(cls.socket_name())
        if not socket.waitForConnected(250):
            return False
        payload = json.dumps({"urls": urls, "minimized": minimized})
        socket.write(payload.encode("utf-8"))
        socket.flush()
        socket.waitForBytesWritten(250)
        socket.disconnectFromServer()
        return True


def _configure_application() -> None:
    QCoreApplication.setOrganizationName(ORG_NAME)
    QCoreApplication.setOrganizationDomain("juanton.local")
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setApplicationVersion(__version__)
    QGuiApplication.setApplicationDisplayName(APP_DISPLAY_NAME)
    QGuiApplication.setDesktopFileName(APP_ID)
    QApplication.setQuitOnLastWindowClosed(False)


def run(argv: list[str] | None = None) -> int:
    _configure_application()
    args = parse_args(argv if argv is not None else sys.argv[1:])
    config = Config.load()
    apply_runtime_environment(config)

    # Qt WebEngine must be imported before QApplication; flags must already be set.
    from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    from messages_kde.notifications import NotificationService
    from messages_kde.tray import TrayController
    from messages_kde.window import MainWindow

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(icon_path())))
    app.setDesktopFileName(APP_ID)

    if SingleInstance.forward(args.urls, args.minimized):
        return 0

    instance = SingleInstance(app)
    instance.listen()

    window = MainWindow(config)
    notifications = NotificationService(app)
    notifications.set_click_handler(window.reveal)

    tray = None
    window.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    if window.tray_available:
        tray = TrayController(
            window,
            on_show=window.reveal,
            on_quit=window.quit_app,
            on_settings=window.open_settings,
            on_reload=window.reload,
        )
        notifications.set_tray(tray.icon)
        window.unread_changed.connect(tray.set_unread)

    window.session.set_notification_presenter(notifications.present)
    instance.message_received.connect(window.handle_urls)
    window.request_quit.connect(app.quit)

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    keepalive = QTimer(app)
    keepalive.start(250)
    keepalive.timeout.connect(lambda: None)

    start_minimized = args.minimized or config.start_minimized
    window.start(args.urls)
    if start_minimized and window.tray_available:
        window.hide()
    else:
        window.show()

    return app.exec()
