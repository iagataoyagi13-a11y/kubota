"""楽天ブログの「メール投稿」機能を使って記事を投稿する.

楽天ブログの管理画面で発行される「投稿用メールアドレス」宛てに
件名 = タイトル / 本文 = 記事 / 添付 = アイキャッチ画像 のメールを SMTP で送ります。
"""

from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path


POST_DOMAIN = "@mb.plaza.rakuten.co.jp"


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class MailConfig:
    post_address: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    sender: str

    @classmethod
    def from_env(cls) -> "MailConfig":
        _load_dotenv()
        get = lambda k, default="": os.environ.get(k, default).strip()  # noqa: E731
        cfg = cls(
            post_address=get("RAKUTEN_POST_ADDRESS"),
            smtp_host=get("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(get("SMTP_PORT", "465")),
            smtp_user=get("SMTP_USER"),
            smtp_password=get("SMTP_PASSWORD"),
            sender=get("SMTP_FROM") or get("SMTP_USER"),
        )
        missing = [k for k, v in (("RAKUTEN_POST_ADDRESS", cfg.post_address), ("SMTP_USER", cfg.smtp_user),
                                  ("SMTP_PASSWORD", cfg.smtp_password)) if not v]
        if missing:
            raise ConfigError(f"環境変数が未設定です: {', '.join(missing)}")
        if not cfg.post_address.lower().endswith(POST_DOMAIN):
            raise ConfigError(
                f"RAKUTEN_POST_ADDRESS は楽天ブログの投稿用アドレス (…{POST_DOMAIN}) を設定してください。"
                "自分のメールアドレスではありません。楽天ブログの「メールで更新」機能から届くメール"
                "(no-reply@mail.plaza.rakuten.co.jp) の本文に書かれています")
        return cfg


def build_message(sender: str, to: str, title: str, body: str, image: Path | None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = title
    msg.set_content(body, charset="utf-8")
    if image is not None:
        msg.add_attachment(image.read_bytes(), maintype="image", subtype="jpeg", filename=image.name)
    return msg


def send(cfg: MailConfig, msg: EmailMessage) -> None:
    ctx = ssl.create_default_context()
    if cfg.smtp_port == 465:
        with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=ctx, timeout=60) as s:
            s.login(cfg.smtp_user, cfg.smtp_password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=60) as s:
            s.starttls(context=ctx)
            s.login(cfg.smtp_user, cfg.smtp_password)
            s.send_message(msg)


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
