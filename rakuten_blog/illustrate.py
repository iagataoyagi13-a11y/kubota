"""62歳ヒゲおやじが公園をサイクリングするイラストを Pillow だけで描く.

写真素材なしで記事のアイキャッチ画像 (1200x800 JPEG) を作ります。
- 背景: 公園ごとのシーン (城跡・鳥居・街なか・桜の丘・丘陵・池・森)
- 主役: 白ヒゲ・丸メガネ・ヘルメット姿の 62 歳サイクリスト (背番号 62)
- 文字: Day 番号バッジ + 市名・公園名 + シリーズ名
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1200, 800
GROUND_Y = 600  # 道路の上端

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
]

SKIN = (241, 194, 160)
BEARD = (228, 228, 224)
BEARD_SHADE = (190, 190, 186)
DARK = (40, 40, 48)


def font(size: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def rgb(hexstr: str) -> tuple[int, int, int]:
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def mix(a, b, t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


# ------------------------------------------------------------------ 背景
def sky(img: Image.Image, top, bottom) -> None:
    d = ImageDraw.Draw(img)
    for y in range(GROUND_Y):
        d.line((0, y, W, y), fill=mix(top, bottom, y / GROUND_Y))


def clouds(img: Image.Image, rnd: random.Random, n: int = 4) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(n):
        cx, cy = rnd.randint(60, W - 60), rnd.randint(40, 220)
        for _ in range(5):
            r = rnd.randint(28, 55)
            ox, oy = rnd.randint(-70, 70), rnd.randint(-15, 15)
            d.ellipse((cx + ox - r, cy + oy - r * 0.7, cx + ox + r, cy + oy + r * 0.7), fill=(255, 255, 255, 215))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(2)))


def tree(d: ImageDraw.ImageDraw, x: int, base: int, h: int, color, trunk=(110, 78, 52)) -> None:
    d.rectangle((x - h // 18, base - h // 3, x + h // 18, base), fill=trunk)
    r = h // 3
    for ox, oy, k in ((0, -h * 0.62, 1.0), (-r * 0.6, -h * 0.45, 0.8), (r * 0.6, -h * 0.45, 0.8)):
        rr = r * k
        d.ellipse((x + ox - rr, base + oy - rr, x + ox + rr, base + oy + rr), fill=color)


def pine(d: ImageDraw.ImageDraw, x: int, base: int, h: int) -> None:
    d.line((x, base, x + h * 0.1, base - h * 0.7), fill=(100, 70, 50), width=max(4, h // 14))
    for i, k in enumerate((0.9, 0.7, 0.5)):
        y = base - h * (0.35 + i * 0.22)
        w = h * 0.45 * k
        d.ellipse((x - w + i * 6, y - h * 0.09, x + w + i * 6, y + h * 0.09), fill=(46, 102, 62))


def sakura(d: ImageDraw.ImageDraw, x: int, base: int, h: int, rnd: random.Random) -> None:
    d.line((x, base, x - h * 0.05, base - h * 0.55), fill=(95, 65, 55), width=max(5, h // 12))
    for _ in range(14):
        ox, oy = rnd.uniform(-h * 0.4, h * 0.4), rnd.uniform(-h * 0.95, -h * 0.45)
        r = rnd.uniform(h * 0.12, h * 0.2)
        col = rnd.choice([(250, 200, 214), (246, 182, 200), (255, 220, 230)])
        d.ellipse((x + ox - r, base + oy - r, x + ox + r, base + oy + r), fill=col)


def water(d: ImageDraw.ImageDraw, y0: int, y1: int, top, bottom, rnd: random.Random) -> None:
    for y in range(y0, y1):
        d.line((0, y, W, y), fill=mix(top, bottom, (y - y0) / max(1, y1 - y0)))
    for _ in range(26):
        x, y = rnd.randint(0, W), rnd.randint(y0 + 6, y1 - 4)
        ln = rnd.randint(30, 90)
        d.line((x, y, x + ln, y), fill=mix(top, (255, 255, 255), 0.55), width=2)


def scene_castle(img, d, rnd):  # 九華公園: お堀・石垣・松・櫓
    water(d, 470, GROUND_Y, (88, 140, 170), (60, 105, 135), rnd)
    d.polygon([(120, 470), (700, 470), (660, 330), (160, 330)], fill=(150, 146, 136))
    for row, y in enumerate(range(330, 470, 22)):
        off = 0 if row % 2 else 30
        for x in range(130 + off, 700, 60):
            d.rectangle((x, y, x + 56, y + 19), outline=(120, 116, 108), width=2)
    d.rectangle((300, 250, 520, 330), fill=(245, 242, 232))
    d.polygon([(270, 255), (550, 255), (500, 205), (320, 205)], fill=(70, 74, 84))
    d.rectangle((345, 175, 475, 210), fill=(245, 242, 232))
    d.polygon([(320, 180), (500, 180), (460, 140), (360, 140)], fill=(70, 74, 84))
    for x in (330, 400, 470):
        d.rectangle((x, 275, x + 26, 300), fill=(70, 74, 84))
    for x, h in ((780, 230), (900, 280), (1040, 250), (60, 200)):
        pine(d, x, 470, h)


def scene_torii(img, d, rnd):  # 七里の渡し: 揖斐川と大鳥居
    water(d, 400, GROUND_Y, (110, 160, 190), (70, 120, 160), rnd)
    d.rectangle((0, 385, W, 400), fill=(120, 150, 100))
    wood, beam = (125, 100, 80), (95, 75, 60)
    x0, x1, top = 640, 1000, 150
    for x in (x0 + 40, x1 - 40):
        d.polygon([(x - 18, 560), (x + 18, 560), (x + 12, top + 40), (x - 12, top + 40)], fill=wood)
    d.polygon([(x0 - 40, top), (x1 + 40, top), (x1 + 20, top + 30), (x0 - 20, top + 30)], fill=beam)
    d.rectangle((x0 + 10, top + 70, x1 - 10, top + 90), fill=wood)
    d.rectangle(((x0 + x1) // 2 - 10, top + 30, (x0 + x1) // 2 + 10, top + 70), fill=wood)
    d.rectangle((560, 560, 1080, 600), fill=(170, 160, 140))
    for x, y in ((150, 470), (300, 520)):  # 小舟
        d.polygon([(x, y), (x + 120, y), (x + 100, y + 18), (x + 20, y + 18)], fill=(90, 70, 55))


def scene_stonewall(img, d, rnd):  # 鵜の森公園: ビルの谷間の森と池
    for x in range(0, W, 110):
        h = rnd.randint(140, 300)
        d.rectangle((x, GROUND_Y - 120 - h, x + 95, GROUND_Y - 120), fill=(170, 180, 195))
        for wy in range(GROUND_Y - 110 - h, GROUND_Y - 130, 30):
            for wx in range(x + 12, x + 85, 24):
                d.rectangle((wx, wy, wx + 12, wy + 16), fill=(205, 215, 228))
    d.ellipse((650, 500, 1150, 590), fill=(90, 150, 165))
    for x in range(40, W, 120):
        tree(d, x + rnd.randint(-20, 20), GROUND_Y - 20, rnd.randint(220, 300), rnd.choice([(58, 128, 72), (72, 140, 80), (48, 112, 64)]))


def scene_sakura(img, d, rnd):  # 垂坂公園: 桜の丘
    d.polygon([(0, GROUND_Y), (0, 420), (350, 300), (700, 340), (1200, 460), (W, GROUND_Y)], fill=(126, 178, 96))
    d.line([(1150, GROUND_Y), (900, 470), (620, 380), (420, 330)], fill=(225, 210, 180), width=26)
    for x, base, h in ((150, 420, 230), (380, 330, 200), (560, 360, 190), (820, 430, 240), (1060, 500, 230)):
        sakura(d, x, base, h, rnd)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for _ in range(70):
        x, y = rnd.randint(0, W), rnd.randint(0, H - 40)
        ld.ellipse((x, y, x + 9, y + 6), fill=(255, 190, 210, 200))
    img.alpha_composite(layer)


def scene_hills(img, d, rnd):  # 南部丘陵公園: 起伏のある芝生と遊具
    d.polygon([(0, 430), (300, 330), (650, 410), (950, 320), (W, 380), (W, GROUND_Y), (0, GROUND_Y)], fill=(150, 196, 110))
    d.polygon([(0, 500), (400, 430), (800, 490), (W, 440), (W, GROUND_Y), (0, GROUND_Y)], fill=(112, 170, 86))
    d.line((880, 380, 960, 300), fill=(220, 80, 70), width=10)  # すべり台
    d.line((960, 300, 1050, 430), fill=(240, 190, 60), width=14)
    d.rectangle((930, 290, 975, 305), fill=(220, 80, 70))
    for x, h in ((120, 210), (520, 180), (720, 200)):
        tree(d, x, 470, h, (66, 132, 70))


def scene_pond(img, d, rnd):  # 石垣池公園: 大きな池と水面の映り込み
    for x in range(-40, W, 140):
        tree(d, x + rnd.randint(-15, 15), 420, rnd.randint(170, 230), rnd.choice([(60, 130, 74), (78, 146, 84)]))
    water(d, 420, GROUND_Y, (120, 175, 205), (80, 135, 175), rnd)
    d.rectangle((420, 470, 760, 482), fill=(160, 120, 90))  # 桟橋
    for x in range(430, 760, 50):
        d.line((x, 482, x, 520), fill=(130, 95, 70), width=6)


def scene_forest(img, d, rnd):  # 鈴鹿青少年の森: 木漏れ日の森
    for layer_i, (col, hmin, hmax) in enumerate((((96, 150, 100), 0, 40), ((60, 120, 70), 20, 60), ((36, 92, 52), 40, 80))):
        for x in range(-30 + layer_i * 40, W + 40, 95 - layer_i * 10):
            tree(d, x + rnd.randint(-20, 20), GROUND_Y - 10 + layer_i * 6, rnd.randint(hmin + 150, hmax + 220),
                 mix(col, (255, 255, 255), rnd.uniform(0, 0.08)), trunk=(90, 64, 44))
    d.rectangle((0, GROUND_Y - 40, W, GROUND_Y), fill=(88, 140, 80))
    rays = Image.new("RGBA", img.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    for x in (250, 520, 830):
        rd.polygon([(x, 0), (x + 70, 0), (x + 260, GROUND_Y), (x + 120, GROUND_Y)], fill=(255, 250, 210, 60))
    img.alpha_composite(rays.filter(ImageFilter.GaussianBlur(12)))


SCENES = {
    "castle": (scene_castle, ((120, 180, 230), (220, 236, 248))),
    "torii": (scene_torii, ((250, 190, 130), (255, 236, 200))),
    "stonewall": (scene_stonewall, ((140, 196, 236), (226, 240, 250))),
    "sakura": (scene_sakura, ((170, 210, 245), (250, 236, 244))),
    "hills": (scene_hills, ((110, 175, 235), (215, 236, 252))),
    "pond": (scene_pond, ((150, 200, 240), (236, 246, 252))),
    "forest": (scene_forest, ((200, 230, 200), (240, 248, 230))),
}


def road(d: ImageDraw.ImageDraw) -> None:
    d.rectangle((0, GROUND_Y, W, H), fill=(196, 182, 160))
    d.rectangle((0, GROUND_Y, W, GROUND_Y + 10), fill=(110, 160, 80))
    for x in range(0, W, 120):
        d.rectangle((x, 690, x + 60, 698), fill=(240, 236, 226))


# ------------------------------------------------------------------ ヒゲおやじ
def _knee(hip, foot, l1: float, l2: float) -> tuple[float, float]:
    """2 リンク IK: 腰と足先から膝の位置を求める (膝は前方へ曲がる)."""
    dx, dy = foot[0] - hip[0], foot[1] - hip[1]
    dist = min(math.hypot(dx, dy), l1 + l2 - 1e-3)
    a = math.acos((l1 ** 2 + dist ** 2 - l2 ** 2) / (2 * l1 * dist))
    base = math.atan2(dy, dx)
    ang = base - a  # 画面座標 (y 下向き) で前方 = 反時計回り
    return hip[0] + l1 * math.cos(ang), hip[1] + l1 * math.sin(ang)


def wheel(d: ImageDraw.ImageDraw, c, r: int) -> None:
    d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=DARK, width=12)
    d.ellipse((c[0] - r + 9, c[1] - r + 9, c[0] + r - 9, c[1] + r - 9), outline=(150, 150, 150), width=2)
    for k in range(12):
        a = k * math.pi / 6
        d.line((c[0], c[1], c[0] + (r - 10) * math.cos(a), c[1] + (r - 10) * math.sin(a)), fill=(170, 170, 170), width=2)
    d.ellipse((c[0] - 8, c[1] - 8, c[0] + 8, c[1] + 8), fill=(120, 120, 120))


def hige_oyaji(img: Image.Image, x0: int, y0: int, jersey, crank_deg: float = 30) -> None:
    """後輪の中心 (x0, y0) を基準に、右向きに走るヒゲおやじと自転車を描く."""
    # 影
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((x0 - 120, y0 + 85, x0 + 430, y0 + 115), fill=(0, 0, 0, 70))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    # スピード線
    d = ImageDraw.Draw(img)
    for i, y in enumerate((y0 - 260, y0 - 180, y0 - 60, y0 + 20)):
        d.line((x0 - 300 + i * 25, y, x0 - 140 + i * 15, y), fill=(255, 255, 255), width=5)

    R = 100
    rear, front = (x0, y0), (x0 + 310, y0)
    bb = (x0 + 130, y0 - 5)
    seat = (x0 + 100, y0 - 165)
    head_top, head_bot = (x0 + 262, y0 - 175), (x0 + 272, y0 - 130)
    frame_col = (30, 110, 180)

    # 奥側の脚 (ペダル反対側, 少し暗め)
    hip = (x0 + 105, y0 - 210)
    pants = (50, 54, 70)
    for k, col in ((1, mix(pants, (0, 0, 0), 0.35)), (0, pants)):
        a = math.radians(crank_deg + 180 * k)
        foot = (bb[0] + 42 * math.cos(a), bb[1] + 42 * math.sin(a))
        knee = _knee(hip, foot, 120, 118)
        if k == 1:
            d.line([hip, knee, foot], fill=col, width=30, joint="curve")
            d.ellipse((foot[0] - 22, foot[1] - 12, foot[0] + 26, foot[1] + 12), fill=DARK)
        else:
            near = (hip, knee, foot)

    wheel(d, rear, R)
    wheel(d, front, R)
    for a, b in ((rear, bb), (rear, seat), (bb, seat), (seat, head_top), (bb, head_bot), (head_bot, front)):
        d.line((a, b), fill=frame_col, width=14)
    d.line((head_bot, head_top), fill=frame_col, width=18)
    d.ellipse((bb[0] - 22, bb[1] - 22, bb[0] + 22, bb[1] + 22), outline=DARK, width=6)  # チェーンリング
    d.line((seat[0] - 5, seat[1], seat[0] - 10, seat[1] - 30), fill=DARK, width=10)  # シートポスト
    d.polygon([(seat[0] - 55, seat[1] - 38), (seat[0] + 30, seat[1] - 40), (seat[0] + 20, seat[1] - 26), (seat[0] - 50, seat[1] - 24)], fill=DARK)
    stem = (head_top[0] + 8, head_top[1] - 20)
    d.line((head_top, stem, (stem[0] + 40, stem[1] - 2)), fill=DARK, width=10)
    d.arc((stem[0] + 15, stem[1] - 2, stem[0] + 75, stem[1] + 60), 270, 120, fill=DARK, width=10)  # ドロップハンドル

    # 胴体 (ジャージ)
    shoulder = (x0 + 215, y0 - 315)
    d.line((hip, shoulder), fill=jersey, width=72)
    d.ellipse((hip[0] - 30, hip[1] - 30, hip[0] + 30, hip[1] + 30), fill=pants)
    d.ellipse((shoulder[0] - 36, shoulder[1] - 36, shoulder[0] + 36, shoulder[1] + 36), fill=jersey)
    num_f = font(34)
    mid = ((hip[0] + shoulder[0]) / 2 - 8, (hip[1] + shoulder[1]) / 2)
    d.text(mid, "62", font=num_f, fill=(255, 255, 255), anchor="mm", stroke_width=2, stroke_fill=mix(jersey, (0, 0, 0), 0.4))

    # 手前の脚
    hip_n, knee_n, foot_n = near
    d.line([hip_n, knee_n], fill=pants, width=34, joint="curve")
    d.line([knee_n, foot_n], fill=SKIN, width=26)  # ふくらはぎ (ハーフパンツ)
    d.ellipse((knee_n[0] - 17, knee_n[1] - 17, knee_n[0] + 17, knee_n[1] + 17), fill=pants)
    d.ellipse((foot_n[0] - 24, foot_n[1] - 13, foot_n[0] + 30, foot_n[1] + 13), fill=(240, 240, 240), outline=DARK, width=3)
    d.line((bb, foot_n), fill=(90, 90, 90), width=8)  # クランク

    # 腕
    hand = (stem[0] + 55, stem[1] + 8)
    elbow = (x0 + 268, y0 - 245)
    d.line([shoulder, elbow], fill=jersey, width=30)
    d.line([elbow, hand], fill=SKIN, width=24)
    d.ellipse((hand[0] - 16, hand[1] - 14, hand[0] + 16, hand[1] + 14), fill=(60, 60, 70))  # グローブ

    # 頭
    hc, hr = (x0 + 250, y0 - 375), 46
    d.ellipse((hc[0] - hr, hc[1] - hr, hc[0] + hr, hc[1] + hr), fill=SKIN)
    d.ellipse((hc[0] - 22, hc[1] - 6, hc[0] - 2, hc[1] + 20), fill=mix(SKIN, (0, 0, 0), 0.12))  # 耳
    d.arc((hc[0] - 20, hc[1] - 3, hc[0] - 4, hc[1] + 17), 90, 270, fill=mix(SKIN, (0, 0, 0), 0.3), width=2)
    # 白髪のもみあげ・後頭部
    d.chord((hc[0] - hr, hc[1] - 20, hc[0] - 8, hc[1] + 36), 90, 270, fill=BEARD)
    # たっぷりの白ヒゲ (あご〜頬)
    beard = [(hc[0] - 6, hc[1] + 2), (hc[0] + 30, hc[1] + 10), (hc[0] + 50, hc[1] + 18), (hc[0] + 46, hc[1] + 48),
             (hc[0] + 26, hc[1] + 78), (hc[0] + 2, hc[1] + 82), (hc[0] - 16, hc[1] + 56), (hc[0] - 14, hc[1] + 20)]
    d.polygon(beard, fill=BEARD)
    for k in range(6):  # ヒゲの毛並み
        bx = hc[0] - 6 + k * 9
        d.line((bx, hc[1] + 40, bx + 4, hc[1] + 70), fill=BEARD_SHADE, width=2)
    d.ellipse((hc[0] + 20, hc[1] + 6, hc[0] + 58, hc[1] + 24), fill=BEARD)  # 口ひげ
    d.line((hc[0] + 32, hc[1] + 28, hc[0] + 46, hc[1] + 28), fill=(170, 90, 80), width=3)  # 口
    d.ellipse((hc[0] + 38, hc[1] - 14, hc[0] + 56, hc[1] + 6), fill=mix(SKIN, (200, 100, 80), 0.25))  # 鼻
    # 丸メガネと目
    d.ellipse((hc[0] + 16, hc[1] - 26, hc[0] + 42, hc[1]), outline=DARK, width=4)
    d.line((hc[0] + 42, hc[1] - 14, hc[0] + 52, hc[1] - 16), fill=DARK, width=3)
    d.line((hc[0] - 6, hc[1] - 12, hc[0] + 16, hc[1] - 14), fill=DARK, width=3)
    d.ellipse((hc[0] + 27, hc[1] - 16, hc[0] + 33, hc[1] - 9), fill=DARK)
    d.arc((hc[0] + 20, hc[1] - 36, hc[0] + 44, hc[1] - 22), 200, 340, fill=BEARD_SHADE, width=4)  # 白い眉
    d.line((hc[0] + 4, hc[1] - 30, hc[0] + 14, hc[1] - 33), fill=mix(SKIN, (0, 0, 0), 0.25), width=2)  # しわ
    # ヘルメット
    d.chord((hc[0] - hr - 6, hc[1] - hr - 14, hc[0] + hr + 10, hc[1] + 22), 180, 360, fill=(250, 250, 250))
    d.chord((hc[0] - hr - 6, hc[1] - hr - 14, hc[0] + hr + 10, hc[1] + 22), 200, 300, fill=jersey)
    for k in range(3):
        vx = hc[0] - 22 + k * 22
        d.line((vx, hc[1] - 48, vx + 8, hc[1] - 30), fill=(150, 150, 150), width=4)
    d.polygon([(hc[0] + 40, hc[1] - 22), (hc[0] + 64, hc[1] - 26), (hc[0] + 60, hc[1] - 16)], fill=(250, 250, 250))  # ひさし
    d.line((hc[0] - 8, hc[1] - 18, hc[0] + 6, hc[1] + 36), fill=DARK, width=3)  # あご紐


# ------------------------------------------------------------------ 文字
def rounded_label(img: Image.Image, box, fill, radius: int = 18) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=radius, fill=fill)
    img.alpha_composite(layer)


def captions(img: Image.Image, day: dict, series: str, accent) -> None:
    rounded_label(img, (30, 28, 230, 108), accent + (240,))
    d = ImageDraw.Draw(img)
    d.text((130, 68), f"Day{day['day']}", font=font(52), fill=(255, 255, 255), anchor="mm")
    rounded_label(img, (0, 708, W, H), (20, 24, 32, 200), radius=0)
    d = ImageDraw.Draw(img)
    d.text((40, 754), place_label(day), font=font(50), fill=(255, 255, 255), anchor="lm")
    d.text((W - 36, 754), series, font=font(26), fill=(235, 225, 190), anchor="rm")


def place_label(day: dict) -> str:
    """「四日市市・四日市市南部丘陵公園」のような重複を避ける."""
    park = day["park"]
    return park if park.startswith(day["city"]) else f"{day['city']}・{park}"


def render_day(day: dict, series: str, out: Path) -> Path:
    rnd = random.Random(day["day"] * 1009)
    draw_scene, (top, bottom) = SCENES[day["scene"]]
    img = Image.new("RGBA", (W, H))
    sky(img, top, bottom)
    clouds(img, rnd)
    d = ImageDraw.Draw(img)
    draw_scene(img, d, rnd)
    road(ImageDraw.Draw(img))
    jersey = rgb(day["jersey"])
    hige_oyaji(img, 430, 588, jersey, crank_deg=20 + day["day"] * 47)
    captions(img, day, series, jersey)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "JPEG", quality=90, optimize=True)
    return out
