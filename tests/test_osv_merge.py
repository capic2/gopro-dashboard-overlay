from datetime import datetime, timedelta, timezone

import pytest
import osv_merge

from osv_merge import apply_gpx_offset
from osv_merge import adjusted_first_gpx_at
from osv_merge import calculate_vertical_speeds
from osv_merge import default_first_gpx_at
from osv_merge import merge_by_timestamp
from osv_merge import points_duration_seconds
from osv_merge import preferred_osv_source
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


def test_preferred_osv_source_uses_smaller_companion_lrf(tmp_path):
    osv_file = tmp_path / 'segment.OSV'
    lrf_file = tmp_path / 'segment.LRF'
    osv_file.write_bytes(b'large-osv')
    lrf_file.write_bytes(b'lrf')

    assert preferred_osv_source(osv_file) == lrf_file


def test_preferred_osv_source_falls_back_to_osv_without_lrf(tmp_path):
    osv_file = tmp_path / 'segment.OSV'
    osv_file.write_bytes(b'osv')

    assert preferred_osv_source(osv_file) == osv_file


def test_vertical_speed_smooths_short_intervals():
    points = [
        gpx_point(0, 100),
        gpx_point(1, 101),
        gpx_point(2, 102),
        gpx_point(3, 109),
        gpx_point(4, 116),
    ]

    vspeeds = calculate_vertical_speeds(points)

    assert vspeeds[1] is None
    assert vspeeds[3] == pytest.approx(3.0)
    assert vspeeds[4] == pytest.approx(5.0)


def test_vertical_speed_changes_sign_after_the_smoothing_window():
    points = [
        gpx_point(0, 100),
        gpx_point(1, 102),
        gpx_point(2, 101),
        gpx_point(3, 99),
    ]

    assert calculate_vertical_speeds(points) == [None, None, None, pytest.approx(-1 / 3)]


