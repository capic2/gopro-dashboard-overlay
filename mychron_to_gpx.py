#!/usr/bin/env python3
"""
Script de conversion MyChron 5 → GPX pour gopro-dashboard-overlay
Version: 3.3 - Avec gestion des tours + Heart Rate externe (optionnel)
"""

import csv
from datetime import datetime, timedelta, timezone
import sys
import os
import subprocess
import json


def parse_osv_timing(osv_file):
    """
    Extrait le CreateDate de l'OSV pour synchronisation
    Returns: (create_datetime, duration_seconds)
    """
    print(f"\n🎥 Lecture OSV pour synchronisation : {osv_file}")

    try:
        result = subprocess.run([
            'exiftool',
            '-ee',
            '-G3',
            '-api', 'LargeFileSupport=1',
            '-CreateDate',
            '-Duration',
            '-json',
            osv_file
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            print(f"❌ Erreur exiftool: {result.stderr}")
            return None, None

        data = json.loads(result.stdout)

        if not data:
            return None, None

        metadata = data[0]

        # Extraire CreateDate
        create_date = None
        for key in metadata.keys():
            if 'CreateDate' in key or 'Create Date' in key:
                try:
                    time_str = metadata[key]
                    print(f"   🕐 CreateDate OSV: {time_str}")

                    # Format: "YYYY:MM:DD HH:MM:SS"
                    create_date = datetime.strptime(time_str, '%Y:%m:%d %H:%M:%S')
                    create_date = create_date.replace(tzinfo=timezone.utc)
                    break
                except Exception as e:
                    print(f"   ⚠️  Erreur parsing CreateDate: {e}")

        # Extraire Duration
        duration = None
        if 'Duration' in metadata:
            duration_str = metadata['Duration']
            print(f"   ⏱️  Durée OSV: {duration_str}")

            try:
                parts = duration_str.split(':')
                if len(parts) == 3:
                    hours, minutes, seconds = parts
                    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                elif len(parts) == 2:
                    minutes, seconds = parts
                    duration = int(minutes) * 60 + float(seconds)
                else:
                    duration = float(duration_str)
            except:
                pass

        if create_date:
            print(f"   ✅ OSV synchronisé: {create_date}")
            return create_date, duration
        else:
            print("   ❌ Impossible d'extraire CreateDate de l'OSV")
            return None, None

    except FileNotFoundError:
        print(f"❌ exiftool non trouvé - installez-le pour la synchronisation OSV")
        return None, None
    except Exception as e:
        print(f"❌ Erreur lecture OSV : {e}")
        return None, None


def parse_external_gpx_hr(gpx_file):
    """
    Parse un GPX externe (ex: Amazfit) pour extraire les données de heart rate
    Returns: dict {datetime: hr_value}
    """
    import xml.etree.ElementTree as ET

    print(f"\n💓 Lecture heart rate depuis : {gpx_file}")

    hr_data = {}

    try:
        tree = ET.parse(gpx_file)
        root = tree.getroot()

        # Namespaces
        ns = {
            'gpx': 'http://www.topografix.com/GPX/1/1',
            'ns3': 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1',
            'gpxtpx': 'http://www.garmin.com/xmlschemas/TrackPointExtension/v2'
        }

        # Trouver tous les trackpoints
        for trkpt in root.findall('.//gpx:trkpt', ns):
            time_elem = trkpt.find('gpx:time', ns)

            if time_elem is not None:
                time_str = time_elem.text

                # Parser le timestamp
                try:
                    # Format: 2025-11-08T13:53:47Z
                    point_time = datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%SZ')
                    point_time = point_time.replace(tzinfo=timezone.utc)
                except:
                    try:
                        # Format alternatif: 2025-11-08T13:53:47.000Z
                        point_time = datetime.strptime(time_str.split('.')[0], '%Y-%m-%dT%H:%M:%S')
                        point_time = point_time.replace(tzinfo=timezone.utc)
                    except:
                        continue

                # Chercher HR dans les extensions
                hr = None
                extensions = trkpt.find('gpx:extensions', ns)
                if extensions is not None:
                    # Essayer ns3:hr (Amazfit)
                    tpe = extensions.find('ns3:TrackPointExtension', ns)
                    if tpe is not None:
                        hr_elem = tpe.find('ns3:hr', ns)
                        if hr_elem is not None:
                            try:
                                hr = int(float(hr_elem.text))
                            except:
                                pass

                    # Essayer gpxtpx:hr (Garmin)
                    if hr is None:
                        tpe = extensions.find('gpxtpx:TrackPointExtension', ns)
                        if tpe is not None:
                            hr_elem = tpe.find('gpxtpx:hr', ns)
                            if hr_elem is not None:
                                try:
                                    hr = int(float(hr_elem.text))
                                except:
                                    pass

                if hr is not None and hr > 0:
                    hr_data[point_time] = hr

        print(f"   ✅ {len(hr_data)} points avec heart rate trouvés")
        if hr_data:
            times = sorted(hr_data.keys())
            print(f"   📅 Plage temporelle : {times[0]} → {times[-1]}")
            hrs = list(hr_data.values())
            print(f"   💓 FC min/max/moy : {min(hrs)}/{max(hrs)}/{sum(hrs) // len(hrs)} bpm")

        return hr_data

    except Exception as e:
        print(f"❌ Erreur lecture GPX externe : {e}")
        return {}


def interpolate_hr(target_time, hr_data):
    """
    Interpole le heart rate pour un timestamp donné
    """
    if not hr_data:
        return None

    # Trouver les deux points HR les plus proches
    times = sorted(hr_data.keys())

    # Si target_time est avant le premier point
    if target_time < times[0]:
        # Accepter si décalage < 5 secondes
        if (times[0] - target_time).total_seconds() < 5:
            return hr_data[times[0]]
        return None

    # Si target_time est après le dernier point
    if target_time > times[-1]:
        # Accepter si décalage < 5 secondes
        if (target_time - times[-1]).total_seconds() < 5:
            return hr_data[times[-1]]
        return None

    # Trouver les deux points encadrants
    before = None
    after = None

    for t in times:
        if t <= target_time:
            before = t
        if t >= target_time and after is None:
            after = t
            break

    # Si on a trouvé un point exact
    if before and (target_time - before).total_seconds() == 0:
        return hr_data[before]

    # Si on a deux points encadrants, interpoler
    if before and after:
        time_diff = (after - before).total_seconds()
        if time_diff <= 10:  # N'interpoler que si les points sont proches (< 10s)
            ratio = (target_time - before).total_seconds() / time_diff
            hr_before = hr_data[before]
            hr_after = hr_data[after]
            interpolated_hr = hr_before + (hr_after - hr_before) * ratio
            return int(interpolated_hr)

    # Sinon, prendre le point le plus proche
    if before:
        if (target_time - before).total_seconds() < 5:
            return hr_data[before]

    return None


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
    """
    Parse les données de tours depuis les métadonnées
    Retourne: (beacon_markers, segment_times, segment_times_str)
    """
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
    """
    Détermine les informations de tour pour un timestamp donné
    Returns: tuple: (lap_number, lap_time, lap_time_str, lap_type)
    """
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


def mychron_to_gpx(csv_file, output_gpx, start_datetime=None, external_gpx=None, osv_file=None):
    """
    Convertit un CSV MyChron 5 en GPX avec extensions Garmin et données de tours

    Args:
        csv_file: Fichier CSV MyChron
        output_gpx: Fichier GPX de sortie
        start_datetime: Datetime de départ (optionnel)
        external_gpx: GPX externe pour merger heart rate (optionnel)
        osv_file: Fichier OSV pour synchronisation temporelle (optionnel)
    """
    print(f"\n📂 Lecture du fichier : {csv_file}")

    # Parse métadonnées
    metadata = parse_mychron_metadata(csv_file)

    # ✅ SYNCHRONISATION OSV
    if osv_file and os.path.exists(osv_file):
        osv_create_date, osv_duration = parse_osv_timing(osv_file)
        if osv_create_date is not None:
            print(f"\n🎯 Synchronisation OSV activée")
            start_datetime = osv_create_date
        else:
            print(f"   ⚠️  Synchronisation OSV échouée, utilisation date MyChron")

    # Fallback sur date MyChron
    if start_datetime is None:
        start_datetime = parse_datetime_from_metadata(metadata)

    if start_datetime is None:
        print("\n⚠️  Heure de départ non détectée - utilisation heure actuelle")
        start_datetime = datetime.now()

    # Parse GPX externe pour heart rate (OPTIONNEL)
    hr_data = {}
    hr_merged_count = 0
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

    with open(csv_file, 'r', encoding='utf-8') as f:
        # Skip les 13 premières lignes de métadonnées
        for _ in range(13):
            next(f)

        # Skip les lignes vides jusqu'aux headers
        headers_line = None
        for line in f:
            if line.strip():  # Si la ligne n'est pas vide
                headers_line = line
                break

        if not headers_line:
            print("❌ Headers introuvables")
            return output_gpx, 0

        headers = [h.strip('"') for h in headers_line.strip().split(',')]
        print(f"   ✅ Headers trouvés : {len(headers)} colonnes")

        # Skip la ligne d'unités (la ligne suivante)
        units_line = next(f, None)
        if not units_line:
            print("❌ Pas de ligne d'unités")
            return output_gpx, 0

        # Maintenant lire les données
        reader = csv.DictReader(f, fieldnames=headers)

        for row in reader:
            try:
                time_s = float(row['Time'])
                lat = float(row['GPS Latitude'])
                lon = float(row['GPS Longitude'])

                if abs(lat) < 0.001 and abs(lon) < 0.001:
                    continue

                point_time = start_datetime + timedelta(seconds=time_s)
                time_str = point_time.isoformat() + 'Z'

                # Données de base
                ele = float(row.get('GPS Altitude', 0))
                speed = float(row.get('GPS Speed', 0)) / 3.6
                rpm = float(row.get('RPM', 0))
                water_temp = float(row.get('Water Temp', 0))
                exhaust_temp = float(row.get('Exhaust Temp', 0))
                calculated_gear = float(row.get('Calculated Gear', 0))

                accel_x = float(row.get('AccelerometerX', 0))
                accel_y = float(row.get('AccelerometerY', 0))
                accel_z = float(row.get('AccelerometerZ', 0))

                # Informations de tour
                lap_number, lap_time, lap_time_str, lap_type = get_lap_info(
                    time_s, beacon_markers, segment_times, segment_times_str
                )

                # Interpoler heart rate depuis GPX externe (si disponible)
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

                # Heart rate (si disponible)
                if hr is not None:
                    gpx_lines.append(f'            <gpxtpx:hr>{int(hr)}</gpxtpx:hr>')

                # Informations de tour
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

            except (ValueError, KeyError) as e:
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
        print(f"💓 {hr_merged_count} points avec heart rate mergés ({hr_merged_count / nbr_point_count * 100:.1f}%)")

    return output_gpx, nbr_point_count


def print_usage():
    """Affiche l'aide"""
    print("""
╔════════════════════════════════════════════════════════════════╗
║  MyChron 5 → GPX Converter (pour gopro-dashboard-overlay)     ║
║  Version 3.4 - Tours + Heart Rate + Sync OSV                  ║
╚════════════════════════════════════════════════════════════════╝

Usage:
    python mychron_to_gpx.py <mychron.csv> [external.gpx] [video.OSV]

Arguments:
    mychron.csv     Fichier CSV MyChron (requis)
    external.gpx    GPX externe pour heart rate (optionnel)
    video.OSV       Fichier OSV pour synchronisation (optionnel)

Exemples:
    # Basique
    python mychron_to_gpx.py 8.csv

    # Avec heart rate
    python mychron_to_gpx.py 8.csv amazfit.gpx

    # Avec synchronisation OSV
    python mychron_to_gpx.py 8.csv video.OSV

    # Complet : HR + OSV
    python mychron_to_gpx.py 8.csv amazfit.gpx video.OSV
    python mychron_to_gpx.py 8.csv video.OSV amazfit.gpx  # ordre flexible
    """)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    mychron_csv = sys.argv[1]
    external_gpx = None
    osv_file = None

    # Si un deuxième fichier est fourni
    if len(sys.argv) >= 3:
        second_file = sys.argv[2]
        # Déterminer si c'est un GPX ou un OSV
        if second_file.lower().endswith('.gpx'):
            external_gpx = second_file
        elif second_file.lower().endswith('.osv'):
            osv_file = second_file
        else:
            print(f"⚠️  Format de fichier inconnu : {second_file}")

    # Si un troisième fichier est fourni
    if len(sys.argv) >= 4:
        third_file = sys.argv[3]
        if third_file.lower().endswith('.gpx') and external_gpx is None:
            external_gpx = third_file
        elif third_file.lower().endswith('.osv') and osv_file is None:
            osv_file = third_file

    if not os.path.exists(mychron_csv):
        print(f"❌ Fichier CSV introuvable : {mychron_csv}")
        sys.exit(1)

    if external_gpx and not os.path.exists(external_gpx):
        print(f"⚠️  GPX externe introuvable : {external_gpx} - ignoré")
        external_gpx = None

    if osv_file and not os.path.exists(osv_file):
        print(f"⚠️  Fichier OSV introuvable : {osv_file} - ignoré")
        osv_file = None

    base_name = os.path.splitext(mychron_csv)[0]
    output_gpx = f"{base_name}.gpx"

    print("\n" + "=" * 70)
    print("🏁 MyChron 5 → GPX Converter v3.4".center(70))
    if osv_file:
        print("🎥 Mode : Synchronisation OSV".center(70))
    if external_gpx:
        print("💓 Mode : Avec Heart Rate externe".center(70))
    print("=" * 70)

    # Conversion
    result_gpx, point_count = mychron_to_gpx(
        mychron_csv,
        output_gpx,
        external_gpx=external_gpx,
        osv_file=osv_file
    )