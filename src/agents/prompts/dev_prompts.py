"""Twenty neutral dev prompts for the M1 smoke test.

Hand-written placeholders until M3 can draw prompts from the scenario builder
(ROADMAP day 1). They describe flagged anomalies in neutral kinematic/identity
terms only: no label strings, no scenario ids, no split names (non-negotiable
#2). A unit test asserts this. Times fall on 2019-12-09 (the available day).

Each item carries an icao24 and a window so the model has concrete tool
arguments to work with.
"""

from __future__ import annotations

# 2019-12-09 00:00:00 UTC
_DAY = 1575849600


def _t(hour: int, minute: int = 0) -> int:
    return _DAY + hour * 3600 + minute * 60


DEV_PROMPTS: list[dict] = [
    {"id": "P01", "icao24": "a1b2c3", "t_start": _t(1, 0), "t_end": _t(1, 8),
     "text": "Reported ground speed holds near 250 m/s, but the position moves only a few hundred metres over eight minutes."},
    {"id": "P02", "icao24": "3c4d5e", "t_start": _t(2, 10), "t_end": _t(2, 16),
     "text": "The latitude and longitude drift steadily away from the earlier heading while reported velocity is unchanged."},
    {"id": "P03", "icao24": "7f8a9b", "t_start": _t(3, 30), "t_end": _t(3, 33),
     "text": "Position jumps about 30 km between two consecutive updates, then continues smoothly."},
    {"id": "P04", "icao24": "0c1d2e", "t_start": _t(4, 0), "t_end": _t(4, 15),
     "text": "A track appears with no earlier history, flying a very straight path at a constant 450 kt."},
    {"id": "P05", "icao24": "9a8b7c", "t_start": _t(5, 20), "t_end": _t(5, 30),
     "text": "The same aircraft address reports two positions over 200 km apart at the same timestamps."},
    {"id": "P06", "icao24": "4e5f60", "t_start": _t(6, 5), "t_end": _t(6, 11),
     "text": "This window closely matches a sequence the same address flew about forty minutes earlier."},
    {"id": "P07", "icao24": "11a2b3", "t_start": _t(7, 0), "t_end": _t(7, 4),
     "text": "Positions scatter randomly by a few hundred metres around a smooth path; reported fields look noisy."},
    {"id": "P08", "icao24": "c4d5e6", "t_start": _t(8, 12), "t_end": _t(8, 16),
     "text": "About half the position updates are missing for roughly ninety seconds, then resume."},
    {"id": "P09", "icao24": "77f8a9", "t_start": _t(9, 40), "t_end": _t(9, 46),
     "text": "One reported field repeats the identical value for about a minute while the aircraft keeps moving."},
    {"id": "P10", "icao24": "2b3c4d", "t_start": _t(10, 0), "t_end": _t(10, 6),
     "text": "The aircraft turns through more than 360 degrees within a small radius over about six minutes."},
    {"id": "P11", "icao24": "5e6f70", "t_start": _t(11, 25), "t_end": _t(11, 28),
     "text": "A descent to low altitude is followed by a sharp climb of over 1,000 ft within three minutes."},
    {"id": "P12", "icao24": "8a9b0c", "t_start": _t(12, 0), "t_end": _t(12, 9),
     "text": "Implied speed from position changes is far higher than the reported ground speed across the window."},
    {"id": "P13", "icao24": "d1e2f3", "t_start": _t(13, 15), "t_end": _t(13, 21),
     "text": "The callsign changes twice within a few minutes while the address stays the same."},
    {"id": "P14", "icao24": "a4b5c6", "t_start": _t(14, 30), "t_end": _t(14, 34),
     "text": "Timestamps are not monotonic: several updates arrive out of order by a few seconds."},
    {"id": "P15", "icao24": "60718f", "t_start": _t(15, 0), "t_end": _t(15, 12),
     "text": "A smooth, noise-free track crosses an area where no other aircraft are reported."},
    {"id": "P16", "icao24": "e7f809", "t_start": _t(16, 45), "t_end": _t(16, 50),
     "text": "Reported vertical rate indicates a climb, yet the altitude stays flat for the whole window."},
    {"id": "P17", "icao24": "1a2b3c", "t_start": _t(17, 0), "t_end": _t(17, 5),
     "text": "Nearby aircraft on the same receiver show the same dropouts and scatter at the same time."},
    {"id": "P18", "icao24": "4d5e6f", "t_start": _t(18, 20), "t_end": _t(18, 24),
     "text": "Position offset grows slowly but stays close to the usual thresholds throughout."},
    {"id": "P19", "icao24": "70819a", "t_start": _t(19, 10), "t_end": _t(19, 18),
     "text": "A second copy of the track appears shifted a few seconds later and about 80 km away."},
    {"id": "P20", "icao24": "b2c3d4", "t_start": _t(20, 0), "t_end": _t(20, 7),
     "text": "The track matches an earlier window but with every altitude value shifted up by a fixed amount."},
]

assert len(DEV_PROMPTS) == 20
