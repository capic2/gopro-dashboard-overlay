"""Interactive editor for the XML overlay layouts.

The renderer deliberately remains independent from Tkinter.  This editor works
on the same XML structure as :mod:`gopro_overlay.layout_xml`, so it is useful
even when a layout contains widgets that cannot be previewed without telemetry.
"""

from __future__ import annotations

import argparse
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Iterable
from xml.etree import ElementTree as ET


PALETTE = (
    ("text", "Texte"),
    ("metric", "Métrique"),
    ("metric_unit", "Métrique + unité"),
    ("icon", "Icône"),
    ("frame", "Cadre"),
    ("composite", "Groupe"),
    ("moving_map", "Carte mobile"),
    ("chart", "Graphique"),
    ("gforce_circle", "G-Force"),
)


def _number(element: ET.Element, name: str, default: int) -> int:
    try:
        return int(float(element.attrib.get(name, default)))
    except (TypeError, ValueError):
        return default


def iter_editable(root: ET.Element) -> Iterable[ET.Element]:
    """Yield drawable nodes, excluding the synthetic layout root."""
    return (node for node in root.iter() if node.tag in {"component", "composite", "translate", "frame"})


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


def preview_size(element: ET.Element) -> tuple[int, int]:
    size = max(24, _number(element, "size", 48))
    width = _number(element, "width", 0)
    height = _number(element, "height", 0)
    if width <= 0:
        width = max(110, min(360, size * 4))
    if height <= 0:
        height = max(42, min(180, size * 2))
    return width, height


