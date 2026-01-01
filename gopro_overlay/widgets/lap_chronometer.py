from typing import Callable, Any
from PIL import Image, ImageDraw, ImageFont
from gopro_overlay.point import Coordinate
from gopro_overlay.widgets.widgets import Widget


class LapChronometer(Widget):
    """
    Widget chronomètre simple : affiche le temps du tour en cours + numéro/total
    """

    def __init__(
            self,
            at: Coordinate,
            entry: Callable,
            font: Any,
            timeseries=None,
            width: int = 280,
            height: int = 100,
            show_lap_number: bool = True,
            bg_colour=(0, 0, 0, 200),
            text_colour=(255, 255, 255),
    ):
        self.at = at
        self.entry = entry
        self.font = font
        self.width = width
        self.height = height
        self.show_lap_number = show_lap_number
        self.bg_colour = bg_colour
        self.text_colour = text_colour

        # État
        self.start_time = None
        self.beacon_markers = {}
        self.last_lap = -1

        # ✅ Comptage des tours
        self.total_timed_laps = 0
        self.highest_timed_lap_seen = 0  # Plus haut numéro de tour TIMED vu
        self.seen_laps = {}  # {lap_number: laptype}

        # PRÉ-CALCULER si timeseries disponible
        if timeseries:
            print("🔍 Pré-calcul du nombre total de tours...")
            for entry in timeseries.items():
                try:
                    lap = getattr(entry, 'lap', None)
                    if lap and hasattr(lap, 'magnitude'):
                        lap = int(lap.magnitude)
                    elif lap is not None:
                        lap = int(lap)
                    else:
                        continue

                    laptype = getattr(entry, 'laptype', None)
                    if laptype and hasattr(laptype, 'magnitude'):
                        laptype = str(laptype.magnitude)
                    elif laptype:
                        laptype = str(laptype)
                    else:
                        continue

                    # Stocker tous les tours avec leur type
                    if lap not in self.seen_laps:
                        self.seen_laps[lap] = laptype
                        if laptype == 'TIMED':
                            self.total_timed_laps += 1
                            if lap > self.highest_timed_lap_seen:
                                self.highest_timed_lap_seen = lap
                except:
                    continue

            print(f"✅ Total de tours chronométrés : {self.total_timed_laps}")
        else:
            print("⚠️ timeseries non disponible, calcul dynamique activé")

    def _format_time(self, seconds):
        """Formate un temps en secondes en M:SS.mmm"""
        if seconds < 0:
            seconds = 0
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{minutes}:{secs:02d}.{millis:03d}"

    def draw(self, image: Image, draw):
        e = self.entry()

        # Initialiser start_time au premier appel
        if self.start_time is None and hasattr(e, 'dt'):
            self.start_time = e.dt

        # Calculer le temps actuel
        current_time = 0
        if hasattr(e, 'dt') and self.start_time:
            current_time = (e.dt - self.start_time).total_seconds()

        # Récupérer le tour actuel
        try:
            current_lap = getattr(e, 'lap', 0)
            if hasattr(current_lap, 'magnitude'):
                current_lap = int(current_lap.magnitude)
            else:
                current_lap = int(current_lap)
        except:
            current_lap = 0

        # Récupérer le type de tour
        try:
            laptype = getattr(e, 'laptype', 'UNKNOWN')
            if hasattr(laptype, 'magnitude'):
                laptype = str(laptype.magnitude)
            else:
                laptype = str(laptype)
        except:
            laptype = 'UNKNOWN'

        # ✅ Calcul dynamique si pré-calcul pas disponible
        if self.total_timed_laps == 0:
            if current_lap not in self.seen_laps:
                self.seen_laps[current_lap] = laptype
                if laptype == 'TIMED':
                    self.total_timed_laps = max(self.total_timed_laps, current_lap - 1)
            else:
                # Mise à jour du total en fonction du plus haut tour TIMED vu
                if laptype == 'TIMED':
                    self.total_timed_laps = max(self.total_timed_laps, current_lap - 1)

        # Détecter changement de tour
        if current_lap != self.last_lap:
            if current_lap not in self.beacon_markers:
                self.beacon_markers[current_lap] = current_time
            self.last_lap = current_lap

        # Temps de début du tour actuel
        lap_start_time = self.beacon_markers.get(current_lap, 0)

        # Temps écoulé dans le tour
        elapsed_time = current_time - lap_start_time

        # Position de base
        base_x = self.at.x
        base_y = self.at.y

        # Polices
        try:
            chrono_font = ImageFont.truetype(self.font.path, size=int(self.font.size * 2.5))
            small_font = ImageFont.truetype(self.font.path, size=int(self.font.size * 0.75))
        except:
            chrono_font = self.font
            small_font = self.font

        current_y = base_y + 8

        # Numéro de tour avec total
        if self.show_lap_number:
            if laptype == 'OUT':
                lap_text = "TOUR DE SORTIE"
            elif laptype == 'IN':
                lap_text = "TOUR DE RENTRÉE"
            else:
                timed_lap_number = current_lap

                if self.total_timed_laps > 0:
                    lap_text = f"TOUR {timed_lap_number}/{self.total_timed_laps}"
                else:
                    # Fallback si total pas encore calculé
                    lap_text = f"TOUR {timed_lap_number}"

            draw.text(
                (base_x + self.width // 2, current_y),
                lap_text,
                font=small_font,
                fill=(180, 180, 180),
                anchor="ma"
            )
            current_y += 5

        # Chrono (GROS, centré)
        time_text = self._format_time(elapsed_time)
        draw.text(
            (base_x + self.width // 2, current_y + 25),
            time_text,
            font=chrono_font,
            fill=self.text_colour,
            anchor="ma",
            stroke_width=2,
            stroke_fill=(0, 0, 0)
        )