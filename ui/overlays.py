"""Векторные направляющие поверх предпросмотра.

Поля для печати рисуются отдельными QGraphicsItem, а не запекаются в растр.
Перо ``cosmetic`` сохраняет толщину линии при любом масштабе, поэтому граница
не исчезает на больших шаблонах и не зависит от успешности рендера текста.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsScene

SAFE_AREA_COLOR = QColor("#8B5CF6")
SAFE_AREA_UNDERLAY = QColor(255, 255, 255, 120)


def safe_area_rect(width: int, height: int, margin: int) -> QRectF | None:
    """Возвращает прямоугольник полей для печати в координатах изображения."""

    margin = max(0, int(margin))
    if margin <= 0 or width <= 2 or height <= 2:
        return None
    margin = min(margin, width // 2, height // 2)
    if width <= margin * 2 or height <= margin * 2:
        return None
    return QRectF(
        float(margin),
        float(margin),
        float(width - margin * 2 - 1),
        float(height - margin * 2 - 1),
    )


def add_safe_area(
    scene: QGraphicsScene,
    width: int,
    height: int,
    margin: int,
    *,
    z: float = 10.0,
) -> list[QGraphicsRectItem]:
    """Добавляет в сцену аккуратную cosmetic-рамку полей для печати."""

    rect = safe_area_rect(width, height, margin)
    if rect is None:
        return []

    underlay = QGraphicsRectItem(rect)
    underlay_pen = QPen(SAFE_AREA_UNDERLAY)
    underlay_pen.setWidthF(2.4)
    underlay_pen.setCosmetic(True)
    underlay.setPen(underlay_pen)
    underlay.setBrush(Qt.NoBrush)
    underlay.setAcceptedMouseButtons(Qt.NoButton)
    underlay.setZValue(z)
    scene.addItem(underlay)

    line = QGraphicsRectItem(rect)
    line_pen = QPen(SAFE_AREA_COLOR)
    line_pen.setWidthF(1.2)
    line_pen.setCosmetic(True)
    line_pen.setStyle(Qt.DashLine)
    line_pen.setDashPattern([5.0, 5.0])
    line.setPen(line_pen)
    line.setBrush(Qt.NoBrush)
    line.setAcceptedMouseButtons(Qt.NoButton)
    line.setZValue(z + 1)
    scene.addItem(line)

    return [underlay, line]


def set_safe_area_visible(items: list[QGraphicsRectItem], visible: bool) -> None:
    for item in items:
        item.setVisible(visible)
