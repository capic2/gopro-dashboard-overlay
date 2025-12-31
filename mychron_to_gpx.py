#!/usr/bin/env python3
"""
Script de conversion MyChron 5 → GPX pour gopro-dashboard-overlay
Version: 3.2 - Avec gestion des tours (laps)
"""

import csv
from datetime import datetime, timedelta
import sys
import os


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
                # Pour Beacon Markers et Segment Times, on garde toutes les valeurs
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
    segment_times_str = []  # *** AJOUT : version string originale ***

    # Parse Beacon Markers (timestamps en secondes)
    if 'Beacon Markers' in metadata:
        for marker in metadata['Beacon Markers']:
            try:
                beacon_markers.append(float(marker))
            except ValueError:
                continue

    # Parse Segment Times
    if 'Segment Times' in metadata:
        for time_str in metadata['Segment Times']:
            try:
                # Garder la version string originale
                segment_times_str.append(time_str)  # *** AJOUT ***

                # Parser en float pour calculs
                parts = time_str.split(':')
                if len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = float(parts[1])
                    total_seconds = minutes * 60 + seconds
                    segment_times.append(total_seconds)
            except (ValueError, IndexError):
                continue

    return beacon_markers, segment_times, segment_times_str  # *** MODIFIÉ ***


def get_lap_info(time_s, beacon_markers, segment_times, segment_times_str):
    """
    Détermine les informations de tour pour un timestamp donné

    Returns:
        tuple: (lap_number, lap_time, lap_time_str, lap_type)
    """
    if not beacon_markers or not segment_times:
        return None, None, None, None

    # Trouve le tour actuel
    lap_number = 0
    for i, marker in enumerate(beacon_markers):
        if time_s >= marker:
            lap_number = i + 1
        else:
            break

    if lap_number >= len(beacon_markers):
        lap_number = len(beacon_markers) - 1

    # Récupère le temps du tour (float et string)
    lap_time = segment_times[lap_number] if lap_number < len(segment_times) else None
    lap_time_str = segment_times_str[lap_number] if lap_number < len(segment_times_str) else None

    # Détermine le type de tour
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


