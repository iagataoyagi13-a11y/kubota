"""撮影素材なしで投稿できる「モーショングラフィックス」シーンと BGM を生成する.

- 背景: Day ごとのテーマ色グラデーション (ゆっくり流れる) + 地名の大きな透かし文字
- 演出: 湯けむり (下から立ちのぼる粒子)・玉ボケ・温泉マーク / どんぶりのイラスト
- テロップ: 下からスライド + フェードイン、上部にストーリー風の進行バー
- BGM: numpy で合成したオリジナル曲 (著作権フリー)
"""

from __future__ import annotations

import math
import random
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30

DEFAULT_THEMES = [
    ("#3b6e8f", "#1a2e3d", "#f2c14e"),
    ("#8f3b3b", "#2d1616", "#ffd166"),
    ("#4a3b6e", "#191427", "#f6bd60"),
    ("#2f6b4f", "#122a1f", "#f4a261"),
    ("#8f6a3b", "#2e2112", "#ffe8a3"),
    ("#2f5f8f", "#0f2236", "#ff9f6b"),
    ("#5a6b3b", "#1d2412", "#f2d16b"),
]
FOOD_WORDS = ("料理", "めし", "汁", "牛", "豚", "とり天", "芋煮", "蒸し", "味噌", "しゃぶ")


def _rgb(hexstr: str) -> tuple[int, int, int]:
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def theme_for(day: dict) -> tuple[tuple[int, int, int], ...]:
    t = day.get("theme") or DEFAULT_THEMES[(day["day"] - 1) % len(DEFAULT_THEMES)]
    return tuple(_rgb(c) for c in t)


def icon_kind(scene: dict, idx: int, total: int) -> str:
    if idx == total:
        return "cta"
    text = scene.get("text", "") + scene.get("sub", "")
    return "food" if any(w in text for w in FOOD_WORDS) else "onsen"


# ------------------------------------------------------------ sprites
def _soft_circle(r: int, alpha: int, blur: float) -> Image.Image:
    pad = int(blur * 3)
    img = Image.new("RGBA", (2 * (r + pad),) * 2, (255, 255, 255, 0))
    ImageDraw.Draw(img).ellipse((pad, pad, pad + 2 * r, pad + 2 * r), fill=(255, 255, 255, alpha))
    return img.filter(ImageFilter.GaussianBlur(blur))


def _with_alpha(img: Image.Image, factor: float) -> Image.Image:
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda a: int(a * factor)))
    return out


def draw_icon(kind: str, accent: tuple[int, int, int]) -> Image.Image:
    s = 420
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 235)
    lw = 18
    if kind == "onsen":  # 温泉マーク: 湯船 + 3 本の湯けむり
        d.arc((60, 190, 360, 380), 200, 340, fill=white, width=lw)
        d.ellipse((95, 250, 325, 345), outline=white, width=lw)
        for x in (150, 210, 270):
            pts = [(x + 18 * math.sin(t / 6 * math.pi * 2), 230 - t * 26) for t in range(7)]
            d.line(pts, fill=accent + (255,), width=lw, joint="curve")
    elif kind == "food":  # どんぶり + 箸 + 湯気
        d.chord((70, 150, 350, 390), 0, 180, fill=white)
        d.rectangle((150, 380, 270, 400), fill=white)
        d.line((250, 60, 380, 230), fill=accent + (255,), width=14)
        d.line((280, 50, 400, 215), fill=accent + (255,), width=14)
        for x in (150, 210):
            pts = [(x + 14 * math.sin(t / 6 * math.pi * 2), 240 - t * 24) for t in range(6)]
            d.line(pts, fill=white, width=12, joint="curve")
    else:  # cta: ブックマーク + 上向き矢印
        d.polygon([(130, 80), (290, 80), (290, 360), (210, 300), (130, 360)], outline=white, width=lw)
        d.line((210, 250, 210, 150), fill=accent + (255,), width=lw)
        d.polygon([(170, 170), (210, 120), (250, 170)], fill=accent + (255,))
    return img


