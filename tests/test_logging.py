"""JSONL writer appends and reads back records; logger is usable."""

from common.logging import JsonlWriter, get_logger


def test_jsonl_writer_round_trips(tmp_path):
    path = tmp_path / "nested" / "calls.jsonl"
    writer = JsonlWriter(path)
    writer.write({"stage": "triage", "tokens": 42})
    writer.write({"stage": "adjudication", "tokens": 7})
    records = writer.read_all()
    assert len(records) == 2
    assert records[0]["stage"] == "triage"
    assert "ts" in records[0]  # auto-stamped


def test_read_all_on_missing_file(tmp_path):
    assert JsonlWriter(tmp_path / "none.jsonl").read_all() == []


def test_get_logger_returns_named_logger():
    assert get_logger("adsb.test").name == "adsb.test"
