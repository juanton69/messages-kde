from __future__ import annotations

import json
from collections.abc import Callable

from PySide6.QtCore import QLocale, QObject, QStandardPaths, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWebEngineCore import (
    QWebEngineCertificateError,
    QWebEngineDownloadRequest,
    QWebEngineFileSystemAccessRequest,
    QWebEngineFullScreenRequest,
    QWebEngineNewWindowRequest,
    QWebEnginePage,
    QWebEnginePermission,
    QWebEngineProfile,
    QWebEngineSettings,
    qWebEngineChromiumVersion,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QDialog, QMessageBox, QVBoxLayout, QWidget

from messages_kde.config import Config, cache_root, icon_path, profile_root
from messages_kde.constants import LOGIN_HINT_JS, UNREAD_COUNT_JS, USER_AGENT_CHROME
from messages_kde.dialogs import confirm_permission
from messages_kde.urls import (
    is_auth_host,
    is_internal_host,
    is_messages_host,
    should_open_externally,
)


PERMISSION_LABELS = {
    QWebEnginePermission.PermissionType.MediaAudioCapture: "microphone",
    QWebEnginePermission.PermissionType.MediaVideoCapture: "camera",
    QWebEnginePermission.PermissionType.MediaAudioVideoCapture: "camera and microphone",
    QWebEnginePermission.PermissionType.DesktopVideoCapture: "screen sharing",
    QWebEnginePermission.PermissionType.DesktopAudioVideoCapture: "screen sharing",
    QWebEnginePermission.PermissionType.Notifications: "notifications",
    QWebEnginePermission.PermissionType.ClipboardReadWrite: "clipboard",
    QWebEnginePermission.PermissionType.LocalFontsAccess: "local fonts",
    QWebEnginePermission.PermissionType.MouseLock: "pointer lock",
}

AUTO_GRANT = set(PERMISSION_LABELS)


def build_user_agent(config: Config) -> str | None:
    version = qWebEngineChromiumVersion()
    mode = config.user_agent_mode
    if mode == "chrome":
        return USER_AGENT_CHROME.format(version=version)
    if mode == "custom" and config.custom_user_agent.strip():
        return config.custom_user_agent.strip()
    return None


def configure_profile(profile: QWebEngineProfile, config: Config) -> None:
    profile.setPersistentStoragePath(str(profile_root()))
    profile.setCachePath(str(cache_root()))
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
    )
    profile.setPersistentPermissionsPolicy(
        QWebEngineProfile.PersistentPermissionsPolicy.StoreOnDisk
    )
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    downloads = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
    if downloads:
        profile.setDownloadPath(downloads)
    ua = build_user_agent(config)
    if ua:
        profile.setHttpUserAgent(ua)
    locale = QLocale.system().name().replace("_", "-")
    profile.setHttpAcceptLanguage(f"{locale},{locale.split('-')[0]},en-US,en")
    profile.setSpellCheckEnabled(config.spellcheck)
    lang = config.spellcheck_language or locale
    if lang:
        profile.setSpellCheckLanguages([lang])

    settings = profile.settings()
    attributes = QWebEngineSettings.WebAttribute
    settings.setAttribute(attributes.JavascriptEnabled, True)
    settings.setAttribute(attributes.JavascriptCanAccessClipboard, True)
    settings.setAttribute(attributes.JavascriptCanPaste, True)
    settings.setAttribute(attributes.JavascriptCanOpenWindows, True)
    settings.setAttribute(attributes.LocalStorageEnabled, True)
    settings.setAttribute(attributes.FullScreenSupportEnabled, True)
    settings.setAttribute(attributes.PlaybackRequiresUserGesture, False)
    settings.setAttribute(attributes.ScreenCaptureEnabled, True)
    settings.setAttribute(attributes.WebGLEnabled, True)
    settings.setAttribute(attributes.Accelerated2dCanvasEnabled, True)
    settings.setAttribute(attributes.DnsPrefetchEnabled, True)
    settings.setAttribute(attributes.AllowWindowActivationFromJavaScript, True)
    settings.setAttribute(attributes.ScrollAnimatorEnabled, True)
    settings.setAttribute(attributes.ErrorPageEnabled, True)
    settings.setAttribute(attributes.PluginsEnabled, True)
    settings.setAttribute(attributes.PdfViewerEnabled, True)
    settings.setAttribute(attributes.FocusOnNavigationEnabled, False)


