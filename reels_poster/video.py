"""投稿前の動画チェック (ffprobe があれば詳細チェック).

Reels の主な仕様 (Graph API):
  - コンテナ: MP4 / MOV,  映像: H.264 / HEVC,  音声: AAC
  - 長さ: 3 秒〜15 分,  サイズ: 最大 300MB,  フレームレート: 23〜60fps
  - 推奨アスペクト比: 9:16 (1080x1920)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field

MAX_BYTES = 300 * 1024 * 1024
MIN_SEC, MAX_SEC = 3.0, 15 * 60.0
ALLOWED_EXT = {".mp4", ".mov"}
MAX_CAPTION = 2200
MAX_HASHTAGS = 30


@dataclass
class CheckResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def check_caption(caption: str, result: CheckResult | None = None) -> CheckResult:
    result = result or CheckResult()
    if len(caption) > MAX_CAPTION:
        result.errors.append(f"キャプションが長すぎます ({len(caption)} > {MAX_CAPTION} 文字)")
    tags = sum(1 for w in caption.split() if w.startswith("#"))
    if tags > MAX_HASHTAGS:
        result.errors.append(f"ハッシュタグが多すぎます ({tags} > {MAX_HASHTAGS})")
    return result


def check_video(path: str, caption: str = "") -> CheckResult:
    result = check_caption(caption)
    if path.startswith(("http://", "https://")):
        result.info["source"] = "url"
        return result  # URL の中身は Instagram 側で検証される

    if not os.path.isfile(path):
        result.errors.append(f"ファイルが見つかりません: {path}")
        return result
    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED_EXT:
        result.errors.append(f"非対応の拡張子です: {ext} (mp4/mov のみ)")
    size = os.path.getsize(path)
    result.info["size_mb"] = round(size / 1024 / 1024, 2)
    if size > MAX_BYTES:
        result.errors.append(f"ファイルサイズが大きすぎます ({result.info['size_mb']}MB > 300MB)")

    probe = _ffprobe(path)
    if probe is None:
        result.warnings.append("ffprobe が無いため長さ/解像度チェックをスキップしました")
        return result

    duration = float(probe.get("format", {}).get("duration", 0) or 0)
    result.info["duration_sec"] = round(duration, 2)
    if not MIN_SEC <= duration <= MAX_SEC:
        result.errors.append(f"動画の長さが範囲外です ({duration:.1f}秒, 3秒〜15分)")

    v = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None)
    if v is None:
        result.errors.append("映像ストリームがありません")
        return result
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    result.info.update(width=w, height=h, codec=v.get("codec_name"))
    if v.get("codec_name") not in ("h264", "hevc"):
        result.warnings.append(f"映像コーデック {v.get('codec_name')} は非推奨 (H.264 推奨)")
    if w and h and abs(w / h - 9 / 16) > 0.02:
        result.warnings.append(f"アスペクト比 {w}x{h} は 9:16 ではありません (余白が付く場合あり)")
    fps = _parse_fps(v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1")
    result.info["fps"] = round(fps, 2)
    if fps and not 23 <= fps <= 60.5:
        result.errors.append(f"フレームレートが範囲外です ({fps:.1f}fps, 23〜60fps)")
    a = next((s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), None)
    if a and a.get("codec_name") != "aac":
        result.warnings.append(f"音声コーデック {a.get('codec_name')} は非推奨 (AAC 推奨)")
    return result


def _parse_fps(text: str) -> float:
    try:
        num, den = text.split("/")
        return float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def _ffprobe(path: str) -> dict | None:
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        return json.loads(out)
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return None