class SceneRenderer:
    """1 シーン分のフレームを生成して ffmpeg に流し込む."""

    def __init__(self, day: dict, scene: dict, idx: int, total: int,
                 telop: Image.Image, font_path: str, seed: int = 0):
        self.day, self.scene, self.idx, self.total = day, scene, idx, total
        self.dur = float(scene["dur"])
        top, bottom, accent = theme_for(day)
        self.accent = accent
        rnd = random.Random(seed * 100 + idx)

        # 背景グラデーション (縦に長く作ってスクロール)
        gh = H + 400
        grad = np.linspace(0, 1, gh)[:, None]
        hue_shift = 0.08 * (idx % 2)
        col = (np.array(top) * (1 - grad) + np.array(bottom) * grad) * (1 - hue_shift) \
            + np.array(accent) * hue_shift * (1 - grad)
        self.bg = Image.fromarray(np.repeat(col[:, None, :], W, axis=1).astype(np.uint8), "RGB")

        # 地名の透かし文字
        kanji = day.get("kanji") or day.get("onsen", "")[:2]
        self.water = Image.new("RGBA", (W, 700), (0, 0, 0, 0))
        f = ImageFont.truetype(font_path, 380 if len(kanji) <= 2 else 260)
        dw = ImageDraw.Draw(self.water)
        tw = dw.textlength(kanji, font=f)
        dw.text(((W - tw) / 2, 120), kanji, font=f, fill=(255, 255, 255, 26))

        self.icon = draw_icon(icon_kind(scene, idx, total), accent)
        self.bokeh = [dict(spr=_soft_circle(rnd.randint(30, 110), rnd.randint(25, 60), rnd.uniform(6, 14)),
                           x=rnd.uniform(0, W), y=rnd.uniform(0, H), vy=rnd.uniform(-30, -10),
                           ph=rnd.uniform(0, 6.28)) for _ in range(12)]
        base_steam = _soft_circle(70, 60, 24)
        self.steam_levels = [_with_alpha(base_steam, a) for a in (1.0, 0.75, 0.5, 0.3, 0.15)]
        self.steam = [dict(x=rnd.uniform(80, W - 80), t0=rnd.uniform(0, 3.0), life=rnd.uniform(2.5, 4.0),
                           drift=rnd.uniform(-40, 40)) for _ in range(14)]

        # テロップは不透明部分だけ切り出して高速に合成
        bbox = telop.getbbox() or (0, 0, 1, 1)
        self.telop_full = telop
        self.label_box = (0, 0, W, 330)  # 上部ラベル領域
        self.main_bbox = (0, 330, W, max(bbox[3], 331))
        self.label = telop.crop(self.label_box)
        self.main = telop.crop(self.main_bbox)

    def frame(self, t: float) -> Image.Image:
        off = int(200 + 200 * math.sin(t * 0.6 + self.idx))
        img = self.bg.crop((0, off, W, off + H))
        img.paste(self.water, (int(12 * math.sin(t * 0.8)), 380), self.water)

        for b in self.bokeh:
            y = (b["y"] + b["vy"] * t) % (H + 200) - 100
            x = b["x"] + 20 * math.sin(t * 0.7 + b["ph"])
            spr = b["spr"]
            img.paste(spr, (int(x - spr.width / 2), int(y - spr.height / 2)), spr)

        for s in self.steam:  # 湯けむり: 下から上へ、だんだん薄く
            age = (t + s["t0"]) % s["life"]
            p = age / s["life"]
            spr = self.steam_levels[min(4, int(p * 5))]
            x = s["x"] + s["drift"] * p + 25 * math.sin(age * 2)
            y = H - 120 - p * 900
            img.paste(spr, (int(x - spr.width / 2), int(y - spr.height / 2)), spr)

        # アイコン: ポップイン + ふわふわ
        pop = min(1.0, t / 0.35)
        scale = 0.6 + 0.4 * (1 - (1 - pop) ** 3)
        icon = self.icon if scale >= 0.999 else self.icon.resize(
            (int(self.icon.width * scale),) * 2, Image.BILINEAR)
        bob = 14 * math.sin(t * 2.2)
        img.paste(icon, (int((W - icon.width) / 2), int(760 - icon.height / 2 + bob)), icon)

        img.paste(self.label, (0, 0), self.label)
        # メインテロップ: 0.4 秒でスライドイン + フェード
        k = min(1.0, max(0.0, (t - 0.1) / 0.4))
        ease = 1 - (1 - k) ** 3
        if ease > 0:
            layer = self.main if ease >= 0.999 else _with_alpha(self.main, ease)
            img.paste(layer, (0, self.main_bbox[1] + int(60 * (1 - ease))), layer)

        self._progress(img, t)
        return img

    def _progress(self, img: Image.Image, t: float) -> None:
        """ストーリー風の進行バー (半透明の下地 + 白い進行分)."""
        strip = Image.new("RGBA", (W, 30), (0, 0, 0, 0))
        d = ImageDraw.Draw(strip)
        gap, x0, x1, y = 10, 60, W - 60, 10
        seg = (x1 - x0 - gap * (self.total - 1)) / self.total
        for i in range(1, self.total + 1):
            sx = x0 + (i - 1) * (seg + gap)
            d.rounded_rectangle((sx, y, sx + seg, y + 8), radius=4, fill=(255, 255, 255, 70))
            fill = 1.0 if i < self.idx else (min(1.0, t / self.dur) if i == self.idx else 0)
            if fill:
                d.rounded_rectangle((sx, y, sx + max(8, seg * fill), y + 8), radius=4,
                                    fill=(255, 255, 255, 255))
        img.paste(strip, (0, 110), strip)

    def write(self, out: str) -> None:
        n = int(round(self.dur * FPS))
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
               "-f", "lavfi", "-t", f"{self.dur}", "-i", "anullsrc=r=44100:cl=stereo",
               "-map", "0:v", "-map", "1:a", "-t", f"{self.dur}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", out]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdin is not None
        try:
            for i in range(n):
                proc.stdin.write(self.frame(i / FPS).tobytes())
        finally:
            proc.stdin.close()
            err = proc.stderr.read().decode() if proc.stderr else ""
            if proc.wait():
                raise RuntimeError(f"ffmpeg エラー: {err[-1500:]}")


