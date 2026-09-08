from __future__ import annotations

from urllib.parse import urlencode

from messages_kde import APP_DISPLAY_NAME, APP_ID, APP_NAME, DEFAULT_GOOGLE_ACCOUNT

DESKTOP_FILE = f"{APP_ID}.desktop"
DBUS_SERVICE = "org.juanton.MessagesKDE"
SOCKET_NAME = APP_NAME

CONVERSATIONS_URL = "https://messages.google.com/web/conversations"
AUTHENTICATION_URL = "https://messages.google.com/web/authentication"
DEFAULT_START_URL = CONVERSATIONS_URL
DEFAULT_ACCOUNT = DEFAULT_GOOGLE_ACCOUNT

START_URL_PRESETS: list[tuple[str, str]] = [
    ("Messages conversations", CONVERSATIONS_URL),
    ("Device pairing / authentication", AUTHENTICATION_URL),
    ("Messages for web home", "https://messages.google.com/web"),
]

INTERNAL_HOST_SUFFIXES = (
    "messages.google.com",
    "accounts.google.com",
    "accounts.youtube.com",
    "myaccount.google.com",
    "oauth2.googleapis.com",
    "www.googleapis.com",
    "content.googleapis.com",
    "clients6.google.com",
    "clients.google.com",
    "apis.google.com",
    "signaler-pa.clients6.google.com",
    "instantmessaging-pa.googleapis.com",
    "googleapis.com",
    "gstatic.com",
    "googleusercontent.com",
    "ggpht.com",
    "gvt1.com",
    "gvt2.com",
    "recaptcha.net",
    "g.co",
    "google.com",
)

EXTERNAL_HOST_SUFFIXES = (
    "support.google.com",
    "www.google.com",
    "youtube.com",
    "youtu.be",
    "maps.google.com",
    "maps.app.goo.gl",
    "mail.google.com",
    "drive.google.com",
    "docs.google.com",
    "photos.google.com",
    "calendar.google.com",
    "meet.google.com",
    "news.google.com",
    "play.google.com",
    "store.google.com",
    "blog.google",
    "android.com",
    "developers.google.com",
    "cloud.google.com",
)

AUTH_HOST_SUFFIXES = (
    "accounts.google.com",
    "accounts.youtube.com",
    "myaccount.google.com",
    "oauth2.googleapis.com",
)

USER_AGENT_CHROME = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/{version} Safari/537.36"
)

ABOUT_TEXT = (
    f"{APP_DISPLAY_NAME} is an unofficial KDE wrapper around Google Messages "
    "for web. It is not affiliated with, endorsed by, or supported by Google.\n\n"
    "Texting still runs through your Android phone. Keep the phone on and "
    "connected, then sign in with your Google account and confirm this computer "
    f"in the Messages app. Default account: {DEFAULT_GOOGLE_ACCOUNT}."
)


def account_chooser_url(
    email: str = DEFAULT_ACCOUNT,
    continue_url: str = CONVERSATIONS_URL,
) -> str:
    return "https://accounts.google.com/AccountChooser?" + urlencode(
        {
            "Email": email,
            "continue": continue_url,
            "hl": "en",
        }
    )


LOGIN_HINT_JS = r"""
(function (email) {
  if (!email) return;
  const wanted = String(email).trim().toLowerCase();
  if (!wanted) return;

  function setInputValue(input, value) {
    const proto = window.HTMLInputElement && window.HTMLInputElement.prototype;
    const desc = proto && Object.getOwnPropertyDescriptor(proto, "value");
    if (desc && desc.set) desc.set.call(input, value);
    else input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function clickMatchingAccount() {
    const identified = Array.from(document.querySelectorAll("[data-identifier], [data-email]"));
    for (const node of identified) {
      const id = (
        node.getAttribute("data-identifier") ||
        node.getAttribute("data-email") ||
        ""
      ).toLowerCase();
      if (id === wanted) {
        node.click();
        return true;
      }
    }
    const candidates = Array.from(document.querySelectorAll("[role='link'], [role='button'], li"));
    for (const node of candidates) {
      const text = (node.textContent || "").toLowerCase();
      if (text.includes(wanted) && node.offsetParent) {
        node.click();
        return true;
      }
    }
    return false;
  }

  if (clickMatchingAccount()) return;

  const input = document.querySelector("#identifierId")
    || document.querySelector("input[type='email']")
    || document.querySelector("input[name='identifier']")
    || document.querySelector("input[autocomplete='username']");
  if (!input) return;
  if ((input.value || "").toLowerCase() === wanted) return;
  setInputValue(input, email);
  window.setTimeout(function () {
    const next = document.querySelector("#identifierNext")
      || document.querySelector("button[type='submit']");
    if (next && (input.value || "").toLowerCase() === wanted) next.click();
  }, 350);
})(%EMAIL%);
"""


UNREAD_COUNT_JS = r"""
(() => {
  try {
    const title = document.title || "";
    const titled = title.match(/^\((\d+)\)/);
    if (titled) return parseInt(titled[1], 10);
    const labeled = document.querySelectorAll('[aria-label*="unread" i]');
    if (labeled.length) return labeled.length;
    const dots = document.querySelectorAll(
      '[data-e2e-unread="true"], [data-is-unread="true"], [class*="unreadCount"], [class*="unread-count"]'
    );
    return dots.length;
  } catch (e) {
    return 0;
  }
})()
"""