def mychron_to_gpx(csv_file, output_gpx, start_datetime=None):
    """Convertit un CSV MyChron 5 en GPX avec extensions Garmin et données de tours"""
    print(f"\n📂 Lecture du fichier : {csv_file}")

    # Parse métadonnées
    metadata = parse_mychron_metadata(csv_file)

    if start_datetime is None:
        start_datetime = parse_datetime_from_metadata(metadata)

    if start_datetime is None:
        print("\n⚠️  Heure de départ non détectée - utilisation heure actuelle")
        start_datetime = datetime.now()

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
        timed_laps = total_laps - 2  # Exclu out-lap et in-lap
        print(f"\n🏁 Données de tours :")
        print(f"   • Total tours    : {total_laps}")
        print(f"   • Tours chronos  : {timed_laps}")

        # Affiche les temps des tours chronométrés
        if timed_laps > 0:
            print(f"   • Temps des tours:")
            for i in range(1, len(segment_times) - 1):  # Skip out-lap et in-lap
                lap_time = segment_times[i]
                print(f"     - Tour {i}: {lap_time:.3f}s")

            # Meilleur tour
            timed_lap_times = segment_times[1:-1] if len(segment_times) > 2 else []
            if timed_lap_times:
                best_lap = min(timed_lap_times)
                best_lap_num = segment_times.index(best_lap)
                print(f"   • Meilleur tour  : Tour {best_lap_num} - {best_lap:.3f}s")

    print(f"\n🔄 Création du GPX...")

    # Construit le XML à la main
    gpx_lines = []
    gpx_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    gpx_lines.append('<gpx version="1.1" creator="MyChron5-GPX-Converter-v3.2"')
    gpx_lines.append('  xmlns="http://www.topografix.com/GPX/1/1"')
    gpx_lines.append('  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"')
    gpx_lines.append('  xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v2"')
    gpx_lines.append('  xmlns:gpxpx="http://www.garmin.com/xmlschemas/GpxExtensions/v3"')
    gpx_lines.append(
        '  xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">')

    # Métadonnées
    gpx_lines.append('  <metadata>')
    gpx_lines.append(f'    <name>{metadata.get("Session", "MyChron Session")}</name>')
    gpx_lines.append(f'    <desc>{metadata.get("Vehicle", "")} - {metadata.get("Racer", "")}</desc>')
    gpx_lines.append('  </metadata>')

    # Track
    gpx_lines.append('  <trk>')
    gpx_lines.append('    <trkseg>')

    # Parse les données
    nbr_point_count = 0
    with open(csv_file, 'r', encoding='utf-8') as f:
    # Skip jusqu'aux en-têtes
        for _ in range(14):
            next(f)

        # Lis les en-têtes
        headers_line = next(f)
        headers = [h.strip('"') for h in headers_line.strip().split(',')]

        # Skip la ligne d'unités
        next(f)

        # Lis les données
        reader = csv.DictReader(f, fieldnames=headers)

        for row in reader:
            try:
                time_s = float(row['Time'])
                lat = float(row['GPS Latitude'])
                lon = float(row['GPS Longitude'])

                # Skip coordonnées invalides
                if abs(lat) < 0.001 and abs(lon) < 0.001:
                    continue

                # Timestamp
                point_time = start_datetime + timedelta(seconds=time_s)
                time_str = point_time.isoformat() + 'Z'

                # Données de base
                ele = float(row.get('GPS Altitude', 0))
                speed = float(row.get('GPS Speed', 0)) / 3.6  # km/h → m/s
                rpm = float(row.get('RPM', 0))
                water_temp = float(row.get('Water Temp', 0))
                exhaust_temp = float(row.get('Exhaust Temp', 0))
                calculated_gear = float(row.get('Calculated Gear', 0))

                # Accélérations GPS (en g)
                lat_accel = float(row.get('GPS LatAcc', 0))
                lon_accel = float(row.get('GPS LonAcc', 0))

                # Accéléromètre (en g)
                accel_x = float(row.get('AccelerometerX', 0))
                accel_y = float(row.get('AccelerometerY', 0))
                accel_z = float(row.get('AccelerometerZ', 0))

                # Informations de tour
                lap_number, lap_time, lap_time_str, lap_type = get_lap_info(
                    time_s, beacon_markers, segment_times, segment_times_str
                )

                # Point GPX
                gpx_lines.append(f'      <trkpt lat="{lat}" lon="{lon}">')
                gpx_lines.append(f'        <ele>{ele}</ele>')
                gpx_lines.append(f'        <time>{time_str}</time>')

                # Extensions Garmin
                gpx_lines.append('        <extensions>')
                gpx_lines.append('          <gpxtpx:TrackPointExtension>')

                # Métriques natives
                gpx_lines.append(f'            <gpxtpx:speed>{speed:.6f}</gpxtpx:speed>')
                gpx_lines.append(f'            <gpxtpx:atemp>{water_temp:.2f}</gpxtpx:atemp>')
                gpx_lines.append(f'            <gpxtpx:exhaust_temp>{exhaust_temp:.2f}</gpxtpx:exhaust_temp>')
                gpx_lines.append(f'            <gpxtpx:cad>{int(rpm)}</gpxtpx:cad>')
                gpx_lines.append(f'            <gpxtpx:calculated_gear>{int(calculated_gear)}</gpxtpx:calculated_gear>')

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

                # Extension personnalisée pour les accélérations
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

    # Ferme le GPX
    gpx_lines.append('    </trkseg>')
    gpx_lines.append('  </trk>')
    gpx_lines.append('</gpx>')

    # Sauvegarde
    with open(output_gpx, 'w', encoding='utf-8') as f:
        f.write('\n'.join(gpx_lines))

    print(f"\n✅ GPX créé : {output_gpx}")
    print(f"📊 {nbr_point_count} points GPS exportés")

    return output_gpx, nbr_point_count


def print_usage():
    """Affiche l'aide"""
    print("""
╔════════════════════════════════════════════════════════════════╗
║  MyChron 5 → GPX Converter (pour gopro-dashboard-overlay)     ║
║  Version 3.2 - Avec gestion des tours                          ║
╚════════════════════════════════════════════════════════════════╝

Usage:
    python mychron_to_gpx.py <mychron.csv>

Exemple:
    python mychron_to_gpx.py 8.csv
    """)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    mychron_csv = sys.argv[1]

    if not os.path.exists(mychron_csv):
        print(f"❌ Fichier CSV introuvable : {mychron_csv}")
        sys.exit(1)

    base_name = os.path.splitext(mychron_csv)[0]
    output_gpx = f"{base_name}.gpx"

    print("\n" + "=" * 70)
    print("🏁 MyChron 5 → GPX Converter v3.2".center(70))
    print("=" * 70)

    # Conversion
    result_gpx, point_count = mychron_to_gpx(mychron_csv, output_gpx)

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