def test_vertical_speed_keeps_real_values_above_old_five_mps_limit():
    points = [
        gpx_point(0, 100),
        gpx_point(3, 124),
        gpx_point(4, 132),
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


def test_auto_align_prefers_gpx_samples_over_a_range_only_overlap_tie(capsys):
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    gpx_points = [
        gpx_point(12 * 3600 + 47 * 60 + 3, 100),
        gpx_point(12 * 3600 + 48 * 60, 101),
        gpx_point(13 * 3600 + 46, 102),
        gpx_point(13 * 3600 + 28 * 60 + 32, 103),
        gpx_point(13 * 3600 + 28 * 60 + 35, 104),
    ]
    osv_start = base_time + timedelta(hours=13, minutes=47, seconds=50)
    osv_points = [osv_point(osv_start, second) for second in range(830)]

    osv_merge.auto_align_osv_time(osv_points, gpx_points)

    # UTC+00:45 and UTC+01:00 both have the same full range overlap, but only
    # UTC+01:00 puts OSV samples in the first GPX segment before its long gap.
    assert osv_points[0]['time'] == base_time + timedelta(hours=12, minutes=47, seconds=50)
    assert 'UTC+01:00' in capsys.readouterr().out


def test_auto_align_does_not_score_gpx_points_outside_candidate_range():
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    osv_start = base_time + timedelta(hours=15)
    gpx_points = [
        gpx_point(14 * 3600 + 45 * 60, 100),
        gpx_point(14 * 3600 + 50 * 60, 101),
        gpx_point(14 * 3600 + 59 * 60 + 59.5, 102),
        gpx_point(15 * 3600 + 10 * 60, 103),
    ]
    osv_points = [
        osv_point(osv_start, second)
        for second in range(10 * 60 + 1)
    ]

    osv_merge.auto_align_osv_time(osv_points, gpx_points)

    # UTC would incorrectly tie UTC+00:15 if the 14:59:59.5 point were
    # counted via tolerance despite falling outside the UTC candidate range.
    assert osv_points[0]['time'] == base_time + timedelta(hours=14, minutes=45)


def test_auto_align_scores_only_gpx_points_inside_forced_video_window():
    video_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    gpx_points = [
        gpx_point(0, 100),
        gpx_point(5, 101),
        gpx_point(10, 102),
        gpx_point(900, 103),
        gpx_point(1500, 104),
    ]
    osv_points = [
        osv_point(video_start, 0),
        osv_point(video_start, 600),
    ]

    osv_merge.auto_align_osv_time(
        osv_points,
        gpx_points,
        video_duration=10,
        first_gpx_at=0,
    )

    assert osv_points[0]['time'] == video_start


def test_merge_uses_nearest_sample_across_multiple_osv_segments():
    video_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first_segment = [osv_point(video_start, second) for second in range(0, 3)]
    second_segment = [osv_point(video_start, second) for second in range(10, 13)]
    second_segment[-1]['g_force'] = 2.0
    gpx_points = [gpx_point(11.4, 100)]

    merged = merge_by_timestamp(
        first_segment + second_segment,
        gpx_points,
        sync_mode='absolute',
        fill_osv_gap=False,
    )

    assert merged[0]['g_force'] == pytest.approx(2.0)


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


def test_empty_merge_reports_time_ranges_without_dividing_by_zero(monkeypatch, capsys):
    video_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    osv_points = [osv_point(video_start, 0), osv_point(video_start, 10)]
    gpx_points = [gpx_point(30, 100), gpx_point(40, 110)]
    monkeypatch.setattr(osv_merge, 'select_osv_only_points', lambda *_args: [])

    merged = merge_by_timestamp(
        osv_points,
        gpx_points,
        sync_mode='absolute',
        fill_osv_gap=True,
        video_duration=10,
    )

    output = capsys.readouterr().out
    assert merged == []
    assert 'ZeroDivisionError' not in output
    assert 'Aucun point conservé' in output
    assert (
        'GPX=2026-01-01 00:00:30+00:00 → 2026-01-01 00:00:40+00:00'
        in output
    )
    assert (
        'OSV=2026-01-01 00:00:00+00:00 → 2026-01-01 00:00:10+00:00'
        in output
    )
    assert (
        'fenêtre vidéo=2026-01-01 00:00:00+00:00 → '
        '2026-01-01 00:00:10+00:00' in output
    )
    assert 'points GPX dans la fenêtre=0/2' in output


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
    )

    assert merged[0]['time'] == video_start
    assert merged[0]['source'] == 'osv-only'
    assert merged[0]['lat'] == pytest.approx(47.0)
    assert merged[0]['lon'] == pytest.approx(6.0)
    assert video_start + timedelta(seconds=3) in [point['time'] for point in merged]


def test_gpx_offset_positive_uses_normal_gap_fill_after_shift():
    video_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    osv_points = [osv_point(video_start, second) for second in range(0, 21)]
    gpx_points = [
        gpx_point(0, 100),
        gpx_point(20, 120),
    ]

    apply_gpx_offset(gpx_points, 14)
    merged = merge_by_timestamp(
        osv_points,
        gpx_points,
        sync_mode='absolute',
        fill_osv_gap=True,
        video_duration=20,
    )

    fill_points = [point for point in merged if point.get('source') == 'osv-only']

    assert [point['time'] for point in fill_points] == [
        video_start + timedelta(seconds=second) for second in range(14)
    ]
    assert all(point['lat'] == pytest.approx(47.0) for point in fill_points)
    assert video_start + timedelta(seconds=14) in [point['time'] for point in merged]


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


def test_gpx_start_positive_offset_uses_normal_first_gpx_at_after_shift():
    gpx_points = [
        gpx_point(0, 100),
        gpx_point(5, 105),
    ]
    apply_gpx_offset(gpx_points, 3)
    first_gpx_at = adjusted_first_gpx_at('gpx-start', 10, gpx_points, 3)
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
        first_gpx_at=first_gpx_at,
    )

    assert merged[0]['time'] == video_start
    assert merged[0]['source'] == 'static-before'
    assert first_gpx_at == pytest.approx(8)
    assert gpx_points[0]['time'] in [point['time'] for point in merged]


def test_gpx_start_negative_offset_uses_normal_first_gpx_at_after_shift():
    gpx_points = [
        gpx_point(3, 100),
        gpx_point(8, 105),
    ]
    apply_gpx_offset(gpx_points, -3)

    assert adjusted_first_gpx_at('gpx-start', 10, gpx_points, -3) == pytest.approx(2)


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
