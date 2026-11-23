import json
from datetime import date, datetime
from email import message_from_bytes, policy
from pathlib import Path

from rakuten_blog import cli, illustrate
from rakuten_blog.content import Plan
from rakuten_blog.mailpost import build_message

ROOT = Path(__file__).resolve().parents[1]


def plan():
    return Plan.load(root=ROOT)


def test_plan_has_7_days_in_three_cities():
    p = plan()
    assert [d["day"] for d in p.days] == list(range(1, 8))
    assert {d["city"] for d in p.days} == {"桑名市", "四日市市", "鈴鹿市"}
    for d in p.days:
        assert d["scene"] in illustrate.SCENES
        assert d["title"].startswith(f"【Day{d['day']}】")
        assert p.image_path(d).exists(), "python -m rakuten_blog build で画像を生成してください"
    assert p.problems() == []


def test_bodies_contain_all_parts():
    p = plan()
    d = p.day(3)
    text = p.text_body(d)
    assert text.startswith(d["lead"]) and "#四日市市" in text and "ヒゲおやじ" in text
    html = p.html_body(d, "https://example.com/a.jpg?x=1&y=2")
    assert 'src="https://example.com/a.jpg?x=1&amp;y=2"' in html and html.count("<h3>") == 4


def test_render_image(tmp_path):
    out = illustrate.render_day(plan().day(1), "テスト", tmp_path / "x.jpg")
    from PIL import Image
    assert Image.open(out).size == (illustrate.W, illustrate.H)


def test_place_label_avoids_duplicate_city():
    assert illustrate.place_label({"city": "四日市市", "park": "四日市市南部丘陵公園"}) == "四日市市南部丘陵公園"
    assert illustrate.place_label({"city": "桑名市", "park": "九華公園"}) == "桑名市・九華公園"


def test_schedule_and_due():
    items = cli.make_schedule(plan(), date(2026, 11, 24), "07:30")
    assert items[0]["scheduled_at"] == "2026-11-24T07:30:00+09:00"
    assert items[6]["scheduled_at"] == "2026-11-30T07:30:00+09:00"
    at = datetime.fromisoformat("2026-11-25T08:00:00+09:00")
    assert [it["day"] for it in cli.due(items, at)] == [1, 2]


def test_mail_message_has_utf8_subject_and_image():
    p = plan()
    d = p.day(1)
    msg = build_message("me@example.com", "post@example.com", d["title"], p.text_body(d), p.image_path(d))
    parsed = message_from_bytes(msg.as_bytes(), policy=policy.default)
    assert parsed["Subject"] == d["title"]
    parts = list(parsed.iter_attachments())
    assert parts[0].get_content_type() == "image/jpeg"
    assert "九華公園" in parsed.get_body(("plain",)).get_content()


def test_run_marks_posted_and_retries(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    q = tmp_path / "queue.json"
    monkeypatch.setattr(cli, "QUEUE_PATH", q)
    items = cli.make_schedule(plan(), date(2020, 1, 1), "07:30")
    q.write_text(json.dumps(items), encoding="utf-8")
    sent = []
    monkeypatch.setattr(cli.MailConfig, "from_env", classmethod(lambda c: c("to@x", "h", 465, "u", "p", "u")))
    monkeypatch.setattr(cli, "send", lambda cfg, msg: sent.append(msg["Subject"]))
    load = lambda: json.loads(q.read_text(encoding="utf-8"))  # noqa: E731
    cli.save_queue(items, q)
    monkeypatch.setattr(cli, "load_queue", lambda path=q: load())
    monkeypatch.setattr(cli, "save_queue", lambda its, path=q: q.write_text(json.dumps(its), encoding="utf-8"))
    assert cli.main(["run"]) == 0
    assert len(sent) == 1 and load()[0]["status"] == "posted" and load()[1]["status"] == "pending"

    def boom(cfg, msg):
        raise OSError("smtp down")
    monkeypatch.setattr(cli, "send", boom)
    for _ in range(3):
        assert cli.main(["run"]) == 1
    assert load()[1]["status"] == "failed" and load()[1]["attempts"] == 3
