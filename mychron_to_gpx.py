#!/usr/bin/env python3
"""
Script de conversion MyChron 5 → GPX pour gopro-dashboard-overlay
Version: 3.3 - Avec merge GPX externe (heart rate)
"""

import csv
from datetime import datetime, timedelta
import sys
import os
import xml.etree.ElementTree as ET
from typing import Optional, Dict, List, Tuple


def parse_external_gpx_hr(gpx_file: str) -> Dict[datetime, float]:
    """
    Parse un GPX externe et extrait les données de heart rate avec timestamps

    Returns:
        Dict[datetime, float]: {timestamp: heart_rate_bpm}
    """
    print(f"\n📂 Lecture GPX externe pour heart rate : {gpx_file}")

    hr_data = {}

    try:
        tree = ET.parse(gpx_file)
        root = tree.getroot()

        # Namespaces GPX/Garmin
        ns = {
            'gpx': 'http://www.topografix.com/GPX/1/1',
            'gpxtpx': 'http://www.garmin.com/xmlschemas/TrackPointExtension/v2',
            'gpxtpx1': 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1'
        }

        # Cherche tous les trackpoints
        for trkpt in root.findall('.//gpx:trkpt', ns):
            time_elem = trkpt.find('gpx:time', ns)
            if time_elem is None:
                continue

            # Parse le timestamp
            time_str = time_elem.text
            try:
                # Format ISO8601
                timestamp = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            except:
                continue

            # Cherche heart rate dans les extensions
            hr = None
            extensions = trkpt.find('gpx:extensions', ns)
            if extensions is not None:
                # TrackPointExtension v2
                tpx = extensions.find('gpxtpx:TrackPointExtension', ns)
                if tpx is not None:
                    hr_elem = tpx.find('gpxtpx:hr', ns)
                    if hr_elem is not None:
                        try:
                            hr = float(hr_elem.text)
                        except:
                            pass

                # TrackPointExtension v1 (fallback)
                if hr is None:
                    tpx1 = extensions.find('gpxtpx1:TrackPointExtension', ns)
                    if tpx1 is not None:
                        hr_elem = tpx1.find('gpxtpx1:hr', ns)
                        if hr_elem is not None:
                            try:
                                hr = float(hr_elem.text)
                            except:
                                pass

            if hr is not None:
                hr_data[timestamp] = hr

        print(f"✅ {len(hr_data)} points avec heart rate trouvés")

        if hr_data:
            hr_values = list(hr_data.values())
            print(f"   • HR min  : {min(hr_values):.0f} bpm")
            print(f"   • HR max  : {max(hr_values):.0f} bpm")
            print(f"   • HR moy  : {sum(hr_values) / len(hr_values):.0f} bpm")

        return hr_data

    except Exception as e:
        print(f"⚠️  Erreur lecture GPX externe : {e}")
        return {}


def interpolate_hr(timestamp: datetime, hr_data: Dict[datetime, float]) -> Optional[float]:
    """
    Interpole la fréquence cardiaque pour un timestamp donné

    Args:
        timestamp: Timestamp pour lequel on veut le HR
        hr_data: Dictionnaire {timestamp: hr}

    Returns:
        Heart rate interpolée ou None
    """
    if not hr_data:
        return None

    timestamps = sorted(hr_data.keys())

    # Si timestamp exact
    if timestamp in hr_data:
        return hr_data[timestamp]

    # Cherche les deux points encadrants
    before = None
    after = None

    for ts in timestamps:
        if ts <= timestamp:
            before = ts
        elif ts > timestamp and after is None:
            after = ts
            break

    # Pas de données disponibles
    if before is None and after is None:
        return None

    # Avant le premier point
    if before is None:
        return hr_data[after]

    # Après le dernier point
    if after is None:
        return hr_data[before]

    # Interpolation linéaire
    hr_before = hr_data[before]
    hr_after = hr_data[after]

    time_total = (after - before).total_seconds()
    time_elapsed = (timestamp - before).total_seconds()

    if time_total == 0:
        return hr_before

    ratio = time_elapsed / time_total
    hr_interpolated = hr_before + (hr_after - hr_before) * ratio

    return hr_interpolated


def parse_mychron_metadata(csv_file):
    """Parse les métadonnées de session du CSV MyChron, incluant les données de tours"""
    metadata = {}
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i >= 13:
                break
            if len(row) >= 2:
                key = row[0].strip('"')
                if key in ['Beacon Markers', 'Segment Times']:
                    metadata[key] = [val.strip('"') for val in row[1:] if val.strip('"')]
                else:
                    value = row[1].strip('"') if len(row) > 1 else ""
                    metadata[key] = value
    return metadata


