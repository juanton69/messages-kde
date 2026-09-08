from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, qVersion
from PySide6.QtGui import QIcon
from PySide6.QtWebEngineCore import qWebEngineChromiumVersion
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from messages_kde import APP_DISPLAY_NAME, APP_ID, DEFAULT_GOOGLE_ACCOUNT, __version__
from messages_kde.config import Config, autostart_path, icon_path
from messages_kde.constants import ABOUT_TEXT, START_URL_PRESETS


def available_spellcheck_languages() -> list[str]:
    roots = [
        Path("/usr/share/qt6/qtwebengine_dictionaries"),
        Path("/usr/lib64/qt6/qtwebengine_dictionaries"),
    ]
    found: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for item in root.glob("*.bdic"):
            found.add(item.stem.replace("_", "-"))
    return sorted(found) or ["en-US", "en-GB"]


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Messages settings")
        self.setWindowIcon(QIcon(str(icon_path())))
        self.resize(540, 420)
        self._config = config

        tabs = QTabWidget(self)
        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._account_tab(), "Account")
        tabs.addTab(self._advanced_tab(), "Advanced")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    def _general_tab(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)

        self.start_url = QComboBox()
        self.start_url.setEditable(True)
        for label, url in START_URL_PRESETS:
            self.start_url.addItem(label, url)
        current = self._config.start_url
        match = self.start_url.findData(current)
        if match >= 0:
            self.start_url.setCurrentIndex(match)
        else:
            self.start_url.setEditText(current)

        self.close_to_tray = QCheckBox("Close window to the system tray")
        self.close_to_tray.setChecked(self._config.close_to_tray)
        self.start_minimized = QCheckBox("Start minimized to the tray")
        self.start_minimized.setChecked(self._config.start_minimized)
        self.autostart = QCheckBox("Launch at login")
        self.autostart.setChecked(self._config.autostart)
        self.restore_geometry = QCheckBox("Remember window size and position")
        self.restore_geometry.setChecked(self._config.restore_geometry)
        self.auto_allow_media = QCheckBox(
            "Allow notifications, camera, and microphone for Messages automatically"
        )
        self.auto_allow_media.setChecked(self._config.auto_allow_media)

        form.addRow("Home page:", self.start_url)
        form.addRow(self.close_to_tray)
        form.addRow(self.start_minimized)
        form.addRow(self.autostart)
        form.addRow(self.restore_geometry)
        form.addRow(self.auto_allow_media)
        return page

    def _account_tab(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        self.google_account = QLineEdit(self._config.google_account)
        self.google_account.setPlaceholderText(DEFAULT_GOOGLE_ACCOUNT)
        note = QLabel(
            "This is the Google account Messages will offer first. Google still "
            "requires you to confirm this computer in the Messages app on your phone. "
            "The phone must stay on and connected for SMS, MMS, and RCS."
        )
        note.setWordWrap(True)
        form.addRow("Google account:", self.google_account)
        form.addRow(note)
        return page

    def _advanced_tab(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)

        self.user_agent_mode = QComboBox()
        self.user_agent_mode.addItem("Chrome (recommended)", "chrome")
        self.user_agent_mode.addItem("Qt WebEngine default", "default")
        self.user_agent_mode.addItem("Custom", "custom")
        index = self.user_agent_mode.findData(self._config.user_agent_mode)
        self.user_agent_mode.setCurrentIndex(max(index, 0))

        self.custom_user_agent = QLineEdit(self._config.custom_user_agent)
        self.custom_user_agent.setPlaceholderText("Custom user agent string")

        self.hardware_acceleration = QCheckBox("Hardware acceleration (restart required)")
        self.hardware_acceleration.setChecked(self._config.hardware_acceleration)

        self.spellcheck = QCheckBox("Spell check")
        self.spellcheck.setChecked(self._config.spellcheck)
        self.spellcheck_language = QComboBox()
        for lang in available_spellcheck_languages():
            self.spellcheck_language.addItem(lang)
        lang = self._config.spellcheck_language
        if lang:
            found = self.spellcheck_language.findText(lang)
            if found >= 0:
                self.spellcheck_language.setCurrentIndex(found)
            else:
                self.spellcheck_language.addItem(lang)
                self.spellcheck_language.setCurrentText(lang)

        form.addRow("User agent:", self.user_agent_mode)
        form.addRow("Custom UA:", self.custom_user_agent)
        form.addRow(self.hardware_acceleration)
        form.addRow(self.spellcheck)
        form.addRow("Dictionary:", self.spellcheck_language)
        return page

    def apply_to(self, config: Config) -> Config:
        text = self.start_url.currentText().strip()
        data = self.start_url.currentData()
        if text.startswith("http"):
            config.start_url = text
        elif data:
            config.start_url = str(data)
        config.google_account = self.google_account.text().strip() or DEFAULT_GOOGLE_ACCOUNT
        config.close_to_tray = self.close_to_tray.isChecked()
        config.start_minimized = self.start_minimized.isChecked()
        config.autostart = self.autostart.isChecked()
        config.restore_geometry = self.restore_geometry.isChecked()
        config.auto_allow_media = self.auto_allow_media.isChecked()
        config.hardware_acceleration = self.hardware_acceleration.isChecked()
        config.user_agent_mode = str(self.user_agent_mode.currentData())
        config.custom_user_agent = self.custom_user_agent.text().strip()
        config.spellcheck = self.spellcheck.isChecked()
        config.spellcheck_language = self.spellcheck_language.currentText()
        return config


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_DISPLAY_NAME}")
        self.setWindowIcon(QIcon(str(icon_path())))
        layout = QVBoxLayout(self)
        icon = QLabel()
        icon.setPixmap(QIcon(str(icon_path())).pixmap(64, 64))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(f"<h2>{APP_DISPLAY_NAME}</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body = QLabel(
            f"Version {__version__}<br>"
            f"Qt {qVersion()} · Chromium {qWebEngineChromiumVersion()}<br><br>"
            + ABOUT_TEXT.replace("\n", "<br>")
        )
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(buttons)


def confirm_permission(parent: QWidget | None, origin: str, what: str) -> bool:
    reply = QMessageBox.question(
        parent,
        "Permission request",
        f"{origin} wants to use your {what}. Allow?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    return reply == QMessageBox.StandardButton.Yes


def sync_autostart(enabled: bool, exec_path: str) -> None:
    path = autostart_path()
    if not enabled:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_DISPLAY_NAME}\n"
        "Comment=Unofficial Google Messages client for KDE Plasma\n"
        f"Exec={exec_path} --minimized\n"
        f"Icon={APP_ID}\n"
        "Terminal=false\n"
        "X-KDE-autostart-after=panel\n"
        "X-KDE-startup-notify=false\n"
        "X-GNOME-Autostart-enabled=true\n",
        encoding="utf-8",
    )


def choose_download_name(parent: QWidget | None, directory: str, filename: str) -> tuple[str, str] | None:
    target = str(Path(directory) / filename)
    chosen, _ = QFileDialog.getSaveFileName(parent, "Save file", target)
    if not chosen:
        return None
    path = Path(chosen)
    return str(path.parent), path.name
