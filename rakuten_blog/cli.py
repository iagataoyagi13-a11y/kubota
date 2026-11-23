"""楽天ブログ自動投稿 CLI.

python -m rakuten_blog build                     # 画像 7 枚 + 本文 (txt/html) を生成
python -m rakuten_blog schedule --start 2026-11-24   # 1 日 1 記事で予約 (時刻は plan.json の post_time)
python -m rakuten_blog list                      # 予約一覧
python -m rakuten_blog post --day 1 [--dry-run]  # 指定 Day を今すぐ投稿
python -m rakuten_blog run [--dry-run]           # 期限が来た予約を投稿 (GitHub Actions から呼ぶ)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import illustrate
from .content import POST_DIR, Plan
from .mailpost import ConfigError, MailConfig, build_message, send

JST = timezone(timedelta(hours=9))
QUEUE_PATH = Path("content/rakuten_cycling/queue.json")
MAX_ATTEMPTS = 3


def now() -> datetime:
    return datetime.now(JST)


# ------------------------------------------------------------ queue
def load_queue(path: Path = QUEUE_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save_queue(items: list[dict], path: Path = QUEUE_PATH) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def make_schedule(plan: Plan, start: date, post_time: str | None = None) -> list[dict]:
    hh, mm = map(int, (post_time or plan.data.get("post_time", "07:30")).split(":"))
    return [{
        "day": d["day"],
        "title": d["title"],
        "scheduled_at": datetime(start.year, start.month, start.day, hh, mm, tzinfo=JST)
        .__add__(timedelta(days=i)).isoformat(),
        "status": "pending",
        "attempts": 0,
    } for i, d in enumerate(plan.days)]


def due(items: list[dict], at: datetime) -> list[dict]:
    return [it for it in items if it["status"] == "pending" and datetime.fromisoformat(it["scheduled_at"]) <= at]


# ------------------------------------------------------------ commands
def cmd_build(plan: Plan, args) -> int:
    POST_DIR.mkdir(parents=True, exist_ok=True)
    for d in plan.days:
        img = illustrate.render_day(d, plan.data["series"], plan.image_path(d))
        stem = f"day{d['day']}_{d['slug']}"
        (POST_DIR / f"{stem}.txt").write_text(f"{d['title']}\n\n{plan.text_body(d)}\n", encoding="utf-8")
        (POST_DIR / f"{stem}.html").write_text(plan.html_body(d, f"../images/{img.name}") + "\n", encoding="utf-8")
        print(f"Day{d['day']}: {img}")
    return 0


def cmd_schedule(plan: Plan, args) -> int:
    items = load_queue()
    if any(it["status"] == "pending" for it in items) and not args.replace:
        print("未投稿の予約があります。作り直す場合は --replace を付けてください", file=sys.stderr)
        return 1
    items = make_schedule(plan, date.fromisoformat(args.start), args.time)
    save_queue(items)
    for it in items:
        print(f"Day{it['day']}  {it['scheduled_at']}  {it['title']}")
    return 0


def cmd_list(plan: Plan, args) -> int:
    for it in load_queue():
        extra = f"  ({it.get('error')})" if it.get("error") else ""
        print(f"Day{it['day']}  {it['scheduled_at']}  [{it['status']}]  {it['title']}{extra}")
    for p in plan.problems():
        print("要対応:", p)
    return 0


def post_day(plan: Plan, n: int, dry_run: bool, cfg: MailConfig | None) -> None:
    d = plan.day(n)
    image = plan.image_path(d)
    if not image.exists():
        raise FileNotFoundError(f"{image} がありません。先に build を実行してください")
    body = plan.text_body(d)
    if dry_run or cfg is None:
        print(f"--- [dry-run] 件名: {d['title']}\n添付: {image}\n{body}\n---")
        return
    send(cfg, build_message(cfg.sender, cfg.post_address, d["title"], body, image))
    print(f"Day{n} を投稿しました: {d['title']}")


def cmd_post(plan: Plan, args) -> int:
    cfg = None if args.dry_run else MailConfig.from_env()
    post_day(plan, args.day, args.dry_run, cfg)
    if not args.dry_run:
        items = load_queue()
        for it in items:
            if it["day"] == args.day and it["status"] == "pending":
                it.update(status="posted", posted_at=now().isoformat())
        save_queue(items)
    return 0


def cmd_run(plan: Plan, args) -> int:
    items = load_queue()
    todo = due(items, now())
    if not todo:
        print("投稿予定の記事はありません")
        return 0
    cfg = None if args.dry_run else MailConfig.from_env()
    failed = 0
    for it in todo[: args.max]:
        try:
            post_day(plan, it["day"], args.dry_run, cfg)
            if not args.dry_run:
                it.update(status="posted", posted_at=now().isoformat(), error=None)
        except Exception as exc:  # noqa: BLE001 - 次回再試行のため記録して続行
            failed += 1
            it["attempts"] = it.get("attempts", 0) + 1
            it["error"] = f"{type(exc).__name__}: {exc}"
            if it["attempts"] >= MAX_ATTEMPTS:
                it["status"] = "failed"
            print(f"Day{it['day']} の投稿に失敗: {it['error']}", file=sys.stderr)
        if not args.dry_run:
            save_queue(items)  # 1 件ごとに保存して二重投稿を防ぐ
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rakuten_blog", description="楽天ブログ サイクリング7日間 自動投稿")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="画像と本文を生成")
    s = sub.add_parser("schedule", help="7日分を予約")
    s.add_argument("--start", required=True, help="Day1 の日付 (YYYY-MM-DD, 日本時間)")
    s.add_argument("--time", help="投稿時刻 HH:MM (省略時は plan.json の post_time)")
    s.add_argument("--replace", action="store_true", help="既存の予約を置き換える")
    sub.add_parser("list", help="予約一覧")
    p = sub.add_parser("post", help="指定した Day を今すぐ投稿")
    p.add_argument("--day", type=int, required=True)
    p.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("run", help="期限が来た予約を投稿")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--max", type=int, default=1, help="1 回の実行で投稿する最大件数 (既定 1)")
    args = ap.parse_args(argv)

    plan = Plan.load()
    handlers = {"build": cmd_build, "schedule": cmd_schedule, "list": cmd_list, "post": cmd_post, "run": cmd_run}
    try:
        return handlers[args.cmd](plan, args)
    except (ConfigError, FileNotFoundError, KeyError) as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 2