class LayoutEditor(tk.Tk):
    """A small, dependency-free visual XML layout editor."""

    def __init__(self, layout_path: Path | None = None, canvas_size: tuple[int, int] = (1920, 1080)):
        super().__init__()
        self.title("GoPro Overlay — éditeur de layout")
        self.geometry("1400x850")
        self.minsize(980, 620)
        self.canvas_size = canvas_size
        self.layout_path = layout_path
        self.root_element = ET.Element("layout")
        self.selected: ET.Element | None = None
        self._canvas_items: dict[int, ET.Element] = {}
        self._drag_start: tuple[int, int] | None = None
        self._drag_origin: tuple[int, int] | None = None
        self._resize_start: tuple[int, int] | None = None
        self._resize_origin: tuple[int, int] | None = None
        self._build_ui()
        if layout_path:
            self.load(layout_path)
        else:
            self._refresh()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=(10, 8))
        toolbar.grid(row=0, column=0, columnspan=3, sticky="ew")
        ttk.Button(toolbar, text="Ouvrir", command=self.open_layout).pack(side="left")
        ttk.Button(toolbar, text="Enregistrer", command=self.save_layout).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Nouveau", command=self.new_layout).pack(side="left")
        self.status = ttk.Label(toolbar, text="Sélectionnez un élément")
        self.status.pack(side="right")

        palette = ttk.LabelFrame(self, text="Ajouter un élément", padding=8)
        palette.grid(row=1, column=0, sticky="ns", padx=(10, 6), pady=(0, 10))
        for type_name, label in PALETTE:
            ttk.Button(palette, text=f"+ {label}", command=lambda t=type_name: self.add_element(t)).pack(fill="x", pady=3)
        ttk.Separator(palette).pack(fill="x", pady=12)
        ttk.Label(palette, text="Canvas logique").pack(anchor="w")
        ttk.Label(palette, text=f"{self.canvas_size[0]} × {self.canvas_size[1]} px", foreground="#667085").pack(anchor="w")
        ttk.Label(palette, text="Glisser : déplacer\nPoignée violette : redimensionner\nSuppr : supprimer", foreground="#667085").pack(anchor="w", pady=(18, 0))

        canvas_frame = ttk.Frame(self)
        canvas_frame.grid(row=1, column=1, sticky="nsew", pady=(0, 10))
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(canvas_frame, background="#111827", highlightthickness=0, scrollregion=(0, 0, *self.canvas_size))
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

        inspector = ttk.LabelFrame(self, text="Configuration", padding=8)
        inspector.grid(row=1, column=2, sticky="ns", padx=(6, 10), pady=(0, 10))
        inspector.columnconfigure(1, weight=1)
        self.inspector = inspector
        self.fields: dict[str, ttk.Entry] = {}
        ttk.Label(inspector, text="Sélectionnez un élément\npour modifier ses options.", foreground="#667085").grid(column=0, row=0, columnspan=2, sticky="w")

    def load(self, path: Path) -> None:
        self.layout_path = path
        self.root_element = ET.parse(path).getroot()
        self.selected = None
        self._refresh()

    def open_layout(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Layout XML", "*.xml"), ("Tous les fichiers", "*")])
        if path:
            try:
                self.load(Path(path))
            except (ET.ParseError, OSError) as exc:
                messagebox.showerror("Ouverture impossible", str(exc))

    def new_layout(self) -> None:
        self.layout_path = None
        self.root_element = ET.Element("layout")
        self.selected = None
        self._refresh()

    def save_layout(self) -> None:
        path = self.layout_path
        if path is None:
            chosen = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("Layout XML", "*.xml")])
            if not chosen:
                return
            path = Path(chosen)
            self.layout_path = path
        ET.indent(self.root_element, space="    ")
        ET.ElementTree(self.root_element).write(path, encoding="utf-8", xml_declaration=False)
        self.status.configure(text=f"Enregistré : {path.name}")

    def add_element(self, type_name: str) -> None:
        tag = "component"
        if type_name in {"composite", "frame"}:
            tag = type_name
        element = ET.Element(tag)
        if tag == "component":
            element.set("type", type_name)
        element.update({"x": "80", "y": "80", "size": "32"})
        if type_name == "text":
            element.text = "Nouveau texte"
        if type_name == "metric":
            element.set("metric", "speed")
        if type_name == "metric_unit":
            element.set("metric", "speed")
            element.text = "{:~P}"
        if type_name == "icon":
            element.set("file", "gauge.png")
        if tag == "frame":
            element.update({"width": "260", "height": "110", "bg": "20,25,35,190"})
        if tag == "composite":
            element.set("name", "nouveau_groupe")
        self.root_element.append(element)
        self.selected = element
        self._refresh()

    def delete_selected(self) -> None:
        if self.selected is None:
            return
        for parent in self.root_element.iter():
            if self.selected in list(parent):
                parent.remove(self.selected)
                break
        self.selected = None
        self._refresh()

    def _refresh(self) -> None:
        self.canvas.delete("all")
        self._canvas_items.clear()
        # A light grid makes alignment easier without changing the saved layout.
        for x in range(0, self.canvas_size[0] + 1, 100):
            self.canvas.create_line(x, 0, x, self.canvas_size[1], fill="#1f2937")
        for y in range(0, self.canvas_size[1] + 1, 100):
            self.canvas.create_line(0, y, self.canvas_size[0], y, fill="#1f2937")
        for element in iter_editable(self.root_element):
            self._draw_element(element)
        self._refresh_inspector()

    def _draw_element(self, element: ET.Element) -> None:
        x, y = absolute_position(self.root_element, element)
        width, height = preview_size(element)
        selected = element is self.selected
        fill = "#312e81" if selected else "#1f4b63"
        outline = "#c4b5fd" if selected else "#5eead4"
        rect = self.canvas.create_rectangle(x, y, x + width, y + height, fill=fill, outline=outline, width=2)
        self._canvas_items[rect] = element
        label = element.attrib.get("name") or element.attrib.get("type") or element.tag
        label_item = self.canvas.create_text(x + 10, y + 10, anchor="nw", text=label, fill="#f8fafc", font=("TkDefaultFont", 11, "bold"))
        self._canvas_items[label_item] = element
        detail = element.text.strip() if element.text and element.text.strip() else ""
        if detail:
            text_item = self.canvas.create_text(x + 10, y + 34, anchor="nw", text=detail[:30], fill="#cbd5e1")
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
        x, y = absolute_position(self.root_element, element)
        width, height = preview_size(element)
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
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
        cx, cy = int(self.canvas.canvasx(event.x)), int(self.canvas.canvasy(event.y))
        if self._resize_start and self._resize_origin:
            width = max(24, self._resize_origin[0] + cx - self._resize_start[0])
            height = max(24, self._resize_origin[1] + cy - self._resize_start[1])
            self.selected.set("width", str(width))
            self.selected.set("height", str(height))
        elif self._drag_start and self._drag_origin:
            set_relative_position(self.root_element, self.selected, self._drag_origin[0] + cx - self._drag_start[0], self._drag_origin[1] + cy - self._drag_start[1])
        self._refresh()

    def _release(self, _event) -> None:
        self._drag_start = self._drag_origin = self._resize_start = self._resize_origin = None

    def _refresh_inspector(self) -> None:
        for child in list(self.inspector.winfo_children())[1:]:
            child.destroy()
        self.fields.clear()
        if self.selected is None:
            return
        ttk.Label(self.inspector, text=self.selected.attrib.get("type", self.selected.tag), font=("TkDefaultFont", 12, "bold")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 8))
        ttk.Button(self.inspector, text="+ Ajouter une option", command=self.add_attribute).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        attrs = list(self.selected.attrib)
        for row, name in enumerate(attrs, start=3):
            ttk.Label(self.inspector, text=name).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=3)
            entry = ttk.Entry(self.inspector, width=23)
            entry.insert(0, self.selected.attrib[name])
            entry.bind("<Return>", lambda _event, n=name: self._apply_field(n))
            entry.bind("<FocusOut>", lambda _event, n=name: self._apply_field(n))
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            self.fields[name] = entry
        row = len(attrs) + 3
        ttk.Label(self.inspector, text="contenu").grid(row=row, column=0, sticky="nw", pady=3)
        text = tk.Text(self.inspector, height=4, width=22)
        text.insert("1.0", self.selected.text or "")
        text.bind("<FocusOut>", lambda _event: self._apply_text(text))
        text.grid(row=row, column=1, sticky="ew", pady=3)

    def _apply_field(self, name: str) -> None:
        if self.selected is None or name not in self.fields:
            return
        value = self.fields[name].get().strip()
        if value:
            self.selected.set(name, value)
        else:
            self.selected.attrib.pop(name, None)
        self._refresh()

    def _apply_text(self, text: tk.Text) -> None:
        if self.selected is not None:
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
    parser.add_argument("--overlay-size", default="1920x1080", help="Taille logique du canvas, ex. 1920x1080")
    args = parser.parse_args()
    try:
        width, height = (int(value) for value in args.overlay_size.lower().split("x", 1))
    except ValueError as exc:
        parser.error(f"--overlay-size invalide : {exc}")
    LayoutEditor(args.layout, (width, height)).mainloop()


if __name__ == "__main__":
    main()