class MessagesPage(QWebEnginePage):
    external_url = Signal(QUrl)

    def __init__(self, profile: QWebEngineProfile, parent: QObject | None = None) -> None:
        super().__init__(profile, parent)
        self.fileSystemAccessRequested.connect(self._on_filesystem)

    def acceptNavigationRequest(  # type: ignore[override]
        self, url: QUrl, _nav_type: QWebEnginePage.NavigationType, is_main_frame: bool
    ) -> bool:
        if not is_main_frame:
            return True
        if should_open_externally(url):
            self.external_url.emit(url)
            return False
        return True

    def _on_filesystem(self, request: QWebEngineFileSystemAccessRequest) -> None:
        if is_internal_host(request.origin().host()):
            request.accept()
        else:
            request.reject()

    def javaScriptConsoleMessage(  # type: ignore[override]
        self,
        level: QWebEnginePage.JavaScriptConsoleMessageLevel,
        message: str,
        line: int,
        source: str,
    ) -> None:
        import os

        if os.environ.get("MESSAGES_KDE_DEBUG"):
            print(f"[messages-kde] {level.name} {source}:{line} {message}")


class WebPopup(QDialog):
    def __init__(self, profile: QWebEngineProfile, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Google Messages")
        self.setWindowIcon(QIcon(str(icon_path())))
        self.resize(520, 720)
        self._last_host = ""
        self.view = QWebEngineView(self)
        self.view.setPage(MessagesPage(profile, self.view))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.view.urlChanged.connect(self._on_url)

    def _on_url(self, url: QUrl) -> None:
        host = url.host()
        if is_auth_host(self._last_host) and is_messages_host(host):
            self.accept()
            return
        self._last_host = host
        if host:
            self.setWindowTitle(self.view.title() or "Google Messages")


class MessagesView(QWebEngineView):
    def __init__(self, page: MessagesPage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPage(page)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

    def createWindow(self, _kind: QWebEnginePage.WebWindowType) -> QWebEngineView | None:
        return None

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        menu = self.createStandardContextMenu()
        data = self.lastContextMenuRequest()
        if data is not None and data.linkUrl().isValid():
            open_in_browser = QAction("Open Link in Browser", menu)
            open_in_browser.triggered.connect(
                lambda: QDesktopServices.openUrl(data.linkUrl())
            )
            menu.addSeparator()
            menu.addAction(open_in_browser)
        menu.exec(event.globalPos())


class WebSession(QObject):
    url_changed = Signal(QUrl)
    title_changed = Signal(str)
    load_progress = Signal(int)
    load_finished = Signal(bool)
    fullscreen_changed = Signal(bool)
    unread_count = Signal(int)
    signed_in = Signal()

    def __init__(self, config: Config, parent: QWidget) -> None:
        super().__init__(parent)
        self._parent = parent
        self.config = config
        self.profile = QWebEngineProfile("messages", self)
        configure_profile(self.profile, config)
        self.page = MessagesPage(self.profile, self)
        self.view = MessagesView(self.page, parent)
        self._popups: list[WebPopup] = []
        self._downloads: set[QWebEngineDownloadRequest] = set()
        self._on_download: Callable[[QWebEngineDownloadRequest], None] | None = None
        self._devtools: QWebEngineView | None = None

        self._bind_page(self.page)
        self.page.titleChanged.connect(self.title_changed)
        self.view.urlChanged.connect(self.url_changed)
        self.view.loadProgress.connect(self.load_progress)
        self.view.loadFinished.connect(self._on_loaded)
        self.profile.downloadRequested.connect(self._on_download_requested)

    def set_download_handler(
        self, handler: Callable[[QWebEngineDownloadRequest], None]
    ) -> None:
        self._on_download = handler

    def _bind_page(self, page: MessagesPage) -> None:
        page.external_url.connect(self._open_external)
        page.newWindowRequested.connect(self._open_popup)
        page.fullScreenRequested.connect(self._on_fullscreen)
        page.permissionRequested.connect(self._on_permission)
        page.certificateError.connect(self._on_certificate)
        page.renderProcessTerminated.connect(self._on_crash)

    def set_notification_presenter(self, presenter) -> None:
        self.profile.setNotificationPresenter(presenter)

    def load(self, url: QUrl | str) -> None:
        self.view.setUrl(QUrl(url) if isinstance(url, str) else url)

    def reload(self, bypass_cache: bool = False) -> None:
        if bypass_cache:
            self.page.triggerAction(QWebEnginePage.WebAction.ReloadAndBypassCache)
        else:
            self.view.reload()

    def apply_zoom(self, factor: float) -> None:
        self.view.setZoomFactor(max(0.5, min(factor, 3.0)))

    def open_devtools(self) -> None:
        if self._devtools is None:
            self._devtools = QWebEngineView()
            self._devtools.setWindowTitle("Messages developer tools")
            self._devtools.setWindowIcon(QIcon(str(icon_path())))
            self._devtools.resize(900, 700)
            self.page.setDevToolsPage(self._devtools.page())
        self._devtools.show()
        self._devtools.raise_()
        self._devtools.activateWindow()

    def clear_session(self) -> None:
        self.profile.cookieStore().deleteAllCookies()
        self.profile.clearHttpCache()

    def poll_unread(self) -> None:
        self.page.runJavaScript(UNREAD_COUNT_JS, self._emit_unread)

    def _emit_unread(self, value) -> None:
        try:
            count = int(value or 0)
        except (TypeError, ValueError):
            count = 0
        self.unread_count.emit(max(0, count))

    def _on_loaded(self, ok: bool) -> None:
        self.load_finished.emit(ok)
        host = self.view.url().host()
        if is_auth_host(host):
            self._inject_login_hint()
        if ok and is_messages_host(host):
            path = self.view.url().path()
            if "conversation" in path or path.endswith("/web") or "/web/" in path:
                self.signed_in.emit()
        self.poll_unread()

    def _inject_login_hint(self) -> None:
        email = (self.config.google_account or "").strip()
        if not email:
            return
        script = LOGIN_HINT_JS.replace("%EMAIL%", json.dumps(email))
        self.page.runJavaScript(script)

    def _open_external(self, url: QUrl) -> None:
        QDesktopServices.openUrl(url)

    def _spawn_popup(self, request: QWebEngineNewWindowRequest, host: str) -> None:
        popup = WebPopup(self.profile, self._parent)
        popup._last_host = host
        popup_page = popup.view.page()
        if isinstance(popup_page, MessagesPage):
            self._bind_page(popup_page)
        popup.finished.connect(lambda _=0, p=popup: self._popups.remove(p) if p in self._popups else None)
        self._popups.append(popup)
        request.openIn(popup.view.page())
        popup.show()
        popup.raise_()

    def _open_popup(self, request: QWebEngineNewWindowRequest) -> None:
        url = request.requestedUrl()
        if url.isValid() and should_open_externally(url):
            self._open_external(url)
            return
        host = url.host()
        if is_auth_host(host) or is_internal_host(host) or not url.isValid() or url.isEmpty():
            self._spawn_popup(request, host)
            return
        if url.isValid():
            self._open_external(url)

    def _on_fullscreen(self, request: QWebEngineFullScreenRequest) -> None:
        request.accept()
        self.fullscreen_changed.emit(request.toggleOn())

    def _on_permission(self, permission: QWebEnginePermission) -> None:
        kind = permission.permissionType()
        origin = permission.origin().host()
        if kind not in AUTO_GRANT:
            permission.deny()
            return
        trusted = is_internal_host(origin) or is_messages_host(origin)
        if trusted and self.config.auto_allow_media:
            permission.grant()
            return
        label = PERMISSION_LABELS.get(kind, "this feature")
        if confirm_permission(self._parent, origin or "This site", label):
            permission.grant()
        else:
            permission.deny()

    def _on_certificate(self, error: QWebEngineCertificateError) -> None:
        if not error.isOverridable():
            error.rejectCertificate()
            return
        reply = QMessageBox.warning(
            self._parent,
            "Certificate warning",
            f"{error.description()}\n\n{error.url().toString()}\n\n"
            "Continue anyway? Only do this if you trust this network "
            "(corporate SSL inspection is a common reason).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            error.acceptCertificate()
        else:
            error.rejectCertificate()

    def _on_crash(self, _status: int, _code: int) -> None:
        QMessageBox.warning(
            self._parent,
            "Messages crashed",
            "The web engine process stopped. Reloading.",
        )
        self.reload()

    def _on_download_requested(self, download: QWebEngineDownloadRequest) -> None:
        self._downloads.add(download)
        download.isFinishedChanged.connect(
            lambda d=download: self._downloads.discard(d) if d.isFinished() else None
        )
        if self._on_download:
            self._on_download(download)
        else:
            download.accept()
