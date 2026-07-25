"""Publish stage — manages the scheduled prompts queue.

Reads and writes queue/scheduled_prompts.json with status tracking.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

QUEUE_DIR = Path("queue")
QUEUE_FILE = QUEUE_DIR / "scheduled_prompts.json"


@dataclass
class QueueEntry:
    id: str
    prompt: str
    scene: str
    wardrobe: str = ""
    pose: str = ""
    camera_angle: str = ""
    status: str = "pending"  # pending → generating → qc_passed → qc_failed → published
    image_path: str = ""
    qc_result: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    seed: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: dict) -> "QueueEntry":
        return cls(**{k: data.get(k) for k in cls.__dataclass_fields__})


def ensure_queue_file() -> None:
    """Create queue file if it doesn't exist."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    if not QUEUE_FILE.exists():
        QUEUE_FILE.write_text(json.dumps([], indent=2))


def load_queue() -> list[dict]:
    """Load the scheduled prompts queue."""
    ensure_queue_file()
    with open(QUEUE_FILE) as f:
        return json.load(f)


def save_queue(entries: list[dict]) -> None:
    """Save the queue back to disk."""
    ensure_queue_file()
    with open(QUEUE_FILE, "w") as f:
        json.dump(entries, f, indent=2)
    logger.info("Queue saved: %d entries", len(entries))


def add_entry(entry: QueueEntry) -> None:
    """Add a new entry to the queue."""
    if not entry.created_at:
        entry.created_at = datetime.now(timezone.utc).isoformat()
        entry.updated_at = entry.created_at
    queue = load_queue()
    queue.append(entry.to_dict())
    save_queue(queue)
    logger.info("Queue entry added: %s (status=%s)", entry.id, entry.status)


def update_entry(entry_id: str, updates: dict) -> None:
    """Update an existing queue entry."""
    queue = load_queue()
    for entry in queue:
        if entry.get("id") == entry_id:
            entry.update(updates)
            entry["updated_at"] = datetime.now(timezone.utc).isoformat()
            break
    save_queue(queue)
    logger.info("Queue entry updated: %s → %s", entry_id, updates.get("status", "?"))


def get_pending() -> list[dict]:
    """Get all pending entries."""
    return [e for e in load_queue() if e.get("status") == "pending"]


def get_by_status(status: str) -> list[dict]:
    """Get all entries with a given status."""
    return [e for e in load_queue() if e.get("status") == status]


def save_image(entry_id: str, image_bytes: bytes, output_dir: str = "output/pipeline") -> str:
    """Save generated image to disk and return path."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{entry_id}.png")
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path