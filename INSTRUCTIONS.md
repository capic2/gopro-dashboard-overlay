## Récupérer le gpx de la montre

## Récupérer le csv mychron (karting seulement)

## Merger le gpx de la montre avec les données de l'osv

### Parpente

`python osv_merge.py fichier_video.OSV fichier_montre.gpx merged.gpx`

### Karting

`python mychron_to_gpx fichier_mychron.csv fichier_montre.gpx fichier_video.osv`

## Choisir les points de vues de la video et l'exporter dans DJI et exporter en panoramique

## Incruster l'overlay dans la video

### Préparer l'environnement local

Le projet doit être lancé depuis le dépôt local pour utiliser les widgets et champs custom (`rpm_bar`, `gforce_circle`, `lap_times_table`, `exhaust_temp`, `calculated_gear`, etc.).

Ce qui a été fait pour remettre l'environnement en route :

```bash
python3 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -e .
```

L'installation en mode editable (`-e .`) fait que `venv/bin/gopro-dashboard.py` utilise le code présent dans ce dossier, et pas une version globale installée ailleurs.

Vérification effectuée :

```bash
venv/bin/gopro-dashboard.py --help
venv/bin/python -m pip install pytest
venv/bin/python -m pytest tests/test_arguments.py
```

Résultat des tests d'arguments : `36 passed`.

### Prérequis système

`ffmpeg` et `ffprobe` doivent être installés et présents dans le `PATH`. Si la commande affiche `Can't start ffmpeg - is it installed?`, installer ffmpeg :

```bash
sudo apt install ffmpeg
```

### Commande locale recommandée

Toujours utiliser le binaire du venv local :

```bash
venv/bin/gopro-dashboard.py --use-gpx-only --overlay-size 1920x1080 --gpx ./8.gpx --layout xml --layout-xml ./layout_karting_1080.xml ./karting.mp4 ./karting_overlay.mp4
```

Points importants :

- `--use-gpx-only` indique que les données viennent du GPX/FIT, pas des métadonnées GoPro.
- `--overlay-size 1920x1080` force la taille du rendu, utile avec ce layout 1080p.
- `--layout xml --layout-xml ./layout_karting_1080.xml` charge le layout custom local.
- Les deux derniers arguments sont obligatoires dans cet ordre : vidéo d'entrée puis vidéo de sortie.
- Les fichiers `.gpx` et `.mp4` sont ignorés par git dans ce repo, donc ils doivent être présents localement mais ne seront pas commités.

Si le venv est activé, la même commande peut être lancée avec `gopro-dashboard.py` directement :

```bash
source venv/bin/activate
gopro-dashboard.py --use-gpx-only --overlay-size 1920x1080 --gpx ./8.gpx --layout xml --layout-xml ./layout_karting_1080.xml ./karting.mp4 ./karting_overlay.mp4
```

### Parapente

`venv/bin/gopro-dashboard.py --use-gpx-only --overlay-size 1920x1080 --gpx ./merged.gpx --layout xml --layout-xml ./layout_parapente_1080.xml video_entree.mp4 video_sortie.mp4`

### Karting 

`venv/bin/gopro-dashboard.py --use-gpx-only --overlay-size 1920x1080 --gpx ./fichier_mychron.gpx --layout xml --layout-xml ./layout_karting_1080.xml video_entree.mp4 video_sortie.mp4`

## Couper la vidéo pour garder ce qu'il y a d'important
