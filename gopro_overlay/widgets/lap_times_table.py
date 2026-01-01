from typing import Callable, Any
from PIL import Image, ImageDraw, ImageFont
from gopro_overlay.point import Coordinate
from gopro_overlay.widgets.widgets import Widget


class LapTimesTable(Widget):
    """
    Widget tableau des temps de tour qui s'affiche progressivement
    Le meilleur tour reste toujours affiché même en dehors de la fenêtre
    Les tours s'affichent seulement quand ils sont terminés
    Affiche la vitesse max atteinte pendant chaque tour
    """

    def __init__(
            self,
            at: Coordinate,
            entry: Callable,
            font: Any,
            width: int = 380,
            max_laps_visible: int = 10,
            show_best: bool = True,
            show_max_speed: bool = True,
            bg_colour=(0, 0, 0, 200),
            text_colour=(255, 255, 255),
            best_colour=(50, 255, 50),
            header_colour=(200, 200, 200),
    ):
        self.at = at
        self.entry = entry
        self.font = font
        self.width = width
        self.max_laps_visible = max_laps_visible
        self.show_best = show_best
        self.show_max_speed = show_max_speed
        self.bg_colour = bg_colour
        self.text_colour = text_colour
        self.best_colour = best_colour
        self.header_colour = header_colour

        # Cache pour stocker les temps de tour vus
        self.lap_times_cache = {}
        self.best_lap = None

        # Mémoriser le tour précédent
        self.last_lap = -1
        self.pending_lap_data = None

        # Dictionnaire pour tracker la vitesse max de chaque tour
        self.lap_max_speeds = {}

    def draw(self, image: Image, draw):
        e = self.entry()

        # Récupérer le tour actuel
        try:
            current_lap = getattr(e, 'lap', 0)
            if hasattr(current_lap, 'magnitude'):
                current_lap = int(current_lap.magnitude)
            else:
                current_lap = int(current_lap)
        except:
            current_lap = 0

        # Récupérer le temps du tour actuel
        try:
            laptime = getattr(e, 'laptime', None)
            if laptime and hasattr(laptime, 'magnitude'):
                laptime = laptime.magnitude
            elif laptime:
                laptime = float(laptime)
        except:
            laptime = None

        # Récupérer le temps formaté
        try:
            laptime_str = getattr(e, 'laptime_str', None)
            if laptime_str and hasattr(laptime_str, 'magnitude'):
                laptime_str = str(laptime_str.magnitude)
            elif laptime_str:
                laptime_str = str(laptime_str)
        except:
            laptime_str = None

        # Récupérer le type de tour
        try:
            laptype = getattr(e, 'laptype', 'UNKNOWN')
            if hasattr(laptype, 'magnitude'):
                laptype = str(laptype.magnitude)
            else:
                laptype = str(laptype)
        except:
            laptype = 'UNKNOWN'

        # ✅ Récupérer la vitesse et convertir m/s → km/h
        try:
            speed_raw = getattr(e, 'speed', 0)

            if hasattr(speed_raw, 'magnitude'):
                speed_value = float(speed_raw.magnitude)
                # ✅ CONVERSION m/s → km/h
                speed_value = speed_value * 3.6
            else:
                speed_value = float(speed_raw) if speed_raw else 0

        except Exception as ex:
            speed_value = 0

        # Mettre à jour la vitesse max du tour ACTUEL
        if current_lap > 0:
            if current_lap not in self.lap_max_speeds:
                self.lap_max_speeds[current_lap] = speed_value
            else:
                if speed_value > self.lap_max_speeds[current_lap]:
                    self.lap_max_speeds[current_lap] = speed_value

        # Détecter changement de tour
        if current_lap != self.last_lap:
            # On vient de changer de tour
            if self.last_lap > 0 and self.pending_lap_data is not None:
                # Récupérer la vitesse max du tour qui vient de se terminer
                max_speed_for_last_lap = self.lap_max_speeds.get(self.last_lap, 0)
                self.pending_lap_data['max_speed'] = max_speed_for_last_lap

                # Ajouter le tour au cache
                self.lap_times_cache[self.last_lap] = self.pending_lap_data

            # Réinitialiser pour le nouveau tour
            self.last_lap = current_lap
            self.pending_lap_data = None

        # Stocker les données du tour en cours
        if current_lap > 0 and laptime is not None and laptime_str is not None:
            self.pending_lap_data = {
                'time': laptime,
                'str': laptime_str,
                'type': laptype,
                'max_speed': 0
            }

        # Calculer le meilleur tour (tours chronométrés seulement)
        timed_laps = {num: data for num, data in self.lap_times_cache.items()
                      if data.get('type') == 'TIMED'}
        if timed_laps and self.show_best:
            best_lap_num = min(timed_laps, key=lambda x: timed_laps[x]['time'])
            self.best_lap = best_lap_num

        # Sélection intelligente des tours à afficher
        all_laps = sorted(self.lap_times_cache.keys())

        if len(all_laps) <= self.max_laps_visible:
            visible_laps = all_laps
        else:
            last_laps = all_laps[-self.max_laps_visible:]

            if self.best_lap is not None and self.best_lap not in last_laps:
                visible_laps = sorted([self.best_lap] + last_laps[-(self.max_laps_visible - 1):])
            else:
                visible_laps = last_laps

        num_rows = len(visible_laps)

        if num_rows == 0:
            return

        # Position de base
        base_x = self.at.x
        base_y = self.at.y

        # Calculer dimensions
        row_height = 30
        header_height = 35
        padding = 10

        table_height = header_height + (num_rows * row_height) + (padding * 2)

        # Fond du tableau
        draw.rectangle(
            ((base_x, base_y),
             (base_x + self.width, base_y + table_height)),
            fill=self.bg_colour,
            outline=(100, 100, 100),
            width=2
        )

        # En-tête
        header_y = base_y + padding

        draw.text(
            (base_x + padding, header_y),
            "TOUR",
            font=self.font,
            fill=self.header_colour
        )

        draw.text(
            (base_x + self.width // 2 - 10, header_y),
            "TEMPS",
            font=self.font,
            fill=self.header_colour,
            anchor="ma"
        )

        if self.show_max_speed:
            draw.text(
                (base_x + self.width - padding, header_y),
                "V MAX",
                font=self.font,
                fill=self.header_colour,
                anchor="ra"
            )

        # Ligne de séparation
        sep_y = header_y + 25
        draw.line(
            ((base_x + padding, sep_y),
             (base_x + self.width - padding, sep_y)),
            fill=(100, 100, 100),
            width=1
        )

        # Lignes de données
        current_y = sep_y + 5

        for lap_num in visible_laps:
            lap_data = self.lap_times_cache[lap_num]

            # Couleur selon si c'est le meilleur tour
            color = self.best_colour if lap_num == self.best_lap else self.text_colour

            # Numéro de tour
            lap_text = f"{lap_num}"
            draw.text(
                (base_x + padding + 10, current_y),
                lap_text,
                font=self.font,
                fill=color
            )

            # Indicateur best lap (étoile)
            if lap_num == self.best_lap and self.show_best:
                draw.text(
                    (base_x + padding + 40, current_y),
                    "*",
                    font=self.font,
                    fill=self.best_colour
                )

            # Temps (centré)
            time_text = lap_data['str']
            draw.text(
                (base_x + self.width // 2 - 10, current_y),
                time_text,
                font=self.font,
                fill=color,
                anchor="ma"
            )

            # Vitesse max (à droite)
            if self.show_max_speed:
                max_speed = lap_data.get('max_speed', 0)
                speed_text = f"{max_speed:.0f}"
                draw.text(
                    (base_x + self.width - padding - 10, current_y),
                    speed_text,
                    font=self.font,
                    fill=color,
                    anchor="ra"
                )

            current_y += row_height