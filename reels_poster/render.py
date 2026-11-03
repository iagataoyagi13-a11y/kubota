"""計画 (scenes) と撮影素材から 1080x1920 のリール動画を生成する.

素材の置き場所:  media/day{N}/{シーン番号}.{mp4|mov|jpg|jpeg|png}   (シーン番号は 1 始まり)
BGM (任意):      media/day{N}/bgm.{mp3|m4a|wav}  または  media/bgm.{mp3|m4a|wav}

- 本番 (final):   全シーンの素材が必要。出力 → videos/day{N}_{slug}.mp4
- 下書き (draft): 素材が無いシーンは「撮影指示カード」で代用。出力 → build/drafts/
                  テロップの位置・尺を確認するためのプレビュー (投稿用ではない)
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
VIDEO_EXT = (".mp4", ".mov", ".m4v")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")
AUDIO_EXT = (".mp3", ".m4a", ".aac", ".wav")

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
    "C:/Windows/Fonts/YuGothB.ttc",
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
]


class RenderError(RuntimeError):
    pass


def find_font() -> str:
    env = os.environ.get("REELS_FONT")
    if env and os.path.exists(env):
        return env
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    if shutil.which("fc-list"):
        out = subprocess.run(["fc-list", ":lang=ja", "file"], capture_output=True, text=True).stdout
        files = [line.split(":")[0].strip() for line in out.splitlines() if line.strip()]
        if files:
            return sorted(files, key=lambda p: ("Bold" not in p, p))[0]
    raise RenderError("日本語フォントが見つかりません (REELS_FONT でパスを指定してください)")


# ----------------------------------------------------------------- telop
def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        line = ""
        for ch in para:
            if draw.textlength(line + ch, font=font) > max_w and line:
                if " " in line.strip():  # 空白があればそこで改行 (1 文字だけ残るのを防ぐ)
                    head, tail = line.rstrip().rsplit(" ", 1)
                    lines.append(head)
                    line = tail + ch
                else:
                    lines.append(line)
                    line = ch
            else:
                line += ch
        lines.append(line)
    return lines


def draw_telop(text: str, sub: str, label: str, font_path: str) -> Image.Image:
    """透過 PNG のテロップ. Reels の UI (下部キャプション・右側アイコン) を避けて配置."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if label:  # 上部の小ラベル (例: Day1 群馬・草津温泉)
        f = ImageFont.truetype(font_path, 44)
        tw = d.textlength(label, font=f)
        x, y = (W - tw) / 2, 230
        d.rounded_rectangle((x - 28, y - 14, x + tw + 28, y + 62), radius=38, fill=(0, 0, 0, 140))
        d.text((x, y), label, font=f, fill="white")

    main_font = ImageFont.truetype(font_path, 86)
    sub_font = ImageFont.truetype(font_path, 46)
    max_w = W - 220  # 右側アイコン領域の分を広めに余白
    main_lines = _wrap(d, text, main_font, max_w) if text else []
    sub_lines = _wrap(d, sub, sub_font, max_w) if sub else []
    line_h, sub_h = 110, 64
    block_h = len(main_lines) * line_h + (len(sub_lines) * sub_h + 20 if sub_lines else 0)
    y = 1180 - block_h / 2  # 画面の中央やや下 (下 20% は UI に隠れる)

    for line in main_lines:
        tw = d.textlength(line, font=main_font)
        d.text(((W - tw) / 2, y), line, font=main_font, fill="white",
               stroke_width=8, stroke_fill=(20, 20, 20))
        y += line_h
    if sub_lines:
        y += 20
        for line in sub_lines:
            tw = d.textlength(line, font=sub_font)
            d.rounded_rectangle(((W - tw) / 2 - 22, y - 6, (W + tw) / 2 + 22, y + 58),
                                radius=12, fill=(200, 60, 40, 220))
            d.text(((W - tw) / 2, y), line, font=sub_font, fill="white")
            y += sub_h
    return img


def draft_card(day: int, idx: int, shot: str, font_path: str) -> Image.Image:
    """素材が無いシーンの代わりに使う「撮影指示カード」."""
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    top, bottom = (38, 70, 92), (16, 28, 40)
    for yy in range(H):
        t = yy / H
        d.line([(0, yy), (W, yy)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    f = ImageFont.truetype(font_path, 40)
    d.text((80, 420), f"DRAFT  Day{day} / シーン{idx}", font=f, fill=(255, 210, 120))
    d.text((80, 480), f"素材: media/day{day}/{idx}.mp4 (または .jpg)", font=f, fill=(180, 200, 210))
    fy = 560
    for line in _wrap(d, "撮影: " + shot, f, W - 160):
        d.text((80, fy), line, font=f, fill=(230, 235, 240))
        fy += 56
    return img


# ----------------------------------------------------------------- media
def find_scene_media(media_dir: str, idx: int) -> str | None:
    for ext in VIDEO_EXT + IMAGE_EXT:
        for cand in (f"{idx}{ext}", f"{idx}{ext.upper()}"):
            p = os.path.join(media_dir, cand)
            if os.path.exists(p):
                return p
    return None


def find_bgm(media_dir: str) -> str | None:
    for base in (media_dir, os.path.dirname(media_dir.rstrip("/"))):
        for ext in AUDIO_EXT:
            hits = glob.glob(os.path.join(base, f"bgm{ext}"))
            if hits:
                return hits[0]
    return None


def _has_audio(path: str) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "json", path], capture_output=True, text=True)
    try:
        return bool(json.loads(out.stdout or "{}").get("streams"))
    except json.JSONDecodeError:
        return False


