from datetime import datetime, timedelta, timezone

import pytest

from osv_merge import calculate_vertical_speeds


def gpx_point(seconds, ele):
    return {
        'time': datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds),
        'ele': ele,
    }


def test_vertical_speed_uses_centered_local_slope_without_lag():
    points = [
        gpx_point(0, 100),
        gpx_point(1, 101),
        gpx_point(2, 102),
        gpx_point(3, 109),
        gpx_point(4, 116),
    ]

    vspeeds = calculate_vertical_speeds(points)

    assert vspeeds[1] == pytest.approx(1.0)
    assert vspeeds[3] == pytest.approx(7.0)


def test_vertical_speed_keeps_real_values_above_old_five_mps_limit():
    points = [
        gpx_point(0, 100),
        gpx_point(1, 108),
        gpx_point(2, 116),
    ]

    assert calculate_vertical_speeds(points)[1] == pytest.approx(8.0)


def test_vertical_speed_ignores_missing_altitudes():
    points = [
        gpx_point(0, 100),
        gpx_point(1, None),
        gpx_point(2, 104),
    ]

    vspeeds = calculate_vertical_speeds(points)

    assert vspeeds[0] is None
    assert vspeeds[1] is None
    assert vspeeds[2] is None
