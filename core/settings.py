"""Хранение и валидация настроек приложения."""

from __future__ import annotations

import logging
import os
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.paths import backup_corrupt_file, load_json, write_json_atomic

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "AutoFill"
    return Path.home() / ".autofill"


def default_settings_path() -> Path:
    return app_data_dir() / "settings.json"


@dataclass
class AppSettings:
    version: int = SCHEMA_VERSION
    template_path: str = ""
    font_path: str = ""
    selected_font_family: str = ""
    selected_font_style: str = "Regular"
    font_size: int = 100
    text_color: tuple[int, int, int] = (0, 0, 0)
    letter_spacing: int = 0
    x: int = 0
    y: int = 0
    x_auto: bool = True
    y_auto: bool = True
    x_offset: int = 0
    y_offset: int = 0
    line_spacing: int = 4
    margin: int = 36
    safe_area_color: tuple[int, int, int] = (139, 92, 246)
    marker_color: tuple[int, int, int] = (139, 92, 246)
    align: str = "left"
    name_mode: str = "single_line"
    split_after: int = 1
    output_dir: str = ""
    output_format: str = "pdf"
    pdf_mode: str = "multi"
    pdf_name: str = "Все_грамоты"
    preview: bool = True
    preview_mode: str = "test"
    preview_custom: str = ""
    theme: str = "dark"
    ask_before_move: bool = True
    cleanup_previous: bool = False
    window_geometry: str = ""
    splitter_sizes: list[int] = field(default_factory=list)
    main_splitter_sizes: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clamp(value: int, low: int, high: int, default: int | None = None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        number = int(default if default is not None else low)
    return max(low, min(high, number))


def _parse_bool(value: Any, default: bool) -> bool:
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        return default
    if value is None:
        return default
    return bool(value)



def _parse_color(value: Any) -> tuple[int, int, int]:
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return tuple(_clamp(int(part), 0, 255) for part in value[:3])  # type: ignore[return-value]
        except (TypeError, ValueError):
            pass
    if isinstance(value, str) and value.startswith("#") and len(value) == 7:
        try:
            return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]
        except ValueError:
            pass
    return (0, 0, 0)


def normalize_settings(raw: dict[str, Any] | None) -> AppSettings:
    """Приводит произвольный словарь к валидной схеме."""

    if not isinstance(raw, dict):
        raw = {}
    defaults = AppSettings()
    data: dict[str, Any] = {}

    for field_name in defaults.__dataclass_fields__:
        if field_name in raw:
            data[field_name] = raw[field_name]

    data["version"] = SCHEMA_VERSION
    data["font_size"] = _clamp(
        data.get("font_size", defaults.font_size) or defaults.font_size,
        1, 2000, defaults.font_size,
    )
    data["letter_spacing"] = _clamp(
        data.get("letter_spacing", defaults.letter_spacing), -20, 200, defaults.letter_spacing,
    )
    data["x"] = _clamp(data.get("x", defaults.x), 0, 100000, defaults.x)
    data["y"] = _clamp(data.get("y", defaults.y), 0, 100000, defaults.y)
    data["x_offset"] = _clamp(
        data.get("x_offset", defaults.x_offset), -100000, 100000, defaults.x_offset,
    )
    data["y_offset"] = _clamp(
        data.get("y_offset", defaults.y_offset), -100000, 100000, defaults.y_offset,
    )
    data["line_spacing"] = _clamp(
        data.get("line_spacing", defaults.line_spacing), -100, 1000, defaults.line_spacing,
    )
    data["margin"] = _clamp(data.get("margin", defaults.margin), 0, 100000, defaults.margin)
    data["split_after"] = _clamp(
        data.get("split_after", defaults.split_after), 1, 30, defaults.split_after,
    )
    data["text_color"] = _parse_color(data.get("text_color", defaults.text_color))
    data["safe_area_color"] = _parse_color(
        data.get("safe_area_color", defaults.safe_area_color)
    )
    data["marker_color"] = _parse_color(data.get("marker_color", defaults.marker_color))

    if not isinstance(data.get("align"), str) or data["align"] not in {"left", "center", "right"}:
        data["align"] = defaults.align
    if not isinstance(data.get("name_mode"), str) or data["name_mode"] not in {
        "single_line", "split_surname", "split_all", "custom", "auto",
    }:
        data["name_mode"] = defaults.name_mode
    if not isinstance(data.get("output_format"), str) or data["output_format"] not in {"png", "pdf"}:
        data["output_format"] = defaults.output_format
    if not isinstance(data.get("pdf_mode"), str) or data["pdf_mode"] not in {"multi", "single"}:
        data["pdf_mode"] = defaults.pdf_mode
    if not isinstance(data.get("theme"), str) or data["theme"] not in {"dark", "light", "system"}:
        data["theme"] = defaults.theme
    if not isinstance(data.get("preview_mode"), str) or data["preview_mode"] not in {
        "test", "longest", "custom",
    }:
        data["preview_mode"] = defaults.preview_mode

    for field_name in (
        "template_path", "font_path", "selected_font_family",
        "selected_font_style", "output_dir", "pdf_name", "preview_custom",
        "window_geometry",
    ):
        if not isinstance(data.get(field_name), str):
            data[field_name] = getattr(defaults, field_name)

    for field_name in (
        "x_auto", "y_auto", "preview", "ask_before_move", "cleanup_previous",
    ):
        data[field_name] = _parse_bool(
            data.get(field_name, getattr(defaults, field_name)),
            getattr(defaults, field_name),
        )

    for field_name in ("splitter_sizes", "main_splitter_sizes"):
        value = data.get(field_name)
        if not isinstance(value, list):
            data[field_name] = []
        else:
            sizes: list[int] = []
            for item in value:
                if isinstance(item, (int, float)):
                    try:
                        sizes.append(max(0, int(item)))
                    except (TypeError, ValueError, OverflowError):
                        continue
            data[field_name] = sizes

    # Убираем неизвестные ключи, чтобы dataclass не падал.
    data = {key: value for key, value in data.items() if key in defaults.__dataclass_fields__}
    return AppSettings(**data)


class SettingsStore:
    def __init__(self, path: str | os.PathLike[str] | None = None):
        self.path = Path(path) if path else default_settings_path()

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        data = load_json(self.path, default=None)
        if not isinstance(data, dict):
            backup = backup_corrupt_file(self.path)
            log.warning("Повреждённые настройки сохранены в %s", backup)
            return AppSettings()
        return normalize_settings(data)

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self.path.exists():
                backup = self.path.with_suffix(self.path.suffix + ".bak")
                with suppress(OSError):
                    backup.write_bytes(self.path.read_bytes())
            write_json_atomic(self.path, settings.to_dict())
        except OSError as exc:
            log.exception("Не удалось сохранить настройки: %s", exc)
            raise
