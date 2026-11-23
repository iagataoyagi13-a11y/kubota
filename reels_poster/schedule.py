"""投稿予約キュー (JSON ファイル).

各エントリ:
  {
    "id": "20261102-0900-a1b2",
    "video": "videos/clip.mp4" または "https://...",
    "caption": "...",
    "scheduled_at": "2026-11-02T09:00:00+09:00",
    "share_to_feed": true,
    "cover_url": null, "thumb_offset_ms": null,
    "status": "pending" | "posted" | "failed",
    "attempts": 0, "media_id": null, "permalink": null,
    "error": null, "posted_at": null
  }
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

JST = timezone(timedelta(hours=9))
DEFAULT_QUEUE = "queue.json"
OPTION_KEYS = ("share_to_feed", "cover_url", "thumb_offset_ms", "audio_name",
               "location_id", "collaborators")


def now() -> datetime:
    return datetime.now(JST)


def parse_time(text: str) -> datetime:
    """ISO 8601 を解釈。タイムゾーン無しは JST とみなす."""
    dt = datetime.fromisoformat(text.strip().replace("Z", "+00:00").replace(" ", "T", 1))
    return dt if dt.tzinfo else dt.replace(tzinfo=JST)


class Queue:
    def __init__(self, path: str = DEFAULT_QUEUE):
        self.path = path
        self.items: list[dict[str, Any]] = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.items = json.load(f) or []

    def save(self) -> None:
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, self.path)

    def add(self, video: str, caption: str, scheduled_at: datetime | str | None = None,
            **options: Any) -> dict[str, Any]:
        when = scheduled_at or now()
        if isinstance(when, str):
            when = parse_time(when)
        item: dict[str, Any] = {
            "id": f"{when.astimezone(JST):%Y%m%d-%H%M}-{secrets.token_hex(2)}",
            "video": video,
            "caption": caption,
            "scheduled_at": when.isoformat(),
            "share_to_feed": True,
            "status": "pending",
            "attempts": 0,
            "media_id": None,
            "permalink": None,
            "error": None,
            "posted_at": None,
        }
        item.update({k: v for k, v in options.items() if k in OPTION_KEYS and v is not None})
        self.items.append(item)
        self.items.sort(key=lambda i: parse_time(i["scheduled_at"]))
        return item

    def get(self, item_id: str) -> dict[str, Any] | None:
        return next((i for i in self.items if i["id"] == item_id), None)

    def remove(self, item_id: str) -> bool:
        before = len(self.items)
        self.items = [i for i in self.items if i["id"] != item_id]
        return len(self.items) != before

    def due(self, at: datetime | None = None, max_attempts: int = 3) -> list[dict[str, Any]]:
        at = at or now()
        return [
            i for i in self.items
            if i["status"] in ("pending", "failed")
            and i.get("attempts", 0) < max_attempts
            and parse_time(i["scheduled_at"]) <= at
        ]

    @staticmethod
    def options_of(item: dict[str, Any]) -> dict[str, Any]:
        return {k: item[k] for k in OPTION_KEYS if item.get(k) is not None}
