"""Пикер цвета в стиле Figma: SV-квадрат, полосы тона и прозрачности, hex.

Вместо системного диалога Windows: он не умеет альфа-канал и выглядит
по-английски.  Здесь прозрачность задаётся в процентах 0–100, как в Figma,
а итоговый цвет собирается в RGBA.
"""

from __future__ import annotations

import logging
from contextlib import suppress

from PySide6.QtCore import QPointF, QRect, QRegularExpression, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QRegularExpressionValidator,
)
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
)

from core.i18n import tr

log = logging.getLogger(__name__)

COLOR_FORMATS = ("Hex", "RGB", "HSL")
_current_format = "Hex"
_format_listeners: list = []


def on_color_format_changed(callback) -> None:
    """Регистрирует колбэк на смену формата ввода цвета."""

    if callback not in _format_listeners:
        _format_listeners.append(callback)


def _remove_format_listener(callback) -> None:
    with suppress(ValueError):
        _format_listeners.remove(callback)


def set_color_format(fmt: str) -> None:
    """Запоминает формат ввода цвета (Hex/RGB/HSL) и оповещает слушателей."""

    global _current_format
    _current_format = fmt if fmt in COLOR_FORMATS else "Hex"
    for callback in list(_format_listeners):
        with suppress(Exception):
            callback()


def color_format() -> str:
    return _current_format


def _persist_color_format(fmt: str) -> None:
    """Сохраняет формат в settings.json сразу, не дожидаясь выхода."""

    try:
        from core.settings import SettingsStore

        store = SettingsStore()
        settings = store.load()
        if settings.color_input_format == fmt:
            return
        settings.color_input_format = fmt
        store.save(settings)
    except OSError as exc:
        log.debug("Не удалось сохранить формат ввода цвета: %s", exc)


def _checker_pixmap(size: int = 12) -> QPixmap:
    pixmap = QPixmap(size * 2, size * 2)
    painter = QPainter(pixmap)
    painter.fillRect(pixmap.rect(), QColor("#FFFFFF"))
    painter.fillRect(QRect(0, 0, size, size), QColor("#C8C8C8"))
    painter.fillRect(QRect(size, size, size, size), QColor("#C8C8C8"))
    painter.end()
    return pixmap


