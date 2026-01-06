"""Text utilities for safe length handling."""


def utf16_length(text: str) -> int:
    """Return UTF-16 code unit length."""
    return len(text.encode("utf-16-le")) // 2


def _slice_utf16(text: str, max_units: int) -> str:
    if max_units <= 0:
        return ""
    units = 0
    end_index = 0
    for ch in text:
        ch_units = 1 if ord(ch) <= 0xFFFF else 2
        if units + ch_units > max_units:
            break
        units += ch_units
        end_index += 1
    return text[:end_index]


def truncate_utf16(text: str, max_units: int, suffix: str = "") -> str:
    """Truncate text to max UTF-16 units, optionally adding suffix."""
    if max_units <= 0:
        return ""
    if utf16_length(text) <= max_units:
        return text
    if suffix:
        suffix_units = utf16_length(suffix)
        if suffix_units >= max_units:
            return _slice_utf16(text, max_units)
        available = max_units - suffix_units
        return f"{_slice_utf16(text, available)}{suffix}"
    return _slice_utf16(text, max_units)
