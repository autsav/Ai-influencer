import threading
import time

from aeloria.approval.handlers import (
    handle_callback,
    handle_caption_reply,
    handle_edit_command,
    handle_photo_command,
    handle_trend_command,
)
from aeloria.approval.telegram_api import Telegram
from aeloria.config import get_settings
from aeloria.db.client import Db


def _chat_matches(chat_id, allowed) -> bool:
    """String/int tolerant compare (Telegram sends int ids, .env stores str)."""
    return chat_id is not None and str(chat_id) == str(allowed)


def process_update(u: dict, db: Db, tg: Telegram, allowed_chat_id=None) -> None:
    if "callback_query" in u:
        cq = u["callback_query"]
        cq_chat = ((cq.get("message") or {}).get("chat") or {}).get("id")
        if allowed_chat_id is not None and cq_chat is not None \
                and not _chat_matches(cq_chat, allowed_chat_id):
            return  # button press surfaced from a foreign chat — ignore
        ack, followup = handle_callback(cq.get("data", ""), db)
        # The action already applied in handle_callback; the toast is only
        # feedback. If it's stale (400 under flaky polling), confirm via a
        # message so the operator always sees the result.
        if not tg.answer_callback(cq["id"], ack):
            tg.send_message(ack)
        if followup:
            tg.send_message(followup, force_reply=True)
        return
    msg = u.get("message")
    if msg and allowed_chat_id is not None \
            and not _chat_matches((msg.get("chat") or {}).get("id"), allowed_chat_id):
        return  # command/reply from a foreign chat — ignore, no reply
    if msg and msg.get("text", "").startswith("/edit"):
        res = handle_edit_command(msg["text"], db, tg)
        tg.send_message(res)
        return
    if msg and msg.get("text", "").startswith("/trend"):
        res = handle_trend_command(msg["text"], db)
        tg.send_message(res)
        return
    if msg and msg.get("text", "").startswith("/photo"):
        res = handle_photo_command(msg["text"], tg)
        if res:
            tg.send_message(res)
        return
    if msg and msg.get("reply_to_message"):
        res = handle_caption_reply(
            msg["reply_to_message"].get("text", ""), msg.get("text", ""), db
        )
        if res:
            tg.send_message(res)


def run(stop_event: threading.Event | None = None) -> None:
    s = get_settings()
    if not s.telegram_bot_token or not s.telegram_chat_id:
        raise SystemExit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set in .env")
    db = Db(s)
    tg = Telegram(s.telegram_bot_token, s.telegram_chat_id)
    offset = None
    poll_timeout = getattr(s, "telegram_poll_timeout", 30)
    print(f"aeloria approval bot: polling… (poll_timeout={poll_timeout}s)")
    while stop_event is None or not stop_event.is_set():
        try:
            updates = tg.get_updates(offset, timeout=poll_timeout)
        except Exception as e:
            print(f"poll error: {e}")
            time.sleep(5)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            try:
                process_update(u, db, tg, allowed_chat_id=s.telegram_chat_id)
            except Exception as e:
                print(f"update {u.get('update_id')}: {e}")


def supervise_bot(stop_event: threading.Event) -> None:
    """Run the poll loop in a thread; restart on top-level crash; exit on stop or misconfig."""
    backoff = 5
    while not stop_event.is_set():
        try:
            run(stop_event)
        except SystemExit:
            print("approval bot: telegram not configured — supervisor exiting")
            return
        except Exception as e:
            print(f"approval bot crashed: {e} — restarting in {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue
        # run() returned normally only because stop_event was set
        return


if __name__ == "__main__":
    run()