def parse_lap_data(metadata):
    """Parse les données de tours depuis les métadonnées"""
    beacon_markers = []
    segment_times = []
    segment_times_str = []

    if 'Beacon Markers' in metadata:
        for marker in metadata['Beacon Markers']:
            try:
                beacon_markers.append(float(marker))
            except ValueError:
                continue

    if 'Segment Times' in metadata:
        for time_str in metadata['Segment Times']:
            try:
                segment_times_str.append(time_str)
                parts = time_str.split(':')
                if len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = float(parts[1])
                    total_seconds = minutes * 60 + seconds
                    segment_times.append(total_seconds)
            except (ValueError, IndexError):
                continue

    return beacon_markers, segment_times, segment_times_str


def get_lap_info(time_s, beacon_markers, segment_times, segment_times_str):
    """Détermine les informations de tour pour un timestamp donné"""
    if not beacon_markers or not segment_times:
        return None, None, None, None

    lap_number = 0
    for i, marker in enumerate(beacon_markers):
        if time_s >= marker:
            lap_number = i + 1
        else:
            break

    if lap_number >= len(beacon_markers):
        lap_number = len(beacon_markers) - 1

    lap_time = segment_times[lap_number] if lap_number < len(segment_times) else None
    lap_time_str = segment_times_str[lap_number] if lap_number < len(segment_times_str) else None

    if lap_number == 0:
        lap_type = 'OUT'
    elif lap_number == len(segment_times) - 1:
        lap_type = 'IN'
    else:
        lap_type = 'TIMED'

    return lap_number, lap_time, lap_time_str, lap_type


