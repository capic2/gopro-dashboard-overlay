import subprocess
import sys

if len(sys.argv) < 2:
    print("Usage: python list_fields.py video.OSV")
    sys.exit(1)

osv_file = sys.argv[1]

print(f"🔍 Extraction des champs de {osv_file}...")

# Exécuter exiftool
result = subprocess.run([
    './exiftool', '-ee', '-s', '-G3',
    '-api', 'LargeFileSupport=1',
    osv_file
], capture_output=True, text=True, encoding='utf-8')

if result.returncode != 0:
    print(f"❌ Erreur: {result.stderr}")
    sys.exit(1)

# Extraire les noms de champs uniques
fields = set()
for line in result.stdout.split('\n'):
    if ':' in line:
        field = line.split(':')[0].strip()
        if field:
            fields.add(field)

# Afficher triés
print(f"\n📋 {len(fields)} champs trouvés:\n")
for field in sorted(fields):
    print(field)

# Sauvegarder
output_file = f"{osv_file}_fields.txt"
with open(output_file, 'w', encoding='utf-8') as f:
    for field in sorted(fields):
        f.write(field + '\n')

print(f"\n✅ Liste sauvegardée dans: {output_file}")