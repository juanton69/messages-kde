"""Best-effort SMS code forwarder to the local otp-grabber daemon."""

from __future__ import annotations

import json
import os
import socket
from typing import Any


def _socket_path() -> str:
    override = os.environ.get("OTP_GRABBER_SOCKET")
    if override:
        return override
    runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return os.path.join(runtime, "otp-grabber.sock")


def forward_sms(title: str, text: str) -> None:
    path = _socket_path()
    if not os.path.exists(path):
        return
    payload: dict[str, Any] = {
        "op": "ingest_text",
        "source": "sms",
        "title": title or "",
        "text": text or "",
    }
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        sock.connect(path)
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        sock.recv(4096)
        sock.close()
    except OSError:
        return
