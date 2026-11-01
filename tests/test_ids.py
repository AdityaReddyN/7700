"""Id and ref_id helpers are deterministic and correctly formatted."""

from common.ids import (
    alert_id,
    hash8,
    new_investigation_id,
    ref_calc,
    ref_case,
    ref_window,
)


def test_hash8_is_stable_and_order_independent():
    a = hash8({"icao24": "abc", "t_start": 1, "t_end": 2})
    b = hash8({"t_end": 2, "t_start": 1, "icao24": "abc"})
    assert a == b
    assert len(a) == 8


def test_alert_id_is_deterministic():
    assert alert_id("abc123", 100, 200) == "alert_abc123_100_200"


def test_ref_formats():
    aid = alert_id("abc123", 100, 200)
    assert ref_window(aid, 100, 200) == "win:alert_abc123_100_200:100-200"
    assert ref_case("spoof_01") == "case:spoof_01"
    calc = ref_calc(aid, "kin", {"icao24": "abc123", "t_start": 100, "t_end": 200})
    assert calc.startswith("calc:alert_abc123_100_200:kin:")
    assert len(calc.split(":")[-1]) == 8


def test_investigation_ids_are_unique():
    assert new_investigation_id() != new_investigation_id()
