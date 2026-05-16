import datetime
from pathlib import Path

import pytest

from gopro_overlay.dimensions import Dimension
from gopro_overlay.arguments import video_arg, video_args
from gopro_overlay.entry import Entry as FrameEntry
from gopro_overlay.ffmpeg import FFMPEG
from gopro_overlay.framemeta import FrameMeta
from gopro_overlay.layout_components import metric_value
from gopro_overlay.layout_xml import metric_accessor_from, date_formatter_from, Converters, quantity_formatter_for
from gopro_overlay.layout_xml import layout_from_xml
from gopro_overlay.timeseries import Entry
from gopro_overlay.timeunits import timeunits
from gopro_overlay.units import units
from gopro_overlay.widgets.video import Video, VideoFrameSource
from test_timeseries import datetime_of


def test_metric_accessor_speed():
    speed = units.Quantity(10, units.mph)
    cspeed = units.Quantity(20, units.mph)
    entry = Entry(datetime_of(0), speed=speed, cspeed=cspeed)

    assert metric_accessor_from("speed")(entry) == speed
    assert metric_accessor_from("cspeed")(entry) == cspeed

def test_metric_accessor_respiration():
    resp = units.Quantity(10, units.brpm)
    entry = Entry(datetime_of(0), respiration=resp)

    assert metric_accessor_from("respiration")(entry) == resp

def test_metric_accessor_gears():
    front = units.Quantity(5)
    back = units.Quantity(10)
    entry = Entry(datetime_of(0), gear_front=front, gear_rear=back)

    assert metric_accessor_from("gear.front")(entry) == front
    assert metric_accessor_from("gear.rear")(entry) == back


def test_metric_accessor_speed_fallback():
    cspeed = units.Quantity(20, units.mph)
    entry = Entry(datetime_of(0), cspeed=cspeed)

    assert metric_accessor_from("speed")(entry) == cspeed


def test_metric_none_after_conversion():
    speed = units.Quantity(0, units.mph)

    converters = Converters()

    entry = Entry(datetime_of(1), speed=speed)

    some_default_value = 123

    value = metric_value(
        lambda: entry,
        accessor=metric_accessor_from("speed"),
        converter=converters.converter("pace"),
        formatter=lambda q: q.m,
        default=some_default_value
    )

    assert value() == some_default_value


def test_formatting():
    assert (quantity_formatter_for("pace", None)((1 / units.Quantity("60 mph")).to("pace_miles"))) == "1:00"
    assert (quantity_formatter_for("pace", None)((1 / units.Quantity("30 mph")).to("pace_miles"))) == "2:00"


def test_date_formatter():
    entry = lambda: Entry(datetime_of(1644606742))

    utc = datetime.timezone.utc
    # timezone doesn't really want to be called externally..., and don't want to depend on pytz
    sort_of_pst = datetime.timezone.__new__(datetime.timezone, datetime.timedelta(hours=-8), "Bodge/PST")

    # Will just have to accept that calling with tz=None will do local tz, as its cached in datetime.py
    assert date_formatter_from(entry, "%Y/%m/%d %H:%M:%S.%f", tz=utc)() == "2022/02/11 19:12:22.000000"
    assert date_formatter_from(entry, "%Y/%m/%d %H:%M:%S.%f", tz=sort_of_pst)() == "2022/02/11 11:12:22.000000"


def test_video_component_from_xml():
    framemeta = FrameMeta()
    framemeta.add(timeunits(seconds=0), FrameEntry(datetime_of(0)))

    create = layout_from_xml(
        '<layout><component type="video" file="pip.mp4" width="320" height="180" fit="contain" offset="1.5" /></layout>',
        renderer=None,
        framemeta=framemeta,
        font=None,
        privacy=None,
        ffmpeg=FFMPEG(binary="ffmpeg-test"),
    )

    root = create(lambda: framemeta.get(framemeta.min))[0]
    video = root.widgets[0]

    assert isinstance(video, Video)
    assert video.source.filepath == Path("pip.mp4")
    assert video.source.dimensions == Dimension(320, 180)
    assert video.source.fit == "contain"


def test_video_component_requires_dimensions():
    framemeta = FrameMeta()
    framemeta.add(timeunits(seconds=0), FrameEntry(datetime_of(0)))

    create = layout_from_xml(
        '<layout><component type="video" file="pip.mp4" /></layout>',
        renderer=None,
        framemeta=framemeta,
        font=None,
        privacy=None,
    )

    with pytest.raises(IOError, match="either 'size' or both 'width' and 'height'"):
        create(lambda: framemeta.get(framemeta.min))


def test_video_component_uses_command_line_video_path_by_id():
    framemeta = FrameMeta()
    framemeta.add(timeunits(seconds=0), FrameEntry(datetime_of(0)))

    create = layout_from_xml(
        '<layout><component type="video" id="pip" size="220" /></layout>',
        renderer=None,
        framemeta=framemeta,
        font=None,
        privacy=None,
        video={"pip": Path("pip-from-cli.mp4")},
    )

    root = create(lambda: framemeta.get(framemeta.min))[0]
    video = root.widgets[0]

    assert video.source.filepath == Path("pip-from-cli.mp4")


def test_video_component_requires_file_or_command_line_video_path():
    framemeta = FrameMeta()
    framemeta.add(timeunits(seconds=0), FrameEntry(datetime_of(0)))

    create = layout_from_xml(
        '<layout><component type="video" size="220" /></layout>',
        renderer=None,
        framemeta=framemeta,
        font=None,
        privacy=None,
    )

    with pytest.raises(IOError, match="either a 'file' attribute or an 'id'"):
        create(lambda: framemeta.get(framemeta.min))


def test_video_component_requires_matching_command_line_video_id():
    framemeta = FrameMeta()
    framemeta.add(timeunits(seconds=0), FrameEntry(datetime_of(0)))

    create = layout_from_xml(
        '<layout><component type="video" id="pip" size="220" /></layout>',
        renderer=None,
        framemeta=framemeta,
        font=None,
        privacy=None,
        video={"other": Path("other.mp4")},
    )

    with pytest.raises(IOError, match="no matching --video pip=file"):
        create(lambda: framemeta.get(framemeta.min))


def test_video_command_line_args():
    assert video_arg("pip=/tmp/pip.mp4") == ("pip", Path("/tmp/pip.mp4"))
    assert video_args([("pip", Path("pip.mp4")), ("front", Path("front.mp4"))]) == {
        "pip": Path("pip.mp4"),
        "front": Path("front.mp4"),
    }


def test_video_frame_source_filters():
    ffmpeg = FFMPEG(binary="ffmpeg-test")

    cover = VideoFrameSource(ffmpeg, Path("pip.mp4"), Dimension(320, 180), fps=10, fit="cover")
    contain = VideoFrameSource(ffmpeg, Path("pip.mp4"), Dimension(320, 180), fps=10, fit="contain")
    stretch = VideoFrameSource(ffmpeg, Path("pip.mp4"), Dimension(320, 180), fps=10, fit="stretch")

    assert cover._video_filter() == "fps=10,scale=320:180:force_original_aspect_ratio=increase,crop=320:180"
    assert contain._video_filter() == "fps=10,scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2:color=black@0"
    assert stretch._video_filter() == "fps=10,scale=320:180"
