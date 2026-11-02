"""コマンドライン.

  python -m reels_poster post  VIDEO -c "キャプション"     # 今すぐ投稿
  python -m reels_poster add   VIDEO -c "..." -t "2026-11-03 19:00"  # 予約
  python -m reels_poster list                              # 予約一覧
  python -m reels_poster run                               # 期限が来た予約を投稿
  python -m reels_poster check VIDEO -c "..."              # 動画チェックのみ
  python -m reels_poster limit                             # 24h 投稿上限
  python -m reels_poster refresh-token                     # 長期トークン更新
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from .client import InstagramAPIError, InstagramClient
from .config import Config, ConfigError
from .schedule import DEFAULT_QUEUE, Queue, now, parse_time
from .video import check_video


def _client() -> InstagramClient:
    return InstagramClient(Config.from_env())


def _read_caption(args: argparse.Namespace) -> str:
    if getattr(args, "caption_file", None):
        with open(args.caption_file, encoding="utf-8") as f:
            return f.read().strip()
    return args.caption or ""


def _options(args: argparse.Namespace) -> dict:
    opts = {
        "share_to_feed": not args.no_feed,
        "cover_url": args.cover_url,
        "thumb_offset_ms": args.thumb_offset,
        "audio_name": args.audio_name,
        "location_id": args.location_id,
        "collaborators": args.collaborator or None,
    }
    return {k: v for k, v in opts.items() if v is not None}


def _print_check(result) -> None:
    for w in result.warnings:
        print(f"  ⚠ {w}")
    for e in result.errors:
        print(f"  ✖ {e}")
    if result.info:
        print(f"  info: {json.dumps(result.info, ensure_ascii=False)}")


def cmd_check(args) -> int:
    result = check_video(args.video, _read_caption(args))
    _print_check(result)
    print("OK" if result.ok else "NG")
    return 0 if result.ok else 1


def cmd_post(args) -> int:
    caption = _read_caption(args)
    result = check_video(args.video, caption)
    _print_check(result)
    if not result.ok and not args.force:
        print("動画チェックに失敗しました (--force で強行)")
        return 1
    client = _client()
    print("投稿中…")
    res = client.post_reel(args.video, caption, **_options(args))
    print(f"✔ 投稿完了 media_id={res.media_id} {res.permalink or ''}")
    return 0


def cmd_add(args) -> int:
    caption = _read_caption(args)
    result = check_video(args.video, caption)
    _print_check(result)
    if not result.ok and not args.force:
        print("動画チェックに失敗しました (--force で強行)")
        return 1
    q = Queue(args.queue)
    item = q.add(args.video, caption, args.time, **_options(args))
    q.save()
    print(f"✔ 予約しました id={item['id']} at={item['scheduled_at']}")
    return 0


def cmd_list(args) -> int:
    q = Queue(args.queue)
    if not q.items:
        print("予約はありません")
        return 0
    for i in q.items:
        if args.pending and i["status"] == "posted":
            continue
        when = parse_time(i["scheduled_at"]).strftime("%Y-%m-%d %H:%M %z")
        cap = i["caption"].replace("\n", " ")[:30]
        extra = i.get("permalink") or i.get("error") or ""
        print(f"{i['id']:<22} {i['status']:<8} {when}  {i['video']}  「{cap}」 {extra}")
    return 0


def cmd_remove(args) -> int:
    q = Queue(args.queue)
    if not q.remove(args.id):
        print(f"見つかりません: {args.id}")
        return 1
    q.save()
    print(f"✔ 削除しました: {args.id}")
    return 0


def run_due(queue: Queue, client: InstagramClient, *, max_posts: int, max_attempts: int,
            interval: float = 0, sleep=time.sleep) -> tuple[int, int]:
    """期限が来た予約を投稿する. 戻り値: (成功数, 失敗数)."""
    due = queue.due(max_attempts=max_attempts)
    if not due:
        print("投稿予定の動画はありません")
        return 0, 0
    try:
        limit = client.publishing_limit()
        if limit["remaining"] is not None:
            print(f"投稿上限: 残り {limit['remaining']}/{limit['quota_total']} (24h)")
            max_posts = min(max_posts, limit["remaining"])
    except InstagramAPIError as e:
        print(f"⚠ 投稿上限の取得に失敗: {e}")

    ok = ng = 0
    for n, item in enumerate(due[:max_posts]):
        if n and interval:
            sleep(interval)
        item["attempts"] = item.get("attempts", 0) + 1
        print(f"→ {item['id']} {item['video']} (試行 {item['attempts']}/{max_attempts})")
        check = check_video(item["video"], item["caption"])
        if not check.ok:
            item.update(status="failed", error="; ".join(check.errors),
                        attempts=max_attempts)  # 動画自体の問題は再試行しない
            ng += 1
            print(f"  ✖ {item['error']}")
            queue.save()
            continue
        try:
            res = client.post_reel(item["video"], item["caption"], **Queue.options_of(item))
        except (InstagramAPIError, OSError) as e:
            item.update(status="failed", error=str(e))
            ng += 1
            print(f"  ✖ {e}")
        else:
            item.update(status="posted", error=None, media_id=res.media_id,
                        permalink=res.permalink, posted_at=now().isoformat())
            ok += 1
            print(f"  ✔ {res.permalink or res.media_id}")
        queue.save()  # 1 件ごとに保存 (途中で落ちても二重投稿しない)
    return ok, ng


def cmd_run(args) -> int:
    q = Queue(args.queue)
    if not q.due(max_attempts=args.max_attempts):
        print("投稿予定の動画はありません")
        return 0
    ok, ng = run_due(q, _client(), max_posts=args.max_posts,
                     max_attempts=args.max_attempts, interval=args.interval)
    print(f"完了: 成功 {ok} / 失敗 {ng}")
    return 1 if ng and not ok else 0


def cmd_limit(args) -> int:
    print(json.dumps(_client().publishing_limit(), ensure_ascii=False))
    return 0


def cmd_refresh(args) -> int:
    data = _client().refresh_long_lived_token()
    days = int(data.get("expires_in", 0)) // 86400
    print(f"新しいトークン (有効 {days} 日):\n{data.get('access_token')}")
    print("→ .env / GitHub Secrets の IG_ACCESS_TOKEN を更新してください")
    return 0


def _add_post_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("video", help="動画ファイルのパス または 公開 URL")
    p.add_argument("-c", "--caption", default="", help="キャプション")
    p.add_argument("-C", "--caption-file", help="キャプションをファイルから読み込む")
    p.add_argument("--no-feed", action="store_true", help="フィードには表示しない")
    p.add_argument("--cover-url", help="カバー画像の公開 URL")
    p.add_argument("--thumb-offset", type=int, help="カバーに使うフレーム位置 (ミリ秒)")
    p.add_argument("--audio-name", help="オリジナル音源の名前")
    p.add_argument("--location-id", help="位置情報 (Facebook ページ ID)")
    p.add_argument("--collaborator", action="append", help="共同投稿者のユーザー名 (複数可)")
    p.add_argument("--force", action="store_true", help="動画チェック失敗でも続行")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="reels_poster", description="Instagram リール自動投稿")
    ap.add_argument("-q", "--queue", default=DEFAULT_QUEUE, help="予約キューの JSON ファイル")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("post", help="今すぐ投稿")
    _add_post_options(p)
    p.set_defaults(func=cmd_post)

    p = sub.add_parser("add", help="予約投稿に追加")
    _add_post_options(p)
    p.add_argument("-t", "--time", help="投稿日時 例: '2026-11-03 19:00' (省略時: 即時, TZ 無しは JST)")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("list", help="予約一覧")
    p.add_argument("--pending", action="store_true", help="未投稿のみ")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("remove", help="予約を削除")
    p.add_argument("id")
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("run", help="期限が来た予約を投稿 (cron / GitHub Actions 用)")
    p.add_argument("--max-posts", type=int, default=5, help="1 回の実行で投稿する最大数")
    p.add_argument("--max-attempts", type=int, default=3, help="失敗時の最大試行回数")
    p.add_argument("--interval", type=float, default=30, help="連続投稿の間隔 (秒)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("check", help="動画とキャプションのチェックのみ")
    p.add_argument("video")
    p.add_argument("-c", "--caption", default="")
    p.add_argument("-C", "--caption-file")
    p.set_defaults(func=cmd_check)

    sub.add_parser("limit", help="24 時間の投稿上限を表示").set_defaults(func=cmd_limit)
    sub.add_parser("refresh-token", help="長期アクセストークンを更新").set_defaults(func=cmd_refresh)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, InstagramAPIError, FileNotFoundError, ValueError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
