#!/usr/bin/env python3
import subprocess
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone


def parse_time_value(value):
    """Parse différents formats de temps et retourne secondes"""
    if value is None:
        return None

    # Si c'est déjà un nombre
    if isinstance(value, (int, float)):
        return float(value)

    # Si c'est une string
    if isinstance(value, str):
        value = value.strip()

        # Format "0 s" ou "0.02 s"
        if value.endswith(' s'):
            return float(value.replace(' s', ''))

        # Format durée "H:MM:SS" ou "M:SS" ou "SS"
        if ':' in value:
            parts = value.split(':')
            if len(parts) == 3:  # H:MM:SS
                hours, minutes, seconds = parts
                return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            elif len(parts) == 2:  # MM:SS ou M:SS
                minutes, seconds = parts
                return int(minutes) * 60 + float(seconds)

        # Format simple nombre
        try:
            return float(value)
        except ValueError:
            pass

    return None


def extract_osv_data(osv_file):
    """
    Extrait les données d'un OSV avec Sample Time en secondes
    """
    from datetime import timezone

    print(f"🔍 Extraction de {osv_file}...")

    # Extraire avec exiftool AVEC -G3 pour avoir Doc1:ChampName
    result = subprocess.run([
        './exiftool/exiftool',
        '-ee',
        '-G3',  # ✅ GARDER -G3
        '-api', 'LargeFileSupport=1',
        '-*Time*', '-Date*', '-Create*',
        '-GPS*', '-Accelerometer*', '-Gyroscope*',
        '-json',
        osv_file
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Erreur exiftool: {result.stderr}")
        return []

    data = json.loads(result.stdout)
    samples = defaultdict(dict)

    for item in data:
        for key, value in item.items():
            # Avec -G3, les clés sont: "Main:CreateDate" ou "Doc1:SampleTime"
            if ':' in key:
                parts = key.split(':', 1)  # Split en 2 parties max
                if len(parts) == 2:
                    group, field_name = parts

                    # Si c'est un Doc numéroté
                    if group.startswith('Doc') and group[3:].isdigit():
                        sample_num = int(group.replace('Doc', ''))
                        samples[sample_num][field_name] = value
                    # Sinon c'est metadata (Main, Track1, etc.)
                    else:
                        samples[0][field_name] = value
            else:
                samples[0][key] = value

    print(f"   📊 {len(samples)} échantillons trouvés")

    # TROUVER CREATE DATE dans les métadonnées (groupe Main)
    base_time = None

    # Chercher CreateDate (sans espace dans le JSON)
    for key in samples[0].keys():
        if 'CreateDate' in key or 'Create Date' in key:
            try:
                time_str = samples[0][key]
                print(f"   🕐 Trouvé {key}: {time_str}")

                # Format: "YYYY:MM:DD HH:MM:SS"
                base_time = datetime.strptime(time_str, '%Y:%m:%d %H:%M:%S')
                base_time = base_time.replace(tzinfo=timezone.utc)
                print(f"   ✅ Base time: {base_time}")
                break
            except Exception as e:
                print(f"   ⚠️  Erreur parsing {key}: {e}")

    if base_time is None:
        print("   ❌ CreateDate non trouvé")
        print(f"   🔑 Clés metadata: {list(samples[0].keys())[:10]}")
        base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    # EXTRAIRE LES POINTS
    points = []

    for sample_num in sorted(samples.keys()):
        if sample_num == 0:
            continue

        sample_data = samples[sample_num]

        # Sample Time (avec debug)
        timestamp_seconds = parse_time_value(
            sample_data.get('SampleTime') or sample_data.get('Sample Time')
        )

        if timestamp_seconds is None:
            continue

        point_time = base_time + timedelta(seconds=timestamp_seconds)

        # G-force
        accel_x = sample_data.get('AccelerometerX')
        accel_y = sample_data.get('AccelerometerY')
        accel_z = sample_data.get('AccelerometerZ')

        # ✅ Convertir en float
        if accel_x is not None:
            accel_x = float(accel_x)
        if accel_y is not None:
            accel_y = float(accel_y)
        if accel_z is not None:
            accel_z = float(accel_z)

        g_force = None
        if all(v is not None for v in [accel_x, accel_y, accel_z]):
            g_force = (accel_x ** 2 + accel_y ** 2 + accel_z ** 2) ** 0.5

        # Gyroscope - même chose
        gyro_x = sample_data.get('GyroscopeX')
        gyro_y = sample_data.get('GyroscopeY')
        gyro_z = sample_data.get('GyroscopeZ')

        if gyro_x is not None:
            gyro_x = float(gyro_x)
        if gyro_y is not None:
            gyro_y = float(gyro_y)
        if gyro_z is not None:
            gyro_z = float(gyro_z)

        points.append({
            'time': point_time,
            'timestamp_offset': timestamp_seconds,
            'g_force': g_force,
            'accel_x': accel_x,
            'accel_y': accel_y,
            'accel_z': accel_z,
            'gyro_x': gyro_x,
            'gyro_y': gyro_y,
            'gyro_z': gyro_z,
            'source': 'osv'
        })

    print(f"   ✅ {len(points)} points OSV extraits")

    if points:
        print(f"   📅 Date début: {points[0]['time']}")
        print(f"   📅 Date fin: {points[-1]['time']}")
        duration = points[-1]['timestamp_offset'] - points[0]['timestamp_offset']
        print(f"   ⏱️  Durée: {duration:.1f}s")

        # Stats G-force
        g_forces = [p['g_force'] for p in points if p['g_force'] is not None]
        if g_forces:
            print(
                f"   📊 G-Force: min={min(g_forces):.2f}, max={max(g_forces):.2f}, moy={sum(g_forces) / len(g_forces):.2f}")

    return points


def parse_gpx(gpx_file):
    """
    Parse un fichier GPX
    Retourne une liste de points avec timestamp ET extensions originales
    """

    print(f"🗺️  Lecture de {gpx_file}...")

    tree = ET.parse(gpx_file)
    root = tree.getroot()

    # Namespace GPX
    ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}

    points = []

    for trkpt in root.findall('.//gpx:trkpt', ns):
        lat = float(trkpt.get('lat'))
        lon = float(trkpt.get('lon'))

        ele_elem = trkpt.find('gpx:ele', ns)
        ele = float(ele_elem.text) if ele_elem is not None else None

        time_elem = trkpt.find('gpx:time', ns)
        if time_elem is not None:
            time_str = time_elem.text.replace('Z', '+00:00')
            time = datetime.fromisoformat(time_str)
        else:
            time = None

        # ✅ NOUVEAU : Récupérer les extensions originales (XML brut)
        extensions_elem = trkpt.find('gpx:extensions', ns)
        original_extensions = None
        if extensions_elem is not None:
            # Convertir l'élément XML en string pour le conserver
            original_extensions = ET.tostring(extensions_elem, encoding='unicode')

        if time:
            points.append({
                'time': time,
                'lat': lat,
                'lon': lon,
                'ele': ele,
                'original_extensions': original_extensions,  # ✅ Stocker
                'source': 'gpx'
            })

    print(f"   ✅ {len(points)} points GPX lus")

    return points


def merge_by_timestamp(osv_points, gpx_points, tolerance_seconds=1.0):
    """
    Enrichit les points GPX avec les données OSV quand disponibles
    Synchronise automatiquement basé sur les timestamps GPS
    """
    print(f"\n🔗 Fusion des données...")
    print(f"   Tolérance: {tolerance_seconds}s")

    if not gpx_points:
        print("   ❌ Pas de points GPX")
        return []

    if not osv_points:
        print("   ⚠️  Pas de données OSV - GPX sans enrichissement")
        return gpx_points

    # ✅ SYNCHRONISATION AUTOMATIQUE
    # On prend le premier point GPS du GPX comme référence
    gpx_start = gpx_points[0]['time']
    osv_first_sample_time = osv_points[0]['timestamp_offset']  # Offset en secondes depuis CreateDate

    print(f"   📅 GPX premier point GPS: {gpx_start}")
    print(f"   📅 OSV premier sample: {osv_first_sample_time:.2f}s après CreateDate")

    # ✅ Recaler tous les points OSV sur le timestamp GPS
    # On suppose que le premier sample OSV correspond au premier point GPX
    from datetime import timedelta

    for osv_point in osv_points:
        # Calculer le temps relatif depuis le premier sample
        relative_time = osv_point['timestamp_offset'] - osv_first_sample_time

        # Appliquer au timestamp GPS de référence
        osv_point['time'] = gpx_start + timedelta(seconds=relative_time)

    osv_start = osv_points[0]['time']
    osv_end = osv_points[-1]['time']

    print(f"   ✅ OSV synchronisé: {osv_start} → {osv_end}")
    print(f"   📍 Durée OSV: {(osv_end - osv_start).total_seconds():.1f}s")
    print(f"   📍 GPX points total: {len(gpx_points)}")

    # Filtrer les points GPX dans la plage temporelle de l'OSV
    filtered_gpx_points = []
    for gpx_point in gpx_points:
        gpx_time = gpx_point['time']
        if osv_start <= gpx_time <= osv_end:
            filtered_gpx_points.append(gpx_point)

    print(f"   ✂️  Points GPX filtrés (dans plage OSV): {len(filtered_gpx_points)}")

    if len(filtered_gpx_points) == 0:
        print("   ⚠️  Aucun point GPX dans la plage temporelle de l'OSV")
        print(f"   💡 GPX plage: {gpx_points[0]['time']} → {gpx_points[-1]['time']}")
        return []

    merged = []
    previous_point = None

    for gpx_point in filtered_gpx_points:
        gpx_time = gpx_point['time']

        merged_point = {
            'time': gpx_time,
            'lat': gpx_point['lat'],
            'lon': gpx_point['lon'],
            'ele': gpx_point['ele'],
            'original_extensions': gpx_point.get('original_extensions'),
        }

        # Calculer vitesse verticale
        vspeed = None
        if previous_point is not None and gpx_point['ele'] is not None and previous_point['ele'] is not None:
            delta_altitude = gpx_point['ele'] - previous_point['ele']
            delta_time = (gpx_time - previous_point['time']).total_seconds()

            if delta_time > 0:
                vspeed = delta_altitude / delta_time

        merged_point['vspeed'] = vspeed

        # Chercher le point OSV le plus proche
        best_osv = None
        best_diff = float('inf')

        for osv_point in osv_points:
            time_diff = abs((osv_point['time'] - gpx_time).total_seconds())
            if time_diff < best_diff:
                best_diff = time_diff
                best_osv = osv_point

        # Enrichir avec OSV si disponible
        if best_osv and best_diff <= tolerance_seconds:
            merged_point.update({
                'g_force': best_osv.get('g_force'),
                'accel_x': best_osv.get('accel_x'),
                'accel_y': best_osv.get('accel_y'),
                'accel_z': best_osv.get('accel_z'),
                'gyro_x': best_osv.get('gyro_x'),
                'gyro_y': best_osv.get('gyro_y'),
                'gyro_z': best_osv.get('gyro_z'),
            })

        merged.append(merged_point)

        previous_point = {
            'time': gpx_time,
            'ele': gpx_point['ele']
        }

    with_gforce = sum(1 for p in merged if p.get('g_force') is not None)
    with_vspeed = sum(1 for p in merged if p.get('vspeed') is not None)

    print(f"   ✅ {len(merged)} points conservés")
    print(f"   📊 {with_gforce} enrichis avec OSV ({with_gforce / len(merged) * 100:.1f}%)")
    print(f"   📈 {with_vspeed} avec vitesse verticale calculée")

    return merged


def generate_gpx(points, output_file):
    """
    Génère le GPX fusionné avec extensions originales + OSV
    Acceleration et Gyroscope dans namespace gpxpx
    """

    gpx = '''<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" 
     creator="OSV+GPX Merger v2.0"
     xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:ns1="http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
     xmlns:gpxpx="http://www.garmin.com/xmlschemas/GpxExtensions/v3"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">
    <name>Merged OSV + GPX Track</name>
    <trk>
    <trkseg>
'''

    for point in points:
        lat = point['lat']
        lon = point['lon']
        ele = point.get('ele')
        time = point['time']
        vspeed = point.get('vspeed')  # ✅

        gpx += f'      <trkpt lat="{lat}" lon="{lon}">\n'

        if ele is not None:
            gpx += f'        <ele>{ele}</ele>\n'

        gpx += f'        <time>{time.isoformat()}</time>\n'

        # Extensions
        gpx += '        <extensions>\n'
        gpx += '          <ns1:TrackPointExtension>\n'

        # Parser les extensions originales
        import re
        original_ext = point.get('original_extensions', '')

        # Extraire données originales
        hr_match = re.search(r'<(?:ns\d+:)?hr>([^<]+)</(?:ns\d+:)?hr>', original_ext)
        speed_match = re.search(r'<(?:ns\d+:)?speed>([^<]+)</(?:ns\d+:)?speed>', original_ext)
        cad_match = re.search(r'<(?:ns\d+:)?cad>([^<]+)</(?:ns\d+:)?cad>', original_ext)

        # Ajouter données Garmin avec préfixe ns1
        if speed_match:
            gpx += f'            <ns1:speed>{speed_match.group(1)}</ns1:speed>\n'

        # ✅ Ajouter vitesse verticale
        if vspeed is not None:
            gpx += f'            <ns1:vspeed>{vspeed:.6f}</ns1:vspeed>\n'

        if cad_match:
            gpx += f'            <ns1:cad>{cad_match.group(1)}</ns1:cad>\n'
        if hr_match:
            gpx += f'            <ns1:hr>{hr_match.group(1)}</ns1:hr>\n'

        gpx += '          </ns1:TrackPointExtension>\n'

        # Acceleration dans gpxpx namespace
        if point.get('accel_x') is not None:
            gpx += '          <gpxpx:Acceleration>\n'
            gpx += f'            <gpxpx:x>{point["accel_x"]:.6f}</gpxpx:x>\n'
            gpx += f'            <gpxpx:y>{point["accel_y"]:.6f}</gpxpx:y>\n'
            gpx += f'            <gpxpx:z>{point["accel_z"]:.6f}</gpxpx:z>\n'
            gpx += '          </gpxpx:Acceleration>\n'

        # Gyroscope dans gpxpx namespace
        if point.get('gyro_x') is not None:
            gpx += '          <gpxpx:Gyroscope>\n'
            gpx += f'            <gpxpx:x>{point["gyro_x"]:.6f}</gpxpx:x>\n'
            gpx += f'            <gpxpx:y>{point["gyro_y"]:.6f}</gpxpx:y>\n'
            gpx += f'            <gpxpx:z>{point["gyro_z"]:.6f}</gpxpx:z>\n'
            gpx += '          </gpxpx:Gyroscope>\n'

        gpx += '        </extensions>\n'
        gpx += '      </trkpt>\n'

    gpx += '''    </trkseg>

</trk>
</gpx>'''

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(gpx)

    print(f"\n✅ GPX fusionné créé: {output_file}")


def generate_gpx_from_osv(points, output_file):
    """Génère un GPX depuis les données OSV uniquement (sans GPS)"""

    gpx = '''<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" 
     creator="OSV+GPX Merger v2.0"
     xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:ns1="http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
     xmlns:gpxpx="http://www.garmin.com/xmlschemas/GpxExtensions/v3"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">

    <name>OSV Sensor Data</name>
    <trk>
        <trkseg>
'''

    for point in points:
        time = point['time']
        g_force = point.get('g_force')

        # Coordonnées fictives (centre de la Terre pour indiquer pas de GPS)
        gpx += f'      <trkpt lat="0" lon="0">\n'
        gpx += f'        <time>{time.isoformat()}</time>\n'

        # Extensions
        if point.get('accel_x') is not None or point.get('gyro_x') is not None:
            gpx += '        <extensions>\n'

            # ✅ Acceleration dans gpxpx namespace
            if point.get('accel_x') is not None:
                accel_x = float(point['accel_x'])
                accel_y = float(point['accel_y'])
                accel_z = float(point['accel_z'])

                gpx += '          <gpxpx:Acceleration>\n'
                gpx += f'            <gpxpx:x>{accel_x:.6f}</gpxpx:x>\n'
                gpx += f'            <gpxpx:y>{accel_y:.6f}</gpxpx:y>\n'
                gpx += f'            <gpxpx:z>{accel_z:.6f}</gpxpx:z>\n'
                gpx += '          </gpxpx:Acceleration>\n'

            # ✅ Gyroscope dans gpxpx namespace
            if point.get('gyro_x') is not None:
                gyro_x = float(point['gyro_x'])
                gyro_y = float(point['gyro_y'])
                gyro_z = float(point['gyro_z'])

                gpx += '          <gpxpx:Gyroscope>\n'
                gpx += f'            <gpxpx:x>{gyro_x:.6f}</gpxpx:x>\n'
                gpx += f'            <gpxpx:y>{gyro_y:.6f}</gpxpx:y>\n'
                gpx += f'            <gpxpx:z>{gyro_z:.6f}</gpxpx:z>\n'
                gpx += '          </gpxpx:Gyroscope>\n'

            gpx += '        </extensions>\n'

        gpx += '      </trkpt>\n'

    gpx += '''
         </trkseg>
    </trk>
</gpx>'''

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(gpx)

    print(f"\n✅ GPX extrait créé: {output_file}")
    print(f"   📊 {len(points)} points avec capteurs")
    print(f"   ⚠️  Pas de coordonnées GPS (lat/lon = 0,0)")


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  Fusion OSV + GPX:")
        print("    python osv_merge_gpx.py video.OSV track.gpx [output.gpx] [tolerance]")
        print("")
        print("  Extraction OSV uniquement:")
        print("    python osv_merge_gpx.py video.OSV --osv-only [output.gpx]")
        print("")
        print("Arguments:")
        print("  tolerance : tolérance en secondes pour la correspondance (défaut: 1.0)")
        sys.exit(1)

    osv_file = sys.argv[1]

    # MODE 1 : Extraction OSV uniquement
    if len(sys.argv) >= 3 and sys.argv[2] == '--osv-only':
        output_file = sys.argv[3] if len(sys.argv) > 3 else 'osv_extracted.gpx'

        print("=" * 60)
        print("🚀 EXTRACTION GPX DEPUIS OSV")
        print("=" * 60)

        # Extraire données OSV
        osv_points = extract_osv_data(osv_file)

        if not osv_points:
            print("❌ Aucune donnée OSV extraite")
            sys.exit(1)

        # Générer GPX depuis OSV uniquement (sans coordonnées GPS)
        generate_gpx_from_osv(osv_points, output_file)

        # Stats finales
        g_forces = [p['g_force'] for p in osv_points if p.get('g_force') is not None]
        if g_forces:
            print(f"\n📊 Statistiques G-Force:")
            print(f"   Min: {min(g_forces):.2f} G")
            print(f"   Max: {max(g_forces):.2f} G")
            print(f"   Moy: {sum(g_forces) / len(g_forces):.2f} G")

        print("\n" + "=" * 60)
        print("✅ TERMINÉ")
        print("=" * 60)
        return

    # MODE 2 : Fusion OSV + GPX (mode original)
    if len(sys.argv) < 3:
        print("❌ Erreur: fichier GPX manquant")
        print("Usage: python osv_merge_gpx.py video.OSV track.gpx [output.gpx] [tolerance]")
        sys.exit(1)

    gpx_file = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else 'merged.gpx'
    tolerance = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0

    print("=" * 60)
    print("🚀 FUSION OSV + GPX")
    print("=" * 60)

    # 1. Extraire données OSV
    osv_points = extract_osv_data(osv_file)

    if not osv_points:
        print("❌ Aucune donnée OSV extraite")
        sys.exit(1)

    # 2. Parser GPX
    gpx_points = parse_gpx(gpx_file)

    if not gpx_points:
        print("❌ Aucun point GPX trouvé")
        sys.exit(1)

    # 3. Fusionner
    merged_points = merge_by_timestamp(osv_points, gpx_points, tolerance)

    # 4. Générer GPX
    generate_gpx(merged_points, output_file)

    # 5. Stats finales
    g_forces = [p['g_force'] for p in merged_points if p.get('g_force') is not None]
    if g_forces:
        print(f"\n📊 Statistiques G-Force:")
        print(f"   Min: {min(g_forces):.2f} G")
        print(f"   Max: {max(g_forces):.2f} G")
        print(f"   Moy: {sum(g_forces) / len(g_forces):.2f} G")

    print("\n" + "=" * 60)
    print("✅ TERMINÉ")
    print("=" * 60)


if __name__ == '__main__':
    main()