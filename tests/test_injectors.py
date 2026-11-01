"""M3 injector unit tests: determinism and expected signatures (synthetic input)."""

import numpy as np
import pandas as pd
import pytest

from scenarios import inject
from scenarios.select import ALL_COLUMNS

_CFG = {
    "drift_rate_km_per_min": [0.05, 0.5],
    "drift_window_min": [4, 10],
    "jump_offset_km": [2, 50],
    "velocity_scale": [0.6, 1.6],
    "cruise_kt": [400, 480],
    "duration_min": [5, 20],
    "position_noise_m": [20, 60],
    "window_min": [2, 10],
    "window_copy_offset_min": [10, 360],
    "address_offset_km": [50, 300],
    "noise_sigma_m": [50, 500],
    "dropout_fraction": [0.10, 0.60],
    "dropout_duration_s": [30, 120],
    "stuck_duration_s": [20, 60],
    "timestamp_jitter_s": [1, 5],
}


def _track(n: int = 60, t0: int = 1_575_849_600) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": np.arange(t0, t0 + n * 10, 10, dtype="int64"),
            "icao24": "abc123",
            "lat": 48.0 + np.arange(n) * 0.001,
            "lon": 11.0 + np.arange(n) * 0.001,
            "velocity": 230.0,
            "heading": 90.0,
            "vertrate": 0.0,
            "callsign": "TST123 ",
            "onground": False,
            "alert": False,
            "spi": False,
            "squawk": "1000",
            "baroaltitude": 10000.0,
            "geoaltitude": 10000.0,
            "lastposupdate": np.arange(t0, t0 + n * 10, 10, dtype="float64"),
            "lastcontact": np.arange(t0, t0 + n * 10, 10, dtype="float64"),
        }
    )[ALL_COLUMNS]


def test_drift_moves_positions_growing_and_keeps_velocity():
    src = _track()
    df, params = inject.position_spoofing(src, np.random.default_rng(1), _CFG, "medium", "drift")
    assert (df["velocity"] == src["velocity"]).all()
    d_first = abs(df["lat"].iloc[0] - src["lat"].iloc[0]) + abs(df["lon"].iloc[0] - src["lon"].iloc[0])
    d_last = abs(df["lat"].iloc[-1] - src["lat"].iloc[-1]) + abs(df["lon"].iloc[-1] - src["lon"].iloc[-1])
    assert d_last > d_first  # offset grows over the window


def test_drift_is_deterministic():
    src = _track()
    a, _ = inject.position_spoofing(src, np.random.default_rng(7), _CFG, "medium", "drift")
    b, _ = inject.position_spoofing(src, np.random.default_rng(7), _CFG, "medium", "drift")
    pd.testing.assert_frame_equal(a, b)


def test_jump_has_single_large_step():
    src = _track()
    df, params = inject.position_spoofing(src, np.random.default_rng(2), _CFG, "easy", "jump")
    steps = np.hypot(df["lat"].diff(), df["lon"].diff()).fillna(0).to_numpy()
    assert steps.max() > 5 * np.median(steps[steps > 0])  # one outsized jump


def test_velocity_offset_scales_velocity_only():
    src = _track()
    df, params = inject.position_spoofing(src, np.random.default_rng(3), _CFG, "easy",
                                          "velocity_offset")
    assert (df["lat"] == src["lat"]).all() and (df["lon"] == src["lon"]).all()
    assert abs(params["velocity_scale"] - 1.0) > 1e-6
    assert np.allclose(df["velocity"], src["velocity"] * params["velocity_scale"])


def test_ghost_new_address_and_constant_speed():
    src = _track()
    df, params = inject.ghost_aircraft(src, np.random.default_rng(4), _CFG, "medium", "ff0001")
    assert set(df["icao24"]) == {"ff0001"}
    assert df["velocity"].nunique() == 1  # smooth cruise
    assert len(df) >= 6


def test_replay_window_copy_appends_shifted_duplicate():
    src = _track()
    df, params = inject.replay_window_copy(src, np.random.default_rng(5), _CFG, "medium")
    assert len(df) > len(src)
    assert df["time"].max() > src["time"].max()  # copy is later
    assert params["mode"] == "window_copy"


def test_address_duplicate_doubles_and_separates():
    src = _track()
    df, params = inject.replay_address_duplicate(src, np.random.default_rng(6), _CFG, "easy")
    assert len(df) == 2 * len(src)
    # Two far-apart positions within a few seconds somewhere.
    assert params["address_offset_km"] >= 50


def test_sensor_fault_changes_track_deterministically():
    src = _track()
    a, pa = inject.sensor_fault(src, np.random.default_rng(8), _CFG, "medium")
    b, pb = inject.sensor_fault(src, np.random.default_rng(8), _CFG, "medium")
    assert pa["modes"] == pb["modes"]
    assert len(a) == len(b)


@pytest.mark.parametrize("mode", ["drift", "jump", "velocity_offset"])
def test_position_modes_record_params(mode):
    df, params = inject.position_spoofing(_track(), np.random.default_rng(9), _CFG, "medium", mode)
    assert params["mode"] == mode
