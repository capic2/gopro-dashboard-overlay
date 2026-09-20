"""Interactive editor for the XML overlay layouts.

The renderer deliberately remains independent from Tkinter.  This editor works
on the same XML structure as :mod:`gopro_overlay.layout_xml`, so it is useful
even when a layout contains widgets that cannot be previewed without telemetry.
"""

from __future__ import annotations

import argparse
import copy
from datetime import timedelta
import re
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Iterable
from xml.etree import ElementTree as ET

from PIL import Image, ImageTk


PALETTE = (
    ("text", "Texte"),
    ("metric", "Métrique"),
    ("metric_unit", "Métrique + unité"),
    ("icon", "Icône"),
    ("datetime", "Date / heure"),
    ("custom_calc", "Calcul personnalisé"),
    ("bar", "Barre"),
    ("zone_bar", "Barre par zones"),
    ("chart", "Graphique"),
    ("gradient_chart", "Graphique dégradé"),
    ("asi", "Indicateur airspeed"),
    ("msi", "Indicateur moteur"),
    ("msi2", "Indicateur moteur 2"),
    ("rpm_bar", "Barre RPM"),
    ("compass", "Boussole"),
    ("compass_arrow", "Flèche de boussole"),
    ("gps_lock_icon", "Verrou GPS"),
    ("gforce_circle", "Cercle G-Force"),
    ("lap_times_table", "Tableau des tours"),
    ("lap_chronometer", "Chronomètre de tour"),
    ("video", "Vidéo"),
    ("frame", "Cadre"),
    ("composite", "Groupe"),
    ("moving_map", "Carte mobile"),
    ("journey_map", "Carte du parcours"),
    ("moving_journey_map", "Carte du parcours mobile"),
    ("circuit_map", "Carte circuit"),
    ("cairo_circuit_map", "Carte circuit Cairo"),
    ("cairo_gauge_marker", "Jauge Cairo marqueur"),
    ("cairo_gauge_round_annotated", "Jauge Cairo ronde"),
    ("cairo_gauge_arc_annotated", "Jauge Cairo arc"),
    ("cairo_gauge_donut", "Jauge Cairo donut"),
)

POSITIONED_TYPES = {
    "text", "metric", "metric_unit", "icon", "datetime", "custom_calc",
    "moving_map", "journey_map", "moving_journey_map", "chart", "gradient_chart",
    "gforce_circle", "lap_times_table", "lap_chronometer", "video",
}


def _number(element: ET.Element, name: str, default: int) -> int:
    try:
        return int(float(element.attrib.get(name, default)))
    except (TypeError, ValueError):
        return default


def iter_editable(root: ET.Element) -> Iterable[ET.Element]:
    """Yield drawable nodes, excluding the synthetic layout root."""
    return (node for node in root.iter() if node.tag in {"component", "composite", "translate", "frame"})


def element_kind(element: ET.Element) -> str:
    return element.attrib.get("type", element.tag).replace("_", "-")


def absolute_position(root: ET.Element, target: ET.Element) -> tuple[int, int]:
    """Return target's canvas position, including all composite parents."""
    parent_map = {child: parent for parent in root.iter() for child in parent}
    x = y = 0
    current = target
    while current is not None and current is not root:
        x += _number(current, "x", 0)
        y += _number(current, "y", 0)
        current = parent_map.get(current)
    return x, y


def set_relative_position(root: ET.Element, target: ET.Element, x: int, y: int) -> None:
    parent_map = {child: parent for parent in root.iter() for child in parent}
    parent = parent_map.get(target)
    px, py = absolute_position(root, parent) if parent is not None and parent is not root else (0, 0)
    target.set("x", str(max(0, x - px)))
    target.set("y", str(max(0, y - py)))


def parent_of(root: ET.Element, target: ET.Element) -> ET.Element | None:
    for parent in root.iter():
        if target in list(parent):
            return parent
    return None


def validate_layout(root: ET.Element) -> list[str]:
    errors = []
    if root.tag != "layout":
        errors.append("La racine XML doit être <layout>.")
    allowed = {"component", "composite", "translate", "frame"}
    for element in root.iter():
        if element is root:
            continue
        if element.tag not in allowed:
            errors.append(f"Élément inconnu : <{element.tag}>.")
        for attribute in ("x", "y", "width", "height", "size"):
            if attribute in element.attrib:
                try:
                    float(element.attrib[attribute])
                except ValueError:
                    errors.append(f"{element.attrib.get('name', element.tag)} : {attribute} doit être numérique.")
        if element.tag == "component" and not element.attrib.get("type"):
            errors.append("Un <component> doit avoir un attribut type.")
    return errors


def preview_size(element: ET.Element) -> tuple[int, int]:
    size = max(24, _number(element, "size", 48))
    width = _number(element, "width", 0)
    height = _number(element, "height", 0)
    if width <= 0:
        width = max(110, min(360, size * 4))
    if height <= 0:
        height = max(42, min(180, size * 2))
    return width, height


def infer_canvas_size(path: Path | None, fallback: tuple[int, int] = (1920, 1080)) -> tuple[int, int]:
    """Infer canvas sizes from layout filenames.

    Layouts named ``*_1080.xml`` use the height convention (1080p), while
    layouts named ``*_3840.xml`` use the width convention. Handle both.
    """
    if path is not None:
        match = re.search(r"(?:^|_)(\d{3,5})(?:[-_.]|$)", path.stem)
        if match:
            value = int(match.group(1))
            height_presets = {720: (1280, 720), 1080: (1920, 1080), 1440: (2560, 1440), 2160: (3840, 2160), 2880: (5120, 2880), 4320: (7680, 4320)}
            if value in height_presets:
                return height_presets[value]
            return value, round(value * 9 / 16)
    return fallback


