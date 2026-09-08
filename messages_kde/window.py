from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtDBus import QDBusConnection, QDBusMessage
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEngineFindTextResult
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from messages_kde import APP_DISPLAY_NAME, DEFAULT_GOOGLE_ACCOUNT
from messages_kde.config import Config, icon_path
from messages_kde.constants import CONVERSATIONS_URL, DESKTOP_FILE, account_chooser_url
from messages_kde.dialogs import AboutDialog, SettingsDialog, choose_download_name, sync_autostart
from messages_kde.urls import convert_app_url, is_messages_host, parse_unread
from messages_kde.web import WebSession


class FindBar(QWidget):
    closed = Signal()
    find_next = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setVisible(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        self.field = QLineEdit()
        self.field.setPlaceholderText("Find in page")
        self.field.returnPressed.connect(self._next)
        self.status = QLabel("")
        next_btn = QPushButton("Next")
        prev_btn = QPushButton("Previous")
        close_btn = QPushButton("Close")
        next_btn.clicked.connect(self._next)
        prev_btn.clicked.connect(self._prev)
        close_btn.clicked.connect(self.hide_bar)
        layout.addWidget(self.field, 1)
        layout.addWidget(prev_btn)
        layout.addWidget(next_btn)
        layout.addWidget(self.status)
        layout.addWidget(close_btn)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.hide_bar)

    def open_bar(self) -> None:
        self.setVisible(True)
        self.field.setFocus()
        self.field.selectAll()

    def hide_bar(self) -> None:
        self.setVisible(False)
        self.closed.emit()

    def _next(self) -> None:
        self.find_next.emit(self.field.text(), False)

    def _prev(self) -> None:
        self.find_next.emit(self.field.text(), True)


