import xml.etree.ElementTree as ET
from pathlib import Path

from gopro_overlay.layout_editor import absolute_position, infer_canvas_size, preview_size, set_relative_position


def test_absolute_position_includes_nested_parent_offsets():
    root = ET.fromstring('<layout><composite x="100" y="40"><component type="text" x="20" y="7" /></composite></layout>')
    child = next(root.iter("component"))

    assert absolute_position(root, child) == (120, 47)


def test_set_relative_position_preserves_parent_coordinates():
    root = ET.fromstring('<layout><composite x="100" y="40"><component type="text" x="20" y="7" /></composite></layout>')
    child = next(root.iter("component"))

    set_relative_position(root, child, 200, 90)

    assert child.attrib["x"] == "100"
    assert child.attrib["y"] == "50"
    assert absolute_position(root, child) == (200, 90)


def test_preview_size_uses_explicit_dimensions_and_defaults_for_components():
    assert preview_size(ET.fromstring('<component type="frame" width="300" height="120" />')) == (300, 120)
    assert preview_size(ET.fromstring('<component type="metric" size="32" />')) == (128, 64)


def test_canvas_size_is_inferred_from_layout_filename():
    assert infer_canvas_size(Path("layout_parapente_3840.xml")) == (3840, 2160)
    assert infer_canvas_size(None) == (1920, 1080)
