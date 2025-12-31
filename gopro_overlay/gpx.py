import collections
import gzip
from pathlib import Path
from typing import List

import gpxpy

from .dimensions import dimension_from
from .gpmf import GPSFix
from .point import Point
from .timeseries import Timeseries, Entry
from gopro_overlay.point import PintPoint3

# Ajoute accl_x, accl_y, accl_z au namedtuple
GPX = collections.namedtuple("GPX", "time lat lon alt hr cad atemp exhaust_temp power speed accl_x accl_y accl_z calculated_gear lap laptime laptime_str laptype")


def fudge(gpx):
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                data = {
                    "time": point.time,
                    "lat": point.latitude,
                    "lon": point.longitude,
                    "alt": point.elevation,
                    "atemp": None,
                    "exhaust_temp": None,  # ← AJOUTE
                    "hr": None,
                    "cad": None,
                    "power": None,
                    "speed": None,
                    "accl_x": None,
                    "accl_y": None,
                    "accl_z": None,
                    "calculated_gear": None,
                    "lap": None,
                    "laptime": None,
                    "laptime_str": None,
                    "laptype": None
                }

                for extension in point.extensions:
                    for child in extension:
                        tag = child.tag[child.tag.find("}") + 1:] if "}" in child.tag else child.tag

                        if not child.text:
                            continue

                        if tag == "atemp":
                            data["atemp"] = float(child.text)
                        elif tag == "exhaust_temp":  # ← AJOUTE water temp → exhaust
                            data["exhaust_temp"] = float(child.text)
                        elif tag == "hr":
                            data["hr"] = float(child.text)
                        elif tag == "cad":
                            data["cad"] = float(child.text)
                        elif tag == "power":
                            data["power"] = float(child.text)
                        elif tag == "speed":
                            data["speed"] = float(child.text)
                        elif tag == "x":
                            data["accl_x"] = float(child.text)
                        elif tag == "y":
                            data["accl_y"] = float(child.text)
                        elif tag == "z":
                            data["accl_z"] = float(child.text)
                        elif tag == "calculated_gear":
                            data["calculated_gear"] = int(child.text)
                        elif tag == "lap":
                            data["lap"] = int(child.text)
                        elif tag == "laptime":
                            data["laptime"] = float(child.text)
                        elif tag == "laptime_str":
                            data["laptime_str"] = child.text
                        elif tag == "laptype":
                            data["laptype"] = str(child.text)

                yield GPX(**data)


# Dans with_unit() - ajoute l'unité
def with_unit(gpx, units):
    return GPX(
        gpx.time,
        gpx.lat,
        gpx.lon,
        units.Quantity(gpx.alt, units.m) if gpx.alt is not None else None,
        units.Quantity(gpx.hr, units.bpm) if gpx.hr is not None else None,
        units.Quantity(gpx.cad, units.rpm) if gpx.cad is not None else None,
        units.Quantity(gpx.atemp, units.celsius) if gpx.atemp is not None else None,
        units.Quantity(gpx.exhaust_temp, units.celsius) if gpx.exhaust_temp is not None else None,  # ← AJOUTE
        units.Quantity(gpx.power, units.watt) if gpx.power is not None else None,
        units.Quantity(gpx.speed, units.mps) if gpx.speed is not None else None,
        units.Quantity(gpx.accl_x, units.dimensionless) if gpx.accl_x is not None else None,
        units.Quantity(gpx.accl_y, units.dimensionless) if gpx.accl_y is not None else None,
        units.Quantity(gpx.accl_z, units.dimensionless) if gpx.accl_z is not None else None,
        units.Quantity(gpx.calculated_gear, units.dimensionless) if gpx.calculated_gear is not None else None,
        units.Quantity(gpx.lap, units.dimensionless) if gpx.lap is not None else None,
        units.Quantity(gpx.laptime, units.dimensionless) if gpx.laptime is not None else None,
        units.Quantity(gpx.laptime_str, units.dimensionless) if gpx.laptime_str is not None else None,
        units.Quantity(gpx.laptype, units.dimensionless) if gpx.laptype is not None else None
    )


def load(filepath: Path, units):
    if filepath.suffix == ".gz":
        with gzip.open(filepath, 'rb') as gpx_file:
            return load_xml(gpx_file, units)
    else:
        with filepath.open('r') as gpx_file:
            return load_xml(gpx_file, units)


def load_xml(file_or_str, units) -> List[GPX]:
    gpx = gpxpy.parse(file_or_str)
    return [with_unit(p, units) for p in fudge(gpx)]


def gpx_to_timeseries(gpx: List[GPX], units):
    gpx_timeseries = Timeseries()

    points = [
        Entry(
            point.time,
            point=Point(point.lat, point.lon),
            alt=point.alt,
            hr=point.hr,
            cad=point.cad,
            atemp=point.atemp,
            exhaust_temp=point.exhaust_temp,  # ← AJOUTE
            power=point.power,
            speed=point.speed,
            accl=PintPoint3(
                x=point.accl_x,
                y=point.accl_y,
                z=point.accl_z,
            ) if point.accl_x is not None else None,
            packet=units.Quantity(index),
            packet_index=units.Quantity(0),
            gpsfix=GPSFix.LOCK_3D.value,
            gpslock=units.Quantity(GPSFix.LOCK_3D.value),
            calculated_gear=point.calculated_gear,
            lap=point.lap,
            laptime=point.laptime,
            laptime_str=point.laptime_str,
            laptype=point.laptype
        )
        for index, point in enumerate(gpx)
    ]

    gpx_timeseries.add(*points)
    return gpx_timeseries


def load_timeseries(filepath: Path, units) -> Timeseries:
    return gpx_to_timeseries(load(filepath, units), units)