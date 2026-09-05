import datetime

import pytest

from gopro_overlay.entry import Entry
from gopro_overlay.point import Point
from gopro_overlay.timeseries import Timeseries
from gopro_overlay.timeseries_process import (
    apply_global_odometer,
    calculate_gradient,
    calculate_odo,
    calculate_speeds,
    process_ses,
)
from gopro_overlay.framemeta import FrameMeta
from gopro_overlay.timeunits import timeunits
from gopro_overlay.units import units


def test_delta_processing():
    ts = Timeseries()
    entry_a = Entry(datetime_of(1), n=1)
    entry_b = Entry(datetime_of(2), n=2)
    ts.add(entry_a)
    ts.add(entry_b)

    ts.process_deltas(lambda a, b, c: {"d": b.n - a.n, "c": c})

    assert entry_a.d == 1
    assert entry_b.d is None
    assert entry_a.c == 1
    assert entry_b.c is None

def test_stepping_through_items():
    ts = Timeseries()
    ts.add(Entry(datetime_of(1), n=1))
    ts.add(Entry(datetime_of(2), n=2))

    stepper = ts.stepper(step=timeunits(seconds=0.1))
    steps = list(stepper.steps())

    assert len(steps) == 11
    assert steps[0] == datetime_of(1)
    assert steps[1] == datetime_of(1.1)
    assert steps[10] == datetime_of(2.0)


def datetime_of(i):
    return datetime.datetime.fromtimestamp(i, tz=datetime.timezone.utc)


def test_processing_with_simple_exp_smoothing():
    ts = Timeseries()
    ts.add(
        Entry(datetime_of(1), n=3),
        Entry(datetime_of(2), n=5),
        Entry(datetime_of(3), n=9),
        Entry(datetime_of(4), n=20),
    )
    ts.process(process_ses("ns", lambda i: i.n, alpha=0.4))

    assert ts.get(datetime_of(1)).ns == 3.0
    assert ts.get(datetime_of(2)).ns == 3.0
    assert ts.get(datetime_of(3)).ns == 3.8
    assert ts.get(datetime_of(4)).ns == 5.88


def test_process_delta_speeds():
    ts = Timeseries()
    ts.add(
        Entry(datetime_of(1), point=Point(51.50186, -0.14056)),
        Entry(datetime_of(61), point=Point(51.50665, -0.12895)),
    )
    ts.process_deltas(calculate_speeds())

    entry = ts.get(datetime_of(1))
    assert entry.time == units.Quantity(60, units.s)
    assert "{0.magnitude:.2f} {0.units}".format(entry.dist) == "966.36 meter"
    assert "{0.magnitude:.2f} {0.units:~P}".format(entry.cspeed) == "16.11 m/s"
    assert "{0.magnitude:.2f} {0.units:~P}".format(entry.azi) == "56.53 deg"
    assert "{0.magnitude:.2f} {0.units:~P}".format(entry.cog) == "56.53 deg"


def metres(n):
    return units.Quantity(n, units.m)


def test_process_gradient():
    processor = calculate_gradient()
    r = processor(
        a=Entry(datetime_of(0), alt=metres(5), point=Point(51.50186, -0.14056)),
        b=Entry(datetime_of(0), alt=metres(6), point=Point(51.50665, -0.12895)),
        c=None
    )
    assert r["cgrad"].magnitude == pytest.approx(0.10348, abs=0.0001)


def test_process_gradient_missing_alt():
    processor = calculate_gradient()
    assert processor(
        a=Entry(datetime_of(0), odo=metres(10)),
        b=Entry(datetime_of(0), alt=metres(6), odo=metres(26)),
        c=None
    ) is None


def test_process_odo():
    processor = calculate_odo()
    r = processor(
        e=Entry(datetime_of(0), alt=metres(5), dist=metres(10)),
    )
    assert r["codo"].magnitude == 10
    r = processor(
        e=Entry(datetime_of(0), alt=metres(5), dist=metres(15)),
    )
    assert r["codo"].magnitude == 25


def test_apply_global_odometer_keeps_distance_continuous_across_a_segment():
    """REGRESSION CONTRACT: split rendering must never restart flight distance.

    Do not weaken, remove, or change this case without explicit user authorization.
    """
    global_timeseries = Timeseries(
        [
            Entry(datetime_of(100), codo=metres(1200)),
            Entry(datetime_of(110), codo=metres(1400)),
        ]
    )
    segment = FrameMeta()
    segment.add(timeunits(seconds=0), Entry(datetime_of(105), codo=metres(0)))
    segment.add(timeunits(seconds=1), Entry(datetime_of(106), codo=metres(10)))

    apply_global_odometer(segment, global_timeseries)

    assert segment.get(timeunits(seconds=0)).codo == metres(1300)
    assert segment.get(timeunits(seconds=1)).codo == metres(1320)
