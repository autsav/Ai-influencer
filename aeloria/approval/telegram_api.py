import httpx

TELEGRAM_CAPTION_LIMIT = 1024  # Telegram sendPhoto caption hard limit


class TelegramError(Exception):
    pass


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self._base = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id

    def _call(self, method: str, **params):
        r = httpx.post(f"{self._base}/{method}", json=params, timeout=35)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise TelegramError(f"{method} failed: {data}")
        return data["result"]

    def send_photo(self, photo_url: str, caption: str,
                   buttons: list[list[tuple[str, str]]]) -> dict:
        # Preview only: Telegram rejects sendPhoto captions over 1024 chars (P4's
        # richer captions exceed it). The full caption still publishes to IG.
        if len(caption) > TELEGRAM_CAPTION_LIMIT:
            caption = caption[:TELEGRAM_CAPTION_LIMIT - 1] + "…"
        kb = {
            "inline_keyboard": [
                [{"text": t, "callback_data": c} for t, c in row] for row in buttons
            ]
        }
        return self._call(
            "sendPhoto", chat_id=self.chat_id, photo=photo_url,
            caption=caption, reply_markup=kb,
        )

    def send_photo_data(self, image_bytes: bytes, caption: str = "") -> bool:
        """Send a photo from raw bytes (used for on-the-fly previews, no R2 needed)."""
        if len(caption) > TELEGRAM_CAPTION_LIMIT:
            caption = caption[:TELEGRAM_CAPTION_LIMIT - 1] + "…"
        try:
            r = httpx.post(
                f"{self._base}/sendPhoto",
                data={"chat_id": self.chat_id, "caption": caption},
                files={"photo": ("photo.jpg", image_bytes, "image/jpeg")},
                timeout=35,
            )
            return r.json().get("ok", False)
        except Exception:
            return False

    def send_message(self, text: str, force_reply: bool = False, buttons=None) -> dict:
        params = {"chat_id": self.chat_id, "text": text}
        if buttons:
            params["reply_markup"] = {
                "inline_keyboard": [[{"text": t, "callback_data": c} for t, c in row] for row in buttons]
            }
        elif force_reply:
            params["reply_markup"] = {"force_reply": True}
        return self._call("sendMessage", **params)

    def get_updates(self, offset: int | None, timeout: int = 30) -> list[dict]:
        # Long-poll seconds. Lower it on networks that reset idle connections
        # (e.g. proxies that kill a held 30s poll) so each request returns fast.
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        return self._call("getUpdates", **params)

    def answer_callback(self, callback_id: str, text: str) -> bool:
        # Best-effort: the toast expires after ~15s, so a delayed poll (network
        # resets) makes answerCallbackQuery 400 with "query too old". That must
        # NOT lose the action — the caller sends a message fallback instead.
        try:
            self._call("answerCallbackQuery", callback_query_id=callback_id, text=text)
            return True
        except (httpx.HTTPError, TelegramError):
            return False
