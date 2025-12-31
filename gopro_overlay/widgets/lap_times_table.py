from typing import Callable, Any
from PIL import Image, ImageDraw, ImageFont
from gopro_overlay.point import Coordinate
from gopro_overlay.widgets.widgets import Widget


class LapTimesTable(Widget):
    """
    Widget tableau des temps de tour qui s'affiche progressivement
    """

    def __init__(
            self,
            at: Coordinate,
            entry: Callable,
            font: Any,
            width: int = 300,
            max_laps_visible: int = 10,
            show_best: bool = True,
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
        self.bg_colour = bg_colour
        self.text_colour = text_colour
        self.best_colour = best_colour
        self.header_colour = header_colour

        # Cache pour stocker les temps de tour vus
        self.lap_times_cache = {}
        self.best_lap = None

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

        # Mettre à jour le cache des tours complétés
        if current_lap is not None and laptime is not None and laptime_str is not None:
            # Stocker le temps du tour actuel dans le cache
            # Le temps affiché correspond au tour dont on affiche le numéro
            if current_lap > 0:  # Ignorer out-lap (tour 0)
                # Mise à jour uniquement si le tour n'est pas déjà dans le cache
                if current_lap not in self.lap_times_cache:
                    self.lap_times_cache[current_lap] = {
                        'time': laptime,
                        'str': laptime_str,
                        'type': laptype
                    }

        # Calculer le meilleur tour (tours chronométrés seulement)
        timed_laps = {num: data for num, data in self.lap_times_cache.items()
                      if data.get('type') == 'TIMED'}
        if timed_laps and self.show_best:
            best_lap_num = min(timed_laps, key=lambda x: timed_laps[x]['time'])
            self.best_lap = best_lap_num

        # Position de base
        base_x = self.at.x
        base_y = self.at.y

        # Récupérer le vrai ImageDraw
        real_draw = draw.draw if hasattr(draw, 'draw') else ImageDraw.Draw(image)

        # Calculer dimensions
        row_height = 30
        header_height = 35
        padding = 10

        # Limiter aux N derniers tours
        visible_laps = sorted(self.lap_times_cache.keys())[-self.max_laps_visible:]
        num_rows = len(visible_laps)

        if num_rows == 0:
            return  # Rien à afficher

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
            (base_x + self.width - padding, header_y),
            "TEMPS",
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

            # Temps
            time_text = lap_data['str']
            draw.text(
                (base_x + self.width - padding - 10, current_y),
                time_text,
                font=self.font,
                fill=color,
                anchor="ra"
            )

            # Indicateur best lap
            if lap_num == self.best_lap and self.show_best:
                draw.text(
                    (base_x + padding + 50, current_y),
                    "*",
                    font=self.font,
                    fill=self.best_colour
                )

            current_y += row_height