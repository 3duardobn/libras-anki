import os
from libras_anki.utils import get_output_dir, sanitize_svg_for_qt

def test_get_output_dir_empty():
    res = get_output_dir(None)
    assert os.path.isabs(res)
    assert res.endswith("output")

def test_get_output_dir_absolute():
    abs_path = os.path.abspath("some/folder")
    assert get_output_dir(abs_path) == abs_path

def test_get_output_dir_relative():
    res = get_output_dir("animais")
    assert os.path.isabs(res)
    assert res.endswith(os.path.join("output", "animais"))

def test_get_output_dir_already_starts_with_output():
    res = get_output_dir("output/cores")
    assert os.path.isabs(res)
    assert res.endswith(os.path.join("output", "cores"))

def test_sanitize_svg_for_qt():
    raw_svg = (
        b'<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="50" height="38" viewBox="0 0 50 38">\n'
        b'  <text font-size="0">invisible</text>\n'
        b'  <svg x="10" y="20"><path d="M0 0 L10 10" /></svg>\n'
        b'</svg>'
    )
    clean = sanitize_svg_for_qt(raw_svg)
    assert b'<svg' in clean
    assert b'<text' not in clean  # font-size=0 removed
    assert b'<g transform="translate(10, 20)"' in clean  # nested svg converted to g
    assert b'</g>' in clean

def test_sanitize_svg_empty():
    assert sanitize_svg_for_qt(b"") == b""
    assert sanitize_svg_for_qt("") == b""