# ------------------------------------------------------------------ BGM
def make_bgm(path: str, seconds: float, seed: int = 0, sr: int = 44100) -> str:
    """ゆったりした和風ペンタトニックの BGM を合成して WAV で保存."""
    rnd = np.random.default_rng(seed)
    n = int(seconds * sr)
    t = np.arange(n) / sr
    root = 220.0 * 2 ** (int(rnd.integers(-3, 4)) / 12)
    ratio = lambda semi: 2 ** (semi / 12)  # noqa: E731
    # I - vi - IV - V 相当 (各和音 = 2小節 80BPM)
    progression = [(0, 4, 7), (-3, 0, 4), (-7, -3, 0), (-5, -1, 2)]
    bar = 60 / 80 * 4
    out = np.zeros((n, 2))

    # パッド (柔らかい和音)
    for ci in range(int(seconds / bar) + 1):
        chord = progression[ci % len(progression)]
        s0, s1 = int(ci * bar * sr), min(n, int((ci + 1) * bar * sr + 0.5 * sr))
        if s0 >= n:
            break
        tt = t[s0:s1] - t[s0]
        env = np.minimum(1, tt / 0.6) * np.minimum(1, (tt[-1] - tt + 1e-3) / 0.6)
        for semi in chord:
            f = root * ratio(semi)
            for det, pan in ((0.998, 0.3), (1.002, 0.7)):
                wv = np.sin(2 * np.pi * f * det * tt) * 0.5 + np.sin(4 * np.pi * f * det * tt) * 0.12
                out[s0:s1, 0] += wv * env * 0.035 * (1 - pan)
                out[s0:s1, 1] += wv * env * 0.035 * pan

    # 琴風のアルペジオ (ペンタトニック)
    scale = [0, 2, 4, 7, 9, 12, 14, 16]
    step = 60 / 80 / 2
    for k in range(int(seconds / step)):
        if rnd.random() < 0.3:
            continue
        s0 = int(k * step * sr)
        length = min(n - s0, int(1.6 * sr))
        if length <= 0:
            break
        tt = np.arange(length) / sr
        f = root * 2 * ratio(int(rnd.choice(scale)))
        tone = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)
                + 0.1 * np.sin(6 * np.pi * f * tt)) * np.exp(-tt * 3.2)
        pan = float(rnd.uniform(0.25, 0.75))
        out[s0:s0 + length, 0] += tone * 0.06 * (1 - pan)
        out[s0:s0 + length, 1] += tone * 0.06 * pan

    fade = int(1.5 * sr)
    out[:int(0.8 * sr)] *= np.linspace(0, 1, int(0.8 * sr))[:, None]
    out[-fade:] *= np.linspace(1, 0, fade)[:, None]
    out *= 0.35 / max(1e-6, np.abs(out).max())
    pcm = (out * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path