def _ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args],
                          capture_output=True, text=True)
    if proc.returncode:
        raise RenderError(proc.stderr.strip()[-2000:])


def _segment(src: str, telop_png: str, dur: float, out: str) -> None:
    is_image = src.lower().endswith(IMAGE_EXT)
    if is_image:
        inputs = ["-loop", "1", "-t", f"{dur}", "-i", src]
        # 静止画はゆっくりズーム (Ken Burns 風)
        frames = int(dur * FPS)
        base = (f"[0:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,"
                f"crop={W * 2}:{H * 2},zoompan=z='1+0.08*on/{frames}':d=1:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}[bg]")
        audio_src = None
    else:
        inputs = ["-t", f"{dur}", "-i", src]
        base = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"fps={FPS},setsar=1,tpad=stop_mode=clone:stop_duration={dur}[bg]")
        audio_src = "0:a" if _has_audio(src) else None
    inputs += ["-loop", "1", "-t", f"{dur}", "-i", telop_png,
               "-f", "lavfi", "-t", f"{dur}", "-i", "anullsrc=r=44100:cl=stereo"]
    fc = f"{base};[bg][1:v]overlay=0:0,format=yuv420p[v]"
    if audio_src:
        fc += f";[{audio_src}]aresample=44100,aformat=channel_layouts=stereo,apad[a]"
        amap = "[a]"
    else:
        amap = "2:a"
    _ffmpeg([*inputs, "-filter_complex", fc, "-map", "[v]", "-map", amap,
             "-t", f"{dur}", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", out])


@dataclass
class RenderResult:
    path: str
    draft: bool
    missing: list[int]
    duration: float


def render_day(day: dict, *, media_root: str = "media", out_dir: str = "videos",
               draft_dir: str = "build/drafts", draft: bool = False,
               graphic: bool = False, bgm_volume: float = 0.25) -> RenderResult:
    """graphic=True: 素材が無いシーンをモーショングラフィックスで生成 (投稿用の本番動画)."""
    if not shutil.which("ffmpeg"):
        raise RenderError("ffmpeg がインストールされていません")
    font = find_font()
    n = day["day"]
    media_dir = os.path.join(media_root, f"day{n}")
    scenes = day["scenes"]
    sources = [find_scene_media(media_dir, i) for i in range(1, len(scenes) + 1)]
    missing = [i for i, s in enumerate(sources, 1) if s is None]
    if missing and not (draft or graphic):
        raise RenderError(f"Day{n}: 素材が足りません シーン {missing} → {media_dir}/ に置くか "
                          "--graphic (モーショングラフィックス) / --draft (下書き)")

    is_draft = draft and not graphic
    target_dir = draft_dir if is_draft else out_dir
    os.makedirs(target_dir, exist_ok=True)
    suffix = "_draft" if is_draft else ""
    out = os.path.join(target_dir, f"day{n}_{day['slug']}{suffix}.mp4")
    label = f"Day{n}  {day['area']}"

    with tempfile.TemporaryDirectory() as tmp:
        segs = []
        for i, (scene, src) in enumerate(zip(scenes, sources), 1):
            telop_img = draw_telop(scene.get("text", ""), scene.get("sub", ""), label, font)
            seg = os.path.join(tmp, f"seg{i}.mp4")
            if src is None and graphic:
                from .graphic import SceneRenderer

                SceneRenderer(day, scene, i, len(scenes), telop_img, font, seed=n).write(seg)
                segs.append(seg)
                continue
            if src is None:
                src = os.path.join(tmp, f"card{i}.png")
                draft_card(n, i, scene.get("shot", ""), font).save(src)
            telop = os.path.join(tmp, f"telop{i}.png")
            telop_img.save(telop)
            _segment(src, telop, float(scene["dur"]), seg)
            segs.append(seg)

        listfile = os.path.join(tmp, "list.txt")
        with open(listfile, "w") as f:
            f.writelines(f"file '{s}'\n" for s in segs)
        joined = os.path.join(tmp, "joined.mp4")
        _ffmpeg(["-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy",
                 "-movflags", "+faststart", joined])

        bgm = find_bgm(media_dir)
        if not bgm and graphic:
            from .graphic import make_bgm

            total_sec = sum(float(s["dur"]) for s in scenes)
            bgm = make_bgm(os.path.join(tmp, "bgm.wav"), total_sec + 1, seed=n)
            bgm_volume = 1.0  # 合成 BGM は音量調整済み
        if bgm:
            _ffmpeg(["-i", joined, "-stream_loop", "-1", "-i", bgm, "-filter_complex",
                     f"[1:a]volume={bgm_volume},afade=t=out:st={sum(s['dur'] for s in scenes) - 1.5}"
                     f":d=1.5[b];[0:a][b]amix=inputs=2:duration=first:normalize=0[a]",
                     "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                     "-movflags", "+faststart", out])
        else:
            shutil.copy(joined, out)

    total = round(sum(float(s["dur"]) for s in scenes), 2)
    return RenderResult(out, is_draft, missing, total)


def save_cover(day: dict, video: str, out_dir: str = "build/covers") -> str:
    """1 シーン目の中央フレームをカバー候補として保存 (thumb_offset 用の確認)."""
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"day{day['day']}_{day['slug']}.jpg")
    t = float(day["scenes"][0]["dur"]) / 2
    _ffmpeg(["-ss", f"{t}", "-i", video, "-frames:v", "1", "-q:v", "3", out])
    return out
