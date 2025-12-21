## Récupérer le gpx de la montre

## Merger le gpx de la montre avec les données de l'osv
python osv_merge.py fichier_video.OSV fichier_montre.gpx 

## Choisir les points de vues de la video et l'exporter

## Incruster l'overlay dans la video
gopro-dashboard.py --use-gpx-only --gpx ./merged.gpx --layout xml --layout-xml ./layout_parapente.xml video_entrer.mp4 video_sortie.mp4

## Couper la vidéo pour garder ce qu'il y a d'important