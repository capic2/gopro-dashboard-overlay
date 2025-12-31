from typing import Callable, Dict, Any, Optional
from PIL import Image, ImageDraw
from gopro_overlay.point import Coordinate
from gopro_overlay.widgets.widgets import Widget

# Dictionnaire d'alignement (cohérent avec le widget Text)
anchors = {
    "left": "la",
    "right": "ra",
    "centre": "ma",
}


class CustomCalcWidget(Widget):
    """
    Widget configurable via XML pour calculs et affichages personnalisés.
    Supporte le pré-calcul des stats globales si timeseries est fourni.
    """

    def __init__(
            self,
            at: Coordinate,
            entry: Callable,
            expression: str,
            font,
            label: str = "",
            unit: str = "",
            dp: int = 1,
            template: str = "text",
            align: str = "left",
            fill=(255, 255, 255),
            stroke=(0, 0, 0),
            stroke_width=2,
            # Paramètres pour template="bar"
            bar_width=200,
            bar_height=20,
            bar_max=100,
            bar_color=(0, 255, 100),
            bar_bg=(50, 50, 50),
            # Nouveau: pour pré-calcul
            timeseries=None,
    ):
        self.at = at
        self.entry = entry
        self.expression = expression
        self.font = font
        self.label = label
        self.unit = unit
        self.dp = dp
        self.template = template
        self.anchor = anchors.get(align, align)
        self.fill = fill
        self.stroke = stroke
        self.stroke_width = stroke_width

        # Paramètres barre
        self.bar_width = bar_width
        self.bar_height = bar_height
        self.bar_max = bar_max
        self.bar_color = bar_color
        self.bar_bg = bar_bg

        # État pour calculs persistants
        self.state = {}

        # PRÉ-CALCUL des stats globales si timeseries fourni
        self.precalc_stats = {}
        if timeseries:
            print("🔍 Pré-calcul des stats globales...")
            self.precalc_stats = self._precalculate_stats(timeseries)
            print(f"✅ Stats pré-calculées: {self.precalc_stats}")

    def _precalculate_stats(self, timeseries):
        """Pré-calcule les statistiques globales sur tout le parcours"""
        stats = {
            # Vitesse
            'max_speed': 0,
            'min_speed': float('inf'),
            'avg_speed': 0,
            'speed_sum': 0,
            'speed_count': 0,

            # Fréquence cardiaque
            'max_hr': 0,
            'min_hr': float('inf'),
            'avg_hr': 0,
            'hr_sum': 0,
            'hr_count': 0,

            # Altitude
            'max_alt': float('-inf'),
            'min_alt': float('inf'),
            'avg_alt': 0,
            'alt_sum': 0,
            'alt_count': 0,

            # Cadence
            'max_cadence': 0,
            'min_cadence': float('inf'),
            'avg_cadence': 0,
            'cadence_sum': 0,
            'cadence_count': 0,

            # Puissance
            'max_power': 0,
            'min_power': float('inf'),
            'avg_power': 0,
            'power_sum': 0,
            'power_count': 0,

            # Température
            'max_temp': float('-inf'),
            'min_temp': float('inf'),
            'avg_temp': 0,
            'temp_sum': 0,
            'temp_count': 0,

            # Dénivelé
            'total_gain': 0,
            'total_loss': 0,

            # Meilleur tour
            'best_lap': None,
            'best_lapnum': None,
        }

        last_alt = None
        laptimes = {}
        laptimes_str = {}

        for entry in timeseries.items():
            def get_val(attr, convert_to_kph=False):
                try:
                    val = getattr(entry, attr, None)
                    if val is None:
                        return None

                    # Si c'est un objet Quantity (Pint)
                    if hasattr(val, 'magnitude') and hasattr(val, 'units'):
                        # Convertir en km/h si demandé
                        if convert_to_kph and 'meter' in str(val.units):
                            # Convertir m/s en km/h
                            return val.magnitude * 3.6
                        return val.magnitude

                    # Sinon retourne la valeur brute
                    return val
                except:
                    return None

            # Vitesse - CONVERTIR en km/h !
            speed = get_val('speed', convert_to_kph=True)
            if speed is not None and speed >= 0:
                stats['max_speed'] = max(stats['max_speed'], speed)
                stats['min_speed'] = min(stats['min_speed'], speed)
                stats['speed_sum'] += speed
                stats['speed_count'] += 1

            # Fréquence cardiaque
            hr = get_val('hr')
            if hr is not None and hr > 0:
                stats['max_hr'] = max(stats['max_hr'], hr)
                stats['min_hr'] = min(stats['min_hr'], hr)
                stats['hr_sum'] += hr
                stats['hr_count'] += 1

            # Altitude
            alt = get_val('alt')
            if alt is not None:
                stats['max_alt'] = max(stats['max_alt'], alt)
                stats['min_alt'] = min(stats['min_alt'], alt)
                stats['alt_sum'] += alt
                stats['alt_count'] += 1

                # Gain/perte d'altitude
                if last_alt is not None:
                    diff = alt - last_alt
                    if diff > 0:
                        stats['total_gain'] += diff
                    elif diff < 0:
                        stats['total_loss'] += abs(diff)
                last_alt = alt

            # Cadence
            cadence = get_val('cad')
            if cadence is not None and cadence > 0:
                stats['max_cadence'] = max(stats['max_cadence'], cadence)
                stats['min_cadence'] = min(stats['min_cadence'], cadence)
                stats['cadence_sum'] += cadence
                stats['cadence_count'] += 1

            # Puissance
            power = get_val('power')
            if power is not None and power > 0:
                stats['max_power'] = max(stats['max_power'], power)
                stats['min_power'] = min(stats['min_power'], power)
                stats['power_sum'] += power
                stats['power_count'] += 1

            # Température
            temp = get_val('atemp')
            if temp is not None:
                stats['max_temp'] = max(stats['max_temp'], temp)
                stats['min_temp'] = min(stats['min_temp'], temp)
                stats['temp_sum'] += temp
                stats['temp_count'] += 1

            lapnum = get_val('lap', None)
            laptime = get_val('laptime', None)
            laptime_str = get_val('laptime_str', None)
            if lapnum is not None and laptime is not None:
                if lapnum not in laptimes:
                    laptimes[lapnum] = laptime
            if lapnum is not None and laptime_str is not None:
                if lapnum not in laptimes_str:
                    laptimes_str[lapnum] = laptime_str

            valid_laps = {num: time for num, time in laptimes.items() if num > 0}
            valid_laps_str = {num: time for num, time in laptimes_str.items() if num > 0}
            if valid_laps:
                best_lapnum = min(valid_laps, key=valid_laps.get)
                stats['best_lap'] = valid_laps[best_lapnum]
                stats['best_lap_str'] = valid_laps_str[best_lapnum]
                stats['best_lapnum'] = best_lapnum

            # Calculer les moyennes
        stats['avg_speed'] = stats['speed_sum'] / stats['speed_count'] if stats['speed_count'] > 0 else 0
        stats['avg_hr'] = stats['hr_sum'] / stats['hr_count'] if stats['hr_count'] > 0 else 0
        stats['avg_alt'] = stats['alt_sum'] / stats['alt_count'] if stats['alt_count'] > 0 else 0
        stats['avg_cadence'] = stats['cadence_sum'] / stats['cadence_count'] if stats['cadence_count'] > 0 else 0
        stats['avg_power'] = stats['power_sum'] / stats['power_count'] if stats['power_count'] > 0 else 0
        stats['avg_temp'] = stats['temp_sum'] / stats['temp_count'] if stats['temp_count'] > 0 else 0

        # Corriger les valeurs infinies
        if stats['min_speed'] == float('inf'):
            stats['min_speed'] = 0
        if stats['min_hr'] == float('inf'):
            stats['min_hr'] = 0
        if stats['min_alt'] == float('inf'):
            stats['min_alt'] = 0
        if stats['max_alt'] == float('-inf'):
            stats['max_alt'] = 0
        if stats['min_cadence'] == float('inf'):
            stats['min_cadence'] = 0
        if stats['min_power'] == float('inf'):
            stats['min_power'] = 0
        if stats['min_temp'] == float('inf'):
            stats['min_temp'] = 0
        if stats['max_temp'] == float('-inf'):
            stats['max_temp'] = 0

        return stats

    def draw(self, image: Image, draw: ImageDraw):
        # Récupérer les données actuelles
        e = self.entry()

        # Helper pour extraire valeur de façon sûre
        def safe_get(attr_name, default=0):
            try:
                val = getattr(e, attr_name, None)
                if val is None:
                    return default

                # Extraire magnitude si c'est un objet Pint
                if hasattr(val, 'magnitude'):
                    return val.magnitude

                return val
            except:
                return default

        # Variables disponibles dans l'expression
        context = {
            'alt': safe_get('alt'),
            'speed': safe_get('speed'),
            'hr': safe_get('hr'),
            'cadence': safe_get('cad'),
            'power': safe_get('power'),
            'temp': safe_get('temp'),
            'grad': safe_get('grad') or safe_get('cgrad'),
            'dist': safe_get('dist'),

            # Données de tour
            'lap': safe_get('lap', 0),
            'laptime': safe_get('laptime', 0.0),
            'laptime_str': safe_get('laptime_str', '--'),
            'laptype': safe_get('laptype', 'UNKNOWN'),
            'best_lap': safe_get('best_lap', 0),
            'best_lap_str': safe_get('best_lap_str', '--'),

            'state': self.state,
            'last': self.state.get('last_value', 0),
            'max': max,
            'min': min,
            'abs': abs,
            'int': int,  # *** AJOUT ***
            'float': float,  # *** AJOUT ***
            'str': str,  # *** AJOUT ***
            'round': round,  # *** AJOUT ***
            'precalc': self.precalc_stats,
        }

        # Évaluer l'expression
        try:
            value = eval(self.expression, {"__builtins__": {}}, context)

            if value is None:
                value = self.state.get('last_value', 0)

            # *** AJOUT : Extraire magnitude si c'est un objet Pint ***
            if hasattr(value, 'magnitude'):
                value = value.magnitude

        except Exception as ex:
            value = 0
            print(f"Erreur dans l'expression '{self.expression}': {ex}")

        # Mettre à jour le state
        self.state['last_value'] = value

        # Render selon le template
        if self.template == "text":
            self._render_text(draw, value)
        elif self.template == "bar":
            self._render_bar(draw, image, value)
        elif self.template == "box":
            self._render_box(draw, image, value)

    def _render_text(self, draw, value):
        """Template texte simple"""
        # Gérer les strings ET les nombres
        if isinstance(value, str):
            text = f"{self.label}{value}{self.unit}"
        else:
            try:
                text = f"{self.label}{value:.{self.dp}f}{self.unit}"
            except (ValueError, TypeError):
                text = f"{self.label}{value}{self.unit}"

        draw.text(
            self.at.tuple(),
            text,
            font=self.font,
            fill=self.fill,
            stroke_width=self.stroke_width,
            stroke_fill=self.stroke,
            anchor=self.anchor
        )

    def _render_bar(self, draw, image, value):
        """Template barre horizontale"""
        x, y = self.at.tuple()

        draw.rectangle(
            [x, y, x + self.bar_width, y + self.bar_height],
            fill=self.bar_bg,
            outline=self.fill
        )

        # Convertir en nombre si c'est une string
        numeric_value = float(value) if not isinstance(value, str) else 0

        fill_width = int((numeric_value / self.bar_max) * self.bar_width)
        fill_width = max(0, min(fill_width, self.bar_width))

        if fill_width > 0:
            draw.rectangle(
                [x, y, x + fill_width, y + self.bar_height],
                fill=self.bar_color
            )

        # Afficher le texte
        if isinstance(value, str):
            text = f"{value}{self.unit}"
        else:
            text = f"{value:.{self.dp}f}{self.unit}"

        text_bbox = draw.textbbox((0, 0), text, font=self.font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = x + (self.bar_width - text_width) // 2
        text_y = y + self.bar_height // 2

        draw.text(
            (text_x, text_y),
            text,
            font=self.font,
            fill=(255, 255, 255),
            anchor='mm'
        )

    def _render_box(self, draw, image, value):
        """Template texte avec fond coloré"""
        # Gérer les strings ET les nombres
        if isinstance(value, str):
            text = f"{self.label}{value}{self.unit}"
        else:
            text = f"{self.label}{value:.{self.dp}f}{self.unit}"

        bbox = draw.textbbox(self.at.tuple(), text, font=self.font, anchor=self.anchor)
        padding = 10

        draw.rectangle(
            [bbox[0] - padding, bbox[1] - padding,
             bbox[2] + padding, bbox[3] + padding],
            fill=self.bar_bg
        )

        draw.text(
            self.at.tuple(),
            text,
            font=self.font,
            fill=self.fill,
            anchor=self.anchor
        )