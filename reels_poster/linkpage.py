"""プロフィールに貼るリンク集ページ (GitHub Pages: docs/index.html) を生成する.

Instagram のキャプション内リンクはクリックできないため、
「プロフィールのリンク → Day 番号」でアフィリエイトリンクへ誘導する。
"""

from __future__ import annotations

import html
import os
from datetime import datetime

from .content import PLACEHOLDER, Plan
from .schedule import JST

CSS = """
:root{--bg:#faf7f2;--card:#fff;--ink:#2a2420;--muted:#7a6f66;--accent:#c8553d;--line:#eadfd3}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#1b1715;--card:#26201d;
--ink:#f2ebe4;--muted:#b3a79c;--accent:#e9785f;--line:#3a312c}}
:root[data-theme="dark"]{--bg:#1b1715;--card:#26201d;--ink:#f2ebe4;--muted:#b3a79c;--accent:#e9785f;--line:#3a312c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font-family:"Hiragino Sans","Noto Sans JP",system-ui,sans-serif;line-height:1.6}
main{max-width:560px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:1.4rem;margin:.2em 0}.pr{font-size:.8rem;color:var(--muted);
border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:12px 0 20px}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:14px 0;
scroll-margin-top:12px}section:target{outline:2px solid var(--accent)}
.day{font-size:.75rem;font-weight:700;color:var(--accent);letter-spacing:.08em}
h2{font-size:1.1rem;margin:.1em 0 .6em}a.btn{display:block;text-decoration:none;color:var(--ink);
border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:8px 0;font-weight:600}
a.btn small{display:block;font-weight:400;color:var(--muted)}a.btn:hover{border-color:var(--accent)}
nav{display:flex;flex-wrap:wrap;gap:6px}nav a{font-size:.8rem;color:var(--accent);text-decoration:none;
border:1px solid var(--line);border-radius:999px;padding:4px 10px}footer{font-size:.75rem;color:var(--muted);margin-top:28px}
"""


def build_html(plan: Plan, allow_placeholders: bool = False) -> str:
    title = plan.data.get("series", "リンク集")
    nav, sections = [], []
    for d in sorted(plan.days, key=lambda x: x["day"]):
        anchor = f"day{d['day']}"
        nav.append(f'<a href="#{anchor}">Day{d["day"]}</a>')
        buttons = []
        for key in d.get("affiliate", []):
            link = plan.links.get(key)
            if not link:
                continue
            url = link.get("url", "")
            if PLACEHOLDER in url or not url:
                if not allow_placeholders:
                    raise ValueError(f"Day{d['day']}: '{key}' の URL が未設定です")
                url = "#"
            buttons.append(
                f'<a class="btn" href="{html.escape(url)}" target="_blank" '
                f'rel="sponsored nofollow noopener">{html.escape(link["label"])}'
                f'<small>{html.escape(link.get("program", ""))}</small></a>')
        sections.append(
            f'<section id="{anchor}"><div class="day">DAY {d["day"]}</div>'
            f'<h2>{html.escape(d["area"])} × {html.escape(d["food"])}</h2>{"".join(buttons)}</section>')
    updated = datetime.now(JST).strftime("%Y-%m-%d")
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body><main>
<h1>{html.escape(title)}</h1>
<p class="pr">【PR】このページにはアフィリエイト広告が含まれています。リンク先での予約・購入により、運営者が報酬を受け取る場合があります。</p>
<nav>{"".join(nav)}</nav>
{"".join(sections)}
<footer>最終更新 {updated}・価格や空室状況はリンク先でご確認ください。</footer>
</main></body></html>
"""


def write_linkpage(plan: Plan, path: str = "docs/index.html", allow_placeholders: bool = False) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_html(plan, allow_placeholders))
    return path
