"""Owner-only Telegram transport and explicit private-chat pairing; no payload logging."""

import json
import re
import time
import urllib.error
import urllib.request


class DeliveryError(Exception):
    def __init__(self, code, *, permanent=False, retry_after=0):
        super().__init__(code)
        self.code = code
        self.permanent = permanent
        self.retry_after = retry_after


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Telegram:
    def __init__(self, token):
        if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{20,}", token):
            raise ValueError("invalid Telegram token configuration")
        self._token = token
        # Credentials are in the URL: never follow redirects or use ambient proxies.
        self._http = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, method, payload):
        if method not in {"getMe", "getChat", "getUpdates", "sendMessage"}:
            raise ValueError("unsupported Telegram operation")
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self._token}/{method}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            try:
                response = self._http.open(request, timeout=10)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status = response.code
                raw = response.read(262145)
            if len(raw) > 262144:
                raise DeliveryError("telegram_response_too_large")
            try:
                body = json.loads(raw)
                if not isinstance(body, dict):
                    raise ValueError
            except (ValueError, UnicodeError):
                raise DeliveryError("telegram_invalid_response") from None
            if status == 200 and body.get("ok") is True:
                return body.get("result")
            code = body.get("error_code", status)
            retry = body.get("parameters", {}).get("retry_after", 0)
            if type(retry) is not int or retry < 0:
                retry = 0
            # Provider descriptions may echo private text; persist only our fixed codes.
            raise DeliveryError(
                "telegram_rate_limited" if code == 429 else "telegram_rejected",
                permanent=code in {400, 401, 403, 404} or 300 <= status < 400,
                retry_after=retry,
            )
        except DeliveryError:
            raise
        except Exception:
            raise DeliveryError("telegram_transport_failed") from None

    def private_chat(self, chat_id):
        if type(chat_id) is not int or chat_id <= 0:
            raise ValueError("a positive private chat ID is required")
        chat = self.request("getChat", {"chat_id": chat_id})
        if not isinstance(chat, dict) or chat.get("type") != "private" or chat.get("id") != chat_id:
            raise ValueError("Telegram recipient is not the configured private chat")

    def send(self, chat_id, text):
        if type(chat_id) is not int or chat_id <= 0:
            raise ValueError("invalid private chat ID")
        if not text or len(text.encode("utf-16-le")) // 2 > 4096:
            raise ValueError("Telegram text exceeds the message limit")
        result = self.request(
            "sendMessage",
            {"chat_id": chat_id, "text": text, "link_preview_options": {"is_disabled": True}},
        )
        if (
            not isinstance(result, dict)
            or type(result.get("message_id")) is not int
            or result.get("chat", {}).get("id") != chat_id
        ):
            raise DeliveryError("telegram_invalid_receipt")
        return result["message_id"]


def paired_chat(updates, code, now=None):
    """Accept only a fresh challenge sent directly by the owner in a private chat."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,64}", code):
        raise ValueError("pairing code must contain at least 24 random URL-safe characters")
    now = time.time() if now is None else now
    matches = set()
    for update in updates:
        message = update.get("message", {})
        chat = message.get("chat", {})
        sender = message.get("from", {})
        if (
            message.get("text") == "/start " + code
            and chat.get("type") == "private"
            and type(chat.get("id")) is int
            and chat["id"] > 0
            and sender.get("id") == chat["id"]
            and not sender.get("is_bot", True)
            and not message.get("forward_origin")
            and 0 <= now - message.get("date", 0) <= 900
        ):
            matches.add(chat["id"])
    if len(matches) != 1:
        raise ValueError("one fresh matching private-chat pairing message is required")
    return matches.pop()
