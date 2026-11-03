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
   - 動画は通常の Git ファイルとして管理します (1 本あたり数 MB。100MB を超える動画は分割・圧縮してください)
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

## 7. 企画: 温泉巡り × 郷土料理 7日間 (アフィリエイト連携)

| Day | 温泉 | 郷土料理 | アフィリエイト (宿 / お取り寄せ) |
|---|---|---|---|
| 1 | 群馬・草津温泉 | おっきりこみ | `kusatsu_stay` / `okkirikomi` |
| 2 | 大分・別府温泉 | 地獄蒸し・とり天 | `beppu_stay` / `toriten` |
| 3 | 山形・銀山温泉 | 芋煮 | `ginzan_stay` / `imoni` |
| 4 | 岐阜・下呂温泉 | 朴葉味噌・飛騨牛 | `gero_stay` / `hobamiso` |
| 5 | 愛媛・道後温泉 | 鯛めし | `dogo_stay` / `taimeshi` |
| 6 | 鹿児島・指宿温泉 | 黒豚しゃぶしゃぶ | `ibusuki_stay` / `kurobuta` |
| 7 | 熊本・黒川温泉 | だご汁 | `kurokawa_stay` / `dagojiru` |

各リールは約 21 秒・6 シーン構成（フック → 温泉 → 見どころ → 郷土料理 → CTA）。
台本・テロップ・撮影指示・キャプション・ハッシュタグ(5個)は `content/plan_7days.json` にあります。

| ファイル | 内容 |
|---|---|
| `content/plan_7days.json` | 7日分の台本 (シーンごとの秒数・テロップ・撮影内容)、キャプション、ハッシュタグ |
| `content/affiliate_links.json` | アフィリエイトリンク (14 件, `REPLACE_ME` を差し替え) |
| `content/captions/` | 投稿用キャプション完成版 (【PR】表記・リンク誘導・ハッシュタグ込み) |
| `content/shot_list.md` | 現地で見る撮影リスト |
| `videos/day1_kusatsu.mp4` 〜 `day7_kurokawa.mp4` | 生成済みリール動画 (モーショングラフィックス版, 各約21秒) |

### 流れ

```bash
# ① アフィリエイトリンクを登録
#    楽天アフィリエイト / A8.net / もしもアフィリエイト / バリューコマース 等で
#    宿 (楽天トラベル・じゃらん・一休) と お取り寄せ商品 のリンクを作り、
#    content/affiliate_links.json の "url" に貼る

# ② 計画とキャプションを確認 (未設定リンクがあれば一覧表示)
python -m reels_poster plan

# ③ 撮影前にテロップと尺を確認 (撮影指示カード入りの下書き動画)
python -m reels_poster render --draft          # → build/drafts/day1_kusatsu_draft.mp4 …

# ④-A 撮影素材なしで、そのまま投稿できるモーショングラフィックス版を作る (生成済み)
#      テーマ色の背景・湯けむり・イラスト・テロップのアニメーション・オリジナル BGM 入り
python -m reels_poster render --graphic        # → videos/day1_kusatsu.mp4 …

# ④-B 撮影素材を media/day1/1.mp4 〜 6.mp4 に置いて本番レンダリング
#      (写真 .jpg/.png も可 → ゆっくりズーム。BGM は media/bgm.mp3 または media/day1/bgm.mp3)
#      --graphic を付けると、素材がそろっていないシーンだけグラフィックで補います
python -m reels_poster render

# ⑤ プロフィール用リンク集ページを生成 → GitHub Pages (docs/ フォルダ) で公開し、URL をプロフィールに設定
python -m reels_poster linkpage                # → docs/index.html

# ⑥ 明日から 1 日 1 本、19:00 に予約 → push すれば GitHub Actions が自動投稿
python -m reels_poster schedule-plan --start 2026-11-04
git add videos queue.json docs && git commit -m "7日分を予約" && git push
```

### 収益化と法令のポイント

- **ステマ規制 (景品表示法)**: アフィリエイトを含む投稿はキャプション冒頭に「【PR】」、末尾に広告を含む旨を自動で入れます。リンク集ページにも PR 表記と `rel="sponsored"` を付けます。消さないでください
- キャプション内の URL はタップできないため、「プロフィールのリンク → Day 番号」で誘導します（ページは `#day1` などで各 Day に飛べます）
- ストーリーズの **リンクスタンプ** に `https://<ページURL>#day1` を貼って、リール投稿と同じ日にシェアすると成果が出やすくなります
- 各 ASP の規約で Instagram 掲載が許可されているかを確認してください (プログラムごとに SNS 掲載の可否が違います)
- キャプションは「行ったらやりたいこと」形式のガイド文です。実際に訪れて撮影した場合は、体験に合わせて書き換えるとより伝わります（行っていない場所の体験談は書かないでください）
- 浴室・脱衣所は撮影禁止の施設がほとんどです。外観・客室・料理・足湯・貸切風呂（無人）を中心に撮影してください

## 開発

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
