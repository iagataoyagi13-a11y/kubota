"""コンテンツ計画 (plan_7days.json) とアフィリエイトリンクの読み込み・キャプション生成.

ステマ規制 (景品表示法, 2023年10月施行) 対応として、アフィリエイトを含む投稿の
キャプション冒頭に必ず「【PR】」を付け、末尾にも広告を含む旨を明記する。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from .schedule import JST

PLACEHOLDER = "REPLACE_ME"
PR_PREFIX = "【PR】"
PR_FOOTER = "※この投稿にはアフィリエイト広告（PR）を含みます"
DEFAULT_PLAN = "content/plan_7days.json"
DEFAULT_LINKS = "content/affiliate_links.json"


@dataclass
class Plan:
    data: dict[str, Any]
    links: dict[str, dict[str, Any]]

    @classmethod
    def load(cls, plan_path: str = DEFAULT_PLAN, links_path: str = DEFAULT_LINKS) -> "Plan":
        with open(plan_path, encoding="utf-8") as f:
            data = json.load(f)
        links: dict[str, dict[str, Any]] = {}
        if os.path.exists(links_path):
            with open(links_path, encoding="utf-8") as f:
                links = json.load(f)
        return cls(data, links)

    @property
    def days(self) -> list[dict[str, Any]]:
        return self.data["days"]

    def day(self, n: int) -> dict[str, Any]:
        for d in self.days:
            if d["day"] == n:
                return d
        raise KeyError(f"Day{n} は計画にありません")

    # ------------------------------------------------------------ captions
    def caption(self, day: dict[str, Any]) -> str:
        prefix = PR_PREFIX if day.get("affiliate") else ""
        parts = [prefix + day["caption"].strip()]
        if day.get("affiliate"):
            parts.append(f"🔗{day['onsen']}の宿・{day['food']}のお取り寄せは"
                         f"プロフィールのリンク「Day{day['day']}」から")
        cta = self.data.get("account_cta")
        if cta:
            parts.append(f"📌{cta}")
        parts.append(" ".join(day.get("hashtags", [])))
        if day.get("affiliate"):
            parts.append(PR_FOOTER)
        return "\n\n".join(p for p in parts if p)

    def video_path(self, day: dict[str, Any], out_dir: str = "videos") -> str:
        return os.path.join(out_dir, f"day{day['day']}_{day['slug']}.mp4")

    def duration(self, day: dict[str, Any]) -> float:
        return round(sum(float(s["dur"]) for s in day["scenes"]), 2)

    # ---------------------------------------------------------- validation
    def problems(self, check_links: bool = True) -> list[str]:
        out: list[str] = []
        for d in self.days:
            tag = f"Day{d['day']}"
            dur = self.duration(d)
            if not 3 <= dur <= 90:
                out.append(f"{tag}: 尺 {dur}秒 (3〜90秒を推奨)")
            for key in d.get("affiliate", []):
                link = self.links.get(key)
                if link is None:
                    out.append(f"{tag}: アフィリエイトキー '{key}' が affiliate_links.json にありません")
                elif check_links and (not link.get("url") or PLACEHOLDER in link["url"]):
                    out.append(f"{tag}: '{key}' の URL が未設定です ({PLACEHOLDER})")
            if len(self.caption(d)) > 2200:
                out.append(f"{tag}: キャプションが 2,200 文字を超えています")
        return out

    # ------------------------------------------------------------ schedule
    def schedule(self, start: date) -> list[tuple[dict[str, Any], datetime]]:
        hh, mm = (int(x) for x in self.data.get("post_time", "19:00").split(":"))
        return [
            (d, datetime.combine(start + timedelta(days=i), time(hh, mm), tzinfo=JST))
            for i, d in enumerate(sorted(self.days, key=lambda x: x["day"]))
        ]
