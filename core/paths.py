"""Безопасные пути, имена файлов и манифест созданных документов."""

from __future__ import annotations

import codecs
import json
import os
import re
import tempfile
import time
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path

MANIFEST_NAME = ".autofill-manifest.json"
MANIFEST_VERSION = 1

_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def safe_filename(stem: str, max_length: int = 100, fallback: str = "грамота") -> str:
    """Делает безопасное имя файла без расширения.

    Убирает запрещённые Windows-символы и управляющие символы, пробелы и точки
    в конце, зарезервированные имена и чрезмерную длину.
    """

    value = str(stem or "")
    value = _INVALID_FILENAME.sub("_", value)
    value = _WHITESPACE.sub(" ", value).strip(" .")
    value = value.replace("\ufeff", "")

    if not value:
        value = fallback

    base = value.split(".", 1)[0].upper()
    if base in _RESERVED_NAMES:
        value = f"_{value}"

    value = value[:max_length].rstrip(" .")
    return value or fallback


def safe_stem_from_parts(parts: Iterable[str], max_length: int = 100) -> str:
    joined = "_".join(str(part).strip() for part in parts if str(part).strip())
    return safe_filename(joined, max_length=max_length)


def safe_pdf_stem(name: str, fallback: str = "Все_грамоты") -> str:
    """Имя общего PDF без повторного добавления расширения ``.pdf``."""

    stem = safe_filename(str(name or ""), fallback=fallback)
    while stem.casefold().endswith(".pdf") and len(stem) > 4:
        stem = safe_filename(stem[:-4], fallback=fallback)
    return stem


def casefold_name(name: str) -> str:
    return name.casefold()


class PathAllocator:
    """Выдаёт уникальные (без учёта регистра) пути в каталоге."""

    def __init__(self, directory: str | os.PathLike[str]):
        self.directory = Path(directory)
        self._used = {
            casefold_name(item.name)
            for item in self.directory.iterdir()
        } if self.directory.exists() else set()

    def reserve(self, path: str | os.PathLike[str]) -> None:
        """Помечает имя занятым в текущем запуске (без создания файла)."""

        self._used.add(casefold_name(Path(path).name))

    def resolve(self, stem: str, suffix: str) -> Path:
        suffix = suffix if suffix.startswith(".") else f".{suffix}"
        stem = safe_filename(stem)
        candidate = self.directory / f"{stem}{suffix}"
        if casefold_name(candidate.name) not in self._used:
            self._used.add(casefold_name(candidate.name))
            return candidate

        counter = 2
        while True:
            name = f"{stem}_{counter}{suffix}"
            candidate = self.directory / name
            if casefold_name(candidate.name) not in self._used:
                self._used.add(casefold_name(candidate.name))
                return candidate
            counter += 1


def ensure_output_dir(
    path: str | os.PathLike[str] | None,
    *,
    fallback: str | os.PathLike[str] | None = None,
) -> Path:
    """Создаёт каталог и проверяет, что в него можно писать."""

    directory = Path(path).expanduser() if path else (
        Path(fallback).expanduser() if fallback else Path.home() / "Documents" / "AutoFill"
    )
    if not directory.is_absolute():
        directory = (Path.home() / directory).resolve()
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)

    try:
        fd, probe = tempfile.mkstemp(prefix=".autofill-write-", dir=directory)
        os.close(fd)
        os.unlink(probe)
    except OSError as exc:
        raise PermissionError(f"Нет прав на запись в папку «{directory}»") from exc

    return directory


def read_text_file(path: str | os.PathLike[str]) -> str:
    """Читает текстовый список в UTF-8/UTF-16/CP1251.

    UTF-16 определяется только по BOM: иначе произвольный чётный набор байт
    (например, CP1251) можно ошибочно принять за UTF-16.
    """

    data = Path(path).read_bytes()
    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        try:
            return data.decode("utf-16")
        except UnicodeError:
            pass
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1251")


def write_text_file_atomic(path: str | os.PathLike[str], text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temp_name, path)
    except Exception:
        with suppress(OSError):
            os.unlink(temp_name)
        raise


def write_json_atomic(path: str | os.PathLike[str], data) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    write_text_file_atomic(path, text + "\n")


def load_json(path: str | os.PathLike[str], default=None):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return default


def backup_corrupt_file(path: str | os.PathLike[str]) -> Path | None:
    path = Path(path)
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
    try:
        os.replace(path, backup)
        return backup
    except OSError:
        return None


def manifest_path(directory: str | os.PathLike[str]) -> Path:
    return Path(directory) / MANIFEST_NAME


def load_manifest(directory: str | os.PathLike[str]) -> list[str]:
    data = load_json(manifest_path(directory), default={})
    if isinstance(data, dict):
        files = data.get("files", [])
    elif isinstance(data, list):
        files = data
    else:
        files = []

    if not isinstance(files, list):
        return []
    return [str(item) for item in files if isinstance(item, str) and item]


def save_manifest(directory: str | os.PathLike[str], files: Iterable[str]) -> Path:
    directory = Path(directory)
    clean: list[str] = []
    for item in files:
        # В манифест попадают только относительные имена внутри output dir.
        candidate = Path(item)
        if candidate.is_absolute() or ".." in candidate.parts:
            continue
        clean.append(candidate.as_posix())
    unique = sorted(dict.fromkeys(clean))
    path = manifest_path(directory)
    write_json_atomic(path, {"version": MANIFEST_VERSION, "files": unique})
    return path


def cleanup_manifest(
    directory: str | os.PathLike[str],
    *,
    exclude: str | os.PathLike[str] | None = None,
) -> tuple[int, list[str]]:
    """Удаляет только файлы, перечисленные в манифесте.

    Возвращает ``(удалено, ошибки)``.  Каталоги и чужие файлы не трогаются.
    Если какой-то файл удалить не удалось, он остаётся в манифесте, чтобы
    повторная очистка не потеряла его из виду.  ``exclude`` защищает выбранный
    шаблон от удаления, даже если он попал в манифест прошлого запуска.
    """

    directory = Path(directory).resolve()
    excluded = Path(exclude).resolve() if exclude else None
    excluded_key = os.path.normcase(str(excluded)) if excluded is not None else None
    removed = 0
    errors: list[str] = []
    remaining: list[str] = []
    for item in load_manifest(directory):
        candidate = (directory / item).resolve()
        try:
            candidate.relative_to(directory)
        except ValueError:
            errors.append(f"Пропущен путь вне папки: {item}")
            continue
        if excluded_key is not None and os.path.normcase(str(candidate)) == excluded_key:
            # Шаблон — входной файл, а не результат очистки.  Убираем его из
            # манифеста, чтобы будущие запуски тоже его не трогали.
            continue
        if not candidate.is_file():
            continue
        try:
            candidate.unlink()
            removed += 1
        except OSError as exc:
            remaining.append(item)
            errors.append(f"{candidate.name}: {exc}")

    manifest = manifest_path(directory)
    try:
        if remaining:
            save_manifest(directory, remaining)
        else:
            manifest.unlink(missing_ok=True)
    except OSError as exc:
        errors.append(f"Не удалось обновить манифест: {exc}")
    return removed, errors
