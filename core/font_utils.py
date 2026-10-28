"""Сканирование системных шрифтов и безопасный выбор файла шрифта."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.ttLib.ttCollection import TTCollection

from core.paths import write_json_atomic

log = logging.getLogger(__name__)

_CACHE_VERSION = 2
_FONT_SUFFIXES = (".ttf", ".otf", ".ttc")
_STYLE_SUFFIXES = (
    "ExtraLight", "UltraLight", "SemiBold", "ExtraBold", "UltraBold",
    "Thin", "Light", "Regular", "Medium", "Bold", "Black", "Italic",
)


def _cache_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    root = Path(base) / "AutoFill" if base else Path.home() / ".autofill"
    return root / "fonts_cache.json"


def _name_record_value(font: TTFont, name_id: int) -> str | None:
    try:
        name_table = font["name"]
    except KeyError:
        return None

    records = [record for record in name_table.names if record.nameID == name_id]
    if not records:
        return None

    def score(record) -> tuple[int, int]:
        # Английский (US) и Windows/Unicode — в приоритете, затем любые.
        return (
            0 if record.platformID == 3 and record.langID == 0x409 else 1,
            0 if record.platformID == 3 else 1,
        )

    for record in sorted(records, key=score):
        try:
            value = record.toUnicode().strip()
        except Exception:
            continue
        if value:
            return value
    return None


def get_font_metadata(path: str | os.PathLike[str]) -> tuple[str | None, str | None]:
    """Читает типографическое семейство и стиль из TTF/OTF/TTC."""

    font = None
    collection = None
    try:
        suffix = Path(path).suffix.lower()
        if suffix == ".ttc":
            collection = TTCollection(path, lazy=True)
            if not collection.fonts:
                return None, None
            font = collection.fonts[0]
        else:
            font = TTFont(path, lazy=True, fontNumber=0)

        # 16/17 — типографические family/subfamily; 1/2 — legacy.
        family = _name_record_value(font, 16) or _name_record_value(font, 1)
        style = _name_record_value(font, 17) or _name_record_value(font, 2) or "Regular"
        return family, style
    except Exception as exc:
        log.debug("Не удалось прочитать шрифт %s: %s", path, exc)
        return None, None
    finally:
        try:
            if font is not None:
                font.close()
            if collection is not None:
                collection.close()
        except Exception:
            pass


def _font_roots() -> list[Path]:
    if os.name != "nt":
        return [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path.home() / ".local" / "share" / "fonts",
            Path.home() / "Library" / "Fonts",
        ]

    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return [
        windir / "Fonts",
        local_appdata / "Microsoft" / "Windows" / "Fonts",
    ]


def _roots_signature(roots: list[Path]) -> dict[str, list[int]]:
    signature: dict[str, list[int]] = {}
    for root in roots:
        try:
            stat = root.stat()
            signature[str(root)] = [stat.st_mtime_ns, stat.st_size]
        except OSError:
            signature[str(root)] = [0, 0]
    return signature


def _load_cache(roots: list[Path]) -> list[list[str]] | None:
    try:
        with open(_cache_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("version") != _CACHE_VERSION:
        return None
    if data.get("roots") != _roots_signature(roots):
        return None
    fonts = data.get("fonts")
    if not isinstance(fonts, list):
        return None
    valid = [
        item for item in fonts
        if isinstance(item, list) and len(item) == 3 and all(isinstance(part, str) for part in item)
    ]
    return valid


def _save_cache(roots: list[Path], entries: list[list[str]]) -> None:
    try:
        write_json_atomic(
            _cache_path(),
            {
                "version": _CACHE_VERSION,
                "created": int(time.time()),
                "roots": _roots_signature(roots),
                "fonts": entries,
            },
        )
    except OSError as exc:
        log.debug("Не удалось сохранить кеш шрифтов: %s", exc)


def _build_fonts(entries: list[tuple[str, str, str]]) -> dict[str, dict[str, str]]:
    fonts: dict[str, dict[str, str]] = {}
    for path, family, style in entries:
        family = family.strip()
        style = (style or "Regular").strip() or "Regular"
        if not family:
            family = Path(path).stem
        fonts.setdefault(family, {})
        # Не перезаписываем уже найденный файл: стабильный результат скана.
        fonts[family].setdefault(style, str(path))

    _merge_style_suffix_families(fonts)
    return dict(sorted(fonts.items(), key=lambda item: item[0].casefold()))


def _merge_style_suffix_families(fonts: dict[str, dict[str, str]]) -> None:
    """Мягко объединяет «Montserrat Black» с «Montserrat»/«Black».

    Делается только если базовое семейство уже существует.  «Arial Narrow» и
    «PT Sans Narrow» не затрагиваются, потому что Narrow нет в списке стилей.
    """

    for family in list(fonts):
        if " " not in family:
            continue
        base, suffix = family.rsplit(" ", 1)
        if base not in fonts or suffix not in _STYLE_SUFFIXES:
            continue

        target = fonts[base]
        for style, path in fonts[family].items():
            if style in ("Regular", "Book"):
                new_style = suffix
            elif style in ("Italic", "Oblique"):
                new_style = f"{suffix} Italic"
            else:
                new_style = f"{suffix} {style}"
            target.setdefault(new_style, path)
        del fonts[family]


def scan_fonts(use_cache: bool = True) -> dict[str, dict[str, str]]:
    """Сканирует системные шрифты и возвращает ``family -> style -> path``."""

    roots = [root for root in _font_roots() if root.exists()]
    if use_cache:
        cached = _load_cache(roots)
        if cached is not None:
            return _build_fonts([(item[0], item[1], item[2]) for item in cached])

    entries: list[tuple[str, str, str]] = []
    seen_paths: set[str] = set()
    for root in roots:
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                if not filename.lower().endswith(_FONT_SUFFIXES):
                    continue
                path = os.path.join(dirpath, filename)
                path_key = os.path.normcase(os.path.abspath(path))
                if path_key in seen_paths:
                    continue
                seen_paths.add(path_key)
                family, style = get_font_metadata(path)
                entries.append((path, family or Path(filename).stem, style or "Regular"))

    entries.sort(key=lambda item: (item[1].casefold(), item[2].casefold(), item[0].casefold()))
    if use_cache:
        _save_cache(roots, [[path, family, style] for path, family, style in entries])
    return _build_fonts(entries)


def resolve_font_path(
    fonts: dict[str, dict[str, str]],
    family: str,
    style: str = "Regular",
) -> str | None:
    """Точно (без учёта регистра) находит путь к файлу шрифта."""

    family = (family or "").strip()
    style = (style or "Regular").strip()
    if not family:
        return None

    family_key = family.casefold()
    matched_family = next((name for name in fonts if name.casefold() == family_key), None)
    if matched_family is None:
        return None

    styles = fonts[matched_family]
    style_key = style.casefold()
    matched_style = next((name for name in styles if name.casefold() == style_key), None)
    if matched_style is None:
        matched_style = next((name for name in styles if name.casefold() == "regular"), None)
    if matched_style is None and styles:
        matched_style = sorted(styles, key=str.casefold)[0]
    if matched_style is None:
        return None

    path = styles[matched_style]
    return path if os.path.isfile(path) else None
