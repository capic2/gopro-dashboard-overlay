from datetime import datetime, timedelta, timezone

import pytest

from osv_merge import apply_gpx_offset
from osv_merge import adjusted_first_gpx_at
from osv_merge import calculate_vertical_speeds
from osv_merge import default_first_gpx_at
from osv_merge import merge_by_timestamp
from osv_merge import points_duration_seconds
from osv_merge import video_start_time


def gpx_point(seconds, ele):
    return {
        'time': datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds),
        'lat': 47.0,
        'lon': 6.0,
        'ele': ele,
    }


def osv_point(video_start, seconds):
    return {
        'time': video_start + timedelta(seconds=seconds),
        'video_start': video_start,
        'timestamp_offset': seconds,
        'g_force': 1.0,
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


def test_absolute_sync_does_not_invent_first_gpx_offset():
    points = [
        gpx_point(0, 100),
        gpx_point(518, 120),
    ]

    assert default_first_gpx_at('absolute', 548.8, points) is None


def test_gpx_start_sync_keeps_legacy_first_gpx_offset():
    points = [
        gpx_point(0, 100),
        gpx_point(518, 120),
    ]

    assert default_first_gpx_at('gpx-start', 548.8, points) == pytest.approx(30.8)


def test_osv_duration_starts_at_video_create_date_before_first_sample():
    video_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    points = [
        osv_point(video_start, 8),
        osv_point(video_start, 548.8),
    ]

    assert video_start_time(points) == video_start
    assert points_duration_seconds(points) == pytest.approx(548.8)


def test_absolute_sync_trims_gpx_before_video_start():
    video_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    osv_points = [
        osv_point(video_start, 0),
        osv_point(video_start, 20),
    ]
    gpx_points = [
        gpx_point(-5, 90),
        gpx_point(0, 100),
        gpx_point(10, 110),
        gpx_point(25, 120),
    ]

    merged = merge_by_timestamp(
        osv_points,
        gpx_points,
        sync_mode='absolute',
        fill_osv_gap=False,
        video_duration=20,
    )

    assert [point['time'] for point in merged] == [
        video_start,
        video_start + timedelta(seconds=10),
    ]


def test_absolute_sync_fills_when_gpx_starts_after_video_start():
    video_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    osv_points = [
        osv_point(video_start, 8),
        osv_point(video_start, 20),
    ]
    gpx_points = [
        gpx_point(10, 100),
        gpx_point(20, 120),
    ]

    merged = merge_by_timestamp(
        osv_points,
        gpx_points,
        sync_mode='absolute',
        fill_osv_gap=True,
        video_duration=20,
    )

    assert merged[0]['time'] == video_start
    assert merged[0]['source'] == 'static-before'
    assert merged[-1]['time'] == video_start + timedelta(seconds=20)


def test_gpx_offset_positive_delays_gpx_and_fills_video_start():
    video_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    osv_points = [
        osv_point(video_start, 0),
        osv_point(video_start, 10),
    ]
    gpx_points = [
        gpx_point(0, 100),
        gpx_point(5, 105),
    ]

    apply_gpx_offset(gpx_points, 3)
    merged = merge_by_timestamp(
        osv_points,
        gpx_points,
        sync_mode='absolute',
        fill_osv_gap=True,
        video_duration=10,
        gpx_offset=3,
    )

    assert merged[0]['time'] == video_start
    assert merged[0]['source'] == 'gpx-offset-fill'
    assert merged[0]['lat'] == pytest.approx(47.0)
    assert merged[0]['lon'] == pytest.approx(6.0)
    assert video_start + timedelta(seconds=3) in [point['time'] for point in merged]


def test_gpx_offset_positive_delays_real_gpx_points_only():
    gpx_points = [
        gpx_point(0, 100),
        gpx_point(5, 105),
    ]

    apply_gpx_offset(gpx_points, 3)

    assert [point['time'] for point in gpx_points] == [
        datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=3),
        datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=8),
    ]


def test_gpx_start_first_gpx_at_includes_positive_offset():
    gpx_points = [
        gpx_point(0, 100),
        gpx_point(5, 105),
    ]

    assert adjusted_first_gpx_at('gpx-start', 10, gpx_points, 3) == pytest.approx(8)


def test_gpx_start_positive_offset_fills_video_start():
    gpx_points = [
        gpx_point(0, 100),
        gpx_point(5, 105),
    ]
    apply_gpx_offset(gpx_points, 3)
    video_start = datetime(2026, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=5)
    osv_points = [
        osv_point(video_start, 0),
        osv_point(video_start, 10),
    ]

    merged = merge_by_timestamp(
        osv_points,
        gpx_points,
        sync_mode='gpx-start',
        fill_osv_gap=True,
        video_duration=10,
        first_gpx_at=8,
        gpx_offset=3,
    )

    assert merged[0]['time'] == video_start
    assert merged[0]['source'] == 'gpx-offset-fill'
    assert gpx_points[0]['time'] in [point['time'] for point in merged]


def test_gpx_offset_negative_advances_gpx_and_trims_before_video_start():
    video_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    osv_points = [
        osv_point(video_start, 0),
        osv_point(video_start, 10),
    ]
    gpx_points = [
        gpx_point(2, 100),
        gpx_point(5, 105),
    ]

    apply_gpx_offset(gpx_points, -3)
    merged = merge_by_timestamp(
        osv_points,
        gpx_points,
        sync_mode='absolute',
        fill_osv_gap=False,
        video_duration=10,
    )

    assert [point['time'] for point in merged] == [
        video_start + timedelta(seconds=2),
    ]
