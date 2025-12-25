#!/usr/bin/env python3
"""
Fusion OSV + FIT - Génération FIT complète avec Developer Fields
Version corrigée - Fix des local message numbers
"""
import sys
import subprocess
import tempfile
import struct
from pathlib import Path
from fitparse import FitFile
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import json


def parse_time_value(value):
    """Parse différents formats de temps"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip()
        if value.endswith(' s'):
            return float(value.replace(' s', ''))
        if ':' in value:
            parts = value.split(':')
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s)
        try:
            return float(value)
        except:
            pass
    return None


def extract_osv_data(osv_file):
    """Extrait données OSV"""
    print(f"🔍 Extraction OSV...")

    result = subprocess.run([
        './exiftool/exiftool', '-ee', '-G3', '-api', 'LargeFileSupport=1',
        '-*Time*', '-Date*', '-Create*',
        '-GPS*', '-Accelerometer*', '-Gyroscope*',
        '-json', osv_file
    ], capture_output=True, text=True)

    if result.returncode != 0:
        return []

    data = json.loads(result.stdout)
    samples = defaultdict(dict)

    for item in data:
        for key, value in item.items():
            if ':' in key:
                parts = key.split(':', 1)
                if len(parts) == 2:
                    group, field = parts
                    if group.startswith('Doc') and group[3:].isdigit():
                        sample_num = int(group.replace('Doc', ''))
                        samples[sample_num][field] = value
                    else:
                        samples[0][field] = value

    base_time = None
    for key in samples[0].keys():
        if 'CreateDate' in key:
            try:
                time_str = samples[0][key]
                base_time = datetime.strptime(time_str, '%Y:%m:%d %H:%M:%S')
                base_time = base_time.replace(tzinfo=timezone.utc)
                break
            except:
                pass

    if not base_time:
        base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    points = []
    for sample_num in sorted(samples.keys()):
        if sample_num == 0:
            continue

        sample = samples[sample_num]
        ts = parse_time_value(sample.get('SampleTime') or sample.get('Sample Time'))
        if ts is None:
            continue

        point_time = base_time + timedelta(seconds=ts)

        ax = sample.get('AccelerometerX')
        ay = sample.get('AccelerometerY')
        az = sample.get('AccelerometerZ')
        gx = sample.get('GyroscopeX')
        gy = sample.get('GyroscopeY')
        gz = sample.get('GyroscopeZ')

        if ax: ax = float(ax)
        if ay: ay = float(ay)
        if az: az = float(az)
        if gx: gx = float(gx)
        if gy: gy = float(gy)
        if gz: gz = float(gz)

        gforce = None
        if all(v is not None for v in [ax, ay, az]):
            gforce = (ax ** 2 + ay ** 2 + az ** 2) ** 0.5

        points.append({
            'time': point_time,
            'accel_x': ax, 'accel_y': ay, 'accel_z': az,
            'gyro_x': gx, 'gyro_y': gy, 'gyro_z': gz,
            'gforce': gforce
        })

    print(f"   ✅ {len(points)} points OSV")
    return points


def parse_fit(fit_file):
    """Parse FIT"""
    print(f"🏃 Lecture FIT...")

    fitfile = FitFile(fit_file)
    points = []

    for record in fitfile.get_messages('record'):
        data = {field.name: field.value for field in record}

        ts = data.get('timestamp')
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        lat = data.get('position_lat')
        lon = data.get('position_long')

        if lat is not None:
            lat = lat * (180.0 / 2 ** 31)
        if lon is not None:
            lon = lon * (180.0 / 2 ** 31)

        if ts:
            points.append({
                'time': ts,
                'lat': lat, 'lon': lon,
                'alt': data.get('altitude') or data.get('enhanced_altitude'),
                'speed': data.get('speed') or data.get('enhanced_speed'),
                'hr': data.get('heart_rate'),
                'cadence': data.get('cadence'),
                'power': data.get('power'),
                'temperature': data.get('temperature')
            })

    print(f"   ✅ {len(points)} points FIT")
    return points


def merge_data(osv_points, fit_points, tolerance=1.0):
    """Merge OSV + FIT"""
    print(f"\n🔗 Fusion (tolérance {tolerance}s)...")

    merged = []
    for fit_pt in fit_points:
        merged_pt = fit_pt.copy()

        best_osv = None
        best_diff = float('inf')

        for osv_pt in osv_points:
            diff = abs((osv_pt['time'] - fit_pt['time']).total_seconds())
            if diff < best_diff:
                best_diff = diff
                best_osv = osv_pt

        if best_osv and best_diff <= tolerance:
            merged_pt.update({
                'accel_x': best_osv.get('accel_x'),
                'accel_y': best_osv.get('accel_y'),
                'accel_z': best_osv.get('accel_z'),
                'gyro_x': best_osv.get('gyro_x'),
                'gyro_y': best_osv.get('gyro_y'),
                'gyro_z': best_osv.get('gyro_z'),
                'gforce': best_osv.get('gforce')
            })

        merged.append(merged_pt)

    with_osv = sum(1 for p in merged if p.get('gforce') is not None)
    print(f"   ✅ {len(merged)} points, {with_osv} avec OSV")
    return merged


def calc_crc(data):
    """Calcule CRC FIT"""
    crc = 0
    for byte in data:
        for _ in range(8):
            if (crc ^ byte) & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
            byte >>= 1
    return crc


def write_fit_file(points, output_file):
    """Écrit FIT avec Developer Fields - VERSION SIMPLIFIÉE"""
    print(f"\n📝 Génération FIT...")

    FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)

    def to_fit_ts(dt):
        return int((dt - FIT_EPOCH).total_seconds())

    messages = []

    # === LOCAL MESSAGE 0: FILE_ID ===
    # Definition
    msg = bytearray([0x40, 0x00, 0x00])  # Header + reserved + arch
    msg.extend(struct.pack('<H', 0))  # Global msg: file_id
    msg.append(5)  # 5 fields
    msg.extend([0, 1, 0x00])  # type (enum)
    msg.extend([1, 2, 0x84])  # manufacturer (uint16)
    msg.extend([2, 2, 0x84])  # product
    msg.extend([3, 4, 0x86])  # serial_number (uint32z)
    msg.extend([4, 4, 0x86])  # time_created
    messages.append(bytes(msg))

    # Data
    msg = bytearray([0x00])  # Local 0
    msg.append(4)  # type = activity
    msg.extend(struct.pack('<H', 1))  # manufacturer
    msg.extend(struct.pack('<H', 0))  # product
    msg.extend(struct.pack('<I', 0x12345678))  # serial
    msg.extend(struct.pack('<I', to_fit_ts(points[0]['time'])))
    messages.append(bytes(msg))

    # === LOCAL MESSAGE 1: DEVELOPER_DATA_ID ===
    # Definition
    msg = bytearray([0x41, 0x00, 0x00])
    msg.extend(struct.pack('<H', 207))  # developer_data_id
    msg.append(2)
    msg.extend([0, 16, 0x0D])  # application_id (byte[16])
    msg.extend([1, 1, 0x02])  # developer_data_index (uint8)
    messages.append(bytes(msg))

    # Data
    msg = bytearray([0x01])
    msg.extend(b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10')
    msg.append(0)  # dev_data_index = 0
    messages.append(bytes(msg))

    # === LOCAL MESSAGE 2: FIELD_DESCRIPTION (7x pour chaque champ OSV) ===
    field_names = ['accl_x', 'accl_y', 'accl_z', 'gyro_x', 'gyro_y', 'gyro_z', 'gforce']
    units_list = ['g', 'g', 'g', 'rad/s', 'rad/s', 'rad/s', 'g']

    for field_num, (fname, funit) in enumerate(zip(field_names, units_list)):
        # Definition (même pour tous)
        msg = bytearray([0x42, 0x00, 0x00])
        msg.extend(struct.pack('<H', 206))  # field_description
        msg.append(5)
        msg.extend([0, 1, 0x02])  # developer_data_index
        msg.extend([1, 1, 0x02])  # field_definition_number
        msg.extend([2, 1, 0x02])  # fit_base_type_id
        msg.extend([3, 64, 0x07])  # field_name (string[64])
        msg.extend([8, 16, 0x07])  # units (string[16])
        messages.append(bytes(msg))

        # Data
        msg = bytearray([0x02])
        msg.append(0)  # dev_data_index
        msg.append(field_num)  # field_def_num
        msg.append(136)  # base_type = float32
        msg.extend((fname + '\x00' * (64 - len(fname))).encode())
        msg.extend((funit + '\x00' * (16 - len(funit))).encode())
        messages.append(bytes(msg))

    # === LOCAL MESSAGE 3: RECORD avec Developer Fields ===
    # Definition UNE SEULE FOIS avant tous les records
    msg = bytearray([0x43, 0x00, 0x00])  # Local 3 definition
    msg.extend(struct.pack('<H', 20))  # record
    msg.append(9)  # 9 fields standards

    msg.extend([253, 4, 0x86])  # timestamp
    msg.extend([0, 4, 0x85])  # position_lat (sint32)
    msg.extend([1, 4, 0x85])  # position_long
    msg.extend([2, 2, 0x84])  # altitude (uint16, scale 5, offset 500)
    msg.extend([3, 1, 0x02])  # heart_rate
    msg.extend([4, 1, 0x02])  # cadence
    msg.extend([5, 2, 0x84])  # speed (uint16, scale 1000)
    msg.extend([7, 2, 0x84])  # power
    msg.extend([13, 1, 0x01])  # temperature (sint8)

    # Developer fields
    msg.append(7)  # 7 dev fields
    for i in range(7):
        msg.append(i)  # field_num
        msg.append(4)  # size (float32 = 4 bytes)
        msg.append(0)  # dev_data_index

    messages.append(bytes(msg))

    # === DATA RECORDS (local msg 3) ===
    for pt in points:
        msg = bytearray([0x03])  # Local 3 data

        # timestamp
        msg.extend(struct.pack('<I', to_fit_ts(pt['time'])))

        # position_lat/long
        if pt.get('lat') is not None and pt.get('lon') is not None:
            msg.extend(struct.pack('<i', int(pt['lat'] * (2 ** 31 / 180.0))))
            msg.extend(struct.pack('<i', int(pt['lon'] * (2 ** 31 / 180.0))))
        else:
            msg.extend(struct.pack('<i', 0x7FFFFFFF))
            msg.extend(struct.pack('<i', 0x7FFFFFFF))

        # altitude (scaled: m * 5 + 500)
        if pt.get('alt'):
            alt_scaled = int(pt['alt'] * 5 + 500)
            msg.extend(struct.pack('<H', max(0, min(65535, alt_scaled))))
        else:
            msg.extend(struct.pack('<H', 0xFFFF))

        # HR
        msg.append(int(pt['hr']) if pt.get('hr') else 0xFF)

        # Cadence
        msg.append(int(pt['cadence']) if pt.get('cadence') else 0xFF)

        # Speed (m/s * 1000)
        if pt.get('speed'):
            speed_scaled = int(pt['speed'] * 1000)
            msg.extend(struct.pack('<H', max(0, min(65535, speed_scaled))))
        else:
            msg.extend(struct.pack('<H', 0xFFFF))

        # Power
        if pt.get('power'):
            msg.extend(struct.pack('<H', int(pt['power'])))
        else:
            msg.extend(struct.pack('<H', 0xFFFF))

        # Temperature
        if pt.get('temperature'):
            msg.append(int(pt['temperature']) & 0xFF)
        else:
            msg.append(0x7F)

        # Developer fields (7 floats)
        for key in ['accel_x', 'accel_y', 'accel_z', 'gyro_x', 'gyro_y', 'gyro_z', 'gforce']:
            val = pt.get(key)
            if val is not None:
                msg.extend(struct.pack('<f', float(val)))
            else:
                msg.extend(struct.pack('<I', 0xFFFFFFFF))  # Invalid float32

        messages.append(bytes(msg))

    # === ASSEMBLER ===
    all_data = b''.join(messages)

    # Header
    header = bytearray()
    header.append(14)  # size
    header.append(0x20)  # protocol 2.0
    header.extend(struct.pack('<H', 2064))  # profile version
    header.extend(struct.pack('<I', len(all_data)))  # data size
    header.extend(b'.FIT')
    header.extend(struct.pack('<H', calc_crc(header)))

    # Écrire
    with open(output_file, 'wb') as f:
        f.write(header)
        f.write(all_data)
        f.write(struct.pack('<H', calc_crc(all_data)))

    print(f"   ✅ {output_file} créé ({len(points)} points)")


def main():
    if len(sys.argv) < 3:
        print("Usage: python osv_merge_fit.py video.OSV track.fit [output.fit] [tolerance]")
        sys.exit(1)

    osv_file = sys.argv[1]
    fit_input = sys.argv[2]
    fit_output = sys.argv[3] if len(sys.argv) > 3 else 'merged.fit'
    tolerance = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0

    print("=" * 60)
    print("🚀 FUSION OSV + FIT")
    print("=" * 60)

    osv_points = extract_osv_data(osv_file)
    if not osv_points:
        print("❌ Pas de données OSV")
        sys.exit(1)

    fit_points = parse_fit(fit_input)
    if not fit_points:
        print("❌ Pas de données FIT")
        sys.exit(1)

    merged = merge_data(osv_points, fit_points, tolerance)
    write_fit_file(merged, fit_output)

    with_osv = [p for p in merged if p.get('gforce')]
    if with_osv:
        gf = [p['gforce'] for p in with_osv]
        print(f"\n📊 G-Force: min={min(gf):.2f}, max={max(gf):.2f}, moy={sum(gf) / len(gf):.2f}")

    print("\n" + "=" * 60)
    print("✅ FIT avec Developer Fields créé!")
    print("=" * 60)


if __name__ == '__main__':
    main()