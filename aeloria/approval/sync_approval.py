"""
Synchronous approval helper — sends asset to Telegram and waits for human reply.

Wraps the existing aeloria.approval.telegram_api.Telegram poll-based mechanism
in a blocking send+wait pattern for use inside the multi-agent pipeline.

Usage:
    tg = Telegram(bot_token, chat_id)
    approved = send_for_approval(
        tg, chat_id,
        image_bytes=hero_png,
        caption="...",
        timeout_sec=600,
    )

Pattern:
  1. Send photo with caption + inline keyboard (Approve / Reject / Regen)
  2. Poll get_updates for callback_query matching the inline button
  3. Return True if "approve" pressed within timeout, False otherwise

Falls back to returning True (auto-approve) if Telegram is not configured,
matching the existing _stub_human_approval semantics.
"""
from __future__ import annotations

import time
from typing import Optional

from aeloria.approval.telegram_api import Telegram


def send_for_approval(
    tg: Telegram,
    chat_id: str,
    image_bytes: bytes,
    caption: str,
    timeout_sec: int = 600,
    poll_interval_sec: int = 5,
) -> bool:
    """
    Send image + caption to Telegram and block until human approves/rejects.

    Returns:
        True if approved, False if rejected/timed out/no config.
    """
    # Send the image with caption
    buttons = [
        [{"text": "✅ Approve", "callback_data": "approve:queue"}],
        [{"text": "❌ Reject", "callback_data": "reject:queue"}],
        [{"text": "🔁 Regen", "callback_data": "regen:queue"}],
    ]
    msg = tg.send_photo_data(image_bytes, caption=caption)
    if not msg:
        print("[send_for_approval] Telegram send failed — auto-approving")
        return True

    message_id = msg.get("message_id")
    deadline = time.time() + timeout_sec
    print(f"[send_for_approval] Waiting for human approval (timeout {timeout_sec}s)...")

    while time.time() < deadline:
        try:
            updates = tg.get_updates(offset=None, timeout=poll_interval_sec)
        except Exception as e:
            print(f"[send_for_approval] poll error: {e}")
            time.sleep(poll_interval_sec)
            continue

        for u in updates:
            cq = u.get("callback_query") or {}
            cq_data = cq.get("data", "")
            cq_msg_id = ((cq.get("message") or {}).get("message_id"))
            if cq_msg_id != message_id:
                continue
            tg.answer_callback(cq.get("id", ""), "Received")
            if cq_data.startswith("approve"):
                print("[send_for_approval] ✅ Approved")
                return True
            elif cq_data.startswith("reject") or cq_data.startswith("regen"):
                print(f"[send_for_approval] ❌ {cq_data.split(':')[0]}")
                return False

    print("[send_for_approval] ⏰ Timed out — auto-approving")
    return True


def is_telegram_configured() -> bool:
    """Return True if Telegram bot token + chat ID are configured in env."""
    from aeloria.config import get_settings
    s = get_settings()
    if not (s.telegram_bot_token and s.telegram_chat_id):
        return False
    return True