def parse_datetime_from_metadata(metadata):
    """Convertit la date/heure du MyChron en datetime Python"""
    try:
        date_str = metadata.get('Date', '')
        time_str = metadata.get('Time', '')

        if not date_str or not time_str:
            return None

        date_parts = date_str.split(', ')
        if len(date_parts) >= 2:
            month_day_year = ', '.join(date_parts[1:])
            datetime_str = f"{month_day_year} {time_str}"

            formats_to_try = [
                "%B %d, %Y %I:%M %p",
                "%B %d, %Y %I:%M:%S %p",
                "%B %d, %Y %H:%M",
                "%B %d, %Y %H:%M:%S",
            ]

            for fmt in formats_to_try:
                try:
                    dt = datetime.strptime(datetime_str, fmt)
                    print(f"✅ Date parsée : {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    return dt
                except ValueError:
                    continue

        print(f"⚠️  Impossible de parser la date")
        return None

    except Exception as e:
        print(f"❌ Erreur parsing date : {e}")
        return None


def mychron_to_gpx(csv_file, output_gpx, start_datetime=None, external_gpx=None):
    """
    Convertit un CSV MyChron 5 en GPX avec extensions Garmin et données de tours

    Args:
        csv_file: Fichier CSV MyChron
        output_gpx: Fichier GPX de sortie
        start_datetime: Datetime de départ (optionnel)
        external_gpx: GPX externe pour merger heart rate (optionnel)
    """
    print(f"\n📂 Lecture du fichier : {csv_file}")

    # Parse métadonnées
    metadata = parse_mychron_metadata(csv_file)

    if start_datetime is None:
        start_datetime = parse_datetime_from_metadata(metadata)

    if start_datetime is None:
        print("\n⚠️  Heure de départ non détectée - utilisation heure actuelle")
        start_datetime = datetime.now()

    # ✅ Parse GPX externe pour heart rate
    hr_data = {}
    if external_gpx and os.path.exists(external_gpx):
        hr_data = parse_external_gpx_hr(external_gpx)

    # Parse les données de tours
    beacon_markers, segment_times, segment_times_str = parse_lap_data(metadata)

    print(f"\n📋 Informations de session :")
    print(f"   • Session    : {metadata.get('Session', 'Unknown')}")
    print(f"   • Véhicule   : {metadata.get('Vehicle', 'Unknown')}")
    print(f"   • Pilote     : {metadata.get('Racer', 'Unknown')}")
    print(f"   • Date/Heure : {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   • Durée      : {metadata.get('Duration', 'Unknown')}s")

    if beacon_markers and segment_times:
        total_laps = len(segment_times)
        timed_laps = total_laps - 2
        print(f"\n🏁 Données de tours :")
        print(f"   • Total tours    : {total_laps}")
        print(f"   • Tours chronos  : {timed_laps}")

        if timed_laps > 0:
            print(f"   • Temps des tours:")
            for i in range(1, len(segment_times) - 1):
                lap_time = segment_times[i]
                print(f"     - Tour {i}: {lap_time:.3f}s")

            timed_lap_times = segment_times[1:-1] if len(segment_times) > 2 else []
            if timed_lap_times:
                best_lap = min(timed_lap_times)
                best_lap_num = segment_times.index(best_lap)
                print(f"   • Meilleur tour  : Tour {best_lap_num} - {best_lap:.3f}s")

    print(f"\n🔄 Création du GPX...")

    # Construit le XML
    gpx_lines = []
    gpx_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    gpx_lines.append('<gpx version="1.1" creator="MyChron5-GPX-Converter-v3.3"')
    gpx_lines.append('  xmlns="http://www.topografix.com/GPX/1/1"')
    gpx_lines.append('  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')
    gpx_lines.append('  xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v2"')
    gpx_lines.append('  xmlns:gpxpx="http://www.garmin.com/xmlschemas/GpxExtensions/v3"')
    gpx_lines.append(
        '  xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">')

    gpx_lines.append('  <metadata>')
    gpx_lines.append(f'    <name>{metadata.get("Session", "MyChron Session")}</name>')
    gpx_lines.append(f'    <desc>{metadata.get("Vehicle", "")} - {metadata.get("Racer", "")}</desc>')
    gpx_lines.append('  </metadata>')

    gpx_lines.append('  <trk>')
    gpx_lines.append('    <trkseg>')

    # Parse les données
    nbr_point_count = 0
    hr_merged_count = 0

    with open(csv_file, 'r', encoding='utf-8') as f:
    # Skip jusqu'aux en-têtes
        for _ in range(14):
            next(f)

            headers_line = next(f)
            headers = [h.strip('"') for h in headers_line.strip().split(',')]
            next(f)  # Skip unités

            reader = csv.DictReader(f, fieldnames=headers)

            for row in reader:
                try:
                    time_s = float(row['Time'])
                    lat = float(row['GPS Latitude'])
                    lon = float(row['GPS Longitude'])

                    if abs(lat) < 0.001 and abs(lon) < 0.001:
                        continue

                    # Timestamp
                    point_time = start_datetime + timedelta(seconds=time_s)
                    time_str = point_time.isoformat() + 'Z'

                    # Données de base
                    ele = float(row.get('GPS Altitude', 0))
                    speed = float(row.get('GPS Speed', 0)) / 3.6
                    rpm = float(row.get('RPM', 0))
                    water_temp = float(row.get('Water Temp', 0))
                    exhaust_temp = float(row.get('Exhaust Temp', 0))
                    calculated_gear = float(row.get('Calculated Gear', 0))

                    lat_accel = float(row.get('GPS LatAcc', 0))
                    lon_accel = float(row.get('GPS LonAcc', 0))

                    accel_x = float(row.get('AccelerometerX', 0))
                    accel_y = float(row.get('AccelerometerY', 0))
                    accel_z = float(row.get('AccelerometerZ', 0))

                    lap_number, lap_time, lap_time_str, lap_type = get_lap_info(
                        time_s, beacon_markers, segment_times, segment_times_str
                    )

                    # ✅ Interpoler heart rate depuis GPX externe
                    hr = None
                    if hr_data:
                        hr = interpolate_hr(point_time, hr_data)
                        if hr is not None:
                            hr_merged_count += 1

                    # Point GPX
                    gpx_lines.append(f'      <trkpt lat="{lat}" lon="{lon}">')
                    gpx_lines.append(f'        <ele>{ele}</ele>')
                    gpx_lines.append(f'        <time>{time_str}</time>')

                    gpx_lines.append('        <extensions>')
                    gpx_lines.append('          <gpxtpx:TrackPointExtension>')

                    gpx_lines.append(f'            <gpxtpx:speed>{speed:.6f}</gpxtpx:speed>')
                    gpx_lines.append(f'            <gpxtpx:atemp>{water_temp:.2f}</gpxtpx:atemp>')
                    gpx_lines.append(f'            <gpxtpx:exhaust_temp>{exhaust_temp:.2f}</gpxtpx:exhaust_temp>')
                    gpx_lines.append(f'            <gpxtpx:cad>{int(rpm)}</gpxtpx:cad>')
                    gpx_lines.append(f'            <gpxtpx:calculated_gear>{int(calculated_gear)}</gpxtpx:calculated_gear>')

                    # ✅ Ajouter heart rate si disponible
                    if hr is not None:
                        gpx_lines.append(f'            <gpxtpx:hr>{int(hr)}</gpxtpx:hr>')

                    if lap_number is not None:
                        gpx_lines.append(f'            <gpxtpx:lap>{lap_number}</gpxtpx:lap>')
                    if lap_time is not None:
                        gpx_lines.append(f'            <gpxtpx:laptime>{lap_time:.3f}</gpxtpx:laptime>')
                    if lap_time_str is not None:
                        gpx_lines.append(f'            <gpxtpx:laptime_str>{lap_time_str}</gpxtpx:laptime_str>')
                    if lap_type is not None:
                        gpx_lines.append(f'            <gpxtpx:laptype>{lap_type}</gpxtpx:laptype>')

                    gpx_lines.append('          </gpxtpx:TrackPointExtension>')

                    gpx_lines.append('          <gpxpx:Acceleration>')
                    gpx_lines.append(f'            <gpxpx:x>{accel_x:.6f}</gpxpx:x>')
                    gpx_lines.append(f'            <gpxpx:y>{accel_y:.6f}</gpxpx:y>')
                    gpx_lines.append(f'            <gpxpx:z>{accel_z:.6f}</gpxpx:z>')
                    gpx_lines.append('          </gpxpx:Acceleration>')

                    gpx_lines.append('        </extensions>')
                    gpx_lines.append('      </trkpt>')

                    nbr_point_count += 1

                except (ValueError, KeyError):
                    continue

    gpx_lines.append('    </trkseg>')
    gpx_lines.append('  </trk>')
    gpx_lines.append('</gpx>')

    # Sauvegarde
    with open(output_gpx, 'w', encoding='utf-8') as f:
        f.write('\n'.join(gpx_lines))

    print(f"\n✅ GPX créé : {output_gpx}")
    print(f"📊 {nbr_point_count} points GPS exportés")
    if hr_data:
        print(f"❤️  {hr_merged_count} points avec heart rate mergés ({hr_merged_count / nbr_point_count * 100:.1f}%)")

    return output_gpx, nbr_point_count


def print_usage():
    """Affiche l'aide"""
    print("""
╔════════════════════════════════════════════════════════════════╗
║  MyChron 5 → GPX Converter (pour gopro-dashboard-overlay)     ║
║  Version 3.3 - Avec merge GPX externe (heart rate)            ║
╚════════════════════════════════════════════════════════════════╝

Usage:
    python mychron_to_gpx.py <mychron.csv> [--merge-gpx <external.gpx>]

Exemples:
    # Sans merge
    python mychron_to_gpx.py 8.csv

    # Avec merge heart rate
    python mychron_to_gpx.py 8.csv --merge-gpx gopro_data.gpx

Options:
    --merge-gpx <file>  GPX externe contenant heart rate à merger
    """)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    mychron_csv = sys.argv[1]
    external_gpx = None

    # Parse arguments
    if '--merge-gpx' in sys.argv:
        idx = sys.argv.index('--merge-gpx')
        if idx + 1 < len(sys.argv):
            external_gpx = sys.argv[idx + 1]

    if not os.path.exists(mychron_csv):
        print(f"❌ Fichier CSV introuvable : {mychron_csv}")
        sys.exit(1)

    if external_gpx and not os.path.exists(external_gpx):
        print(f"⚠️  GPX externe introuvable : {external_gpx}")
        external_gpx = None

    base_name = os.path.splitext(mychron_csv)[0]
    output_gpx = f"{base_name}.gpx"

    print("\n" + "=" * 70)
    print("🏁 MyChron 5 → GPX Converter v3.3".center(70))
    print("=" * 70)

    # Conversion
    result_gpx, point_count = mychron_to_gpx(mychron_csv, output_gpx, external_gpx=external_gpx)

    if point_count == 0:
        print("\n❌ Aucun point GPS valide trouvé")
        sys.exit(1)

    # Résumé
    print("\n" + "=" * 70)
    print("🎉 Conversion terminée !".center(70))
    print("=" * 70)
    print(f"\n📁 Fichier : {result_gpx}")
    print(f"📊 Points  : {point_count}")

    print("\n" + "-" * 70)
    print("💡 Données disponibles :")
    print("-" * 70)
    print("  • speed      - Vitesse GPS")
    print("  • temp       - Température eau")
    print("  • cadence    - RPM moteur")
    print("  • hr         - Heart rate (si mergé)")
    print("  • accl.x/y/z - Accélérations (g)")
    print("  • lap        - Numéro de tour")
    print("  • laptime    - Temps du tour (s)")
    print("  • laptype    - Type (OUT/TIMED/IN)")
    print("\n" + "-" * 70)
    print("💡 Commande gopro-dashboard-overlay :")
    print("-" * 70)
    print(f"gopro-dashboard.py --gpx {result_gpx} --gpx-merge OVERWRITE \\")
    print(f"    --input ta_video.MP4 --output overlay.MP4 \\")
    print(f"    --layout karting.xml")
    print("\n" + "=" * 70 + "\n")