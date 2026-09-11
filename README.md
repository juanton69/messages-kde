# Google Messages for KDE

An unofficial Google Messages desktop client for KDE Plasma. It wraps [Messages for web](https://messages.google.com/web) in Qt WebEngine so it behaves like a normal KDE application: Kickoff launcher, system tray, Plasma notifications, and a remembered Google session.

This is not affiliated with Google. There is no public Messages API; the official desktop interface is still the web client, and your Android phone remains the SMS/RCS engine.

Default Google account: **juanton@wahcha.com**

## What you get

- A dedicated window with KDE titlebar, menus, and Breeze theming
- First-run sign-in aimed at `juanton@wahcha.com`
- Persistent login in `~/.local/share/messages-kde`
- System tray with unread badge; closing the window hides to tray
- Plasma notifications for incoming texts
- Forwards SMS one-time codes to the local `otp-grabber` daemon when that service is running
- Camera and microphone for photos and voice messages
- Downloads through the native file dialog
- `sms:` links can open in this app
- Optional launch at login

## Requirements

Already present on this Fedora 44 + Plasma 6 machine:

- Python 3 with `python3-pyside6`
- `qt6-qtwebengine`
- An Android phone with Google Messages, signed into the same Google account

## Install

From the project directory:

```bash
chmod +x install.sh uninstall.sh messages-kde
./install.sh
```

Then start **Google Messages** from Kickoff / KRunner, or run `messages-kde`.

## First sign-in

1. Open the app. It offers Google account chooser for `juanton@wahcha.com`.
2. Complete Google sign-in (password / passkey / 2FA).
3. On your phone, open **Messages → your profile → Device pairing** (or the on-device prompt) and confirm the matching emoji.
4. Keep the phone on and connected. Messages for web cannot send or receive if the phone is offline.

The session stays on this computer until you sign out from **Account → Sign out and clear session**.

## Settings

Open **File → Settings** (or the tray menu):

- Home page: conversations, pairing, or Messages for web home
- Google account used for the sign-in hint
- Close to tray, start minimized, launch at login
- Automatic notification / camera / microphone permission
- Hardware acceleration and user agent (Chrome is the default)

## Command line

```bash
messages-kde
messages-kde --minimized
messages-kde 'https://messages.google.com/web/conversations'
messages-kde 'sms:+15551234567'
```

Debug JavaScript console output:

```bash
MESSAGES_KDE_DEBUG=1 messages-kde
```

Extra Chromium flags:

```bash
MESSAGES_KDE_CHROMIUM_FLAGS='--disable-gpu-sandbox' messages-kde
```

## Uninstall

```bash
./uninstall.sh          # keep saved login
./uninstall.sh --purge  # also delete cookies, cache, and settings
```

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| Ctrl+R | Reload |
| Ctrl+Shift+R | Hard reload |
| Ctrl+F | Find in page |
| Ctrl++ / Ctrl+- / Ctrl+0 | Zoom |
| F11 | Full screen |
| Ctrl+, | Settings |
| Ctrl+Shift+I | Developer tools |
| Ctrl+Q | Quit |
| Ctrl+W | Close window (hide to tray) |
