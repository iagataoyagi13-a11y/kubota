"""7日分の記事データ (plan.json) を読み込み、タイトル・本文・画像パスを組み立てる."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path

PLAN_PATH = Path("content/rakuten_cycling/plan.json")
IMAGE_DIR = Path("content/rakuten_cycling/images")
POST_DIR = Path("content/rakuten_cycling/posts")


@dataclass
class Plan:
    data: dict
    root: Path = Path(".")

    @classmethod
    def load(cls, path: str | Path = PLAN_PATH, root: str | Path = ".") -> "Plan":
        root = Path(root)
        return cls(json.loads((root / path).read_text(encoding="utf-8")), root)

    @property
    def days(self) -> list[dict]:
        return self.data["days"]

    def day(self, n: int) -> dict:
        for d in self.days:
            if d["day"] == n:
                return d
        raise KeyError(f"Day{n} は plan.json にありません")

    def image_path(self, d: dict) -> Path:
        return self.root / IMAGE_DIR / f"day{d['day']}_{d['slug']}.jpg"

    # ------------------------------------------------------------ 本文
    def text_body(self, d: dict) -> str:
        """メール投稿用のプレーンテキスト本文."""
        lines = [d["lead"], ""]
        for sec in d["sections"]:
            lines += [f"【{sec['h']}】", sec["p"], ""]
        lines.append("【今日のワンポイント】")
        lines += [f"・{t}" for t in d["tips"]]
        if self.data.get("notice"):
            lines += ["", self.data["notice"]]
        lines += ["", self.data["signature"], "", " ".join(f"#{t}" for t in d["tags"])]
        return "\n".join(lines)

    def html_body(self, d: dict, image_url: str | None = None) -> str:
        """楽天ブログのエディタ (HTML モード) に貼り付ける用の本文."""
        e = html.escape
        src = image_url or self.image_path(d).name
        parts = [
            f'<p><img src="{e(src)}" alt="{e(d["city"])}・{e(d["park"])}をサイクリングする62歳ヒゲおやじ" width="600"></p>',
            f"<p>{e(d['lead'])}</p>",
        ]
        for sec in d["sections"]:
            parts += [f"<h3>{e(sec['h'])}</h3>", f"<p>{e(sec['p'])}</p>"]
        parts.append("<h3>今日のワンポイント</h3>")
        parts.append("<ul>" + "".join(f"<li>{e(t)}</li>" for t in d["tips"]) + "</ul>")
        if self.data.get("notice"):
            parts.append(f"<p>{e(self.data['notice'])}</p>")
        parts.append("<p>" + e(self.data["signature"]).replace("\n", "<br>") + "</p>")
        parts.append("<p>" + " ".join(f"#{e(t)}" for t in d["tags"]) + "</p>")
        return "\n".join(parts)

    def problems(self) -> list[str]:
        out = []
        for d in self.days:
            if len(d["title"]) > 100:
                out.append(f"Day{d['day']}: タイトルが長すぎます")
            if not self.image_path(d).exists():
                out.append(f"Day{d['day']}: 画像がありません → python -m rakuten_blog build")
        return out
