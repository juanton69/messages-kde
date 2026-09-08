from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from messages_kde import APP_ID, DEFAULT_GOOGLE_ACCOUNT
from messages_kde.constants import DEFAULT_START_URL


def _settings() -> QSettings:
    return QSettings()


@dataclass
class Config:
    start_url: str = DEFAULT_START_URL
    google_account: str = DEFAULT_GOOGLE_ACCOUNT
    close_to_tray: bool = True
    start_minimized: bool = False
    autostart: bool = False
    hardware_acceleration: bool = True
    user_agent_mode: str = "chrome"  # chrome | default | custom
    custom_user_agent: str = ""
    auto_allow_media: bool = True
    spellcheck: bool = True
    spellcheck_language: str = ""
    zoom_factor: float = 1.0
    restore_geometry: bool = True
    shown_tray_hint: bool = False
    shown_signin_hint: bool = False
    session_ready: bool = False

    def save(self) -> None:
        s = _settings()
        for field in fields(self):
            s.setValue(field.name, getattr(self, field.name))
        s.sync()

    @classmethod
    def load(cls) -> Config:
        s = _settings()
        data = cls()
        for field in fields(cls):
            if not s.contains(field.name):
                continue
            value = getattr(data, field.name)
            if isinstance(value, bool):
                setattr(data, field.name, s.value(field.name, value, type=bool))
            elif isinstance(value, float):
                setattr(data, field.name, float(s.value(field.name, value)))
            else:
                setattr(data, field.name, s.value(field.name, value))
        if not str(data.start_url).strip():
            data.start_url = DEFAULT_START_URL
        if not str(data.google_account).strip():
            data.google_account = DEFAULT_GOOGLE_ACCOUNT
        return data


def profile_root() -> Path:
    base = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    path = base / "profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_root() -> Path:
    base = Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation))
    path = base / "webengine"
    path.mkdir(parents=True, exist_ok=True)
    return path


def autostart_path() -> Path:
    config = Path(QStandardPaths.writableLocation(QStandardPaths.ConfigLocation))
    return config / "autostart" / f"{APP_ID}.desktop"


def icon_path() -> Path:
    return Path(__file__).resolve().parent / "resources" / f"{APP_ID}.svg"