class MainWindow(QMainWindow):
    unread_changed = Signal(int)
    request_quit = Signal()

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self._really_quit = False
        self._unread = 0
        self._was_maximized = False
        self.tray_available = False
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setWindowIcon(QIcon(str(icon_path())))
        self.setMinimumSize(860, 560)
        self.resize(1180, 780)

        self.session = WebSession(config, self)
        self._build_chrome()
        self.session.set_download_handler(self._handle_download)
        self.session.title_changed.connect(self._on_title)
        self.session.load_progress.connect(self._on_progress)
        self.session.load_finished.connect(self._on_loaded)
        self.session.fullscreen_changed.connect(self._on_fullscreen)
        self.session.unread_count.connect(self._set_unread)
        self.session.signed_in.connect(self._mark_session_ready)
        self.session.page.findTextFinished.connect(self._on_find_result)

        if config.restore_geometry:
            self._restore_geometry()
        self.session.apply_zoom(config.zoom_factor)

        self._unread_timer = QTimer(self)
        self._unread_timer.setInterval(4000)
        self._unread_timer.timeout.connect(self.session.poll_unread)
        self._unread_timer.start()

    def _build_chrome(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        file_menu.addAction("Reload", QKeySequence.StandardKey.Refresh, self.reload)
        file_menu.addAction(
            "Hard reload",
            QKeySequence("Ctrl+Shift+R"),
            lambda: self.session.reload(True),
        )
        file_menu.addAction("Home", QKeySequence("Alt+Home"), self.go_home)
        file_menu.addAction(
            "Open in browser",
            lambda: QDesktopServices.openUrl(self.session.view.url()),
        )
        file_menu.addSeparator()
        file_menu.addAction("Settings…", QKeySequence.StandardKey.Preferences, self.open_settings)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("Quit", QKeySequence.StandardKey.Quit, self.quit_app)
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)

        view_menu = menubar.addMenu("&View")
        view_menu.addAction("Zoom in", QKeySequence.StandardKey.ZoomIn, self.zoom_in)
        view_menu.addAction("Zoom out", QKeySequence.StandardKey.ZoomOut, self.zoom_out)
        view_menu.addAction("Reset zoom", QKeySequence("Ctrl+0"), self.zoom_reset)
        view_menu.addAction("Find", QKeySequence.StandardKey.Find, self.show_find)
        view_menu.addSeparator()
        view_menu.addAction("Full screen", QKeySequence.StandardKey.FullScreen, self.toggle_fullscreen)

        account_menu = menubar.addMenu("&Account")
        account_menu.addAction(
            f"Sign in as {self.config.google_account or DEFAULT_GOOGLE_ACCOUNT}",
            self.sign_in_account,
        )
        account_menu.addAction("Open conversations", self.go_home)
        account_menu.addSeparator()
        account_menu.addAction("Sign out and clear session", self._sign_out)

        tools_menu = menubar.addMenu("&Tools")
        tools_menu.addAction("Developer tools", QKeySequence("Ctrl+Shift+I"), self.session.open_devtools)
        tools_menu.addAction("Open downloads folder", self._open_downloads)

        help_menu = menubar.addMenu("&Help")
        about = help_menu.addAction("About Messages", self._about)
        about.setMenuRole(QAction.MenuRole.AboutRole)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(3)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setMaximumWidth(16777215)

        self.find_bar = FindBar(self)
        self.find_bar.find_next.connect(self._find)
        self.find_bar.closed.connect(lambda: self.session.view.findText(""))
        self.find_bar.field.textChanged.connect(lambda text: self._find(text, False))

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.progress)
        layout.addWidget(self.session.view, 1)
        layout.addWidget(self.find_bar)
        self.setCentralWidget(central)

        status = QStatusBar()
        status.setSizeGripEnabled(False)
        self.setStatusBar(status)
        status.hide()

        QShortcut(QKeySequence("Ctrl+W"), self, self.close)
        QShortcut(QKeySequence("Ctrl+L"), self, self.go_home)

    def start(self, urls: list[str]) -> None:
        if urls:
            self.handle_urls(urls)
        elif self.config.session_ready:
            self.session.load(self.config.start_url or CONVERSATIONS_URL)
        else:
            self.sign_in_account()
        if not self.config.shown_signin_hint:
            QTimer.singleShot(600, self._show_signin_hint)

    def handle_urls(self, urls: list[str]) -> None:
        for raw in urls:
            url = convert_app_url(raw)
            self.session.load(url)
        self.reveal()

    def reveal(self) -> None:
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        QApplication.alert(self, 0)

    def reload(self) -> None:
        self.session.reload()

    def go_home(self) -> None:
        self.session.load(self.config.start_url or CONVERSATIONS_URL)

    def sign_in_account(self) -> None:
        email = self.config.google_account or DEFAULT_GOOGLE_ACCOUNT
        self.session.load(account_chooser_url(email, self.config.start_url or CONVERSATIONS_URL))

    def quit_app(self) -> None:
        self._really_quit = True
        self.request_quit.emit()
        self.close()

    def zoom_in(self) -> None:
        self._set_zoom(self.session.view.zoomFactor() + 0.1)

    def zoom_out(self) -> None:
        self._set_zoom(self.session.view.zoomFactor() - 0.1)

    def zoom_reset(self) -> None:
        self._set_zoom(1.0)

    def _set_zoom(self, factor: float) -> None:
        factor = round(max(0.5, min(factor, 3.0)), 2)
        self.session.apply_zoom(factor)
        self.config.zoom_factor = factor
        self.config.save()

    def show_find(self) -> None:
        self.find_bar.open_bar()

    def _find(self, text: str, backward: bool) -> None:
        from PySide6.QtWebEngineCore import QWebEnginePage

        if backward:
            self.session.view.findText(text, QWebEnginePage.FindFlag.FindBackward)
        else:
            self.session.view.findText(text)

    def _on_find_result(self, result: QWebEngineFindTextResult) -> None:
        if not self.find_bar.field.text():
            self.find_bar.status.setText("")
            return
        if result.numberOfMatches() == 0:
            self.find_bar.status.setText("No matches")
        else:
            self.find_bar.status.setText(
                f"{result.activeMatch()} of {result.numberOfMatches()}"
            )

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.menuBar().show()
        else:
            self.showFullScreen()

    def _on_fullscreen(self, enable: bool) -> None:
        if enable:
            self._was_maximized = self.isMaximized()
            self.menuBar().hide()
            self.find_bar.hide_bar()
            self.showFullScreen()
        else:
            self.menuBar().show()
            if self._was_maximized:
                self.showMaximized()
            else:
                self.showNormal()

    def _on_title(self, title: str) -> None:
        count = parse_unread(title)
        if count:
            self._set_unread(count)

    def _set_unread(self, count: int) -> None:
        count = max(0, int(count))
        self._unread = count
        display = APP_DISPLAY_NAME if count == 0 else f"{APP_DISPLAY_NAME} ({count})"
        self.setWindowTitle(display)
        self.unread_changed.emit(count)
        self._publish_launcher_count(count)
        if count:
            QApplication.alert(self, 0)

    def _publish_launcher_count(self, count: int) -> None:
        message = QDBusMessage.createSignal(
            "/org/juanton/MessagesKDE",
            "com.canonical.Unity.LauncherEntry",
            "Update",
        )
        message.setArguments(
            [
                f"application://{DESKTOP_FILE}",
                {
                    "count": int(count),
                    "count-visible": bool(count > 0),
                    "urgent": bool(count > 0),
                },
            ]
        )
        QDBusConnection.sessionBus().send(message)

    def _on_progress(self, value: int) -> None:
        self.progress.setValue(value)
        self.progress.setVisible(0 < value < 100)

    def _on_loaded(self, ok: bool) -> None:
        self.progress.setVisible(False)
        if not ok:
            self.statusBar().show()
            self.statusBar().showMessage("Could not load Messages. Check your network.", 8000)
            QTimer.singleShot(8000, self.statusBar().hide)

    def _mark_session_ready(self) -> None:
        if self.config.session_ready:
            return
        if is_messages_host(self.session.view.url().host()):
            self.config.session_ready = True
            self.config.save()

    def _show_signin_hint(self) -> None:
        if self.config.shown_signin_hint:
            return
        self.config.shown_signin_hint = True
        self.config.save()
        account = self.config.google_account or DEFAULT_GOOGLE_ACCOUNT
        QMessageBox.information(
            self,
            APP_DISPLAY_NAME,
            "Sign in with "
            f"{account}.\n\n"
            "Google Messages for web still needs your Android phone:\n"
            "1. Choose that Google account if Google asks.\n"
            "2. Confirm the matching emoji or pairing prompt in Messages on the phone.\n"
            "3. Leave the phone on and connected so SMS, MMS, and RCS keep working.\n\n"
            "This computer will stay signed in after that.",
        )

    def _handle_download(self, download: QWebEngineDownloadRequest) -> None:
        directory = download.downloadDirectory() or str(
            Path.home() / "Downloads"
        )
        name = download.suggestedFileName() or "download"
        chosen = choose_download_name(self, directory, name)
        if chosen is None:
            download.cancel()
            return
        folder, filename = chosen
        download.setDownloadDirectory(folder)
        download.setDownloadFileName(filename)
        download.accept()
        download.isFinishedChanged.connect(
            lambda d=download, folder=folder, filename=filename: self._download_done(
                d, folder, filename
            )
        )

    def _download_done(
        self, download: QWebEngineDownloadRequest, folder: str, filename: str
    ) -> None:
        if not download.isFinished():
            return
        path = Path(folder) / filename
        if download.state() == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self.statusBar().show()
            self.statusBar().showMessage(f"Saved {path}", 6000)
            QTimer.singleShot(6000, self.statusBar().hide)

    def _open_downloads(self) -> None:
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(Path.home() / "Downloads"))
        )

    def _sign_out(self) -> None:
        reply = QMessageBox.question(
            self,
            "Sign out",
            "Clear the saved Google Messages session and cookies on this computer?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.session_ready = False
            self.config.save()
            self.session.clear_session()
            self.sign_in_account()

    def _about(self) -> None:
        AboutDialog(self).exec()

    def open_settings(self) -> None:
        previous_hw = self.config.hardware_acceleration
        previous_ua = self.config.user_agent_mode
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        dialog.apply_to(self.config)
        self.config.save()
        exec_path = _current_executable()
        sync_autostart(self.config.autostart, exec_path)
        self.session.profile.setSpellCheckEnabled(self.config.spellcheck)
        if self.config.spellcheck_language:
            self.session.profile.setSpellCheckLanguages([self.config.spellcheck_language])
        if (
            previous_hw != self.config.hardware_acceleration
            or previous_ua != self.config.user_agent_mode
        ):
            QMessageBox.information(
                self,
                "Restart required",
                "User agent and hardware acceleration changes apply the next time Messages starts.",
            )

    def _restore_geometry(self) -> None:
        settings = QSettings()
        geometry = settings.value("window/geometry")
        state = settings.value("window/state")
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)
        if isinstance(state, QByteArray) and not state.isEmpty():
            self.restoreState(state)

    def _save_geometry(self) -> None:
        if not self.config.restore_geometry:
            return
        settings = QSettings()
        settings.setValue("window/geometry", self.saveGeometry())
        settings.setValue("window/state", self.saveState())

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self._save_geometry()
        tray_ok = bool(QApplication.instance() and hasattr(self, "tray_available") and self.tray_available)
        if not self._really_quit and self.config.close_to_tray and tray_ok:
            event.ignore()
            self.hide()
            if not self.config.shown_tray_hint:
                self.config.shown_tray_hint = True
                self.config.save()
                QMessageBox.information(
                    self,
                    APP_DISPLAY_NAME,
                    "Messages is still running in the system tray. Quit from the tray menu to exit completely.",
                )
            return
        event.accept()
        self.request_quit.emit()


def _current_executable() -> str:
    import shutil
    import sys
    from pathlib import Path

    found = shutil.which("messages-kde")
    if found:
        return found
    return str(Path(sys.argv[0]).resolve())
