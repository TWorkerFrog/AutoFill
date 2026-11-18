"""Поле цвета в стиле Figma: компактная плашка и значение в строке-инпуте.

Отображение подстраивается под выбранный формат ввода (Hex/RGB/HSL из
:mod:`ui.color_picker`): в Hex-режиме это текстовое поле, в RGB и HSL -
три мини-бокса с числами.  Клик по плашке открывает пикер, значения правятся
прямо в поле.  Альфа хранится внутри (RGBA) и показывается в пикере
процентами.
"""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression, Qt, Signal
from PySide6.QtGui import QColor, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QWidget,
)

from core.i18n import tr
from ui.color_picker import (
    COLOR_FORMATS,
    _remove_format_listener,
    color_format,
    on_color_format_changed,
    open_color_picker,
)


def clamp_rgba(color) -> tuple[int, int, int, int]:
    """Приводит цвет (3 или 4 компонента) к кортежу RGBA."""

    parts = [int(part) for part in tuple(color)][:4]
    while len(parts) < 4:
        parts.append(255)
    return tuple(max(0, min(255, part)) for part in parts)  # type: ignore[return-value]


class ColorField(QFrame):
    """Строка-инпут: плашка + значение в активном формате (Hex/RGB/HSL)."""

    changed = Signal(tuple)

    def __init__(self, rgba=(0, 0, 0, 255), *, title: str = "Цвет", parent=None):
        super().__init__(parent)
        self.setObjectName("color_field")
        self._title = title
        self._rgba = clamp_rgba(rgba)
        self._loading = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(6)

        self.chip = QPushButton()
        self.chip.setObjectName("color_chip")
        self.chip.setFixedSize(20, 20)
        self.chip.setCursor(Qt.PointingHandCursor)
        self.chip.setToolTip(tr(title))
        self.chip.clicked.connect(self._open_picker)
        layout.addWidget(self.chip)

        self.stack = QStackedWidget()
        self.stack.setMinimumWidth(0)
        layout.addWidget(self.stack, 1)

        # Процент непрозрачности: показывается в самом ряду, меняется
        # в пикере (как «100 %» в Figma).
        self.alpha_label = QLabel()
        self.alpha_label.setObjectName("color_alpha")
        self.alpha_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alpha_label.setFixedWidth(40)
        self.alpha_label.setToolTip(tr("Непрозрачность в процентах"))
        layout.addWidget(self.alpha_label)

        # Hex: одно текстовое поле с валидатором (цифры 0-9 и A-F, до 8).
        hex_page = QWidget()
        hex_layout = QHBoxLayout(hex_page)
        hex_layout.setContentsMargins(0, 0, 0, 0)
        self.hex_edit = QLineEdit()
        self.hex_edit.setFrame(False)
        self.hex_edit.setMinimumWidth(0)
        self.hex_edit.setToolTip(tr(title))
        self.hex_edit.setValidator(
            QRegularExpressionValidator(QRegularExpression("#?[0-9A-Fa-f]{0,8}"))
        )
        self.hex_edit.editingFinished.connect(self._on_hex_edited)
        hex_layout.addWidget(self.hex_edit)
        self.stack.addWidget(hex_page)

        # RGB: три мини-бокса 0-255 со светлыми перегородками между ними.
        rgb_page = QWidget()
        rgb_layout = QHBoxLayout(rgb_page)
        rgb_layout.setContentsMargins(0, 0, 0, 0)
        rgb_layout.setSpacing(6)
        self.rgb_spins: list[QSpinBox] = []
        for _index in range(3):
            if _index:
                rgb_layout.addWidget(self._separator())
            spin = self._mini_spin(0, 255)
            spin.valueChanged.connect(self._on_component_changed)
            rgb_layout.addWidget(spin, 1)
            self.rgb_spins.append(spin)
        self.stack.addWidget(rgb_page)

        # HSL: тон 0-360, насыщенность и светлота 0-100.
        hsl_page = QWidget()
        hsl_layout = QHBoxLayout(hsl_page)
        hsl_layout.setContentsMargins(0, 0, 0, 0)
        hsl_layout.setSpacing(6)
        self.hsl_spins: list[QSpinBox] = []
        for _index in range(3):
            if _index:
                hsl_layout.addWidget(self._separator())
            spin = self._mini_spin(0, 360 if _index == 0 else 100)
            spin.valueChanged.connect(self._on_component_changed)
            hsl_layout.addWidget(spin, 1)
            self.hsl_spins.append(spin)
        self.stack.addWidget(hsl_page)

        self._apply_visible_page()
        self._update_width()
        self._refresh()
        # Любая смена формата (в любом пикере) перестраивает все поля сразу.
        on_color_format_changed(self.refresh_format)
        self.destroyed.connect(
            lambda *_: _remove_format_listener(self.refresh_format)
        )

    def _separator(self) -> QFrame:
        """Светло-серая перегородка между числами на плашке."""

        line = QFrame()
        line.setObjectName("color_sep")
        line.setFixedWidth(1)
        line.setFixedHeight(16)
        return line

    def _update_width(self) -> None:
        """Hex — компактно, RGB и HSL — шире: под текущий формат ввода."""

        self.setFixedWidth(160 if color_format() == "Hex" else 200)

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------
    def rgba(self) -> tuple[int, int, int, int]:
        return self._rgba

    def match_height(self, reference: QWidget) -> None:
        """Высота по соседнему полю: ряды одинаковые, без растяжек."""

        height = reference.sizeHint().height() or reference.height() or 32
        self.setFixedHeight(max(28, int(height)))

    def set_rgba(self, color) -> None:
        """Обновляет отображение без сигнала changed."""

        self._rgba = clamp_rgba(color)
        self._refresh()

    def refresh_format(self) -> None:
        """Перестраивает отображение под текущий формат ввода."""

        self._apply_visible_page()
        self._update_width()
        self._refresh()

    # ------------------------------------------------------------------
    # Внутреннее
    # ------------------------------------------------------------------
    def _mini_spin(self, low: int, high: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        spin.setAlignment(Qt.AlignCenter)
        spin.setMinimumWidth(34)
        return spin

    def _apply_visible_page(self) -> None:
        self.stack.setCurrentIndex(COLOR_FORMATS.index(color_format()))

    def _refresh(self) -> None:
        red, green, blue, alpha = self._rgba
        self.chip.setStyleSheet(
            f"background-color: rgba({red}, {green}, {blue}, {alpha});"
        )
        self.alpha_label.setText(f"{max(0, min(100, round(alpha / 2.55)))} %")
        self._loading = True
        try:
            self.hex_edit.setText(f"{red:02X}{green:02X}{blue:02X}")
            for spin, part in zip(self.rgb_spins, (red, green, blue), strict=False):
                spin.setValue(part)
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
            self._loading = False

    def _open_picker(self) -> None:
        window = self.window()
        theme = str(self.property("theme") or window.property("theme") or "dark")
        selected = open_color_picker(window, theme, self._title, self._rgba)
        if selected is None:
            return
        self.set_rgba(selected)
        self.changed.emit(self._rgba)

    def _on_hex_edited(self) -> None:
        if self._loading:
            return
        text = self.hex_edit.text().strip().lstrip("#")
        if len(text) not in (6, 8) or not all(
            ch in "0123456789abcdefABCDEF" for ch in text
        ):
            self._refresh()  # неверный ввод: вернуть текущий цвет
            return
        color = QColor(f"#{text}")
        if len(text) == 6:
            # Альфа в hex не пишется — сохраняем текущую.
            color.setAlpha(self._rgba[3])
        self._rgba = color.red(), color.green(), color.blue(), color.alpha()
        self._refresh()
        self.changed.emit(self._rgba)

    def _on_component_changed(self, _value: int) -> None:
        if self._loading:
            return
        fmt = color_format()
        if fmt == "RGB":
            red, green, blue = (spin.value() for spin in self.rgb_spins)
            color = QColor(red, green, blue)
        else:
            hue, sat, light = (spin.value() for spin in self.hsl_spins)
            color = QColor.fromHslF(
                (hue % 360) / 360.0,
                sat / 100.0,
                light / 100.0,
            )
        color.setAlpha(self._rgba[3])
        self._rgba = color.red(), color.green(), color.blue(), color.alpha()
        self._refresh()
        self.changed.emit(self._rgba)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        # F2/Enter на строке тоже открывают пикер.
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_F2):
            self._open_picker()
            event.accept()
            return
        super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._open_picker()
        event.accept()
