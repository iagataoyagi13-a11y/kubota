import json
import subprocess
from datetime import timedelta

import pytest

from reels_poster.cli import run_due
from reels_poster.client import InstagramAPIError, InstagramClient
from reels_poster.config import Config
from reels_poster.schedule import Queue, now, parse_time
from reels_poster.video import check_caption, check_video


class FakeResp:
    def __init__(self, data, status=200):
        self._data, self.status_code, self.text = data, status, json.dumps(data)

    def json(self):
        return self._data


class FakeSession:
    """URL の末尾と HTTP メソッドで応答を返す偽セッション."""

    def __init__(self, statuses=("IN_PROGRESS", "FINISHED")):
        self.calls = []
        self.statuses = list(statuses)

    def request(self, method, url, params=None, data=None, **kw):
        self.calls.append((method, url, params, data))
        if method == "POST" and url.endswith("/media"):
            return FakeResp({"id": "C1"})
        if method == "POST" and url.endswith("/media_publish"):
            return FakeResp({"id": "M1"})
        if url.endswith("/content_publishing_limit"):
            return FakeResp({"data": [{"config": {"quota_total": 100}, "quota_usage": 98}]})
        if url.endswith("/C1"):
            return FakeResp({"status_code": self.statuses.pop(0)})
        if url.endswith("/M1"):
            return FakeResp({"permalink": "https://www.instagram.com/reel/abc/"})
        return FakeResp({"error": {"message": "unknown"}}, 400)

    def post(self, url, headers=None, data=None, **kw):
        body = data.read()
        self.calls.append(("UPLOAD", url, headers, len(body)))
        return FakeResp({"success": True})

    def get(self, url, params=None, **kw):
        return self.request("GET", url, params=params)


CFG = Config(ig_user_id="17841400000000000", access_token="TOKEN")


def make_client(session):
    return InstagramClient(CFG, session=session, sleep=lambda s: None)


def test_post_reel_from_url():
    s = FakeSession()
    res = make_client(s).post_reel("https://example.com/a.mp4", "hello #reels")
    assert (res.container_id, res.media_id) == ("C1", "M1")
    assert res.permalink.endswith("/reel/abc/")
    create = s.calls[0]
    assert create[3]["media_type"] == "REELS"
    assert create[3]["video_url"] == "https://example.com/a.mp4"
    assert create[2]["access_token"] == "TOKEN"
    assert any(c[1].endswith("/media_publish") for c in s.calls)


def test_post_reel_local_uses_resumable_upload(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x" * 1234)
    s = FakeSession(statuses=("FINISHED",))
    make_client(s).post_reel(str(f), "cap", share_to_feed=False, thumb_offset_ms=500)
    assert s.calls[0][3]["upload_type"] == "resumable"
    assert s.calls[0][3]["share_to_feed"] == "false"
    assert s.calls[0][3]["thumb_offset"] == "500"
    upload = s.calls[1]
    assert upload[0] == "UPLOAD"
    assert upload[1] == "https://rupload.facebook.com/ig-api-upload/v23.0/C1"
    assert upload[2]["file_size"] == "1234" and upload[2]["Authorization"] == "OAuth TOKEN"


def test_container_error_raises():
    s = FakeSession(statuses=("ERROR",))
    with pytest.raises(InstagramAPIError, match="ERROR"):
        make_client(s).post_reel("https://example.com/a.mp4")
    assert not any(c[1].endswith("/media_publish") for c in s.calls)


def test_wait_timeout():
    s = FakeSession(statuses=["IN_PROGRESS"] * 10)
    c = make_client(s)
    with pytest.raises(InstagramAPIError, match="タイムアウト"):
        c.wait_until_ready("C1", poll_interval=10, timeout=30)


def test_publishing_limit():
    assert make_client(FakeSession()).publishing_limit() == {
        "quota_total": 100, "quota_usage": 98, "remaining": 2}


def test_queue_add_due_and_persist(tmp_path):
    path = tmp_path / "q.json"
    q = Queue(str(path))
    past = q.add("https://e.com/1.mp4", "past", now() - timedelta(minutes=1))
    q.add("https://e.com/2.mp4", "future", now() + timedelta(days=1))
    q.save()
    q2 = Queue(str(path))
    assert [i["id"] for i in q2.due()] == [past["id"]]


def test_parse_time_defaults_to_jst():
    assert parse_time("2026-11-03 19:00").utcoffset() == timedelta(hours=9)
    assert parse_time("2026-11-03T10:00:00Z").utcoffset() == timedelta(0)


def test_run_due_respects_quota_and_marks_posted(tmp_path):
    q = Queue(str(tmp_path / "q.json"))
    for n in range(4):
        q.add(f"https://e.com/{n}.mp4", f"cap {n}", now() - timedelta(minutes=5))
    ok, ng = run_due(q, make_client(FakeSession(statuses=["FINISHED"] * 4)),
                     max_posts=5, max_attempts=3)
    assert (ok, ng) == (2, 0)  # 残り枠 2 件で打ち切り
    posted = [i for i in Queue(q.path).items if i["status"] == "posted"]
    assert len(posted) == 2 and posted[0]["media_id"] == "M1"


def test_run_due_records_failure_and_retries_limit(tmp_path):
    q = Queue(str(tmp_path / "q.json"))
    q.add("https://e.com/x.mp4", "c", now() - timedelta(minutes=1))
    for _ in range(3):
        run_due(q, make_client(FakeSession(statuses=["ERROR"])), max_posts=5, max_attempts=3)
    item = q.items[0]
    assert item["status"] == "failed" and item["attempts"] == 3
    assert q.due(max_attempts=3) == []


def test_caption_limits():
    assert not check_caption("a" * 2201).ok
    assert not check_caption(" ".join(f"#t{i}" for i in range(31))).ok
    assert check_caption("ok #one #two").ok


def test_check_video_missing_and_bad_ext(tmp_path):
    assert not check_video(str(tmp_path / "none.mp4")).ok
    f = tmp_path / "a.avi"
    f.write_bytes(b"x")
    assert any("拡張子" in e for e in check_video(str(f)).errors)


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode,
                    reason="ffmpeg がありません")
def test_check_video_with_ffprobe(tmp_path):
    f = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=540x960:r=30",
                    "-f", "lavfi", "-i", "anullsrc", "-t", "4", "-c:v", "libx264",
                    "-c:a", "aac", "-pix_fmt", "yuv420p", str(f)], check=True)
    r = check_video(str(f))
    assert r.ok, r.errors
    assert r.info["width"] == 540 and r.info["fps"] == 30 and not r.warnings
