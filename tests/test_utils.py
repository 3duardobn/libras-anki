import os
from libras_anki.utils import get_output_dir

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
