from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import replace

from PIL import Image, ImageFont
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QDialog,
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.generator import RenderConfig, render_page
from core.screen_utils import get_window_size
from ui.overlays import add_safe_area, set_safe_area_visible

log = logging.getLogger(__name__)

# Полноразмерный рендер текста на 6000x4000 занимает сотни миллисекунд.
# Для интерактивного выбора точки достаточно 3000 px по длинной стороне.
PREVIEW_MAX_SIDE = 3000


class PointPickerDialog(QDialog):
    """Редактор грамоты: положение, размер, цвет и поля для печати."""

    def __init__(
        self,
        image_path,
        parent=None,
        initial_x=None,
        initial_y=None,
        align="left",
        render_config: RenderConfig | None = None,
        preview_parts: Sequence[str] | None = None,
        safe_margin: int | None = None,
        auto_x: bool = False,
        auto_y: bool = False,
        safe_area_color: tuple[int, int, int] | None = None,
        marker_color: tuple[int, int, int] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Редактор грамоты")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self.align = align
        self.point_changed = False
        self.auto_x = bool(auto_x)
        self.auto_y = bool(auto_y)
        self.safe_area_color = tuple(safe_area_color or (139, 92, 246))
        self.marker_color = tuple(marker_color or (139, 92, 246))
        self.render_config = render_config
        self.preview_parts = list(preview_parts or [])
        if safe_margin is None and render_config is not None:
            safe_margin = render_config.margin
        self.safe_margin = max(0, int(safe_margin or 0))

        self.image_path = image_path
        self.pil_image = Image.open(image_path)
        self.img_width = self.pil_image.width
        self.img_height = self.pil_image.height

        self.marker_x = initial_x if initial_x is not None else self.img_width // 2
        self.marker_y = initial_y if initial_y is not None else self.img_height // 2

        self.marker_x = max(0, min(self.img_width - 1, int(self.marker_x)))
        self.marker_y = max(0, min(self.img_height - 1, int(self.marker_y)))
        self.pil_image_rgb = self.pil_image.convert("RGB")
        self.pil_image.close()
        self.base_image = self.pil_image_rgb.copy()
        self.pil_image_rgb.close()

        self.display_scale = min(
            1.0,
            PREVIEW_MAX_SIDE / max(self.img_width, self.img_height),
        )
        if self.display_scale < 1.0:
            preview_size = (
                max(1, round(self.img_width * self.display_scale)),
                max(1, round(self.img_height * self.display_scale)),
            )
            self.preview_base_image = self.base_image.resize(
                preview_size,
                Image.Resampling.LANCZOS,
            )
        else:
            self.preview_base_image = self.base_image

        self.text_color = tuple(
            render_config.text_color if render_config is not None else (0, 0, 0)
        )
        self.letter_spacing = int(
            render_config.letter_spacing if render_config is not None else 0
        )
        self.preview_config = self._scaled_render_config(
            self.render_config,
            self.display_scale,
        )
        self.preview_font = None
        if self.preview_config is not None and self.preview_parts:
            self.preview_font = self._load_preview_font(self.preview_config)

        self.pixmap = self._pil_to_pixmap(self.preview_base_image)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setObjectName("editor_view")
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.view.setFocusPolicy(Qt.StrongFocus)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setMouseTracking(True)
        self.view.setFrameShape(QFrame.NoFrame)
        self.view.setToolTip(self._align_hint())
        self.view.setStyleSheet("QGraphicsView { background: transparent; border: none; }")
        self.view.viewport().setAutoFillBackground(False)

        self.pixmap_item = QGraphicsPixmapItem(self.pixmap)
        self.pixmap_item.setTransformationMode(Qt.SmoothTransformation)
        if self.display_scale < 1.0:
            self.pixmap_item.setScale(1.0 / self.display_scale)
        self.scene.addItem(self.pixmap_item)

        self.safe_area_items = add_safe_area(
            self.scene,
            self.img_width,
            self.img_height,
            self.safe_margin,
            z=10,
            color=QColor(*self.safe_area_color),
        )
        set_safe_area_visible(self.safe_area_items, self.safe_margin > 0)

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(60)
        self._preview_timer.timeout.connect(self._render_preview)

        self.marker_pen = QPen(QColor(*self.marker_color))
        self.marker_pen.setWidth(3)
        self.marker_pen.setCosmetic(True)
        self.marker_lines = []

        self.info_label = QLabel()
        self.info_label.setObjectName("editor_info")
        self.info_label.setAlignment(Qt.AlignCenter)

        self._build_ui()
        self._apply_theme_to_children()

        w, h = get_window_size(self, 0.78, 0.82)
        self.resize(max(1040, w), max(700, h))
        self.setMinimumSize(900, 600)
        if parent:
            screen = parent.screen() or QApplication.primaryScreen()
            if screen is not None:
                parent_center = screen.availableGeometry().center()
                self.move(
                    parent_center.x() - self.width() // 2,
                    parent_center.y() - self.height() // 2,
                )

        self.scale_factor = 1.0
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.scale_factor = self.view.transform().m11()

        self.view.mousePressEvent = self.on_mouse_press
        self.view.keyPressEvent = self.on_key_press
        self.view.wheelEvent = self.on_wheel
        self.view.mouseMoveEvent = self.on_mouse_move

        self.draw_marker()
        self._render_preview()
        self.view.setFocus()

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel("Редактор грамоты")
        title.setObjectName("dialog_title")
        header.addWidget(title)
        meta = QLabel(f"{self.img_width} × {self.img_height} px")
        meta.setObjectName("dialog_meta")
        header.addWidget(meta)
        header.addStretch()

        self.help_btn = QPushButton("?")
        self.help_btn.setObjectName("help_btn")
        self.help_btn.setFixedSize(26, 26)
        self.help_btn.setToolTip(
            "Правый клик — поставить точку.\n"
            "Левая кнопка — перемещать изображение.\n"
            "Колесо — зум; стрелки — сдвиг; Shift — 10 px; Ctrl — 50 px.\n"
            "Alt + движение мыши — расстояние до точки.\n"
            "Поля для печати — отступ, за который не должен выходить текст."
        )
        header.addWidget(self.help_btn)
        root.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)

        canvas = QFrame()
        canvas.setObjectName("editor_canvas")
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(12, 12, 12, 12)
        canvas_layout.setSpacing(10)
        canvas_layout.addWidget(self.view, 1)
        canvas_layout.addLayout(self._build_zoom_bar())
        canvas_layout.addWidget(self.info_label)
        body.addWidget(canvas, 1)

        inspector = QFrame()
        inspector.setObjectName("inspector")
        inspector.setFixedWidth(286)
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(16, 16, 16, 16)
        inspector_layout.setSpacing(10)

        inspector_layout.addWidget(self._heading("Текст"))
        inspector_layout.addLayout(
            self._field_row("Размер", self._build_font_size_spin())
        )
        inspector_layout.addLayout(
            self._field_row("Цвет", self._build_color_row())
        )
        inspector_layout.addLayout(
            self._field_row("Интервал", self._build_letter_spacing_spin())
        )

        inspector_layout.addSpacing(6)
        inspector_layout.addWidget(self._heading("Положение"))
        inspector_layout.addWidget(self._build_align_segments())
        inspector_layout.addWidget(self._build_auto_row())
        inspector_layout.addLayout(
            self._field_row("Крестик", self._build_marker_color_row())
        )

        inspector_layout.addSpacing(6)
        inspector_layout.addWidget(self._heading("Печать"))
        inspector_layout.addLayout(self._build_margin_row())
        inspector_layout.addLayout(
            self._field_row("Линия", self._build_safe_color_row())
        )
        self.safe_check = QCheckBox("Показывать поля для печати")
        self.safe_check.setObjectName("safe_area_check")
        self.safe_check.setChecked(self.safe_margin > 0)
        self.safe_check.setToolTip(
            "Показывает границу полей для печати. Текст не должен выходить за неё."
        )
        self.safe_check.toggled.connect(self._on_safe_area_toggled)
        inspector_layout.addWidget(self.safe_check)

        inspector_layout.addStretch()
        body.addWidget(inspector)

        root.addLayout(body, 1)

        footer = QFrame()
        footer.setObjectName("dialog_footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 12, 0, 0)
        footer_layout.setSpacing(8)

        self.reset_btn = QPushButton("Сбросить оформление")
        self.reset_btn.setObjectName("link_btn")
        self.reset_btn.setAutoDefault(False)
        self.reset_btn.clicked.connect(self.reset_style)
        footer_layout.addWidget(self.reset_btn)
        footer_layout.addStretch()

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setObjectName("tertiary_btn")
        self.cancel_btn.setAutoDefault(False)
        self.cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.cancel_btn)

        self.ok_btn = QPushButton("Применить")
        self.ok_btn.setObjectName("primary_btn")
        self.ok_btn.setMinimumWidth(160)
        self.ok_btn.setMinimumHeight(38)
        self.ok_btn.setDefault(True)
        self.ok_btn.setAutoDefault(True)
        self.ok_btn.clicked.connect(self.accept)
        footer_layout.addWidget(self.ok_btn)

        root.addWidget(footer)

    @staticmethod
    def _heading(text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setObjectName("inspector_heading")
        return label

    @staticmethod
    def _field_row(label_text: str, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        label = QLabel(label_text)
        label.setObjectName("field_label")
        label.setMinimumWidth(70)
        row.addWidget(label)
        row.addWidget(widget, 1)
        return row

    def _build_font_size_spin(self) -> QSpinBox:
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(1, 2000)
        self.font_size_spin.setSuffix(" px")
        self.font_size_spin.setValue(
            self.render_config.font_size if self.render_config is not None else 100
        )
        self.font_size_spin.setEnabled(self.render_config is not None)
        self.font_size_spin.valueChanged.connect(self._on_font_size_changed)
        return self.font_size_spin

    def _build_letter_spacing_spin(self) -> QSpinBox:
        self.letter_spacing_spin = QSpinBox()
        self.letter_spacing_spin.setRange(-20, 200)
        self.letter_spacing_spin.setSuffix(" px")
        self.letter_spacing_spin.setValue(self.letter_spacing)
        self.letter_spacing_spin.setEnabled(self.render_config is not None)
        self.letter_spacing_spin.valueChanged.connect(self._on_letter_spacing_changed)
        return self.letter_spacing_spin

    def _build_color_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.color_button = QPushButton()
        self.color_button.setObjectName("color_swatch")
        self.color_button.setFixedSize(34, 34)
        self.color_button.setToolTip("Выбрать цвет текста")
        self.color_button.setEnabled(self.render_config is not None)
        self.color_button.clicked.connect(self.choose_color)
        layout.addWidget(self.color_button)

        self.color_label = QLabel()
        self.color_label.setObjectName("secondary_label")
        layout.addWidget(self.color_label)
        layout.addStretch()
        self._set_color_button(self.text_color)
        return row

    def _build_auto_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.auto_x_check = QCheckBox("Авто по X")
        self.auto_x_check.setToolTip("Центрировать текст по горизонтали, игнорируя X точки")
        self.auto_x_check.setChecked(self.auto_x)
        self.auto_x_check.toggled.connect(self._on_auto_changed)
        layout.addWidget(self.auto_x_check)

        self.auto_y_check = QCheckBox("Авто по Y")
        self.auto_y_check.setToolTip("Центрировать текст по вертикали, игнорируя Y точки")
        self.auto_y_check.setChecked(self.auto_y)
        self.auto_y_check.toggled.connect(self._on_auto_changed)
        layout.addWidget(self.auto_y_check)
        layout.addStretch()
        return row

    def _build_marker_color_row(self) -> QWidget:
        return self._build_color_control(
            self.marker_color,
            self.choose_marker_color,
            "marker_color_button",
            "marker_color_label",
            "Выбрать цвет крестика",
        )

    def _build_safe_color_row(self) -> QWidget:
        return self._build_color_control(
            self.safe_area_color,
            self.choose_safe_area_color,
            "safe_color_button",
            "safe_color_label",
            "Выбрать цвет линии полей для печати",
        )

    def _build_color_control(
        self,
        color: tuple[int, int, int],
        callback,
        button_name: str,
        label_name: str,
        tooltip: str,
    ) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        button = QPushButton()
        button.setObjectName("color_swatch")
        button.setFixedSize(30, 30)
        button.setToolTip(tooltip)
        button.clicked.connect(callback)
        layout.addWidget(button)

        label = QLabel()
        label.setObjectName("secondary_label")
        layout.addWidget(label)
        layout.addStretch()

        setattr(self, button_name, button)
        setattr(self, label_name, label)
        self._set_color_control(button, label, color)
        return row

    def _build_align_segments(self) -> QWidget:
        wrapper = QFrame()
        wrapper.setObjectName("segmented")
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.align_group = QButtonGroup(self)
        self.align_buttons: dict[str, QPushButton] = {}
        for value, label in (
            ("left", "Слева"),
            ("center", "Центр"),
            ("right", "Справа"),
        ):
            button = QPushButton(label)
            button.setObjectName("seg_btn")
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.clicked.connect(
                lambda _checked=False, align=value: self.on_align_changed(align)
            )
            self.align_group.addButton(button)
            self.align_buttons[value] = button
            layout.addWidget(button, 1)
            if value == self.align:
                button.setChecked(True)
        if not any(button.isChecked() for button in self.align_buttons.values()):
            self.align = "center"
            self.align_buttons["center"].setChecked(True)
        return wrapper

    def _build_zoom_bar(self) -> QHBoxLayout:
        zoom_layout = QHBoxLayout()
        zoom_layout.setSpacing(4)

        btn_zoom_out = QPushButton("−")
        btn_zoom_out.setObjectName("tool_btn")
        btn_zoom_out.setFixedWidth(34)
        btn_zoom_out.setToolTip("Уменьшить")
        btn_zoom_out.clicked.connect(self.zoom_out)
        zoom_layout.addWidget(btn_zoom_out)

        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setObjectName("tool_btn")
        btn_zoom_in.setFixedWidth(34)
        btn_zoom_in.setToolTip("Увеличить")
        btn_zoom_in.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(btn_zoom_in)

        btn_fit = QPushButton("По размеру")
        btn_fit.setObjectName("tool_btn")
        btn_fit.clicked.connect(self.fit_to_view)
        zoom_layout.addWidget(btn_fit)

        btn_center = QPushButton("В центр")
        btn_center.setObjectName("tool_btn")
        btn_center.clicked.connect(self.center_marker)
        zoom_layout.addWidget(btn_center)
        zoom_layout.addStretch()
        return zoom_layout

    def _build_margin_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        label = QLabel("Поля")
        label.setObjectName("field_label")
        label.setMinimumWidth(70)
        row.addWidget(label)
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 100000)
        self.margin_spin.setSuffix(" px")
        self.margin_spin.setValue(self.safe_margin)
        self.margin_spin.setToolTip(
            "Отступ от краёв, за который не должен выходить текст при печати. 0 — без ограничения."
        )
        self.margin_spin.valueChanged.connect(self._on_margin_changed)
        row.addWidget(self.margin_spin, 1)
        return row

    def _apply_theme_to_children(self) -> None:
        theme = self.property("theme")
        if not theme:
            return
        for widget in self.findChildren(QWidget):
            widget.setProperty("theme", theme)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    # ------------------------------------------------------------------
    # Оформление текста
    # ------------------------------------------------------------------
    @staticmethod
    def _load_preview_font(config: RenderConfig | None):
        if config is None:
            return None
        try:
            return ImageFont.truetype(config.font_path, size=config.font_size)
        except (OSError, ValueError):
            return None

    def _refresh_render_config(self) -> None:
        if self.render_config is None:
            return
        self.render_config = replace(
            self.render_config,
            font_size=self.font_size_spin.value(),
            text_color=tuple(self.text_color),
            letter_spacing=self.letter_spacing_spin.value(),
            margin=self.safe_margin,
        )
        self.preview_config = self._scaled_render_config(
            self.render_config,
            self.display_scale,
        )
        self.preview_font = self._load_preview_font(self.preview_config)
        self._schedule_preview()

    def _on_font_size_changed(self, _value: int) -> None:
        self._refresh_render_config()

    def _on_letter_spacing_changed(self, _value: int) -> None:
        self.letter_spacing = self.letter_spacing_spin.value()
        self._refresh_render_config()

    def _on_margin_changed(self, value: int) -> None:
        self.safe_margin = max(0, int(value))
        self._rebuild_safe_area()
        self._refresh_render_config()

    def _set_color_button(self, color: tuple[int, int, int]) -> None:
        value = QColor(*color).name()
        self.color_button.setStyleSheet(f"background-color: {value};")
        self.color_label.setText(value.upper())

    @staticmethod
    def _set_color_control(button: QPushButton, label: QLabel, color) -> None:
        value = QColor(*color).name()
        button.setStyleSheet(f"background-color: {value};")
        label.setText(value.upper())

    def _pick_color(self, current, title: str) -> tuple[int, int, int] | None:
        color = QColorDialog.getColor(
            QColor(*current),
            self,
            title,
            QColorDialog.DontUseNativeDialog,
        )
        if not color.isValid():
            return None
        return color.red(), color.green(), color.blue()

    def choose_marker_color(self) -> None:
        selected = self._pick_color(self.marker_color, "Цвет крестика")
        if selected is None:
            return
        self.marker_color = selected
        self._set_color_control(
            self.marker_color_button,
            self.marker_color_label,
            self.marker_color,
        )
        self.marker_pen.setColor(QColor(*self.marker_color))
        self.draw_marker()

    def choose_safe_area_color(self) -> None:
        selected = self._pick_color(self.safe_area_color, "Цвет полей для печати")
        if selected is None:
            return
        self.safe_area_color = selected
        self._set_color_control(
            self.safe_color_button,
            self.safe_color_label,
            self.safe_area_color,
        )
        self._rebuild_safe_area()

    def choose_color(self) -> None:
        if self.render_config is None:
            return
        color = QColorDialog.getColor(
            QColor(*self.text_color),
            self,
            "Цвет текста",
            QColorDialog.DontUseNativeDialog,
        )
        if not color.isValid():
            return
        self.text_color = (color.red(), color.green(), color.blue())
        self._set_color_button(self.text_color)
        self._refresh_render_config()

    def reset_style(self) -> None:
        if self.render_config is None:
            return
        self.font_size_spin.setValue(100)
        self.letter_spacing_spin.setValue(0)
        self.text_color = (0, 0, 0)
        self._set_color_button(self.text_color)
        self.margin_spin.setValue(36)
        self._refresh_render_config()

    def _rebuild_safe_area(self) -> None:
        for item in self.safe_area_items:
            self.scene.removeItem(item)
        self.safe_area_items = add_safe_area(
            self.scene,
            self.img_width,
            self.img_height,
            self.safe_margin,
            z=10,
            color=QColor(*self.safe_area_color),
        )
        set_safe_area_visible(
            self.safe_area_items,
            self.safe_check.isChecked() and self.safe_margin > 0,
        )

    def get_text_color(self) -> tuple[int, int, int]:
        return tuple(self.text_color)

    def get_font_size(self) -> int:
        return self.font_size_spin.value()

    def get_letter_spacing(self) -> int:
        return self.letter_spacing_spin.value()

    def get_margin(self) -> int:
        return self.safe_margin

    # ------------------------------------------------------------------
    # Сцена и предпросмотр
    # ------------------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.scale_factor = self.view.transform().m11()

    def _align_hint(self) -> str:
        if self.align == "left":
            return "Правый клик — поставить точку (левый край блока)"
        if self.align == "right":
            return "Правый клик — поставить точку (правый край блока)"
        return "Правый клик — поставить точку (центр блока)"

    def on_align_changed(self, align: str | None = None) -> None:
        if align is None:
            align = next(
                (value for value, button in self.align_buttons.items() if button.isChecked()),
                None,
            )
        if align not in {"left", "center", "right"}:
            return
        self.align = align
        for value, button in self.align_buttons.items():
            button.setChecked(value == align)
        self.view.setToolTip(self._align_hint())
        self.draw_marker()

    def _on_safe_area_toggled(self, checked: bool) -> None:
        set_safe_area_visible(self.safe_area_items, checked and self.safe_margin > 0)

    def _on_auto_changed(self, _checked: bool = False) -> None:
        if self.auto_x_check.isChecked():
            self.marker_x = self.img_width // 2
        if self.auto_y_check.isChecked():
            self.marker_y = self.img_height // 2
        self.draw_marker()

    def get_align(self) -> str:
        return self.align

    def get_auto_x(self) -> bool:
        return self.auto_x_check.isChecked()

    def get_auto_y(self) -> bool:
        return self.auto_y_check.isChecked()

    def get_safe_area_color(self) -> tuple[int, int, int]:
        return tuple(self.safe_area_color)

    def get_marker_color(self) -> tuple[int, int, int]:
        return tuple(self.marker_color)

    def _clamp_marker(self):
        self.marker_x = max(0, min(self.img_width - 1, int(self.marker_x)))
        self.marker_y = max(0, min(self.img_height - 1, int(self.marker_y)))

    @staticmethod
    def _pil_to_pixmap(image: Image.Image) -> QPixmap:
        rgb = image.convert("RGB")
        data = rgb.tobytes("raw", "RGB")
        qimage = QImage(
            data,
            rgb.width,
            rgb.height,
            rgb.width * 3,
            QImage.Format_RGB888,
        ).copy()
        return QPixmap.fromImage(qimage)

    @staticmethod
    def _scaled_render_config(config: RenderConfig | None, scale: float) -> RenderConfig | None:
        if config is None or scale >= 1.0:
            return config

        def scaled(value):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value * scale
            return value

        return replace(
            config,
            font_size=max(1, int(round(config.font_size * scale))),
            x=scaled(config.x),
            y=scaled(config.y),
            x_offset=scaled(config.x_offset),
            y_offset=scaled(config.y_offset),
            line_spacing=scaled(config.line_spacing),
            letter_spacing=scaled(config.letter_spacing),
            margin=scaled(config.margin),
        )

    def _schedule_preview(self) -> None:
        if self.preview_config is not None and self.preview_font is not None:
            self._preview_timer.start()

    def _render_preview(self) -> None:
        image = self.preview_base_image.copy()
        if self.preview_config is not None and self.preview_font is not None and self.preview_parts:
            config = replace(
                self.preview_config,
                x=(
                    "center"
                    if self.auto_x_check.isChecked()
                    else self.marker_x * self.display_scale
                ),
                y=(
                    "center"
                    if self.auto_y_check.isChecked()
                    else self.marker_y * self.display_scale
                ),
                align=self.align,
            )
            try:
                image = render_page(image, self.preview_parts, self.preview_font, config)
            except Exception:
                log.debug("Не удалось нарисовать предпросмотр в редакторе", exc_info=True)
                image = self.preview_base_image.copy()
        self.pixmap_item.setPixmap(self._pil_to_pixmap(image))

    def center_marker(self) -> None:
        self.point_changed = True
        self.marker_x = self.img_width // 2
        self.marker_y = self.img_height // 2
        self.draw_marker()
        self.view.setFocus()

    def on_key_press(self, event):
        if event.modifiers() & Qt.ShiftModifier:
            step = 10
        elif event.modifiers() & Qt.ControlModifier:
            step = 50
        else:
            step = 1

        if event.key() == Qt.Key_Left:
            self.auto_x_check.setChecked(False)
            self.marker_x -= step
        elif event.key() == Qt.Key_Right:
            self.auto_x_check.setChecked(False)
            self.marker_x += step
        elif event.key() == Qt.Key_Up:
            self.auto_y_check.setChecked(False)
            self.marker_y -= step
        elif event.key() == Qt.Key_Down:
            self.auto_y_check.setChecked(False)
            self.marker_y += step
        else:
            QGraphicsView.keyPressEvent(self.view, event)
            return
        self.point_changed = True
        self._clamp_marker()
        self.draw_marker()

    def zoom_in(self):
        self.zoom_at_cursor(1.2)

    def zoom_out(self):
        self.zoom_at_cursor(1 / 1.2)

    def zoom_at_cursor(self, factor):
        cursor_pos = self.view.mapFromGlobal(self.view.cursor().pos())
        if not self.view.viewport().rect().contains(cursor_pos):
            cursor_pos = self.view.viewport().rect().center()
        scene_pos = self.view.mapToScene(cursor_pos)

        new_scale = max(0.01, min(50.0, self.scale_factor * factor))
        self.scale_factor = new_scale

        self.view.resetTransform()
        self.view.scale(self.scale_factor, self.scale_factor)

        new_cursor_pos = self.view.mapFromScene(scene_pos)
        delta = new_cursor_pos - cursor_pos

        h_bar = self.view.horizontalScrollBar()
        v_bar = self.view.verticalScrollBar()
        h_bar.setValue(h_bar.value() + delta.x())
        v_bar.setValue(v_bar.value() + delta.y())

    def fit_to_view(self):
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.scale_factor = self.view.transform().m11()

    def on_wheel(self, event):
        if event.angleDelta().y() > 0:
            self.zoom_at_cursor(1.2)
        else:
            self.zoom_at_cursor(1 / 1.2)
        event.accept()

    def draw_marker(self):
        for item in self.marker_lines:
            self.scene.removeItem(item)
        self.marker_lines.clear()

        self._clamp_marker()
        size = 20
        self.marker_pen.setCosmetic(True)

        line1 = QGraphicsLineItem(
            self.marker_x - size,
            self.marker_y,
            self.marker_x + size,
            self.marker_y,
        )
        line1.setPen(self.marker_pen)
        line1.setZValue(20)
        self.scene.addItem(line1)
        self.marker_lines.append(line1)

        line2 = QGraphicsLineItem(
            self.marker_x,
            self.marker_y - size,
            self.marker_x,
            self.marker_y + size,
        )
        line2.setPen(self.marker_pen)
        line2.setZValue(20)
        self.scene.addItem(line2)
        self.marker_lines.append(line2)

        dot = QGraphicsEllipseItem(self.marker_x - 3, self.marker_y - 3, 6, 6)
        dot.setPen(self.marker_pen)
        dot.setBrush(QBrush(QColor(*self.marker_color)))
        dot.setZValue(20)
        self.scene.addItem(dot)
        self.marker_lines.append(dot)

        label = {
            "left": "Левый край",
            "right": "Правый край",
            "center": "Центр текста",
        }.get(self.align, "Точка")
        self.info_label.setText(f"{label}: X={self.marker_x}, Y={self.marker_y}")
        self._schedule_preview()

    def on_mouse_press(self, event):
        if event.button() == Qt.RightButton:
            self.auto_x_check.setChecked(False)
            self.auto_y_check.setChecked(False)
            scene_pos = self.view.mapToScene(event.position().toPoint())
            self.marker_x = int(scene_pos.x())
            self.marker_y = int(scene_pos.y())
            self.point_changed = True
            self.draw_marker()
            event.accept()
        else:
            QGraphicsView.mousePressEvent(self.view, event)

    def on_mouse_move(self, event):
        if event.modifiers() & Qt.AltModifier:
            scene_pos = self.view.mapToScene(event.position().toPoint())
            dx = scene_pos.x() - self.marker_x
            dy = scene_pos.y() - self.marker_y
            dist = (dx**2 + dy**2) ** 0.5
            self.info_label.setText(
                f"X={self.marker_x}, Y={self.marker_y} | "
                f"ΔX={int(dx)} ΔY={int(dy)} | Дистанция: {int(dist)} px"
            )
        QGraphicsView.mouseMoveEvent(self.view, event)

    def get_point(self):
        return self.marker_x, self.marker_y
