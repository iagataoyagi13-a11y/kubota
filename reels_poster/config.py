"""環境変数から設定を読み込む."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    ig_user_id: str
    access_token: str
    api_version: str = "v23.0"
    # Facebook ログイン経由のトークン: graph.facebook.com
    # Instagram ログイン経由のトークン: graph.instagram.com
    graph_host: str = "graph.facebook.com"

    @classmethod
    def from_env(cls) -> "Config":
        _load_dotenv()
        user_id = os.environ.get("IG_USER_ID", "").strip()
        token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
        missing = [n for n, v in (("IG_USER_ID", user_id), ("IG_ACCESS_TOKEN", token)) if not v]
        if missing:
            raise ConfigError(f"環境変数が未設定です: {', '.join(missing)}")
        return cls(
            ig_user_id=user_id,
            access_token=token,
            api_version=os.environ.get("GRAPH_API_VERSION", cls.api_version),
            graph_host=os.environ.get("GRAPH_HOST", cls.graph_host),
        )


def _load_dotenv(path: str = ".env") -> None:
    """依存なしの簡易 .env ローダー（既存の環境変数は上書きしない）."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
