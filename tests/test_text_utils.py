"""Text utility tests."""

from src.utils.text_utils import truncate_utf16, utf16_length


def test_utf16_length_basic():
    assert utf16_length("abc") == 3


def test_utf16_length_emoji():
    assert utf16_length("😀") == 2


def test_truncate_utf16_basic():
    assert truncate_utf16("abcd", 3) == "abc"


def test_truncate_utf16_with_suffix():
    assert truncate_utf16("hello", 4, suffix="...") == "h..."


def test_truncate_utf16_emoji_suffix():
    assert truncate_utf16("😀😀", 3, suffix="...") == "😀"