class _GradientStrip(QFrame):
    """Вертикальная или горизонтальная полоса с градиентом и ручкой."""

    changed = Signal(float)  # позиция 0..1

    def __init__(self, *, horizontal: bool, fixed_size: int, parent=None):
        super().__init__(parent)
        self._horizontal = horizontal
        self._position = 0.0
        self._pixmap: QPixmap | None = None
        if horizontal:
            self.setFixedHeight(fixed_size)
        else:
            self.setFixedWidth(fixed_size)
        self.setMinimumWidth(120 if horizontal else 24)
        self.setMinimumHeight(24 if horizontal else 120)
        self.setCursor(Qt.CrossCursor)

    def set_position(self, value: float) -> None:
        self._position = max(0.0, min(1.0, value))
        self.update()

    def position(self) -> float:
        return self._position

    def set_gradient(self, builder) -> None:
        """Перерисовывает полосу: builder(w, h) -> QImage."""

        width = max(1, self.width())
        height = max(1, self.height())
        self._pixmap = QPixmap.fromImage(builder(width, height))
        self.update()

    def mousePressEvent(self, event) -> None:
        self._pick(event)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.LeftButton:
            self._pick(event)
        event.accept()

    def _pick(self, event) -> None:
        if self._horizontal:
            self._position = max(0.0, min(1.0, event.position().x() / max(1, self.width())))
        else:
            self._position = max(0.0, min(1.0, 1.0 - event.position().y() / max(1, self.height())))
        self.changed.emit(self._position)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if self._pixmap is not None:
            painter.drawPixmap(self.rect(), self._pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#FFFFFF"))
        pen.setWidth(2)
        painter.setPen(pen)
        size = 12
        if self._horizontal:
            x = self._position * self.width()
            painter.drawEllipse(QPointF(x, self.height() / 2), size / 2, size / 2)
            painter.setPen(QPen(QColor("#000000")))
            painter.drawEllipse(QPointF(x, self.height() / 2), size / 2 + 1, size / 2 + 1)
        else:
            y = (1.0 - self._position) * self.height()
            painter.drawEllipse(QPointF(self.width() / 2, y), size / 2, size / 2)
            painter.setPen(QPen(QColor("#000000")))
            painter.drawEllipse(QPointF(self.width() / 2, y), size / 2 + 1, size / 2 + 1)
        painter.end()


class _SvSquare(QFrame):
    """Квадрат насыщенности и яркости (S по горизонтали, V по вертикали)."""

    changed = Signal(float, float)  # saturation, value (0..1)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hue = 0.0
        self._s = 1.0
        self._v = 1.0
        self.setMinimumSize(180, 150)
        self.setCursor(Qt.CrossCursor)

    def set_color(self, hue: float, saturation: float, value: float) -> None:
        self._hue = hue
        self._s = saturation
        self._v = value
        self.update()

    def mousePressEvent(self, event) -> None:
        self._pick(event)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.LeftButton:
            self._pick(event)
        event.accept()

    def _pick(self, event) -> None:
        self._s = max(0.0, min(1.0, event.position().x() / max(1, self.width())))
        self._v = max(0.0, min(1.0, 1.0 - event.position().y() / max(1, self.height())))
        self.changed.emit(self._s, self._v)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        width, height = max(1, self.width()), max(1, self.height())
        image = QImage(width, height, QImage.Format_RGB32)
        for x in range(width):
            for y in range(height):
                image.setPixelColor(
                    x, y,
                    QColor.fromHsvF(self._hue, x / width, 1.0 - y / height),
                )
        painter.drawImage(self.rect(), image)
        painter.setRenderHint(QPainter.Antialiasing)
        cx, cy = self._s * width, (1.0 - self._v) * height
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.drawEllipse(QPointF(cx, cy), 7, 7)
        painter.setPen(QPen(QColor("#000000"), 1))
        painter.drawEllipse(QPointF(cx, cy), 8, 8)
        painter.end()


class ColorPickerDialog(QDialog):
    """Диалог выбора цвета: SV-квадрат + тон + прозрачность + hex."""

    def __init__(self, parent=None, caption: str = "", current=(0, 0, 0, 255)):
        super().__init__(parent)
        self.setWindowTitle(caption or tr("Цвет"))
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setModal(True)
        self.setFixedWidth(404)
        self.setMinimumHeight(430)

        red, green, blue, alpha = (list(current) + [255])[:4]
        initial = QColor(red, green, blue, alpha)
        hue, sat, val, _ = initial.getHsvF()
        if hue < 0:
            hue = 0.0
        self._hue = hue
        self._alpha = alpha / 255.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        self.sv_square = _SvSquare()
        layout.addWidget(self.sv_square)

        self.hue_strip = _GradientStrip(horizontal=True, fixed_size=16)
        layout.addWidget(self.hue_strip)

        self.alpha_strip = _GradientStrip(horizontal=True, fixed_size=16)
        layout.addWidget(self.alpha_strip)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        # Формат ввода как в Figma: Hex / RGB / HSL.  Для RGB и HSL - три
        # отдельных бокса с числами: запятые вручную набирать не нужно.
        self.format_combo = QComboBox()
        for label in COLOR_FORMATS:
            self.format_combo.addItem(label)
        self.format_combo.setCurrentText(color_format())
        self.format_combo.setFixedWidth(70)
        self.format_combo.setToolTip(tr("Формат ввода цвета"))
        bottom.addWidget(self.format_combo)

        self.value_stack = QStackedWidget()
        self.value_stack.setFixedHeight(34)

        # Hex: одно текстовое поле без альфы (она задаётся в процентах).
        # Значение в «плашке» — как в рядах цвета главного окна: один инпут,
        # внутри которого светло-серые перегородки между числами.
        def _plate() -> tuple[QFrame, QHBoxLayout]:
            plate = QFrame()
            plate.setObjectName("color_field")
            plate_layout = QHBoxLayout(plate)
            plate_layout.setContentsMargins(5, 3, 5, 3)
            plate_layout.setSpacing(6)
            return plate, plate_layout

        def _separator() -> QFrame:
            line = QFrame()
            line.setObjectName("color_sep")
            line.setFixedWidth(1)
            line.setFixedHeight(16)
            return line

        # Hex: одно текстовое поле без альфы (она задаётся в процентах).
        hex_page, hex_layout = _plate()
        self.hex_edit = QLineEdit()
        self.hex_edit.setPlaceholderText("F3E8E0")
        self.hex_edit.setValidator(
            QRegularExpressionValidator(QRegularExpression("#?[0-9A-Fa-f]{0,8}"))
        )
        hex_layout.addWidget(self.hex_edit)
        self.value_stack.addWidget(hex_page)

        # RGB: три компактных бокса 0–255 с перегородками.
        rgb_page, rgb_layout = _plate()
        self.rgb_spins: list[QSpinBox] = []
        for _index in range(3):
            if _index:
                rgb_layout.addWidget(_separator())
            spin = QSpinBox()
            spin.setRange(0, 255)
            spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            spin.setAlignment(Qt.AlignCenter)
            spin.setMinimumWidth(34)
            rgb_layout.addWidget(spin, 1)
            self.rgb_spins.append(spin)
        self.value_stack.addWidget(rgb_page)

        # HSL: тон 0–360, насыщенность и светлота 0–100.
        hsl_page, hsl_layout = _plate()
        self.hsl_spins: list[QSpinBox] = []
        for _index in range(3):
            if _index:
                hsl_layout.addWidget(_separator())
            spin = QSpinBox()
            spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            spin.setAlignment(Qt.AlignCenter)
            spin.setMinimumWidth(34)
            hsl_layout.addWidget(spin, 1)
            self.hsl_spins.append(spin)
        self.hsl_spins[0].setRange(0, 360)
        self.hsl_spins[1].setRange(0, 100)
        self.hsl_spins[2].setRange(0, 100)
        self.value_stack.addWidget(hsl_page)
        self.value_stack.setCurrentIndex(COLOR_FORMATS.index(color_format()))

        bottom.addWidget(self.value_stack, 1)

        self.alpha_spin = QSpinBox()
        self.alpha_spin.setRange(0, 100)
        self.alpha_spin.setValue(max(0, min(100, round(alpha / 2.55))))
        self.alpha_spin.setSuffix(" %")
        self.alpha_spin.setFixedWidth(96)
        self.alpha_spin.setToolTip(tr("Непрозрачность в процентах"))
        bottom.addWidget(self.alpha_spin)
        layout.addLayout(bottom)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel_btn = QPushButton(tr("Отмена"))
        cancel_btn.setObjectName("tertiary_btn")
        cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)
        ok_btn = QPushButton(tr("Готово"))
        ok_btn.setObjectName("primary_btn")
        ok_btn.setAutoDefault(False)
        ok_btn.clicked.connect(self.accept)
        footer.addWidget(ok_btn)
        layout.addLayout(footer)

        self.sv_square.set_color(self._hue, sat, val)
        self._current_s, self._current_v = sat, val
        self.hue_strip.set_position(self._hue)
        self.alpha_strip.set_position(self._alpha)

        self.hue_strip.changed.connect(self._on_hue)
        self.alpha_strip.changed.connect(self._on_alpha)
        self.sv_square.changed.connect(self._on_sv)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        self.hex_edit.editingFinished.connect(self._on_hex_edited)
        for spin in self.rgb_spins:
            spin.valueChanged.connect(self._on_rgb_changed)
        for spin in self.hsl_spins:
            spin.valueChanged.connect(self._on_hsl_changed)
        self.alpha_spin.valueChanged.connect(self._on_alpha_percent)

        self._loading_fields = False
        self._repaint_strips()
        self._sync_fields()

    # ------------------------------------------------------------------
    # Пересчёты
    # ------------------------------------------------------------------
    def _rgba(self) -> tuple[int, int, int, int]:
        color = QColor.fromHsvF(self._hue, self._current_s, self._current_v)
        return color.red(), color.green(), color.blue(), round(self._alpha * 255)

    def _repaint_strips(self) -> None:
        hue = self._hue

        def hue_builder(width: int, height: int) -> QImage:
            image = QImage(width, height, QImage.Format_RGB32)
            for x in range(width):
                color = QColor.fromHsvF(x / max(1, width - 1), 1.0, 1.0)
                for y in range(height):
                    image.setPixelColor(x, y, color)
            return image

        def alpha_builder(width: int, height: int) -> QImage:
            image = QImage(width, height, QImage.Format_ARGB32)
            base = QColor.fromHsvF(hue, self._current_s, self._current_v)
            for x in range(width):
                color = QColor(base)
                color.setAlphaF(x / max(1, width - 1))
                for y in range(height):
                    image.setPixelColor(x, y, color)
            return image

        self.hue_strip.set_gradient(hue_builder)
        self.alpha_strip.set_gradient(alpha_builder)

    def _sync_fields(self) -> None:
        """Обновляет поля ввода под текущий цвет и активный формат."""

        red, green, blue, alpha = self._rgba()
        self._loading_fields = True
        try:
            fmt = self.format_combo.currentText()
            if fmt == "Hex":
                self.hex_edit.setText(f"{red:02X}{green:02X}{blue:02X}")
            elif fmt == "RGB":
                for spin, part in zip(self.rgb_spins, (red, green, blue), strict=False):
                    spin.setValue(part)
            elif fmt == "HSL":
                color = QColor(red, green, blue)
                hue, sat, light, _ = color.getHslF()
                values = (
                    round(hue * 360) if hue >= 0 else 0,
                    round(sat * 100),
                    round(light * 100),
                )
                for spin, part in zip(self.hsl_spins, values, strict=False):
                    spin.setValue(part)
        finally:
            self._loading_fields = False
        self.alpha_spin.blockSignals(True)
        self.alpha_spin.setValue(max(0, min(100, round(alpha / 2.55))))
        self.alpha_spin.blockSignals(False)

    def _apply_rgb_color(self, color: QColor) -> None:
        """Принимает разобранный цвет; альфа остаётся в процентном поле."""

        color.setAlphaF(self._alpha)
        hue, sat, val, _ = color.getHsvF()
        if hue < 0:
            hue = 0.0
        self._hue, self._current_s, self._current_v = hue, sat, val
        self.sv_square.set_color(self._hue, sat, val)
        self.hue_strip.set_position(self._hue)
        self._repaint_strips()
        self._sync_fields()

    def _on_format_changed(self, _index: int) -> None:
        fmt = self.format_combo.currentText()
        set_color_format(fmt)
        # Формат запоминается сразу: при следующем открытии пикера и во
        # всех полях цвета он будет применён.
        _persist_color_format(fmt)
        self.value_stack.setCurrentIndex(self.format_combo.currentIndex())
        self._sync_fields()

    def _on_hue(self, position: float) -> None:
        self._hue = position
        self.sv_square.set_color(self._hue, self._current_s, self._current_v)
        self._repaint_strips()
        self._sync_fields()

    def _on_sv(self, saturation: float, value: float) -> None:
        self._current_s, self._current_v = saturation, value
        self._repaint_strips()
        self._sync_fields()

    def _on_alpha(self, position: float) -> None:
        self._alpha = position
        self._sync_fields()

    def _on_alpha_percent(self, value: int) -> None:
        self._alpha = value / 100.0
        self.alpha_strip.set_position(self._alpha)

    def _on_hex_edited(self) -> None:
        """Разбирает hex; 6-значный ввод сохраняет текущую прозрачность."""

        text = self.hex_edit.text().strip().lstrip("#")
        if len(text) in (6, 8) and all(ch in "0123456789abcdefABCDEF" for ch in text):
            color = QColor(f"#{text}")
            if color.isValid() and not self._loading_fields:
                self._apply_rgb_color(color)

    def _on_rgb_changed(self, _value: int) -> None:
        if self._loading_fields:
            return
        red, green, blue = (spin.value() for spin in self.rgb_spins)
        self._apply_rgb_color(QColor(red, green, blue))

    def _on_hsl_changed(self, _value: int) -> None:
        if self._loading_fields:
            return
        hue, sat, light = (spin.value() for spin in self.hsl_spins)
        self._apply_rgb_color(
            QColor.fromHslF(
                (hue % 360) / 360.0,
                sat / 100.0,
                light / 100.0,
            )
        )

    def selected_rgba(self) -> tuple[int, int, int, int]:
        return self._rgba()


def open_color_picker(
    parent,
    theme: str,
    caption: str,
    current: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    """Открывает оформленный пикер; возвращает RGBA или None."""

    dialog = ColorPickerDialog(parent, caption, current)
    dialog.setObjectName("color_picker_dialog")
    # Тема применяется вызывающей стороной через apply_theme_to_dialog,
    # но и прямой вызов должен работать.
    if theme:
        dialog.setProperty("theme", theme)
    if hasattr(parent, "apply_theme_to_dialog"):
        parent.apply_theme_to_dialog(dialog, theme)
    else:
        from ui.themed_dialogs import apply_theme_tree, apply_title_bar

        apply_theme_tree(dialog, theme)
        apply_title_bar(dialog, theme)
    if dialog.exec() == int(QDialog.Accepted):
        return dialog.selected_rgba()
    return None