def fake_preview_framemeta():
    """Create deterministic telemetry covering the metrics used by widgets."""
    from datetime import timedelta
    from gopro_overlay import fake
    from gopro_overlay.units import units

    framemeta = fake.fake_framemeta(length=timedelta(seconds=60), step=timedelta(seconds=0.1))
    for index, entry in enumerate(framemeta.items()):
        seconds = index / 10
        lap = int(seconds // 30) + 1
        lap_seconds = seconds % 30
        entry.update(
            exhaust_temp=units.Quantity(80 + (index % 40), units.degC),
            power=units.Quantity(180 + (index % 60), units.watt),
            vspeed=units.Quantity(((index % 30) - 15) / 10, units.mps),
            cog=units.Quantity((index * 3) % 360, units.degree),
            azi=units.Quantity((index * 3) % 360, units.degree),
            accel=units.Quantity(((index % 20) - 10) / 10, units.mps ** 2),
            grad=units.Quantity(((index % 20) - 10) / 2, units.percent),
            cgrad=units.Quantity(((index % 20) - 10) / 2, units.percent),
            respiration=units.Quantity(14 + (index % 8), units.brpm),
            calculated_gear=units.Quantity((index // 15) % 6 + 1, units.number),
            gear_front=units.Quantity((index // 30) % 2 + 1, units.number),
            gear_rear=units.Quantity((index // 10) % 6 + 1, units.number),
            lap=units.Quantity(lap, units.number),
            laptime=units.Quantity(lap_seconds, units.second),
            laptime_str=f"0:{int(lap_seconds):02d}.000",
            laptype="OUT" if lap == 1 else "TIMED",
        )
    return framemeta


def preview_xml(root: ET.Element) -> ET.Element:
    """Make a renderable copy by replacing external-only widgets with labels."""
    result = copy.deepcopy(root)
    try:
        import cairo  # noqa: F401
        cairo_available = True
    except (ImportError, AttributeError):
        cairo_available = False

    for element in result.iter():
        if element.tag != "component":
            continue
        component_type = element.attrib.get("type", "")
        unavailable = component_type == "video" or (component_type.startswith("cairo-") and not cairo_available)
        if not unavailable:
            continue
        label = "[vidéo]" if component_type == "video" else f"[{component_type}]"
        preserved = {key: element.attrib[key] for key in ("name", "x", "y", "size") if key in element.attrib}
        preserved.update({"type": "text", "size": element.attrib.get("size", "24")})
        element.attrib.clear()
        element.attrib.update(preserved)
        element.text = label
    return result


class CollapsibleSection(ttk.Frame):
    """Small accordion section used by the scrollable left sidebar."""

    def __init__(self, parent, title: str, expanded: bool = True):
        super().__init__(parent)
        self.expanded = expanded
        self.toggle_button = ttk.Label(self, text="⌄  " + title, cursor="hand2", relief="groove", padding=(5, 3))
        self.toggle_button.pack(fill="x")
        self.toggle_button.bind("<Button-1>", lambda _event: self.toggle())
        self.toggle_button.bind("<Return>", lambda _event: self.toggle())
        self.toggle_button.bind("<space>", lambda _event: self.toggle())
        self.content = ttk.Frame(self, padding=(4, 5, 4, 2))
        if expanded:
            self.content.pack(fill="both", expand=True)
        self.title = title

    def toggle(self) -> None:
        self.expanded = not self.expanded
        if self.expanded:
            self.content.pack(fill="both", expand=True)
            self.toggle_button.configure(text="⌄  " + self.title)
        else:
            self.content.pack_forget()
            self.toggle_button.configure(text="›  " + self.title)


class LayoutEditor(tk.Tk):
    """A small, dependency-free visual XML layout editor."""

    def __init__(self, layout_path: Path | None = None, canvas_size: tuple[int, int] = (1920, 1080)):
        super().__init__()
        self.title("GoPro Overlay — éditeur de layout")
        self.geometry("1400x850")
        self.minsize(980, 620)
        self.canvas_size = canvas_size
        self.layout_path = layout_path
        self.zoom = 1.0
        self.background_path: Path | None = None
        self._background_photo = None
        self.preview_framemeta = None
        self.preview_source: Path | None = None
        self._render_cache_key = None
        self._render_cache_frame = None
        self.view_mode = "edit"
        self.render_var = tk.BooleanVar(value=False)
        self.snap_enabled = True
        self.grid_enabled = True
        self.locked: set[int] = set()
        self.hidden: set[int] = set()
        self.undo_stack: list[bytes] = []
        self.redo_stack: list[bytes] = []
        self._tree_items: dict[str, ET.Element] = {}
        self._tree_open_states: dict[int, bool] = {}
        self._tree_drag_item: str | None = None
        self._tree_drag_source: ET.Element | None = None
        self._tree_dragging = False
        self._refreshing_tree = False
        self.root_element = ET.Element("layout")
        self.selected: ET.Element | None = None
        self._canvas_items: dict[int, ET.Element] = {}
        self._drag_start: tuple[int, int] | None = None
        self._drag_origin: tuple[int, int] | None = None
        self._resize_start: tuple[int, int] | None = None
        self._resize_origin: tuple[int, int] | None = None
        self._build_ui()
        self._bind_arrow_shortcuts(self)
        self.bind_all("<Control-z>", self._undo_shortcut)
        self.bind_all("<Control-y>", self._redo_shortcut)
        self.bind_all("<Control-Shift-Z>", self._redo_shortcut)
        self.bind_all("<Left>", lambda event: self._keyboard_nudge(event, -1, 0))
        self.bind_all("<Right>", lambda event: self._keyboard_nudge(event, 1, 0))
        self.bind_all("<Up>", lambda event: self._keyboard_nudge(event, 0, -1))
        self.bind_all("<Down>", lambda event: self._keyboard_nudge(event, 0, 1))
        if layout_path:
            self.load(layout_path)
        else:
            self._refresh()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=(10, 8))
        toolbar.grid(row=0, column=0, columnspan=3, sticky="ew")
        toolbar_top = ttk.Frame(toolbar)
        toolbar_top.pack(fill="x", pady=(0, 4))
        toolbar_bottom = ttk.Frame(toolbar)
        toolbar_bottom.pack(fill="x")

        file_group = ttk.LabelFrame(toolbar_top, text="Fichier", padding=(4, 2))
        file_group.pack(side="left", padx=(0, 6))
        ttk.Button(file_group, text="Ouvrir", command=self.open_layout).pack(side="left")
        ttk.Button(file_group, text="Enregistrer", command=self.save_layout).pack(side="left", padx=3)
        ttk.Button(file_group, text="Enregistrer sous…", command=self.save_layout_as).pack(side="left")
        ttk.Button(file_group, text="Nouveau", command=self.new_layout).pack(side="left", padx=(3, 0))
        ttk.Button(file_group, text="Publier sur GitHub", command=self.publish_to_github).pack(side="left", padx=(3, 0))

        edit_group = ttk.LabelFrame(toolbar_top, text="Édition", padding=(4, 2))
        edit_group.pack(side="left", padx=6)
        ttk.Button(edit_group, text="Annuler", command=self.undo).pack(side="left")
        ttk.Button(edit_group, text="Rétablir", command=self.redo).pack(side="left", padx=3)
        ttk.Button(edit_group, text="Dupliquer", command=self.duplicate_selected).pack(side="left")

        hierarchy_group = ttk.LabelFrame(toolbar_top, text="Calques / imbrication", padding=(4, 2))
        hierarchy_group.pack(side="left", padx=6)
        ttk.Button(hierarchy_group, text="↑", width=3, command=lambda: self.move_layer(-1)).pack(side="left")
        ttk.Button(hierarchy_group, text="↓", width=3, command=lambda: self.move_layer(1)).pack(side="left", padx=2)
        ttk.Button(hierarchy_group, text="Indenter", command=self.indent_selected).pack(side="left", padx=(3, 2))
        ttk.Button(hierarchy_group, text="Désindenter", command=self.outdent_selected).pack(side="left")

        render_group = ttk.LabelFrame(toolbar_bottom, text="Rendu", padding=(4, 2))
        render_group.pack(side="left", padx=(0, 6))
        ttk.Button(render_group, text="Valider XML", command=self.validate).pack(side="left")
        ttk.Checkbutton(render_group, text="Vue rendu", variable=self.render_var, command=self.toggle_render_view).pack(side="left", padx=3)
        ttk.Button(render_group, text="Données GPX…", command=self.choose_preview_data).pack(side="left")
        ttk.Button(render_group, text="Image de fond", command=self.choose_background).pack(side="left", padx=(3, 0))

        canvas_group = ttk.LabelFrame(toolbar_bottom, text="Canvas", padding=(4, 2))
        canvas_group.pack(side="left", padx=6)
        ttk.Button(canvas_group, text="−", width=3, command=lambda: self.change_zoom(0.8)).pack(side="left")
        self.zoom_label = ttk.Label(canvas_group, text="100 %", width=7, anchor="center")
        self.zoom_label.pack(side="left")
        ttk.Button(canvas_group, text="+", width=3, command=lambda: self.change_zoom(1.25)).pack(side="left")
        ttk.Button(canvas_group, text="Ajuster à l’écran", command=self.fit_canvas).pack(side="left", padx=(3, 0))
        ttk.Label(canvas_group, text="Résolution").pack(side="left", padx=(8, 4))
        self.resolution_var = tk.StringVar(value=f"{self.canvas_size[0]}x{self.canvas_size[1]}")
        resolution = ttk.Combobox(canvas_group, textvariable=self.resolution_var, width=12, state="readonly", values=("1920x1080", "2560x1440", "3840x2160", "5120x2880", "7680x4320"))
        resolution.pack(side="left")
        resolution.bind("<<ComboboxSelected>>", self.change_resolution)
        self.status = ttk.Label(toolbar_bottom, text="Sélectionnez un élément")
        self.status.pack(side="right", padx=(12, 0))

        content = ttk.PanedWindow(self, orient="horizontal")
        content.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=10, pady=(0, 10))

        sidebar = ttk.Frame(content, padding=(0, 0, 6, 0))
        sidebar.rowconfigure(0, weight=1)
        sidebar.columnconfigure(0, weight=1)
        sidebar_canvas = tk.Canvas(sidebar, width=260, highlightthickness=0, background="#f7f7f7")
        sidebar_canvas.grid(row=0, column=0, sticky="nsew")
        sidebar_scroll = ttk.Scrollbar(sidebar, orient="vertical", command=sidebar_canvas.yview)
        sidebar_scroll.grid(row=0, column=1, sticky="ns")
        sidebar_canvas.configure(yscrollcommand=sidebar_scroll.set)
        palette = ttk.LabelFrame(sidebar_canvas, text="Ajouter un élément", padding=8)
        palette_window = sidebar_canvas.create_window((0, 0), window=palette, anchor="nw")
        palette.bind("<Configure>", lambda _event: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all")))
        sidebar_canvas.bind("<Configure>", lambda event: sidebar_canvas.itemconfigure(palette_window, width=event.width))

        def scroll_sidebar(event):
            sidebar_canvas.yview_scroll(-1 * (event.delta // 120 or -1), "units")

        sidebar_canvas.bind_all("<MouseWheel>", scroll_sidebar, add="+")
        widgets_section = CollapsibleSection(palette, "Widgets")
        widgets_section.pack(fill="x", pady=(0, 6))
        for type_name, label in PALETTE:
            ttk.Button(widgets_section.content, text=f"+ {label}", command=lambda t=type_name: self.add_element(t)).pack(fill="x", pady=2)
        ttk.Button(widgets_section.content, text="+ Bloc vitesse (modèle)", command=self.add_speed_template).pack(fill="x", pady=(3, 0))

        browser_section = CollapsibleSection(palette, "Arborescence")
        browser_section.pack(fill="both", expand=True, pady=6)
        ttk.Label(browser_section.content, text="Rechercher un widget").pack(anchor="w")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_args: self._refresh_tree())
        ttk.Entry(browser_section.content, textvariable=self.search_var, width=25).pack(fill="x", pady=(2, 6))
        tree_frame = ttk.Frame(browser_section.content)
        tree_frame.pack(fill="both", expand=True)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, height=12, show="tree", selectmode="browse")
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self._tree_select)
        self.tree.bind("<ButtonPress-1>", self._tree_drag_start, add="+")
        self.tree.bind("<B1-Motion>", self._tree_drag_motion, add="+")
        self.tree.bind("<ButtonRelease-1>", self._tree_drag_release, add="+")

        options_section = CollapsibleSection(palette, "Options d’édition")
        options_section.pack(fill="x", pady=6)
        self.lock_var = tk.BooleanVar(value=False)
        self.grid_var = tk.BooleanVar(value=True)
        self.snap_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_section.content, text="Grille", variable=self.grid_var, command=self._toggle_grid).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(options_section.content, text="Accrochage 10 px", variable=self.snap_var).pack(anchor="w")
        ttk.Button(options_section.content, text="Verrouiller / déverrouiller", command=self.toggle_lock).pack(fill="x", pady=(6, 0))
        ttk.Button(options_section.content, text="Afficher / masquer", command=self.toggle_hidden).pack(fill="x", pady=3)

        canvas_section = CollapsibleSection(palette, "Canvas")
        canvas_section.pack(fill="x", pady=6)
        ttk.Label(canvas_section.content, text=f"{self.canvas_size[0]} × {self.canvas_size[1]} px", foreground="#667085").pack(anchor="w")
        ttk.Label(canvas_section.content, text="Glisser : déplacer\nPoignée violette : redimensionner\nSuppr : supprimer", foreground="#667085").pack(anchor="w", pady=(8, 0))

        canvas_frame = ttk.Frame(content)
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(canvas_frame, background="#111827", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        xbar = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        ybar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        xbar.grid(row=1, column=0, sticky="ew")
        ybar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Delete>", lambda _event: self.delete_selected())
        self.canvas.bind("<Left>", lambda event: self._keyboard_nudge(event, -1, 0), add="+")
        self.canvas.bind("<Right>", lambda event: self._keyboard_nudge(event, 1, 0), add="+")
        self.canvas.bind("<Up>", lambda event: self._keyboard_nudge(event, 0, -1), add="+")
        self.canvas.bind("<Down>", lambda event: self._keyboard_nudge(event, 0, 1), add="+")
        self.canvas.bind("<Control-MouseWheel>", self._wheel_zoom)
        self.canvas.bind("<Control-Button-4>", lambda _event: self.change_zoom(1.25))
        self.canvas.bind("<Control-Button-5>", lambda _event: self.change_zoom(0.8))

        inspector = ttk.LabelFrame(content, text="Configuration", padding=8)
        inspector.columnconfigure(1, weight=1)
        self.inspector = inspector
        self.fields: dict[str, ttk.Entry] = {}
        ttk.Label(inspector, text="Sélectionnez un élément\npour modifier ses options.", foreground="#667085").grid(column=0, row=0, columnspan=2, sticky="w")
        content.add(sidebar, weight=0)
        content.add(canvas_frame, weight=1)
        content.add(inspector, weight=0)

    def _bind_arrow_shortcuts(self, widget: tk.Misc) -> None:
        """Handle arrows before native canvas/tree navigation can consume them."""
        if not isinstance(widget, (tk.Entry, tk.Text, ttk.Entry)):
            widget.bind("<Left>", lambda event: self._keyboard_nudge(event, -1, 0), add="+")
            widget.bind("<Right>", lambda event: self._keyboard_nudge(event, 1, 0), add="+")
            widget.bind("<Up>", lambda event: self._keyboard_nudge(event, 0, -1), add="+")
            widget.bind("<Down>", lambda event: self._keyboard_nudge(event, 0, 1), add="+")
        for child in widget.winfo_children():
            self._bind_arrow_shortcuts(child)

    def load(self, path: Path) -> None:
        self.layout_path = path
        self.root_element = ET.parse(path).getroot()
        self.resolution_var.set(f"{self.canvas_size[0]}x{self.canvas_size[1]}")
        self.selected = None
        self.locked.clear()
        self.hidden.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._refresh()
        self.after_idle(self.fit_canvas)

    def open_layout(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Layout XML", "*.xml"), ("Tous les fichiers", "*")])
        if path:
            try:
                selected_path = Path(path)
                self.canvas_size = infer_canvas_size(selected_path, self.canvas_size)
                self.load(selected_path)
            except (ET.ParseError, OSError) as exc:
                messagebox.showerror("Ouverture impossible", str(exc))

    def new_layout(self) -> None:
        self._remember_state()
        self.layout_path = None
        self.root_element = ET.Element("layout")
        self.selected = None
        self.locked.clear()
        self.hidden.clear()
        self.redo_stack.clear()
        self._refresh()

    def save_layout(self) -> bool:
        errors = validate_layout(self.root_element)
        if errors:
            messagebox.showerror("Layout invalide", "\n".join(errors[:12]), parent=self)
            return False
        path = self.layout_path
        if path is None:
            chosen = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("Layout XML", "*.xml")])
            if not chosen:
                return False
            path = Path(chosen)
            self.layout_path = path
        ET.indent(self.root_element, space="    ")
        ET.ElementTree(self.root_element).write(path, encoding="utf-8", xml_declaration=False)
        self.status.configure(text=f"Enregistré : {path.name}")
        return True

    def publish_to_github(self) -> None:
        """Commit and push only the currently opened layout file."""
        if self.layout_path is None:
            messagebox.showinfo("Publication GitHub", "Enregistrez d’abord le layout dans un fichier XML.", parent=self)
            return
        if not self.save_layout():
            return

        try:
            repo = Path(subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=self.layout_path.parent,
                text=True,
                stderr=subprocess.STDOUT,
            ).strip()).resolve()
            layout_path = self.layout_path.resolve()
            relative_path = layout_path.relative_to(repo)
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"], cwd=repo, text=True, stderr=subprocess.STDOUT
            ).strip()
            if not branch:
                raise RuntimeError("Le dépôt est sur une branche détachée.")
        except (subprocess.CalledProcessError, ValueError, OSError) as exc:
            messagebox.showerror("Publication GitHub impossible", str(exc), parent=self)
            return

        changed = subprocess.run(
            ["git", "status", "--porcelain", "--", str(relative_path)],
            cwd=repo, text=True, capture_output=True, check=False,
        )
        if not changed.stdout.strip():
            self.status.configure(text="Aucune modification à publier")
            messagebox.showinfo("Publication GitHub", "Le layout est déjà à jour dans Git.", parent=self)
            return

        default_message = f"Update layout {layout_path.name}"
        commit_message = simpledialog.askstring(
            "Publication GitHub", "Message du commit :", initialvalue=default_message, parent=self
        )
        if not commit_message or not commit_message.strip():
            return

        try:
            subprocess.run(["git", "add", "--", str(relative_path)], cwd=repo, check=True, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", commit_message.strip()], cwd=repo, check=True, capture_output=True, text=True)
            result = subprocess.run(
                ["git", "push", "origin", branch], cwd=repo, check=True, capture_output=True, text=True
            )
            output = (result.stdout + result.stderr).strip()
            self.status.configure(text=f"Publié sur GitHub : {branch}")
            messagebox.showinfo("Publication GitHub réussie", output or f"Le layout a été poussé sur {branch}.", parent=self)
        except subprocess.CalledProcessError as exc:
            output = ((exc.stdout or "") + (exc.stderr or "")).strip()
            messagebox.showerror("Publication GitHub échouée", output or str(exc), parent=self)

    def validate(self) -> None:
        errors = validate_layout(self.root_element)
        if errors:
            messagebox.showwarning("Validation XML", "\n".join(errors[:20]), parent=self)
        else:
            messagebox.showinfo("Validation XML", "Le layout est valide.", parent=self)

    def _snapshot(self) -> bytes:
        return ET.tostring(self.root_element, encoding="utf-8")

    def _remember_state(self) -> None:
        snapshot = self._snapshot()
        if not self.undo_stack or self.undo_stack[-1] != snapshot:
            self.undo_stack.append(snapshot)
        self.redo_stack.clear()

    def _restore_snapshot(self, snapshot: bytes) -> None:
        self.root_element = ET.fromstring(snapshot)
        self.selected = None
        self._refresh()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        self.redo_stack.append(self._snapshot())
        self._restore_snapshot(self.undo_stack.pop())
        self.status.configure(text="Action annulée")

    def _undo_shortcut(self, _event=None) -> str:
        self.undo()
        return "break"

    def redo(self) -> None:
        if not self.redo_stack:
            return
        snapshot = self.redo_stack.pop()
        self.undo_stack.append(snapshot)
        self._restore_snapshot(snapshot)
        self.status.configure(text="Action rétablie")

    def _redo_shortcut(self, _event=None) -> str:
        self.redo()
        return "break"

    def _keyboard_nudge(self, event, dx: int, dy: int) -> str:
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Text, ttk.Entry)) or self.selected is None:
            return ""
        if id(self.selected) in self.locked:
            self.status.configure(text="Widget verrouillé")
            return "break"
        step = 10 if event.state & 0x0001 else 1
        self._remember_state()
        x, y = absolute_position(self.root_element, self.selected)
        parent = parent_of(self.root_element, self.selected)
        parent_x, parent_y = absolute_position(self.root_element, parent) if parent is not None else (0, 0)
        # Update only the axis requested by the key.  Apart from being clearer,
        # this preserves the other XML attribute even for nested widgets.
        if dx:
            self.selected.set("x", str(max(0, x + dx * step - parent_x)))
        if dy:
            self.selected.set("y", str(max(0, y + dy * step - parent_y)))
        self.status.configure(text=f"Position : {x + dx * step}, {y + dy * step}")
        self._refresh()
        return "break"

    def _refresh_tree(self) -> None:
        if not hasattr(self, "tree") or self._refreshing_tree:
            return
        self._refreshing_tree = True
        # Rebuilding the Treeview is needed after every edit, but must not
        # unexpectedly reopen composites that the user has collapsed.
        for item_id, element in self._tree_items.items():
            if self.tree.exists(item_id):
                self._tree_open_states[id(element)] = bool(self.tree.item(item_id, "open"))
        query = self.search_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        self._tree_items.clear()
        selected_item = None

        def add(parent_id: str, element: ET.Element) -> None:
            nonlocal selected_item
            name = element.attrib.get("name", "(sans nom)")
            label = f"{name}  ·  {element_kind(element)}"
            if query and query not in label.lower() and not any(query in (child.attrib.get("name", "") + element_kind(child)).lower() for child in element):
                return
            item_id = self.tree.insert(
                parent_id,
                "end",
                text=label,
                open=self._tree_open_states.get(id(element), True),
            )
            self._tree_items[item_id] = element
            if element is self.selected:
                selected_item = item_id
            for child in element:
                if child.tag in {"component", "composite", "translate", "frame"}:
                    add(item_id, child)

        for element in self.root_element:
            if element.tag in {"component", "composite", "translate", "frame"}:
                add("", element)
        if selected_item is not None:
            if self.tree.selection() != (selected_item,):
                self.tree.selection_set(selected_item)
            self.tree.focus(selected_item)
            self.tree.see(selected_item)
        self._refreshing_tree = False

    def _tree_select(self, _event=None) -> None:
        if self._refreshing_tree:
            return
        selection = self.tree.selection()
        if selection and selection[0] in self._tree_items:
            element = self._tree_items[selection[0]]
            # Tk can deliver <<TreeviewSelect>> after the tree has been
            # rebuilt. Do not start another full refresh for the same node.
            if element is self.selected:
                return
            self.selected = element
            self._refresh()

    def _tree_drag_start(self, event) -> None:
        item_id = self.tree.identify_row(event.y)
        self._tree_drag_item = item_id or None
        self._tree_drag_source = self._tree_items.get(item_id) if item_id else None
        self._tree_dragging = False

    def _tree_drag_motion(self, _event) -> None:
        if self._tree_drag_item:
            self._tree_dragging = True
            self.tree.configure(cursor="hand2")

    def _tree_drag_release(self, event) -> None:
        source_id = self._tree_drag_item
        source = self._tree_drag_source
        was_dragging = self._tree_dragging
        self._tree_drag_item = None
        self._tree_drag_source = None
        self._tree_dragging = False
        self.tree.configure(cursor="")
        if not was_dragging or source is None:
            return
        target_id = self.tree.identify_row(event.y)
        if not target_id or target_id == source_id or target_id not in self._tree_items:
            return
        target = self._tree_items[target_id]
        if source is target or self._is_tree_descendant(source, target):
            self.status.configure(text="Impossible d’imbriquer un groupe dans son propre contenu")
            return

        containers = {"composite", "translate", "frame"}
        if target.tag in containers:
            new_parent = target
            new_index = len(target)
            message = "Widget imbriqué dans le groupe sélectionné"
        else:
            new_parent = parent_of(self.root_element, target)
            if new_parent is None:
                return
            bbox = self.tree.bbox(target_id)
            after_target = bool(bbox and event.y > bbox[1] + bbox[3] / 2)
            new_index = list(new_parent).index(target) + (1 if after_target else 0)
            message = "Widget repositionné dans l’arborescence"
        self._move_tree_node(source, new_parent, new_index)
        self.status.configure(text=message)

    def _is_tree_descendant(self, ancestor: ET.Element, candidate: ET.Element) -> bool:
        return any(child is candidate for child in ancestor.iter() if child is not ancestor)

    def _move_tree_node(self, node: ET.Element, new_parent: ET.Element, index: int) -> None:
        old_parent = parent_of(self.root_element, node)
        if old_parent is None:
            return
        absolute_x, absolute_y = absolute_position(self.root_element, node)
        new_parent_x, new_parent_y = absolute_position(self.root_element, new_parent)
        self._remember_state()
        if old_parent is new_parent:
            old_index = list(old_parent).index(node)
            if old_index < index:
                index -= 1
        old_parent.remove(node)
        if old_parent is new_parent and index > len(new_parent):
            index = len(new_parent)
        new_parent.insert(max(0, min(index, len(new_parent))), node)
        node.set("x", str(absolute_x - new_parent_x))
        node.set("y", str(absolute_y - new_parent_y))
        self.selected = node
        self._refresh()

    def _toggle_grid(self) -> None:
        self.grid_enabled = self.grid_var.get()
        self._refresh()

    def toggle_lock(self) -> None:
        if self.selected is None:
            return
        self._remember_state()
        key = id(self.selected)
        if key in self.locked:
            self.locked.remove(key)
            self.status.configure(text="Widget déverrouillé")
        else:
            self.locked.add(key)
            self.status.configure(text="Widget verrouillé")
        self._refresh()

    def toggle_hidden(self) -> None:
        if self.selected is None:
            return
        self._remember_state()
        key = id(self.selected)
        if key in self.hidden:
            self.hidden.remove(key)
            self.status.configure(text="Widget visible")
        else:
            self.hidden.add(key)
            self.status.configure(text="Widget masqué")
        self._refresh()

    def save_layout_as(self) -> None:
        chosen = filedialog.asksaveasfilename(
            title="Enregistrer le layout sous…",
            defaultextension=".xml",
            filetypes=[("Layout XML", "*.xml"), ("Tous les fichiers", "*")],
        )
        if chosen:
            self.layout_path = Path(chosen)
            self.save_layout()

    def choose_background(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Choisir l’image de fond",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Tous les fichiers", "*")],
        )
        if not chosen:
            return
        try:
            with Image.open(chosen) as image:
                image = image.convert("RGB")
                image.thumbnail(self.canvas_size, Image.Resampling.LANCZOS)
                background = Image.new("RGB", self.canvas_size, "#111827")
                background.paste(image, ((self.canvas_size[0] - image.width) // 2, (self.canvas_size[1] - image.height) // 2))
                self._background_photo = ImageTk.PhotoImage(background)
            self.background_path = Path(chosen)
            self._refresh()
            self.status.configure(text=f"Fond : {self.background_path.name}")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Image impossible à ouvrir", str(exc))

    def choose_preview_data(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Choisir les données GPX de prévisualisation",
            filetypes=[("Traces GPX", "*.gpx *.gpx.gz"), ("Tous les fichiers", "*")],
        )
        if not chosen:
            return
        try:
            from gopro_overlay.gpx import load_timeseries
            from gopro_overlay.framemeta_gpx import timeseries_to_framemeta
            from gopro_overlay.units import units

            source = Path(chosen)
            timeseries = load_timeseries(source, units)
            self.preview_framemeta = timeseries_to_framemeta(timeseries, units)
            self.preview_source = source
            self.status.configure(text=f"Données de rendu : {source.name}")
            if self.view_mode == "render":
                self._refresh()
        except Exception as exc:
            messagebox.showerror("Données GPX invalides", str(exc), parent=self)

    def toggle_render_view(self) -> None:
        self.view_mode = "render" if self.render_var.get() else "edit"
        self.status.configure(text="Vue rendu" if self.view_mode == "render" else "Vue édition")
        self._refresh()

    def _render_real_preview(self) -> Image.Image:
        """Render the XML through the real Pillow widget engine.

        GPX data is used when selected; otherwise deterministic test telemetry
        is used. Map tiles are intentionally replaced by a neutral renderer so
        previewing never requires network access or API keys.
        """
        from gopro_overlay import fake
        from gopro_overlay.font import load_font
        from gopro_overlay.layout import Overlay
        from gopro_overlay.layout_xml import layout_from_xml
        from gopro_overlay.privacy import NoPrivacyZone
        from gopro_overlay.widgets.widgets import SimpleFrameSupplier

        render_key = (
            ET.tostring(self.root_element, encoding="utf-8"),
            str(self.preview_source) if self.preview_source else None,
            self.canvas_size,
            str(self.background_path) if self.background_path else None,
        )
        if render_key == self._render_cache_key and self._render_cache_frame is not None:
            return self._render_cache_frame.copy()

        framemeta = self.preview_framemeta or fake_preview_framemeta()
        font_candidates = (
            Path("/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Medium.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        )
        font_path = next((path for path in font_candidates if path.exists()), None)
        if font_path is None:
            raise RuntimeError("Aucune police TrueType disponible pour le rendu.")

        def map_preview(map_object):
            from PIL import ImageDraw

            image = Image.new("RGBA", map_object.size, (38, 48, 62, 255))
            draw = ImageDraw.Draw(image)
            width, height = map_object.size
            for x in range(0, width, max(20, width // 6)):
                draw.line((x, 0, x, height), fill=(67, 82, 101, 180), width=1)
            for y in range(0, height, max(20, height // 6)):
                draw.line((0, y, width, y), fill=(67, 82, 101, 180), width=1)
            route = [
                (int(width * 0.05), int(height * 0.78)),
                (int(width * 0.25), int(height * 0.62)),
                (int(width * 0.38), int(height * 0.68)),
                (int(width * 0.55), int(height * 0.35)),
                (int(width * 0.72), int(height * 0.46)),
                (int(width * 0.94), int(height * 0.18)),
            ]
            draw.line(route, fill=(80, 210, 170, 255), width=max(3, width // 70), joint="curve")
            draw.text((10, 10), "CARTE · APERÇU", fill=(225, 235, 245, 230))
            return image

        render_root = preview_xml(self.root_element)
        layout = layout_from_xml(
            ET.tostring(render_root, encoding="unicode"),
            renderer=map_preview,
            framemeta=framemeta,
            font=load_font(str(font_path)),
            privacy=NoPrivacyZone(),
        )
        overlay = Overlay(framemeta, layout)
        supplier = SimpleFrameSupplier(self._dimension())
        target = framemeta.mid
        frame = supplier.drawing_frame()
        # Some widgets (lap table, chronometer, journey) build state while
        # receiving successive frames. Replay the preview timeline up to the
        # selected instant so one screenshot contains their useful content.
        from gopro_overlay.timeunits import timeunits
        for entry in framemeta.items(step=timedelta(seconds=1)):
            pts = timeunits(millis=int(entry.timestamp.magnitude))
            if pts > target:
                break
            frame = overlay.draw(pts, supplier.drawing_frame())
        if self.background_path is not None:
            with Image.open(self.background_path) as image:
                background = image.convert("RGBA").resize(self.canvas_size, Image.Resampling.LANCZOS)
            frame = Image.alpha_composite(background, frame)
        self._render_cache_key = render_key
        self._render_cache_frame = frame.copy()
        return frame

    def _dimension(self):
        from gopro_overlay.dimensions import Dimension
        return Dimension(*self.canvas_size)

    def fit_canvas(self) -> None:
        available_width = max(400, self.canvas.winfo_width() - 20)
        available_height = max(300, self.canvas.winfo_height() - 20)
        self.zoom = min(1.0, available_width / self.canvas_size[0], available_height / self.canvas_size[1])
        self._refresh()

    def change_zoom(self, factor: float) -> None:
        self.zoom = max(0.1, min(3.0, self.zoom * factor))
        self._refresh()

    def change_resolution(self, _event=None) -> None:
        try:
            width, height = (int(value) for value in self.resolution_var.get().split("x", 1))
        except ValueError:
            return
        self.canvas_size = (width, height)
        self.fit_canvas()

    def _wheel_zoom(self, event) -> str:
        self.change_zoom(1.25 if event.delta > 0 else 0.8)
        return "break"

    def add_element(self, type_name: str) -> None:
        self._remember_state()
        tag = "component"
        if type_name in {"composite", "frame"}:
            tag = type_name
        element = ET.Element(tag)
        if tag == "component":
            element.set("type", type_name)
        self.update_idletasks()
        visible_x = self.canvas.canvasx(max(0, self.canvas.winfo_width() // 2)) / self.zoom
        visible_y = self.canvas.canvasy(max(0, self.canvas.winfo_height() // 2)) / self.zoom
        position = {"x": str(max(0, int(visible_x - 100))), "y": str(max(0, int(visible_y - 45)))}
        element.set("size", "32")
        if tag != "component" or type_name in POSITIONED_TYPES:
            element.update(position)
        element.set("name", self._new_element_name(type_name))
        if type_name == "text":
            element.text = "Nouveau texte"
        if type_name == "metric":
            element.set("metric", "speed")
        if type_name == "metric_unit":
            element.set("metric", "speed")
            element.text = "{:~P}"
        if type_name == "icon":
            element.set("file", "gauge.png")
        if type_name == "datetime":
            element.set("format", "%H:%M:%S")
        if type_name == "custom_calc":
            element.set("expression", "speed")
        if type_name in {"bar", "zone_bar"}:
            element.update({"width": "320", "height": "30", "metric": "speed"})
        if type_name in {"chart", "gradient_chart"}:
            element.update({"width": "400", "height": "100", "metric": "alt"})
        if type_name in {"asi", "msi", "msi2"}:
            element.update({"metric": "speed", "textsize": "16", "needle": "1", "end": "120"})
        if type_name in {"compass", "compass_arrow", "circuit_map", "cairo_circuit_map"}:
            element.set("size", "200")
        if type_name in {"moving_map", "journey_map", "moving_journey_map"}:
            element.set("size", "200")
        if type_name == "rpm_bar":
            element.update({"width": "320", "height": "45", "max_rpm": "15000"})
        if type_name == "gps_lock_icon":
            element.set("size", "64")
        if type_name == "gforce_circle":
            element.set("max_g", "3")
        if type_name == "lap_times_table":
            element.update({"width": "320", "max_laps": "8"})
        if type_name == "lap_chronometer":
            element.update({"width": "280", "height": "100"})
        if type_name == "video":
            element.update({"width": "320", "height": "180", "file": "video.mp4"})
        if tag == "frame":
            element.update({"width": "260", "height": "110", "bg": "20,25,35,190"})
        if tag == "composite":
            element.set("name", self._new_element_name("groupe"))
        container = element
        if tag == "component" and type_name not in POSITIONED_TYPES:
            container = ET.Element("translate", position)
            container.append(element)
        self.root_element.append(container)
        self.selected = element
        self._refresh()
        self.status.configure(text=f"Élément ajouté : {type_name}")
        self._show_selected()

    def add_speed_template(self) -> None:
        self._remember_state()
        group = ET.Element("composite", {"name": self._new_element_name("speed-block"), "x": "80", "y": "80"})
        group.extend([
            ET.Element("component", {"name": "speed-gauge", "type": "msi", "metric": "speed", "size": "200"}),
            ET.Element("component", {"name": "speed-value", "type": "metric", "metric": "speed", "size": "40", "x": "100", "y": "140", "align": "centre"}),
            ET.Element("component", {"name": "speed-unit", "type": "metric_unit", "metric": "speed", "size": "18", "x": "100", "y": "185", "align": "centre"}),
        ])
        self.root_element.append(group)
        self.selected = group
        self._refresh()
        self.status.configure(text="Modèle ajouté : bloc vitesse")
        self._show_selected()

    def _new_element_name(self, kind: str) -> str:
        used = {element.attrib.get("name") for element in iter_editable(self.root_element)}
        index = 1
        candidate = f"{kind.replace('_', '-')}-{index}"
        while candidate in used:
            index += 1
            candidate = f"{kind.replace('_', '-')}-{index}"
        return candidate

    def _show_selected(self) -> None:
        if self.selected is None:
            return
        for item, element in self._canvas_items.items():
            if element is self.selected:
                self.canvas.see(item)
                return

    def delete_selected(self) -> None:
        if self.selected is None:
            return
        parent = parent_of(self.root_element, self.selected)
        if parent is None:
            return
        self._remember_state()
        parent.remove(self.selected)
        self.selected = None
        self._refresh()

    def duplicate_selected(self) -> None:
        if self.selected is None:
            return
        parent = parent_of(self.root_element, self.selected)
        if parent is None:
            return
        self._remember_state()
        duplicate = copy.deepcopy(self.selected)
        if duplicate.attrib.get("name"):
            duplicate.set("name", self._new_element_name(duplicate.attrib["name"] + "-copy"))
        index = list(parent).index(self.selected)
        parent.insert(index + 1, duplicate)
        self.selected = duplicate
        self._refresh()
        self.status.configure(text="Widget dupliqué")

    def move_layer(self, direction: int) -> None:
        if self.selected is None:
            return
        parent = parent_of(self.root_element, self.selected)
        if parent is None:
            return
        siblings = list(parent)
        index = siblings.index(self.selected)
        target = index + direction
        if target < 0 or target >= len(siblings):
            return
        self._remember_state()
        parent.remove(self.selected)
        parent.insert(target, self.selected)
        self._refresh()

    def _reparent_selected(self, new_parent: ET.Element, index: int) -> None:
        """Move the selected node while preserving its absolute canvas position."""
        if self.selected is None:
            return
        old_parent = parent_of(self.root_element, self.selected)
        if old_parent is None or old_parent is new_parent:
            return
        absolute_x, absolute_y = absolute_position(self.root_element, self.selected)
        new_parent_x, new_parent_y = absolute_position(self.root_element, new_parent)
        self._remember_state()
        old_parent.remove(self.selected)
        new_parent.insert(max(0, min(index, len(new_parent))), self.selected)
        self.selected.set("x", str(absolute_x - new_parent_x))
        self.selected.set("y", str(absolute_y - new_parent_y))
        self._refresh()

    def indent_selected(self) -> None:
        """Nest the selected node in the immediately preceding container."""
        if self.selected is None:
            return
        parent = parent_of(self.root_element, self.selected)
        if parent is None:
            return
        siblings = list(parent)
        index = siblings.index(self.selected)
        if index == 0:
            self.status.configure(text="Aucun groupe précédent")
            return
        target = siblings[index - 1]
        if target.tag not in {"composite", "translate", "frame"}:
            self.status.configure(text="L’élément précédent n’est pas un groupe")
            return
        self._reparent_selected(target, len(target))
        self.status.configure(text="Widget indenté dans le groupe précédent")

    def outdent_selected(self) -> None:
        """Move the selected node one level up in the XML hierarchy."""
        if self.selected is None:
            return
        parent = parent_of(self.root_element, self.selected)
        if parent is None or parent is self.root_element:
            self.status.configure(text="Déjà au niveau racine")
            return
        grandparent = parent_of(self.root_element, parent)
        if grandparent is None:
            return
        index = list(grandparent).index(parent) + 1
        self._reparent_selected(grandparent, index)
        self.status.configure(text="Widget désindenté")

    def _refresh(self) -> None:
        self.canvas.delete("all")
        self._canvas_items.clear()
        scaled_width = int(self.canvas_size[0] * self.zoom)
        scaled_height = int(self.canvas_size[1] * self.zoom)
        self.canvas.configure(scrollregion=(0, 0, scaled_width, scaled_height))
        self.zoom_label.configure(text=f"{round(self.zoom * 100)} %")
        if self.view_mode == "render":
            try:
                frame = self._render_real_preview()
                if self.zoom != 1.0:
                    frame = frame.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
                self._render_photo = ImageTk.PhotoImage(frame)
                self.canvas.create_image(0, 0, image=self._render_photo, anchor="nw")
                self._refresh_inspector()
                self._refresh_tree()
            except Exception as exc:
                self.canvas.create_text(20, 20, anchor="nw", text=f"Rendu impossible :\n{exc}", fill="#fca5a5")
                self._refresh_inspector()
                self._refresh_tree()
            return
        if self._background_photo is not None:
            background = self._background_photo
            if self.zoom != 1.0:
                with Image.open(self.background_path) as image:
                    image = image.convert("RGB")
                    image.thumbnail(self.canvas_size, Image.Resampling.LANCZOS)
                    background_image = Image.new("RGB", self.canvas_size, "#111827")
                    background_image.paste(image, ((self.canvas_size[0] - image.width) // 2, (self.canvas_size[1] - image.height) // 2))
                    background = ImageTk.PhotoImage(background_image.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS))
                    self._background_photo = background
            self.canvas.create_image(0, 0, image=background, anchor="nw")
        # A light grid makes alignment easier without changing the saved layout.
        if self.grid_enabled:
            for x in range(0, self.canvas_size[0] + 1, 100):
                self.canvas.create_line(x * self.zoom, 0, x * self.zoom, scaled_height, fill="#1f2937")
            for y in range(0, self.canvas_size[1] + 1, 100):
                self.canvas.create_line(0, y * self.zoom, scaled_width, y * self.zoom, fill="#1f2937")
        for element in iter_editable(self.root_element):
            self._draw_element(element)
        self._refresh_inspector()
        self._refresh_tree()

    def _draw_element(self, element: ET.Element) -> None:
        if id(element) in self.hidden:
            return
        x, y = absolute_position(self.root_element, element)
        width, height = preview_size(element)
        x, y = x * self.zoom, y * self.zoom
        width, height = width * self.zoom, height * self.zoom
        selected = element is self.selected
        fill = "#312e81" if selected else "#1f4b63"
        outline = "#c4b5fd" if selected else "#5eead4"
        if id(element) in self.locked:
            outline = "#f59e0b"
        rect = self.canvas.create_rectangle(x, y, x + width, y + height, fill=fill, outline=outline, width=2)
        self._canvas_items[rect] = element
        label = element.attrib.get("name") or "(sans nom)"
        label_item = self.canvas.create_text(x + 10 * self.zoom, y + 10 * self.zoom, anchor="nw", text=label, fill="#f8fafc", font=("TkDefaultFont", max(7, int(11 * self.zoom)), "bold"))
        self._canvas_items[label_item] = element
        detail = element.text.strip() if element.text and element.text.strip() else ""
        type_label = element_kind(element)
        detail = f"{type_label}  ·  {detail}" if detail else type_label
        if detail:
            text_item = self.canvas.create_text(x + 10 * self.zoom, y + 34 * self.zoom, anchor="nw", text=detail[:38], fill="#cbd5e1", font=("TkDefaultFont", max(6, int(10 * self.zoom))))
            self._canvas_items[text_item] = element
        if selected:
            handle = self.canvas.create_rectangle(x + width - 12, y + height - 12, x + width, y + height, fill="#c4b5fd", outline="")
            self._canvas_items[handle] = element

    def _element_at(self, event) -> ET.Element | None:
        current = self.canvas.find_withtag("current")
        return self._canvas_items.get(current[-1]) if current else None

    def _press(self, event) -> None:
        self.canvas.focus_set()
        element = self._element_at(event)
        if element is None:
            self.selected = None
            self._refresh()
            return
        self.selected = element
        if id(element) in self.locked:
            self._refresh()
            self.status.configure(text="Widget verrouillé")
            return
        self._remember_state()
        x, y = absolute_position(self.root_element, element)
        width, height = preview_size(element)
        cx = self.canvas.canvasx(event.x) / self.zoom
        cy = self.canvas.canvasy(event.y) / self.zoom
        if cx >= x + width - 18 and cy >= y + height - 18:
            self._resize_start = (int(cx), int(cy))
            self._resize_origin = (width, height)
            self._drag_start = None
        else:
            self._drag_start = (int(cx), int(cy))
            self._drag_origin = (x, y)
        self._refresh()

    def _drag(self, event) -> None:
        if self.selected is None:
            return
        cx, cy = int(self.canvas.canvasx(event.x) / self.zoom), int(self.canvas.canvasy(event.y) / self.zoom)
        if self._resize_start and self._resize_origin:
            width = max(24, self._resize_origin[0] + cx - self._resize_start[0])
            height = max(24, self._resize_origin[1] + cy - self._resize_start[1])
            self.selected.set("width", str(width))
            self.selected.set("height", str(height))
        elif self._drag_start and self._drag_origin:
            new_x = self._drag_origin[0] + cx - self._drag_start[0]
            new_y = self._drag_origin[1] + cy - self._drag_start[1]
            if self.snap_var.get():
                new_x = round(new_x / 10) * 10
                new_y = round(new_y / 10) * 10
            set_relative_position(self.root_element, self.selected, new_x, new_y)
        self._refresh()

    def _release(self, _event) -> None:
        self._drag_start = self._drag_origin = self._resize_start = self._resize_origin = None

    def _refresh_inspector(self) -> None:
        for child in list(self.inspector.winfo_children())[1:]:
            child.destroy()
        self.fields.clear()
        if self.selected is None:
            return
        ttk.Label(self.inspector, text=self.selected.attrib.get("name", "(sans nom)"), font=("TkDefaultFont", 12, "bold")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 2))
        ttk.Label(self.inspector, text=element_kind(self.selected), foreground="#667085").grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Button(self.inspector, text="+ Ajouter une option", command=self.add_attribute).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        attrs = list(self.selected.attrib)
        if "name" not in attrs:
            attrs.insert(0, "name")
        for row, name in enumerate(attrs, start=4):
            ttk.Label(self.inspector, text=name).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=3)
            entry = ttk.Entry(self.inspector, width=23)
            entry.insert(0, self.selected.attrib.get(name, ""))
            entry.bind("<Return>", lambda _event, n=name: self._apply_field(n))
            entry.bind("<FocusOut>", lambda _event, n=name: self._apply_field(n))
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            self.fields[name] = entry
        row = len(attrs) + 4
        ttk.Label(self.inspector, text="contenu").grid(row=row, column=0, sticky="nw", pady=3)
        text = tk.Text(self.inspector, height=4, width=22)
        text.insert("1.0", self.selected.text or "")
        text.bind("<FocusOut>", lambda _event: self._apply_text(text))
        text.grid(row=row, column=1, sticky="ew", pady=3)

    def _apply_field(self, name: str) -> None:
        if self.selected is None or name not in self.fields:
            return
        value = self.fields[name].get().strip()
        self._remember_state()
        if value:
            self.selected.set(name, value)
        else:
            self.selected.attrib.pop(name, None)
        self._refresh()

    def _apply_text(self, text: tk.Text) -> None:
        if self.selected is not None:
            self._remember_state()
            self.selected.text = text.get("1.0", "end-1c") or None
            self._refresh()

    def add_attribute(self) -> None:
        if self.selected is None:
            return
        dialog = tk.Toplevel(self)
        dialog.title("Nouvelle option")
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)
        ttk.Label(dialog, text="Nom").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        name_entry = ttk.Entry(dialog, width=26)
        name_entry.grid(row=0, column=1, padx=(0, 10), pady=8)
        ttk.Label(dialog, text="Valeur").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        value_entry = ttk.Entry(dialog, width=26)
        value_entry.grid(row=1, column=1, padx=(0, 10), pady=8)

        def confirm() -> None:
            name = name_entry.get().strip()
            if not name or any(char.isspace() for char in name):
                messagebox.showwarning("Option invalide", "Le nom doit être renseigné sans espace.", parent=dialog)
                return
            self.selected.set(name, value_entry.get())
            dialog.destroy()
            self._refresh()

        ttk.Button(dialog, text="Ajouter", command=confirm).grid(row=2, column=0, columnspan=2, pady=(0, 10))
        name_entry.focus_set()


def main() -> None:
    parser = argparse.ArgumentParser(description="Éditeur interactif de layouts XML GoPro Overlay")
    parser.add_argument("layout", nargs="?", type=Path, help="Layout XML à ouvrir")
    parser.add_argument("--overlay-size", help="Taille logique du canvas, ex. 1920x1080 (déduite du nom du fichier si absente)")
    args = parser.parse_args()
    if args.overlay_size:
        try:
            canvas_size = tuple(int(value) for value in args.overlay_size.lower().split("x", 1))
        except ValueError as exc:
            parser.error(f"--overlay-size invalide : {exc}")
    else:
        canvas_size = infer_canvas_size(args.layout)
    LayoutEditor(args.layout, canvas_size).mainloop()


if __name__ == "__main__":
    main()
