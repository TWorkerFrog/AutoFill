"""Рендер грамот и сохранение PNG/PDF без зависимости от Qt.

Модуль можно безопасно вызывать из worker-потока: здесь нет виджетов и
модальных диалогов.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import tempfile
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from core.name_format import format_name_lines, resolve_auto_lines
from core.paths import (
    PathAllocator,
    casefold_name,
    cleanup_manifest,
    ensure_output_dir,
    load_manifest,
    safe_filename,
    safe_pdf_stem,
    safe_stem_from_parts,
    save_manifest,
)
from core.text_render import draw_text_block

log = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]

DEFAULT_DPI = 150.0


@dataclass(frozen=True)
class RenderConfig:
    font_path: str
    font_size: int
    text_color: tuple[int, int, int] = (0, 0, 0)
    x: int | str = 0
    y: int | str = 0
    x_offset: int = 0
    y_offset: int = 0
    align: str = "left"
    line_spacing: int = 4
    letter_spacing: int = 0
    margin: int = 36
    name_mode: str = "single_line"
    split_after: int = 1


@dataclass(frozen=True)
class OutputConfig:
    output_dir: str
    output_format: str = "pdf"
    pdf_mode: str = "multi"
    pdf_name: str = "Все_грамоты"
    conflict_policy: str = "number"  # replace | number | skip | cancel
    cleanup_previous: bool = False


@dataclass(frozen=True)
class GenerationJob:
    template_path: str
    people: tuple[tuple[str, ...], ...]
    render: RenderConfig
    output: OutputConfig


@dataclass
class GenerationResult:
    output_dir: str
    created: int = 0
    skipped: int = 0
    cancelled: bool = False
    errors: list[tuple[str, str]] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.skipped + len(self.errors)


def _parse_dpi(info: dict) -> float:
    dpi = info.get("dpi")
    if isinstance(dpi, (tuple, list)) and dpi:
        try:
            value = float(dpi[0])
            if value >= 10:
                return value
        except (TypeError, ValueError):
            pass
    return DEFAULT_DPI


def load_template(path: str | os.PathLike[str]) -> tuple[Image.Image, float]:
    """Загружает шаблон, применяет EXIF-поворот и нормализует цветовой режим."""

    with Image.open(path) as source:
        source.load()
        image = ImageOps.exif_transpose(source)
        info = dict(source.info)
        dpi = _parse_dpi(info)
        if image.mode in ("RGB", "RGBA"):
            result = image.copy()
        elif image.mode in ("P", "LA") or "transparency" in info:
            result = image.convert("RGBA")
        else:
            result = image.convert("RGB")
    result.info["dpi"] = (dpi, dpi)
    return result, dpi


def load_font(config: RenderConfig) -> ImageFont.FreeTypeFont:
    if not config.font_path:
        raise FileNotFoundError("Файл шрифта не указан")
    if config.font_size <= 0:
        raise ValueError("Размер шрифта должен быть положительным")
    try:
        return ImageFont.truetype(config.font_path, size=config.font_size)
    except OSError as exc:
        raise FileNotFoundError(f"Файл шрифта не найден: {config.font_path}") from exc


def lines_for_parts(parts: Sequence[str], config: RenderConfig, font, img_width: int) -> list[str]:
    lines = format_name_lines(parts, config.name_mode, config.split_after)
    if lines is None:
        lines = resolve_auto_lines(parts, font, config.letter_spacing, img_width, config.margin)
    return lines


def render_page(
    template: Image.Image,
    parts: Sequence[str],
    font,
    config: RenderConfig,
) -> Image.Image:
    img = template.copy()
    draw = ImageDraw.Draw(img)
    lines = lines_for_parts(parts, config, font, img.width)
    draw_text_block(
        draw,
        lines,
        font,
        config.text_color,
        config.x,
        config.y,
        config.x_offset,
        config.y_offset,
        config.align,
        config.line_spacing,
        config.letter_spacing,
        img.width,
        img.height,
    )
    return img


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image.copy()
    rgba = image.convert("RGBA")
    background = Image.new("RGB", rgba.size, (255, 255, 255))
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def _save_atomic(image: Image.Image, path: Path, *, as_pdf: bool, dpi: float, title: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    try:
        if as_pdf:
            page = _flatten_to_rgb(image)
            kwargs = {"resolution": float(dpi)}
            if title:
                kwargs.update({"title": title, "author": "AutoFill", "creator": "AutoFill"})
            try:
                page.save(temp_name, "PDF", **kwargs)
            except (TypeError, ValueError):
                page.save(temp_name, "PDF", resolution=float(dpi))
        else:
            image.save(temp_name, "PNG", dpi=(float(dpi), float(dpi)))
        os.replace(temp_name, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(temp_name)
        raise


def _relative_files(output_dir: Path, files: Iterable[str]) -> list[str]:
    result: list[str] = []
    for item in files:
        try:
            result.append(Path(item).resolve().relative_to(output_dir).as_posix())
        except (ValueError, OSError):
            continue
    return result


def _write_manifest(output_dir: Path, new_files: Iterable[str]) -> None:
    existing = set(load_manifest(output_dir))
    existing.update(_relative_files(output_dir, new_files))
    save_manifest(output_dir, existing)


def _avoid_template_target(
    target: Path,
    template_path: Path,
    allocator: PathAllocator,
    stem: str,
    suffix: str,
    used_names: set[str] | None = None,
) -> Path:
    """Не позволяет выходному файлу совпасть с выбранным шаблоном."""

    try:
        same = os.path.normcase(str(target.resolve())) == os.path.normcase(str(template_path))
    except OSError:
        same = False
    if not same:
        return target
    replacement = allocator.resolve(stem, suffix)
    if used_names is not None:
        used_names.add(casefold_name(replacement.name))
    log.warning("Имя результата совпало с шаблоном; выбрано: %s", replacement.name)
    return replacement


def _safe_target(
    allocator: PathAllocator | None,
    output_dir: Path,
    stem: str,
    suffix: str,
    policy: str,
    used_names: set[str] | None = None,
) -> tuple[Path, bool]:
    """Выбирает цель с учётом политики и повторов имён в одном запуске."""

    base = output_dir / f"{safe_filename(stem)}{suffix}"
    key = casefold_name(base.name)
    if allocator is None:
        allocator = PathAllocator(output_dir)

    duplicate_in_run = used_names is not None and key in used_names
    if policy == "cancel":
        if base.exists():
            return base, True
        if duplicate_in_run:
            return allocator.resolve(stem, suffix), False
        if used_names is not None:
            used_names.add(key)
        allocator.reserve(base)
        return base, False
    if policy == "replace":
        if duplicate_in_run:
            return allocator.resolve(stem, suffix), False
        if used_names is not None:
            used_names.add(key)
        allocator.reserve(base)
        return base, False
    if policy == "skip":
        if duplicate_in_run:
            # Одинаковые ФИО в одном запуске должны получить разные файлы.
            return allocator.resolve(stem, suffix), False
        if base.exists():
            return base, True
        if used_names is not None:
            used_names.add(key)
        allocator.reserve(base)
        return base, False

    # number: PathAllocator сам учитывает имена, занятые ранее в этом запуске.
    target = allocator.resolve(stem, suffix)
    if used_names is not None:
        used_names.add(casefold_name(target.name))
    return target, False


def _try_merge_pdfs(page_paths: Sequence[Path], target: Path, title: str) -> bool:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return False

    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    os.close(fd)
    try:
        writer = PdfWriter()
        for page_path in page_paths:
            reader = PdfReader(str(page_path))
            for page in reader.pages:
                writer.add_page(page)
        if title:
            writer.add_metadata({
                "/Title": title,
                "/Author": "AutoFill",
                "/Creator": "AutoFill",
            })
        with open(temp_name, "wb") as handle:
            writer.write(handle)
        writer.close()
        os.replace(temp_name, target)
        return True
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(temp_name)
        log.exception("Не удалось объединить PDF")
        return False


def _save_single_pdf(
    job: GenerationJob,
    template: Image.Image,
    font,
    dpi: float,
    output_dir: Path,
    target: Path,
    result: GenerationResult,
    progress: ProgressCallback | None,
    cancel_event: threading.Event | None,
) -> None:
    import importlib.util

    people = list(job.people)
    total = len(people)
    has_pypdf = importlib.util.find_spec("pypdf") is not None
    temp_dir = Path(tempfile.mkdtemp(prefix=".autofill-pdf-", dir=output_dir))
    page_paths: list[Path] = []
    images: list[Image.Image] = []
    try:
        for index, parts in enumerate(people, 1):
            if cancel_event is not None and cancel_event.is_set():
                result.cancelled = True
                break
            name = " ".join(parts)
            try:
                image = render_page(template, parts, font, job.render)
                if has_pypdf:
                    page_path = temp_dir / f"{index:05d}.pdf"
                    _save_atomic(image, page_path, as_pdf=True, dpi=dpi, title=name)
                    page_paths.append(page_path)
                else:
                    # Без pypdf страницы приходится держать в памяти: Pillow не
                    # умеет открывать PDF-страницы для повторной сборки.
                    images.append(_flatten_to_rgb(image))
                result.created += 1
            except Exception as exc:
                log.exception("Ошибка PDF-страницы %s", name)
                result.errors.append((name, str(exc)))
            if progress:
                progress(index, total, name)

        if result.cancelled or not (page_paths or images):
            return

        if has_pypdf:
            if not _try_merge_pdfs(page_paths, target, job.output.pdf_name):
                raise RuntimeError("Не удалось объединить PDF-страницы")
            result.files.append(str(target))
            return

        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        os.close(fd)
        try:
            kwargs = {
                "resolution": dpi,
                "save_all": True,
                "append_images": images[1:],
                "title": job.output.pdf_name,
                "author": "AutoFill",
            }
            try:
                images[0].save(temp_name, "PDF", **kwargs)
            except (TypeError, ValueError):
                images[0].save(
                    temp_name,
                    "PDF",
                    resolution=dpi,
                    save_all=True,
                    append_images=images[1:],
                )
            os.replace(temp_name, target)
            result.files.append(str(target))
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(temp_name)
            raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def generate(
    job: GenerationJob,
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> GenerationResult:
    """Выполняет задание и возвращает точный отчёт."""

    output_dir = ensure_output_dir(job.output.output_dir)
    result = GenerationResult(output_dir=str(output_dir))
    template_path = Path(job.template_path).resolve()
    template, dpi = load_template(job.template_path)
    font = load_font(job.render)

    if job.output.cleanup_previous:
        removed, cleanup_errors = cleanup_manifest(output_dir, exclude=template_path)
        log.info("Очищено файлов по манифесту: %s", removed)
        for error in cleanup_errors:
            log.warning("Очистка: %s", error)

    total = len(job.people)
    if progress:
        progress(0, total, "")

    if job.output.output_format == "pdf" and job.output.pdf_mode == "single":
        stem = safe_pdf_stem(job.output.pdf_name)
        allocator = PathAllocator(output_dir)
        target, skip = _safe_target(allocator, output_dir, stem, ".pdf", job.output.conflict_policy)
        if job.output.conflict_policy == "cancel" and target.exists():
            result.cancelled = True
            return result
        if skip:
            result.skipped = total
            return result
        target = _avoid_template_target(
            target, template_path, allocator, stem, ".pdf",
        )
        _save_single_pdf(job, template, font, dpi, output_dir, target, result, progress, cancel_event)
        if result.files:
            _write_manifest(output_dir, result.files)
        return result

    suffix = ".png" if job.output.output_format == "png" else ".pdf"
    allocator = PathAllocator(output_dir)
    used_names: set[str] = set()
    for index, parts in enumerate(job.people, 1):
        if cancel_event is not None and cancel_event.is_set():
            result.cancelled = True
            break

        name = " ".join(parts)
        stem = safe_stem_from_parts(parts)
        try:
            target, skip = _safe_target(
                allocator, output_dir, stem, suffix, job.output.conflict_policy, used_names,
            )
            if job.output.conflict_policy == "cancel" and target.exists():
                result.cancelled = True
                break
            if not skip:
                target = _avoid_template_target(
                    target, template_path, allocator, stem, suffix, used_names,
                )
            if skip:
                result.skipped += 1
            else:
                image = render_page(template, parts, font, job.render)
                _save_atomic(
                    image,
                    target,
                    as_pdf=suffix == ".pdf",
                    dpi=dpi,
                    title=name,
                )
                result.created += 1
                result.files.append(str(target))
        except Exception as exc:
            log.exception("Ошибка генерации %s", name)
            result.errors.append((name, str(exc)))

        if progress:
            progress(index, total, name)

    if result.files:
        _write_manifest(output_dir, result.files)
    return result
