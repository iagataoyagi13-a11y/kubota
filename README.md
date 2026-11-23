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

## 8. 楽天ブログ自動投稿: おべおやじの北勢ぽたりんぐ7日間 (rakuten_blog)

投稿先: [おべおやじのブログ](https://plaza.rakuten.co.jp/agata13/) — 既存記事にそろえて【見出し】形式・※注意書き付き・毎朝 9:00 投稿

桑名市・四日市市・鈴鹿市の公園をめぐるサイクリング記事 7 日分と、
白ヒゲ・丸メガネの 62 歳サイクリストのイラスト (1200x800, Pillow で生成) を用意し、
楽天ブログの **メール投稿** 機能で 1 日 1 記事ずつ自動投稿します。

| Day | 市 | 公園 | 画像 |
|---|---|---|---|
| 1 | 桑名市 | 九華公園 (桑名城跡) | `day1_kuwana_kyuka.jpg` |
| 2 | 桑名市 | 七里の渡し公園 | `day2_kuwana_shichiri.jpg` |
| 3 | 四日市市 | 鵜の森公園 | `day3_yokkaichi_unomori.jpg` |
| 4 | 四日市市 | 垂坂公園 | `day4_yokkaichi_tarusaka.jpg` |
| 5 | 四日市市 | 四日市市南部丘陵公園 | `day5_yokkaichi_nanbu.jpg` |
| 6 | 鈴鹿市 | 石垣池公園 | `day6_suzuka_ishigakiike.jpg` |
| 7 | 鈴鹿市 | 鈴鹿青少年の森 | `day7_suzuka_seishonen.jpg` |

| ファイル | 内容 |
|---|---|
| `content/rakuten_cycling/plan.json` | 7日分のタイトル・本文・ワンポイント・タグ・画像の背景シーン |
| `content/rakuten_cycling/images/` | 生成済みアイキャッチ画像 |
| `content/rakuten_cycling/posts/` | 本文 (メール用 `.txt` / エディタ貼り付け用 `.html`) |
| `content/rakuten_cycling/queue.json` | 予約キュー (2026-11-24 から毎日 09:00 で登録済み) |

```bash
# ① 楽天ブログの「メールで更新」機能を使うと no-reply@mail.plaza.rakuten.co.jp からメールが届く。
#    本文の「日記を更新する場合は XXXXX_XXX_XXXX@mb.plaza.rakuten.co.jp に…」のアドレスを .env に記入
#    Gmail で送る場合は 2 段階認証を有効にして「アプリパスワード」を SMTP_PASSWORD に
python -m rakuten_blog build                        # 画像と本文を作り直す (plan.json を編集したら)
python -m rakuten_blog post --day 1 --dry-run       # 送信内容を確認
python -m rakuten_blog post --day 1                 # 今すぐ 1 記事投稿 (まず 1 本で動作確認)
python -m rakuten_blog schedule --start 2026-12-01 --replace   # 開始日を変える
python -m rakuten_blog list                         # 予約一覧
python -m rakuten_blog run                          # 期限が来た予約を投稿 (1 回 1 件まで)
```

GitHub Actions で自動化する場合は Secrets に `RAKUTEN_POST_ADDRESS` / `SMTP_USER` / `SMTP_PASSWORD` を登録します。
`.github/workflows/rakuten-autopost.yml` が毎時 5 分にキューを確認して投稿し、結果を `queue.json` にコミットします
(Secrets 未設定のあいだは何もしません。スケジュール実行はデフォルトブランチにマージ後に有効になります)。

### 楽天アフィリエイト連携

`.env` (または GitHub Secrets) に `RAKUTEN_AFFILIATE_ID` を入れると、投稿時に各記事へ
「【今日のおやじの相棒アイテム（楽天市場）】」欄 (Day ごとに 2 商品) と、冒頭の【PR】表記が自動で入ります。

| 設定 | 記事に入るリンク |
|---|---|
| `RAKUTEN_AFFILIATE_ID` のみ | 楽天市場の検索結果ページ (例: 「自転車 ヘルメット 大人 軽量」) へのアフィリエイトリンク |
| + `RAKUTEN_APP_ID` | 楽天市場 商品検索 API でレビュー件数の多い商品を探し、商品名・価格・商品リンク (affiliateUrl) を表示 |
| 未設定 | アフィリエイト欄なし |

```bash
python -m rakuten_blog affiliate                 # 各 Day に入るリンクを確認
python -m rakuten_blog post --day 1 --dry-run    # アフィリエイト欄込みの本文を確認
```

- 商品はキーワード (`plan.json` の `affiliate`) で投稿時に検索するので、売り切れ商品が載りにくく、価格も投稿時点のものになります
- API が失敗しても検索結果ページへのリンクに切り替えて投稿を続けます
- アフィリエイトID は楽天アフィリエイトの「サイト設定」付近、アプリID は楽天ウェブサービスでアプリを登録すると発行されます
- ステマ規制 (景品表示法) 対応として【PR】表記を自動で入れています。消さないでください
- 商品は紹介であり、おべおやじが実際に使った感想ではありません。実際に使った物があれば `plan.json` の文面を体験に合わせて書き換えるとより伝わります

注意点:
- メール投稿の受付設定 (アドレス・送信元の登録・画像の扱い) は楽天ブログ側の仕様に従います。最初は `post --day 1` で 1 本だけ送り、
  タイトル・改行・画像が意図どおりか確認してから予約を有効にしてください
- 本文は公園紹介 + おやじの一言の構成で、走行距離などの数値や具体的な体験談は入れていません。実際に走ったら写真や感想を足すとより伝わります
- 公園内の自転車乗り入れ可否は現地の案内に従ってください (記事内でも押し歩きを推奨しています)

## 開発

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
