from __future__ import annotations

from collections.abc import Sequence

from core.text_render import text_width


def format_name_lines(parts: Sequence[str], mode: str, split_after: int = 1) -> list[str] | None:
    """Разбивает ФИО на строки согласно выбранному режиму.

    ``None`` возвращается только для режима ``auto`` — решение о переносе
    принимает :func:`resolve_auto_lines` с учётом реальной ширины шрифта.
    """

    words = [str(part).strip() for part in parts if str(part).strip()]
    if not words:
        return [""]

    if mode == "single_line":
        return [" ".join(words)]
    if mode == "split_surname":
        if len(words) > 2:
            return [words[0], " ".join(words[1:])]
        return words
    if mode == "split_all":
        return words
    if mode == "custom":
        split_after = max(1, int(split_after))
        if len(words) <= split_after:
            return [" ".join(words)]
        return [" ".join(words[:split_after]), " ".join(words[split_after:])]
    if mode == "auto":
        return None
    return [" ".join(words)]


def wrap_text(
    text: str,
    font,
    max_width: float,
    letter_spacing: float = 0,
) -> list[str]:
    """Жадно переносит текст по словам на любое число строк."""

    words = text.split()
    if not words:
        return [""]

    max_width = max(1.0, float(max_width))
    lines: list[str] = []
    current = words[0]

    for word in words[1:]:
        candidate = f"{current} {word}"
        if text_width(candidate, font, letter_spacing) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


def resolve_auto_lines(
    parts: Sequence[str],
    font,
    letter_spacing: float,
    img_width: int,
    margin: float,
) -> list[str]:
    """Переносит ФИО по доступной ширине, а не только на две строки."""

    safe_width = max(1.0, float(img_width) - 2.0 * float(margin))
    return wrap_text(" ".join(str(part).strip() for part in parts if str(part).strip()), font, safe_width, letter_spacing)


def plural(n: int, forms: Sequence[str]) -> str:
    """forms = ('грамота', 'грамоты', 'грамот')"""

    n = abs(int(n)) % 100
    if 11 <= n <= 19:
        return forms[2]
    n = n % 10
    if n == 1:
        return forms[0]
    if 2 <= n <= 4:
        return forms[1]
    return forms[2]
