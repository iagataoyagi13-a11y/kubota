# Instagram リール動画 自動投稿 (reels_poster)

Instagram Graph API の公式 **Content Publishing API** を使って、リール動画を
「今すぐ投稿」「日時を指定して予約投稿」できる Python ツールです。
GitHub Actions で 15 分ごとに予約キューを確認し、自動で投稿します。

```
動画(mp4) ──▶ ① コンテナ作成 (media_type=REELS)
               ├ 公開URL → video_url
               └ ローカル → resumable アップロード (rupload.facebook.com)
           ──▶ ② 処理待ち (status_code が FINISHED になるまでポーリング)
           ──▶ ③ media_publish で公開 ──▶ permalink を queue.json に記録
```

## 1. 事前準備 (Meta 側)

1. Instagram アカウントを **プロアカウント (ビジネス or クリエイター)** に切り替える
2. [Meta for Developers](https://developers.facebook.com/) でアプリを作成し、Instagram API を追加
3. 次のどちらかでアクセストークンを取得
   | ログイン方式 | 必要な権限 | `GRAPH_HOST` |
   |---|---|---|
   | Instagram ログイン | `instagram_business_basic`, `instagram_business_content_publish` | `graph.instagram.com` |
   | Facebook ログイン (FB ページ連携) | `instagram_basic`, `instagram_content_publish`, `pages_read_engagement` | `graph.facebook.com` |
4. 短期トークンを **長期トークン (60 日)** に交換し、IG ユーザー ID を確認

> 自分のアカウントだけで使う場合、アプリは開発モードのままで OK です（アプリの役割に自分を追加）。

## 2. インストール

```bash
pip install -r requirements.txt     # ffmpeg (ffprobe) があると動画の詳細チェックも行います
cp .env.example .env                # IG_USER_ID / IG_ACCESS_TOKEN を記入
```

## 3. 使い方

```bash
# 今すぐ投稿 (ローカルファイル or 公開 URL)
python -m reels_poster post videos/clip.mp4 -c "今日の作業風景 #リール #kubota"

# 予約投稿 (タイムゾーン省略時は日本時間)
python -m reels_poster add videos/clip2.mp4 -C caption.txt -t "2026-11-03 19:00"
python -m reels_poster list            # 予約一覧
python -m reels_poster remove <ID>     # 予約削除
python -m reels_poster run             # 期限が来た予約を投稿 (cron から呼ぶ)

# その他
python -m reels_poster check videos/clip.mp4 -c "..."   # 投稿前チェックのみ
python -m reels_poster limit                            # 24 時間の投稿上限 / 使用数
python -m reels_poster refresh-token                    # 長期トークン更新 (Instagram ログインのみ)
```

主なオプション: `--no-feed` (フィードに出さない) / `--cover-url` / `--thumb-offset 1500` (カバーにするフレーム, ms) /
`--audio-name` / `--location-id` / `--collaborator ユーザー名` / `--force` (チェック失敗でも投稿)

## 4. GitHub Actions で完全自動化

1. リポジトリの **Settings → Secrets and variables → Actions** に登録
   - Secrets: `IG_USER_ID`, `IG_ACCESS_TOKEN`
   - Variables (任意): `GRAPH_HOST` (Instagram ログインなら `graph.instagram.com`)
2. 動画を `videos/` に置き、`python -m reels_poster add ...` で `queue.json` に予約を追加して push
   - 動画は Git LFS で管理されます (`git lfs install` を事前に実行)
3. `.github/workflows/reels-autopost.yml` が 15 分ごとに `run` を実行し、
   投稿結果 (`status`, `permalink` など) を `queue.json` にコミットします

`queue.json` のエントリ例:

```json
{
  "id": "20261103-1900-a1b2",
  "video": "videos/clip2.mp4",
  "caption": "夕方の圃場 #リール",
  "scheduled_at": "2026-11-03T19:00:00+09:00",
  "share_to_feed": true,
  "status": "pending",
  "attempts": 0
}
```

## 5. 安全装置

- 投稿前に動画をチェック: mp4/mov・300MB 以下・3 秒〜15 分・23〜60fps・キャプション 2,200 字/ハッシュタグ 30 個以内
  （9:16 以外のアスペクト比・H.264/AAC 以外は警告）
- API の **24 時間投稿上限** を取得し、残り枠を超えて投稿しない
- 1 件投稿するごとに `queue.json` を保存 → 途中で止まっても二重投稿しない
- API エラー時は最大 3 回まで次回実行時に再試行。動画自体の不備は再試行しない
- ワークフローは `concurrency` で同時実行を防止

## 6. 注意点

- 長期トークンは **60 日で失効** します。期限前に `refresh-token` を実行し Secrets を更新してください
- GitHub Actions の cron は混雑時に数分〜十数分遅れることがあります
- 公開 URL で投稿する場合、Instagram のサーバーから直接ダウンロード可能な URL である必要があります
- 著作権のある音源はこの API では付けられません (動画に含まれる音声がそのまま使われます)

## 開発

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
