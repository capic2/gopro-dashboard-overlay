from PIL import Image, ImageDraw, ImageFont
import math

from gopro_overlay.point import Coordinate
from gopro_overlay.widgets.widgets import Widget


class GForceCircle(Widget):
    """Widget G-Force circulaire avec point mobile basé sur accl.x et accl.y"""

    def __init__(self, at: Coordinate, entry, font, size=300, max_g=2.5,
                 bg_colour=(0, 0, 0, 220),
                 grid_colour=(80, 80, 80, 150),
                 point_colour=(255, 50, 50, 255),
                 line_colour=(255, 50, 50, 150)):
        self.at = at
        self.entry = entry
        self.font = font
        self.size = size
        self.max_g = max_g
        self.center = size // 2
        self.bg_colour = bg_colour
        self.grid_colour = grid_colour
        self.point_colour = point_colour
        self.line_colour = line_colour

    def _get_accl_value(self, axis):
        """Récupère la valeur d'accélération de manière robuste"""
        e = self.entry()
        try:
            # Essaie d'abord d'accéder via l'objet accl (PintPoint3)
            accl = getattr(e, 'accl', None)
            if accl and hasattr(accl, axis):
                val = getattr(accl, axis)
                # Si c'est un Quantity Pint
                if hasattr(val, 'magnitude'):
                    return val.magnitude
                return val

            # Sinon essaie accl.x ou accl.y comme attribut direct
            attr_name = f'accl_{axis}' if '_' not in axis else axis
            val = getattr(e, attr_name, 0)
            if hasattr(val, 'magnitude'):
                return val.magnitude
            return val if val is not None else 0
        except:
            return 0

    def draw(self, image: Image, draw):
        # Récupère les accélérations
        accl_x = self._get_accl_value('x')  # Latéral
        accl_y = self._get_accl_value('y')  # Longitudinal

        # ✅ Utiliser self.at comme RPMBarWidget
        x_base = self.at.x
        y_base = self.at.y
        center_x = x_base + self.center
        center_y = y_base + self.center

        # ✅ Récupérer le vrai ImageDraw pour textbbox
        real_draw = draw.draw if hasattr(draw, 'draw') else ImageDraw.Draw(image)

        # Cercles concentriques avec labels (0.5g, 1g, 1.5g, 2g, 2.5g)
        g_values = [0.5, 1.0, 1.5, 2.0, 2.5]
        for i, g_value in enumerate(g_values):
            if g_value > self.max_g:
                continue

            radius = int((g_value / self.max_g) * (self.size / 2 - 30))

            # Cercle
            draw.ellipse(
                ((center_x - radius, center_y - radius),
                 (center_x + radius, center_y + radius)),
                outline=self.grid_colour,
                width=1
            )

            label_text = f"{g_value:.1f}"

            # Alterne entre haut (45°) et bas (-45°) selon l'index
            if i % 2 == 0:
                angle = math.radians(45)
            else:
                angle = math.radians(-45)

            label_x = center_x + radius * math.cos(angle)
            label_y = center_y - radius * math.sin(angle)

            # ✅ Utiliser real_draw pour textbbox
            bbox = real_draw.textbbox((label_x, label_y), label_text, font=self.font, anchor="mm")
            padding = 3

            # Rectangle de fond
            draw.rectangle(
                ((bbox[0] - padding, bbox[1] - padding),
                 (bbox[2] + padding, bbox[3] + padding)),
                fill=(0, 0, 0, 180)
            )

            # Texte
            draw.text(
                (label_x, label_y),
                label_text,
                font=self.font,
                fill=(200, 200, 200, 220),
                anchor="mm"
            )

        # Axes centraux
        draw.line(
            ((center_x, y_base + 30), (center_x, y_base + self.size - 30)),
            fill=(120, 120, 120, 120),
            width=2
        )
        draw.line(
            ((x_base + 30, center_y), (x_base + self.size - 30, center_y)),
            fill=(120, 120, 120, 120),
            width=2
        )

        # Labels directionnels
        draw.text(
            (center_x, y_base + 20),
            "Frein",
            font=self.font,
            fill=(200, 200, 200, 180),
            anchor="mm"
        )
        draw.text(
            (center_x, y_base + self.size - 20),
            "Accel",
            font=self.font,
            fill=(200, 200, 200, 180),
            anchor="mm"
        )

        # Calcule la position du point
        scale = (self.size / 2 - 30) / self.max_g

        # Calcul position
        point_x = center_x - (accl_y * scale)
        point_y = center_y + (accl_x * scale)

        # Limite le point au cercle extérieur
        dx = point_x - center_x
        dy = point_y - center_y
        distance = math.sqrt(dx ** 2 + dy ** 2)
        max_distance = self.size / 2 - 30

        if distance > max_distance:
            ratio = max_distance / distance
            point_x = center_x + dx * ratio
            point_y = center_y + dy * ratio

        # Ligne du centre au point
        draw.line(
            ((center_x, center_y), (point_x, point_y)),
            fill=self.line_colour,
            width=3
        )

        # Point rouge
        point_radius = 5
        draw.ellipse(
            ((point_x - point_radius, point_y - point_radius),
             (point_x + point_radius, point_y + point_radius)),
            fill=self.point_colour,
            outline=(255, 255, 255, 230),
            width=2
        )