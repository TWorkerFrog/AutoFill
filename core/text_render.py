"""Измерение и отрисовка текстовых блоков.

Модуль намеренно не зависит от Qt.  Координаты ``x``/``y`` задают точку
привязки *блока*, а ``align`` — выравнивание строк внутри блока.  Это разделение
устраняет старую путаницу, когда выравнивание одновременно управляло и
положением блока, и положением строки.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from PIL import ImageDraw, ImageFont

Align = Literal["left", "center", "right"]
AnchorX = int | float | Literal["center"]
AnchorY = int | float | Literal["center"]


@dataclass(frozen=True)
class BlockMetrics:
    """Геометрия многострочного блока в пикселях."""

    width: float
    height: float
    line_widths: tuple[float, ...]
    line_heights: tuple[float, ...]
    ascent: int
    descent: int
    line_spacing: float = 0.0


@dataclass(frozen=True)
class BlockLayout:
    """Результат раскладки блока на изображении."""

    metrics: BlockMetrics
    left: float
    top: float
    align: Align

    @property
    def right(self) -> float:
        return self.left + self.metrics.width

    @property
    def bottom(self) -> float:
        return self.top + self.metrics.height

    def line_left(self, index: int) -> float:
        line_width = self.metrics.line_widths[index]
        if self.align == "center":
            return self.left + (self.metrics.width - line_width) / 2.0
        if self.align == "right":
            return self.left + self.metrics.width - line_width
        return self.left

    def line_top(self, index: int) -> float:
        return self.top + sum(self.metrics.line_heights[:index]) + (
            index * self.metrics.line_spacing
        )


def _font_metrics(font: ImageFont.ImageFont | ImageFont.FreeTypeFont) -> tuple[int, int]:
    try:
        ascent, descent = font.getmetrics()
    except Exception:
        ascent, descent = 0, 0
    return max(0, int(ascent)), max(0, int(descent))


def text_width(text: str, font: ImageFont.ImageFont | ImageFont.FreeTypeFont, letter_spacing: float = 0) -> float:
    """Ширина строки по advance-ширинам, а не по чернилам.

    Для ``letter_spacing == 0`` используется ``font.getlength`` — это учитывает
    кернинг.  При дополнительном трекинге символы рисуются по одному, поэтому
    ширина считается как сумма advance-ширин символов.
    """

    if not text:
        return 0.0
    if not letter_spacing:
        try:
            return float(font.getlength(text))
        except Exception:
            return 0.0
    total = sum(float(font.getlength(ch)) for ch in text)
    return total + float(letter_spacing) * (len(text) - 1)


def measure_block(
    lines: Sequence[str],
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    letter_spacing: float = 0,
    line_spacing: float = 0,
) -> BlockMetrics:
    """Измеряет блок по advance-ширинам и метрикам шрифта."""

    lines = list(lines)
    ascent, descent = _font_metrics(font)
    line_height = float(ascent + descent)
    widths = tuple(max(0.0, text_width(line, font, letter_spacing)) for line in lines)
    heights = tuple(line_height for _ in lines)
    width = max(widths, default=0.0)
    height = sum(heights) + line_spacing * max(0, len(lines) - 1)
    return BlockMetrics(
        width=width,
        height=height,
        line_widths=widths,
        line_heights=heights,
        ascent=ascent,
        descent=descent,
        line_spacing=float(line_spacing),
    )


def resolve_block_origin(
    x: AnchorX,
    y: AnchorY,
    block_width: float,
    block_height: float,
    img_width: int,
    img_height: int,
    align: Align = "left",
    x_offset: float = 0,
    y_offset: float = 0,
) -> tuple[float, float]:
    """Вычисляет левый верхний угол блока.

    - ``x == "center"`` — блок центрируется независимо от выравнивания строк;
    - числовой ``x`` — левый/центральный/правый край блока в зависимости от
      ``align``;
    - ``y == "center"`` — блок центрируется по вертикали;
    - числовой ``y`` — верх блока.
    """

    if x == "center":
        left = (img_width - block_width) / 2.0
    elif align == "center":
        left = float(x) - block_width / 2.0
    elif align == "right":
        left = float(x) - block_width
    else:
        left = float(x)

    top = (img_height - block_height) / 2.0 if y == "center" else float(y)

    return left + x_offset, top + y_offset


def layout_block(
    lines: Sequence[str],
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    x: AnchorX,
    y: AnchorY,
    align: Align,
    letter_spacing: float,
    line_spacing: float,
    img_width: int,
    img_height: int,
    x_offset: float = 0,
    y_offset: float = 0,
) -> BlockLayout:
    lines = list(lines)
    metrics = measure_block(lines, font, letter_spacing, line_spacing)
    left, top = resolve_block_origin(
        x,
        y,
        metrics.width,
        metrics.height,
        img_width,
        img_height,
        align,
        x_offset,
        y_offset,
    )
    # line_spacing уже сохранён в metrics и используется при расчёте baseline.
    return BlockLayout(metrics=metrics, left=left, top=top, align=align)


def iter_line_positions(layout: BlockLayout) -> Iterable[tuple[float, float]]:
    """Возвращает ``(left, baseline)`` для каждой строки блока."""

    baseline = layout.top + layout.metrics.ascent
    for index, height in enumerate(layout.metrics.line_heights):
        yield layout.line_left(index), baseline
        baseline += height + layout.metrics.line_spacing


def draw_text_block(
    draw: ImageDraw.ImageDraw,
    lines: Sequence[str],
    font,
    color,
    x: AnchorX,
    y: AnchorY,
    x_offset: float,
    y_offset: float,
    align: Align,
    line_spacing: float,
    letter_spacing: float,
    img_width: int,
    img_height: int,
) -> BlockLayout:
    """Рисует многострочный блок и возвращает его геометрию."""

    lines = list(lines)
    layout = layout_block(
        lines,
        font,
        x,
        y,
        align,
        letter_spacing,
        line_spacing,
        img_width,
        img_height,
        x_offset,
        y_offset,
    )

    for line, (line_left, baseline) in zip(lines, iter_line_positions(layout), strict=True):
        if not letter_spacing:
            draw.text((line_left, baseline), line, fill=color, font=font, anchor="ls")
            continue
        current_x = line_left
        for ch in line:
            draw.text((current_x, baseline), ch, fill=color, font=font, anchor="ls")
            current_x += float(font.getlength(ch)) + letter_spacing

    return layout


def check_text_bounds(
    lines: Sequence[str],
    font,
    x: AnchorX,
    align: Align,
    letter_spacing: float,
    img_width: int,
    margin: float,
    img_height: int | None = None,
    y: AnchorY | None = None,
    x_offset: float = 0,
    y_offset: float = 0,
    line_spacing: float = 0,
) -> list[tuple[str, int, str]]:
    """Проверяет выход текста за safe-area.

    Возвращает список ``(строка, переполнение_в_px, сторона)``.  Стороны:
    ``left``, ``right``, ``top``, ``bottom``.  Никаких временных изображений не
    создаётся.
    """

    lines = list(lines)
    if not lines:
        return []

    # Без высоты изображения проверить вертикаль невозможно.
    check_y = y if y is not None else 0
    check_height = img_height if img_height is not None else max(
        1, int(measure_block(lines, font, letter_spacing, line_spacing).height + margin * 2 + 1)
    )
    layout = layout_block(
        lines,
        font,
        x,
        check_y,
        align,
        letter_spacing,
        line_spacing,
        img_width,
        check_height,
        x_offset,
        y_offset,
    )

    problems: list[tuple[str, int, str]] = []
    for index, line in enumerate(lines):
        line_left = layout.line_left(index)
        line_right = line_left + layout.metrics.line_widths[index]
        if line_left < margin:
            problems.append((line, _ceil(margin - line_left), "left"))
        if line_right > img_width - margin:
            problems.append((line, _ceil(line_right - (img_width - margin)), "right"))

    if img_height is not None and y is not None:
        if layout.top < margin:
            problems.append(("", _ceil(margin - layout.top), "top"))
        if layout.bottom > img_height - margin:
            problems.append(("", _ceil(layout.bottom - (img_height - margin)), "bottom"))

    return problems


def _ceil(value: float) -> int:
    return max(0, int(value + 0.999999))
