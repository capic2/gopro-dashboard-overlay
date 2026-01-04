## Récupérer le gpx de la montre

## Récupérer le csv mychron (karting seulement)

## Merger le gpx de la montre avec les données de l'osv

### Parpente

`python osv_merge.py fichier_video.OSV fichier_montre.gpx merged.gpx`

### Karting

`python mychron_to_gpx fichier_mychron.csv fichier_montre.gpx fichier_video.osv`

## Choisir les points de vues de la video et l'exporter dans DJI et exporter en panoramique

## Incruster l'overlay dans la video

### Parapente

`gopro-dashboard.py --use-gpx-only --gpx ./merged.gpx --layout xml --layout-xml ./layout_parapente_1080.xml video_entree.mp4 video_sortie.mp4`

### Karting 

`gopro-dashboard.py --use-gpx-only --gpx ./fichier_mychron.gpx --layout xml --layout-xml ./layout_karting_1080.xml video_entree.mp4 video_sortie.mp4`

## Couper la vidéo pour garder ce qu'il y a d'important