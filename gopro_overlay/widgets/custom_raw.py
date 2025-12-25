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
class CustomRawWidget(Widget):
    """
    Widget simplifié pour afficher directement des champs raw data.
    Plus simple que CustomCalcWidget pour l'affichage de données brutes.
    """

    def __init__(
            self,
            at: Coordinate,
            entry: Callable,
            field: str,  # ✅ Nom du champ à afficher
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
            # Fallback si champ non trouvé
            default_value=0,
    ):
        self.at = at
        self.entry = entry
        self.field = field
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

        self.default_value = default_value

    def _get_field_value(self, entry):
        """Récupère la valeur du champ de façon flexible"""
        if entry is None:
            return self.default_value

        # Liste des variantes à essayer
        variants = [
            self.field,  # Nom tel quel
            self.field.replace('.', '_').replace(' ', '_'),  # dots et espaces → underscores
            self.field.replace('_', '').replace(' ', '').replace('.', ''),  # tout collé
            self.field.lower(),  # lowercase
            self.field.replace('.', '_').replace(' ', '_').lower(),  # underscores + lowercase
        ]

        for variant in variants:
            try:
                val = getattr(entry, variant, None)
                if val is not None:
                    # Extraire .m si c'est un objet Unit
                    return getattr(val, 'm', val)
            except:
                continue

        return self.default_value

    def draw(self, image: Image, draw: ImageDraw):
        # Récupérer la valeur du champ
        entry = self.entry()
        value = self._get_field_value(entry)

        # Convertir en float pour le formatage
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = self.default_value

        # Render selon le template
        if self.template == "text":
            self._render_text(draw, value)
        elif self.template == "bar":
            self._render_bar(draw, image, value)
        elif self.template == "box":
            self._render_box(draw, image, value)

    def _render_text(self, draw, value):
        """Template texte simple"""
        text = f"{self.label}{value:.{self.dp}f}{self.unit}"
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

        fill_width = int((value / self.bar_max) * self.bar_width)
        fill_width = max(0, min(fill_width, self.bar_width))

        if fill_width > 0:
            draw.rectangle(
                [x, y, x + fill_width, y + self.bar_height],
                fill=self.bar_color
            )

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