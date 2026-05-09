#!/usr/bin/env python3
import os

activities = ["Karting", "Parapente"]

def activity_type_choice():
    for index, activity in enumerate(activities):
        print(f"{index + 1} - {activity} ")

    activity_index = int(input("Pour quel type d'activité ?\n"))

    if activity_index < 1 or activity_index > len(activities):
        raise Exception("Mauvais choix d'activité")

    return activity_index - 1


def add_overlay(gpx_path):
    print("\n\n")
    print("Convertir la vidéo OSV en MP4\n")

    mp4_path = input("Taper le chemin du fichier MP4\n")
    layout_path = input("Taper le chemin du fichier layout\n")
    output_path = input("Taper le chemin du fichier de sortie\n")
    os.system(
        f"bin/gopro-dashboard.py --use-gpx-only --gpx {gpx_path} --layout xml --layout-xml {layout_path} {mp4_path} {output_path}")


def main():
    activity_index = activity_type_choice()
    osv_path = input("Taper le chemin du fichier OSV\n")
    gpx_path = input("Taper le chemin du fichier gpx de la montre\n")

    if osv_path == "":
        raise Exception("Le chemin du fichier OSV ne peut pas être vide")

    if activity_index == 0:
        csv_path = input("Taper le chemin du fichier csv extrait du mychron\n")
        os.system(f"python3 mychron_to_gpx.py {csv_path} {osv_path} {gpx_path}")

        add_overlay(f"{os.path.dirname(csv_path)}{ os.path.basename(csv_path).split('.')[0]}.gpx")
    elif activity_index == 1:
        add_overlay(gpx_path)


if __name__ == '__main__':
    main()