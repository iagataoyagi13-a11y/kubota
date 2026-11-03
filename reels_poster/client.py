"""Instagram Graph API (Content Publishing) でリールを投稿するクライアント.

投稿フロー:
  1. POST /{ig-user-id}/media (media_type=REELS) でメディアコンテナ作成
     - 公開 URL の動画: video_url を指定
     - ローカル動画: upload_type=resumable → rupload.facebook.com にバイナリ送信
  2. GET /{container-id}?fields=status_code を FINISHED になるまでポーリング
  3. POST /{ig-user-id}/media_publish で公開
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

from .config import Config


class InstagramAPIError(RuntimeError):
    def __init__(self, message: str, payload: Any = None):
        super().__init__(message)
        self.payload = payload


@dataclass
class PublishResult:
    container_id: str
    media_id: str
    permalink: str | None = None


class InstagramClient:
    def __init__(
        self,
        config: Config,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        timeout: float = 60.0,
    ):
        self.config = config
        self.session = session or requests.Session()
        self._sleep = sleep
        self.timeout = timeout

    # ------------------------------------------------------------------ utils
    @property
    def base_url(self) -> str:
        return f"https://{self.config.graph_host}/{self.config.api_version}"

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        params = kwargs.pop("params", {}) or {}
        params.setdefault("access_token", self.config.access_token)
        resp = self.session.request(method, url, params=params, timeout=self.timeout, **kwargs)
        return self._parse(resp)

    @staticmethod
    def _parse(resp: requests.Response) -> dict:
        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text}
        if resp.status_code >= 400 or (isinstance(data, dict) and "error" in data):
            err = data.get("error", {}) if isinstance(data, dict) else {}
            msg = err.get("error_user_msg") or err.get("message") or resp.text
            raise InstagramAPIError(f"HTTP {resp.status_code}: {msg}", data)
        return data

    # -------------------------------------------------------------- container
    def create_reel_container(
        self,
        *,
        caption: str = "",
        video_url: str | None = None,
        resumable: bool = False,
        share_to_feed: bool = True,
        cover_url: str | None = None,
        thumb_offset_ms: int | None = None,
        audio_name: str | None = None,
        location_id: str | None = None,
        collaborators: list[str] | None = None,
    ) -> str:
        if not video_url and not resumable:
            raise ValueError("video_url か resumable=True のどちらかが必要です")
        data: dict[str, Any] = {
            "media_type": "REELS",
            "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false",
        }
        if resumable:
            data["upload_type"] = "resumable"
        else:
            data["video_url"] = video_url
        if cover_url:
            data["cover_url"] = cover_url
        if thumb_offset_ms is not None:
            data["thumb_offset"] = str(thumb_offset_ms)
        if audio_name:
            data["audio_name"] = audio_name
        if location_id:
            data["location_id"] = location_id
        if collaborators:
            import json

            data["collaborators"] = json.dumps(collaborators)
        result = self._request("POST", f"{self.config.ig_user_id}/media", data=data)
        return result["id"]

    def upload_local_video(self, container_id: str, path: str) -> dict:
        """resumable コンテナにローカル動画ファイルを送信する."""
        size = os.path.getsize(path)
        url = f"https://rupload.facebook.com/ig-api-upload/{self.config.api_version}/{container_id}"
        headers = {
            "Authorization": f"OAuth {self.config.access_token}",
            "offset": "0",
            "file_size": str(size),
        }
        with open(path, "rb") as f:
            resp = self.session.post(url, headers=headers, data=f, timeout=max(self.timeout, 600))
        data = self._parse(resp)
        if data.get("success") is False:
            raise InstagramAPIError(f"アップロード失敗: {data}", data)
        return data

    def get_container_status(self, container_id: str) -> dict:
        return self._request("GET", container_id, params={"fields": "status_code,status"})

    def wait_until_ready(
        self, container_id: str, poll_interval: float = 10.0, timeout: float = 900.0
    ) -> None:
        """status_code が FINISHED になるまで待機する."""
        waited = 0.0
        while True:
            info = self.get_container_status(container_id)
            code = info.get("status_code")
            if code == "FINISHED":
                return
            if code in ("ERROR", "EXPIRED"):
                raise InstagramAPIError(
                    f"コンテナ処理失敗 ({code}): {info.get('status', '')}", info
                )
            if code == "PUBLISHED":
                raise InstagramAPIError("このコンテナは既に公開済みです", info)
            if waited >= timeout:
                raise InstagramAPIError(f"処理待ちタイムアウト ({timeout}s): {info}", info)
            self._sleep(poll_interval)
            waited += poll_interval

    def publish(self, container_id: str) -> str:
        result = self._request(
            "POST", f"{self.config.ig_user_id}/media_publish", data={"creation_id": container_id}
        )
        return result["id"]

    def get_permalink(self, media_id: str) -> str | None:
        try:
            return self._request("GET", media_id, params={"fields": "permalink"}).get("permalink")
        except InstagramAPIError:
            return None

    # ------------------------------------------------------------- high level
    def post_reel(
        self,
        video: str,
        caption: str = "",
        *,
        poll_interval: float = 10.0,
        timeout: float = 900.0,
        **options: Any,
    ) -> PublishResult:
        """URL またはローカルパスの動画をリールとして投稿する."""
        is_url = video.startswith(("http://", "https://"))
        if is_url:
            container_id = self.create_reel_container(caption=caption, video_url=video, **options)
        else:
            if not os.path.isfile(video):
                raise FileNotFoundError(video)
            container_id = self.create_reel_container(caption=caption, resumable=True, **options)
            self.upload_local_video(container_id, video)
        self.wait_until_ready(container_id, poll_interval=poll_interval, timeout=timeout)
        media_id = self.publish(container_id)
        return PublishResult(container_id, media_id, self.get_permalink(media_id))

    # ------------------------------------------------------------------ misc
    def publishing_limit(self) -> dict:
        """24 時間あたりの投稿上限と使用量."""
        data = self._request(
            "GET",
            f"{self.config.ig_user_id}/content_publishing_limit",
            params={"fields": "config,quota_usage"},
        )
        item = (data.get("data") or [{}])[0]
        total = (item.get("config") or {}).get("quota_total")
        used = item.get("quota_usage", 0)
        return {"quota_total": total, "quota_usage": used,
                "remaining": None if total is None else total - used}

    def refresh_long_lived_token(self) -> dict:
        """Instagram ログインの長期トークン(60日)を更新する (graph.instagram.com)."""
        resp = self.session.get(
            "https://graph.instagram.com/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": self.config.access_token},
            timeout=self.timeout,
        )
        return self._parse(resp)
