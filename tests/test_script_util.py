import pytest

from script_util import normalize_script


def test_normalize_script_strips_and_ok():
    assert normalize_script("  hello  ", max_chars=100) == "hello"


def test_normalize_script_truncates():
    long = "a" * 100
    out = normalize_script(long, max_chars=10)
    assert out == "a" * 10


def test_normalize_script_rejects_none():
    with pytest.raises(ValueError, match="None"):
        normalize_script(None, max_chars=100)


def test_normalize_script_rejects_blank():
    with pytest.raises(ValueError, match="empty"):
        normalize_script("   \n", max_chars=100)
