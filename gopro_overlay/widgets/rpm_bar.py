from typing import Callable, Tuple, Any
from PIL import Image, ImageDraw, ImageFont
from gopro_overlay.point import Coordinate
from gopro_overlay.widgets.widgets import Widget


class RPMBarWidget(Widget):
    """
    Widget barre RPM segmentée avec dégradé de couleurs (style racing)
    Barres étroites avec hauteur croissante
    """

    def __init__(
            self,
            at: Coordinate,
            entry: Callable,
            width: int = 300,
            height: int = 50,
            segments: int = 24,  # Plus de segments pour effet plus fluide
            max_rpm: int = 15000,
            font: Any = None,
            show_value: bool = True,
            show_label: bool = True,
            segment_width: int = 8,  # Largeur fixe des barres
            segment_spacing: int = 2,  # Espacement entre barres
    ):
        self.at = at
        self.entry = entry
        self.width = width
        self.height = height
        self.segments = segments
        self.max_rpm = max_rpm
        self.font = font
        self.show_value = show_value
        self.show_label = show_label
        self.segment_width = segment_width
        self.segment_spacing = segment_spacing

        # Hauteur de la zone de barres (sans le label)
        self.bar_zone_height = height - 20

    def _get_segment_color(self, segment_index: int) -> Tuple:
        """Retourne la couleur pour un segment donné (dégradé cyan → vert → jaune → orange → rouge)"""
        ratio = segment_index / self.segments

        if ratio < 0.3:  # Cyan → Vert
            r = 0
            g = 255
            b = int(255 * (1 - ratio / 0.3))
            return (r, g, b)
        elif ratio < 0.5:  # Vert → Jaune
            r = int(255 * ((ratio - 0.3) / 0.2))
            g = 255
            b = 0
            return (r, g, b)
        elif ratio < 0.7:  # Jaune → Orange
            r = 255
            g = int(255 - 90 * ((ratio - 0.5) / 0.2))
            b = 0
            return (r, g, b)
        else:  # Orange → Rouge
            r = 255
            g = int(165 * (1 - (ratio - 0.7) / 0.3))
            b = 0
            return (r, g, b)

    def _get_segment_height(self, segment_index: int) -> int:
        """Retourne la hauteur pour un segment donné (croissante)"""
        # Hauteur minimale et maximale
        min_height = int(self.bar_zone_height * 0.3)  # 30% de la hauteur max
        max_height = self.bar_zone_height

        # Progression linéaire
        ratio = segment_index / (self.segments - 1) if self.segments > 1 else 0
        segment_height = int(min_height + (max_height - min_height) * ratio)

        return segment_height

    def draw(self, image: Image, draw):
        e = self.entry()

        # Récupérer le RPM
        try:
            rpm = getattr(e, 'cad', 0)
            if rpm is None:
                rpm = 0
            if hasattr(rpm, 'magnitude'):
                rpm = rpm.magnitude
            rpm = float(rpm)
        except:
            rpm = 0

        # Calculer le nombre de segments à allumer
        rpm_ratio = min(rpm / self.max_rpm, 1.0)
        active_segments = int(rpm_ratio * self.segments)

        # ✅ UTILISER self.at pour position relative au composite
        base_x = self.at.x  # 0
        base_y = self.at.y  # 500 (ou la valeur que vous mettez dans le XML)

        # Pour textbbox
        real_draw = draw.draw if hasattr(draw, 'draw') else ImageDraw.Draw(image)

        # Dessiner les segments
        for i in range(self.segments):
            segment_x = base_x + i * (self.segment_width + self.segment_spacing)
            segment_height = self._get_segment_height(i)
            segment_y = base_y + (self.bar_zone_height - segment_height)

            if i < active_segments:
                color = self._get_segment_color(i)
            else:
                color = (40, 40, 40)

            draw.rectangle(
                ((segment_x, segment_y),
                 (segment_x + self.segment_width, segment_y + segment_height)),
                fill=color,
                outline=(20, 20, 20),
                width=1
            )

        if self.font:
            # Police plus petite pour les graduations
            try:
                grad_font = ImageFont.truetype(self.font.path, size=int(self.font.size * 0.5))
            except:
                grad_font = self.font

            # Définir les graduations à afficher (en milliers)
            graduations = [1, 5, 10, 15]  # 1k, 5k, 10k, 15k RPM

            for grad_rpm in graduations:
                # Calculer la position du segment correspondant
                rpm_ratio = grad_rpm * 1000 / self.max_rpm
                segment_index = int(rpm_ratio * self.segments)

                if segment_index < self.segments:
                    # Position X du segment
                    grad_x = base_x + segment_index * (self.segment_width + self.segment_spacing)
                    grad_y = base_y + self.bar_zone_height + 2

                    # Texte de la graduation
                    grad_text = f"{grad_rpm}"

                    # Centrer le texte sur le segment
                    text_bbox = real_draw.textbbox((0, 0), grad_text, font=grad_font)
                    text_width = text_bbox[2] - text_bbox[0]
                    grad_x_centered = grad_x + (self.segment_width - text_width) // 2

                    draw.text(
                        (grad_x_centered, grad_y),
                        grad_text,
                        font=grad_font,
                        fill=(200, 200, 200),
                        stroke_width=1,
                        stroke_fill=(0, 0, 0)
                    )

        # Calculer la largeur totale
        total_segments_width = self.segments * (self.segment_width + self.segment_spacing)

        # Afficher la valeur RPM
        if self.show_value and self.font:
            rpm_value = rpm / 1000
            value_text = f"{rpm_value:.1f}"

            text_bbox = real_draw.textbbox((0, 0), value_text, font=self.font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            text_x = base_x - text_width - 10
            text_y = base_y + (self.bar_zone_height - text_height) // 2

            draw.text(
                (text_x, text_y),
                value_text,
                font=self.font,
                fill=(255, 255, 255),
                stroke_width=2,
                stroke_fill=(0, 0, 0)
            )

        # Afficher le label
        if self.show_label and self.font:
            label_text = "x1000"

            try:
                small_font = ImageFont.truetype(self.font.path, size=int(self.font.size * 0.6))
            except:
                small_font = self.font

            text_bbox = real_draw.textbbox((0, 0), label_text, font=small_font)
            text_width = text_bbox[2] - text_bbox[0]

            label_x = base_x + (total_segments_width - text_width) // 2
            label_y = base_y + self.bar_zone_height + 12

            draw.text(
                (label_x, label_y),
                label_text,
                font=small_font,
                fill=(180, 180, 180),
                stroke_width=1,
                stroke_fill=(0, 0, 0)
            )