import json
import shutil
from datetime import date

import pytest

from reels_poster.cli import main
from reels_poster.content import PR_FOOTER, Plan
from reels_poster.linkpage import build_html
from reels_poster.schedule import Queue

PLAN = "content/plan_7days.json"
LINKS = "content/affiliate_links.json"


def test_real_plan_is_complete():
    plan = Plan.load(PLAN, LINKS)
    assert [d["day"] for d in plan.days] == list(range(1, 8))
    for d in plan.days:
        assert 15 <= plan.duration(d) <= 30
        assert len(d["hashtags"]) <= 5
        cap = plan.caption(d)
        assert cap.startswith("【PR】") and cap.endswith(PR_FOOTER)
        assert f"「Day{d['day']}」" in cap and len(cap) <= 2200
        for key in d["affiliate"]:
            assert key in plan.links
    # 出荷時は URL 未設定なので要対応が出る
    assert any("REPLACE_ME" in p for p in plan.problems())


def _mini_plan(tmp_path, url="https://example.com/aff?id=1&x=<b>"):
    plan = {"series": "テスト", "post_time": "20:30", "days": [
        {"day": 1, "slug": "a", "area": "A県", "onsen": "A温泉", "food": "A鍋",
         "scenes": [{"dur": 1.5, "text": "見出し", "sub": "補足", "shot": "全景"},
                    {"dur": 1.5, "text": "長いテキストが折り返されるか確認するための文章です", "sub": ""}],
         "caption": "本文", "hashtags": ["#a"], "affiliate": ["a_stay"]},
        {"day": 2, "slug": "b", "area": "B県", "onsen": "B温泉", "food": "B飯",
         "scenes": [{"dur": 3.0, "text": "x"}], "caption": "本文2", "hashtags": [], "affiliate": []},
    ]}
    p, l = tmp_path / "plan.json", tmp_path / "links.json"
    p.write_text(json.dumps(plan, ensure_ascii=False))
    l.write_text(json.dumps({"a_stay": {"label": "宿", "program": "楽天", "url": url}}))
    return str(p), str(l)


def test_schedule_one_per_day(tmp_path):
    plan = Plan.load(*_mini_plan(tmp_path))
    sched = plan.schedule(date(2026, 11, 4))
    assert [w.isoformat() for _, w in sched] == [
        "2026-11-04T20:30:00+09:00", "2026-11-05T20:30:00+09:00"]


def test_no_pr_label_without_affiliate(tmp_path):
    plan = Plan.load(*_mini_plan(tmp_path))
    assert not plan.caption(plan.day(2)).startswith("【PR】")


def test_linkpage_escapes_and_marks_sponsored(tmp_path):
    out = build_html(Plan.load(*_mini_plan(tmp_path)))
    assert 'rel="sponsored nofollow noopener"' in out
    assert "&amp;x=&lt;b&gt;" in out and "<b>" not in out
    assert "【PR】" in out and 'id="day1"' in out


def test_linkpage_refuses_placeholders(tmp_path):
    plan = Plan.load(*_mini_plan(tmp_path, url="REPLACE_ME"))
    with pytest.raises(ValueError):
        build_html(plan)
    assert 'href="#"' in build_html(plan, allow_placeholders=True)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg がありません")
def test_render_draft_then_schedule(tmp_path, capsys):
    p, l = _mini_plan(tmp_path)
    media, out, q = tmp_path / "media", tmp_path / "videos", tmp_path / "q.json"
    common = ["--plan", p, "--links", l, "--out", str(out)]
    # 素材なし → 本番レンダリングは失敗
    assert main(["render", *common, "--media", str(media), "--day", "1"]) == 2
    # 素材を用意して本番レンダリング
    (media / "day1").mkdir(parents=True)
    from PIL import Image
    Image.new("RGB", (800, 600), "teal").save(media / "day1" / "1.jpg")
    Image.new("RGB", (600, 800), "navy").save(media / "day1" / "2.png")
    assert main(["render", *common, "--media", str(media), "--day", "1"]) == 0
    video = out / "day1_a.mp4"
    assert video.exists()
    # 予約登録: Day1 のみ動画があるので 1 件
    assert main(["-q", str(q), "schedule-plan", *common, "--start", "2026-11-04"]) == 0
    items = Queue(str(q)).items
    assert len(items) == 1 and items[0]["video"] == str(video)
    assert items[0]["caption"].startswith("【PR】")
    # 二重登録しない
    main(["-q", str(q), "schedule-plan", *common, "--start", "2026-11-04"])
    assert len(Queue(str(q)).items) == 1


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg がありません")
def test_render_graphic_without_media(tmp_path):
    from reels_poster.video import check_video

    p, l = _mini_plan(tmp_path)
    out = tmp_path / "videos"
    assert main(["render", "--plan", p, "--links", l, "--out", str(out),
                 "--media", str(tmp_path / "none"), "--day", "1", "--graphic"]) == 0
    video = out / "day1_a.mp4"
    r = check_video(str(video))
    assert r.ok, r.errors
    assert r.info["width"] == 1080 and r.info["height"] == 1920
    assert abs(r.info["duration_sec"] - 3.0) < 0.1


def test_bgm_is_generated(tmp_path):
    import wave

    from reels_poster.graphic import make_bgm

    path = make_bgm(str(tmp_path / "b.wav"), 4.0, seed=3)
    with wave.open(path) as w:
        assert w.getnchannels() == 2 and abs(w.getnframes() / w.getframerate() - 4.0) < 0.01


def test_telop_wraps_at_space():
    from PIL import Image, ImageDraw, ImageFont

    from reels_poster.render import _wrap, find_font

    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines = _wrap(d, "熊本の郷土料理 だご汁", ImageFont.truetype(find_font(), 86), 860)
    assert lines == ["熊本の郷土料理", "だご汁"]
