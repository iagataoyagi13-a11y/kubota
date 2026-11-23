"""楽天アフィリエイト連携.

1. 楽天市場 商品検索 API (applicationId + affiliateId) があれば、キーワードで商品を検索し
   API が返す affiliateUrl (アフィリエイト計測付き URL) を使う
2. API キーがない / API が失敗したときは、楽天市場の検索結果ページを
   アフィリエイトリンク (hb.afl.rakuten.co.jp) で包んだ URL にフォールバックする

どちらも affiliateId がない場合はリンクを出さない (広告表記も付けない)。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import quote

import requests

DEFAULT_ENDPOINT = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
SEARCH_URL = "https://search.rakuten.co.jp/search/mall/{kw}/"
AFL_URL = "https://hb.afl.rakuten.co.jp/hgc/{aid}/?pc={pc}&m={pc}"
PR_HEADER = "【PR】この記事には楽天アフィリエイトの広告リンクが含まれています。"


@dataclass(frozen=True)
class AffiliateConfig:
    affiliate_id: str = ""
    application_id: str = ""
    access_key: str = ""
    endpoint: str = DEFAULT_ENDPOINT

    @classmethod
    def from_env(cls) -> "AffiliateConfig":
        g = lambda k, d="": os.environ.get(k, d).strip()  # noqa: E731
        return cls(g("RAKUTEN_AFFILIATE_ID"), g("RAKUTEN_APP_ID"), g("RAKUTEN_ACCESS_KEY"),
                   g("RAKUTEN_ITEM_API", DEFAULT_ENDPOINT))

    @property
    def enabled(self) -> bool:
        return bool(self.affiliate_id)


@dataclass
class Item:
    label: str           # 記事内での見出し (例: ヘルメット)
    name: str            # 商品名 (検索リンクの場合は「楽天市場で『…』を探す」)
    url: str
    price: int | None = None
    image: str = ""
    shop: str = ""
    extra: dict = field(default_factory=dict)


def search_link(keyword: str, affiliate_id: str) -> str:
    """楽天市場の検索結果ページへのアフィリエイトリンク."""
    target = SEARCH_URL.format(kw=quote(keyword))
    return AFL_URL.format(aid=affiliate_id, pc=quote(target, safe=""))


def fetch_items(cfg: AffiliateConfig, keyword: str, hits: int = 1, session=requests) -> list[dict]:
    params = {
        "applicationId": cfg.application_id,
        "affiliateId": cfg.affiliate_id,
        "keyword": keyword,
        "hits": hits,
        "sort": "-reviewCount",
        "availability": 1,
        "imageFlag": 1,
        "format": "json",
        "formatVersion": 2,
    }
    if cfg.access_key:
        params["accessKey"] = cfg.access_key
    r = session.get(cfg.endpoint, params=params, timeout=20)
    r.raise_for_status()
    items = r.json().get("Items", [])
    return [it.get("Item", it) for it in items]  # formatVersion=1 互換


def _short(name: str, n: int = 60) -> str:
    name = " ".join(name.split())
    return name if len(name) <= n else name[: n - 1] + "…"


def resolve(cfg: AffiliateConfig, picks: list[dict], session=requests, log=print) -> list[Item]:
    """plan.json の affiliate 指定 [{label, keyword}] を記事に載せる商品リストに変換する."""
    if not cfg.enabled:
        return []
    out: list[Item] = []
    for pick in picks:
        kw, label = pick["keyword"], pick["label"]
        if cfg.application_id:
            try:
                found = fetch_items(cfg, kw, session=session)
                if found:
                    it = found[0]
                    imgs = it.get("mediumImageUrls") or []
                    img = imgs[0] if imgs else ""
                    img = img.get("imageUrl", "") if isinstance(img, dict) else img
                    out.append(Item(label, _short(it.get("itemName", kw)), it.get("affiliateUrl") or it["itemUrl"],
                                    it.get("itemPrice"), img, it.get("shopName", "")))
                    continue
            except Exception as exc:  # noqa: BLE001 - 失敗しても検索リンクで投稿を続ける
                log(f"楽天API エラー ({kw}): {type(exc).__name__}: {exc} → 検索リンクを使います")
        out.append(Item(label, f"楽天市場で「{kw}」を探す", search_link(kw, cfg.affiliate_id)))
    return out


def text_block(items: list[Item], intro: str = "") -> list[str]:
    if not items:
        return []
    lines = ["【今日のおやじの相棒アイテム（楽天市場）】"]
    if intro:
        lines.append(intro)
    for it in items:
        price = f"（{it.price:,}円）" if it.price else ""
        lines += [f"▼{it.label}：{it.name}{price}", it.url]
    return lines


def html_block(items: list[Item], intro: str = "") -> list[str]:
    import html as h
    if not items:
        return []
    parts = ["<h3>今日のおやじの相棒アイテム（楽天市場）</h3>"]
    if intro:
        parts.append(f"<p>{h.escape(intro)}</p>")
    for it in items:
        price = f"（{it.price:,}円）" if it.price else ""
        img = (f'<a href="{h.escape(it.url)}" target="_blank" rel="sponsored nofollow noopener">'
               f'<img src="{h.escape(it.image)}" alt="{h.escape(it.name)}" width="128"></a><br>') if it.image else ""
        parts.append(f'<p>{img}{h.escape(it.label)}：<a href="{h.escape(it.url)}" target="_blank" '
                     f'rel="sponsored nofollow noopener">{h.escape(it.name)}</a>{price}</p>')
    return parts
