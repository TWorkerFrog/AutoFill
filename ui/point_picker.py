from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageFont
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QCompleter,
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
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.font_utils import ordered_style_names, scan_fonts
from core.generator import RenderConfig, render_page
from core.i18n import tr, translate_widget_tree
from core.screen_utils import place_window_on_screen
from ui.color_field import ColorField, clamp_rgba
from ui.overlays import add_safe_area, set_safe_area_visible
from ui.themed_dialogs import (
    apply_theme_tree,
    get_open_file_name,
    style_popup,
)

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
        safe_area_color: tuple[int, int, int, int] | None = None,
        marker_color: tuple[int, int, int, int] | None = None,
        fonts_data: dict[str, dict[str, str]] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Редактор грамоты")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self.align = align
        self.point_changed = False
        self.auto_x = bool(auto_x)
        self.auto_y = bool(auto_y)
        self.safe_area_color = tuple(safe_area_color or (139, 92, 246, 255))
        self.marker_color = tuple(marker_color or (139, 92, 246, 255))
        self.render_config = render_config
        self.preview_parts = list(preview_parts or [])
        self.fonts_data = fonts_data if fonts_data is not None else scan_fonts()
        self.font_path = (
            str(render_config.font_path)
            if render_config is not None and render_config.font_path
            else ""
        )
        self._loading_font = True
        self.font_family: str | None = None
        self._selected_style: str | None = None
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
            render_config.text_color if render_config is not None else (0, 0, 0, 255)
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

        # Размер и позиция считаются по экрану родителя: у ещё не показанного
        # диалога screen() возвращает основной монитор, а родитель может быть
        # на втором.  Итоговый размер ограничен доступной областью экрана.
        place_window_on_screen(
            self,
            parent,
            width_ratio=0.78,
            height_ratio=0.82,
            min_width=1040,
            min_height=700,
        )
        self.setMinimumSize(900, 600)

        self.scale_factor = 1.0
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.scale_factor = self.view.transform().m11()

        self.view.mousePressEvent = self.on_mouse_press
        self.view.keyPressEvent = self.on_key_press
        self.view.wheelEvent = self.on_wheel
        self.view.mouseMoveEvent = self.on_mouse_move

        self.draw_marker()
        self._render_preview()
        translate_widget_tree(self)
        self.view.setFocus()

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 18)
        root.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel("Редактор грамоты")
        title.setObjectName("dialog_title")
        header.addWidget(title)
        meta = QLabel(f"{self.img_width} × {self.img_height} px")
        meta.setObjectName("dialog_meta")
        header.addWidget(meta)
        header.addStretch()
        root.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)

        canvas = QFrame()
        canvas.setObjectName("editor_canvas")
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(12, 14, 12, 14)
        canvas_layout.setSpacing(14)
        canvas_layout.addWidget(self.view, 1)
        canvas_layout.addLayout(self._build_zoom_bar())
        self.hint_label = QLabel(
            " · ".join(
                tr(part)
                for part in (
                    "ПКМ: поставить и тянуть крестик",
                    "ЛКМ + перетаскивание: двигать изображение",
                    "Колесо: масштаб",
                    "Стрелки: сдвиг на 1 px",
                    "Shift + стрелки: 10 px",
                    "Ctrl + стрелки: 50 px",
                    "Alt: расстояние до крестика",
                )
            )
        )
        self.hint_label.setObjectName("editor_hint")
        self.hint_label.setWordWrap(True)
        canvas_layout.addWidget(self.hint_label)
        canvas_layout.addWidget(self.info_label)
        body.addWidget(canvas, 1)

        inspector = QFrame()
        inspector.setObjectName("inspector")
        # 340 px: ряд цвета по рефу Figma (плашка + значение + процент)
        # требует ~280 px контента, плюс строка шрифта с кнопкой «Обзор».
        inspector.setFixedWidth(340)
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        inspector_layout.setSpacing(0)

        inspector_scroll = QScrollArea(inspector)
        inspector_scroll.setObjectName("inspector_scroll")
        inspector_scroll.setWidgetResizable(True)
        inspector_scroll.setFrameShape(QFrame.NoFrame)
        inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inspector_content = QWidget()
        inspector_content.setObjectName("inspector_content")
        content_layout = QVBoxLayout(inspector_content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(14)

        content_layout.addWidget(self._heading("Текст"))
        content_layout.addLayout(
            self._field_row("Шрифт", self._build_font_combo())
        )
        content_layout.addLayout(
            self._field_row("Начертание", self.style_combo)
        )
        content_layout.addLayout(
            self._field_row("Размер", self._build_font_size_spin())
        )
        content_layout.addLayout(
            self._field_row(
                "Цвет", self._build_color_row(), stretch=False
            )
        )
        content_layout.addLayout(
            self._field_row("Интервал", self._build_letter_spacing_spin())
        )

        content_layout.addSpacing(10)
        content_layout.addWidget(self._heading("Положение"))
        content_layout.addWidget(self._build_align_segments())
        content_layout.addWidget(self._build_auto_row())
        content_layout.addWidget(self._build_coord_row())
        content_layout.addLayout(
            self._field_row(
                "Крестик", self._build_marker_color_row(), stretch=False
            )
        )

        content_layout.addSpacing(10)
        content_layout.addWidget(self._heading("Печать"))
        content_layout.addLayout(self._build_margin_row())
        content_layout.addLayout(
            self._field_row(
                "Линия", self._build_safe_color_row(), stretch=False
            )
        )
        self.safe_check = QCheckBox("Показывать поля для печати")
        self.safe_check.setObjectName("safe_area_check")
        self.safe_check.setChecked(self.safe_margin > 0)
        self.safe_check.setToolTip(
            "Показывает границу полей для печати. Текст не должен выходить за неё."
        )
        self.safe_check.toggled.connect(self._on_safe_area_toggled)
        content_layout.addWidget(self.safe_check)

        content_layout.addStretch()
        inspector_scroll.setWidget(inspector_content)
        inspector_layout.addWidget(inspector_scroll)
        body.addWidget(inspector)

        root.addLayout(body, 1)

        footer = QFrame()
        footer.setObjectName("dialog_footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 16, 0, 0)
        footer_layout.setSpacing(10)

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
        # Без кнопки по умолчанию: Enter в поле ввода не должен закрывать
        # редактор и случайно применять изменения.
        self.ok_btn.setDefault(False)
        self.ok_btn.setAutoDefault(False)
        self.ok_btn.clicked.connect(self.accept)
        footer_layout.addWidget(self.ok_btn)

        root.addWidget(footer)

        # Единая колонка меток: все метки рядов фиксируются по самой широкой
        # («Начертание»), поэтому каждое поле начинается с одной линии и не
        # растягивается — лишняя ширина уходит в пустое пространство справа.
        field_labels = self.findChildren(QLabel, "field_label")
        if field_labels:
            column = max(label.sizeHint().width() for label in field_labels)
            for label in field_labels:
                label.setFixedWidth(column)

    @staticmethod
    def _heading(text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setObjectName("inspector_heading")
        return label

    @staticmethod
    def _field_row(
        label_text: str,
        widget: QWidget,
        *,
        stretch: bool = True,
    ) -> QHBoxLayout:
        """Ряд «метка + поле».  Для полей фиксированной ширины (цветовых)
        stretch=False прижимает их к метке: лейаут иначе центрирует
        виджеты, которые не могут заполнить выделенную ячейку."""

        row = QHBoxLayout()
        row.setSpacing(10)
        label = QLabel(label_text)
        label.setObjectName("field_label")
        label.setMinimumWidth(64)
        row.addWidget(label)
        if stretch:
            row.addWidget(widget, 1)
        else:
            row.addWidget(widget, 0, Qt.AlignLeft)
        return row

    @staticmethod
    def _same_path(first: str, second: str) -> bool:
        try:
            return Path(first).resolve() == Path(second).resolve()
        except OSError:
            return str(first) == str(second)

    def _populate_font_combo(self) -> None:
        """Заполняет список семействами; начертания живут в отдельном списке.

        Подпись вида «Семейство (Стиль)» в узком поле обрезалась до
        нечитаемого «Семейство ()», поэтому здесь остаются только имена
        семейств, а текущее начертание показывает отдельный комбобокс.
        """

        self.font_combo.blockSignals(True)
        self.font_combo.clear()
        for family in sorted(self.fonts_data, key=str.casefold):
            self.font_combo.addItem(family, family)

        # Восстанавливаем текущий шрифт: семейство + начертание.
        current = -1
        self.font_family = None
        preferred_style = None
        if self.font_path and Path(self.font_path).is_file():
            match = self._find_family_style_by_path(self.font_path)
            if match is not None:
                family, style = match
                current = self.font_combo.findText(family, Qt.MatchFixedString)
                self.font_family = family
                preferred_style = style
            else:
                self.font_combo.insertItem(
                    0,
                    f"Файл: {Path(self.font_path).name}",
                    None,
                )
                current = 0
        if current < 0 and self.font_combo.count():
            current = 0
            if self.font_combo.itemData(current):
                self.font_family = str(self.font_combo.itemData(current))
        self.font_combo.setCurrentIndex(current)
        self._populate_style_combo(self.font_family, preferred_style)
        self.font_combo.blockSignals(False)

    def _find_family_style_by_path(self, path: str) -> tuple[str, str] | None:
        """Ищет (семейство, начертание) по пути файла шрифта."""

        for family in sorted(self.fonts_data, key=str.casefold):
            for style, candidate in self.fonts_data[family].items():
                if self._same_path(candidate, path):
                    return family, style
        return None

    def _build_style_combo(self) -> QComboBox:
        self.style_combo = QComboBox()
        self.style_combo.setMaxVisibleItems(20)
        self.style_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.style_combo.setMinimumContentsLength(6)
        self.style_combo.setMinimumWidth(0)
        self.style_combo.setEnabled(False)
        self.style_combo.setToolTip("Начертание выбранного семейства")
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        self.style_combo.setEnabled(
            self.render_config is not None and getattr(self, "font_family", None) is not None
        )
        return self.style_combo

    def _populate_style_combo(self, family: str | None, preferred: str | None = None) -> None:
        """Обновляет список начертаний под выбранное семейство."""

        self.style_combo.blockSignals(True)
        self.style_combo.clear()
        styles = self.fonts_data.get(family, {}) if family else {}
        if styles:
            ordered = ordered_style_names(styles)
            for style in ordered:
                self.style_combo.addItem(style, style)
            match = preferred if preferred in styles else (
                "Regular" if "Regular" in styles else ordered[0]
            )
            index = self.style_combo.findText(match, Qt.MatchFixedString)
            self.style_combo.setCurrentIndex(max(0, index))
            self.style_combo.setEnabled(self.render_config is not None)
            self._selected_style = match
        else:
            self.style_combo.setEnabled(False)
            self._selected_style = None
        self.style_combo.blockSignals(False)

    def _on_style_changed(self, index: int) -> None:
        """Смена начертания: путь шрифта обновляется под выбранное семейство."""

        if self._loading_font or index < 0 or not self.font_family:
            return
        style = self.style_combo.itemData(index)
        if not style:
            return
        path = self.fonts_data.get(self.font_family, {}).get(str(style))
        if not path:
            return
        self._selected_style = str(style)
        self.font_path = str(path)
        self.font_combo.setToolTip(
            self.font_family
            if style == "Regular"
            else f"{self.font_family} ({style})"
        )
        self._refresh_render_config()

    def _build_font_combo(self) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Список начертаний создаётся до заполнения семейств: популяция
        # сразу выбирает текущее начертание.
        self._build_style_combo()

        self.font_combo = QComboBox()
        # Редактируемое поле: можно не только выбрать из списка, но и набрать
        # название семейства с нуля - текст приводится к ближайшему шрифту.
        self.font_combo.setEditable(True)
        self.font_combo.setInsertPolicy(QComboBox.NoInsert)
        self.font_combo.setMaxVisibleItems(20)
        self.font_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.font_combo.setMinimumContentsLength(5)
        self.font_combo.setMinimumWidth(0)
        self.font_combo.setMaximumWidth(176)
        self.font_combo.setEnabled(self.render_config is not None)
        self._populate_font_combo()
        self.font_combo.currentIndexChanged.connect(self._on_font_changed)
        self.font_combo.currentTextChanged.connect(self._on_font_text_changed)
        self.font_combo.lineEdit().returnPressed.connect(self._normalize_font_text)
        self._install_font_completer()
        layout.addWidget(self.font_combo, 1)

        self.font_file_btn = QPushButton("Обзор")
        self.font_file_btn.setObjectName("link_btn")
        self.font_file_btn.setFixedWidth(56)
        self.font_file_btn.setToolTip("Выбрать файл шрифта")
        self.font_file_btn.setEnabled(self.render_config is not None)
        self.font_file_btn.clicked.connect(self.choose_font_file)
        layout.addWidget(self.font_file_btn)
        self.font_combo.setToolTip(self.font_combo.currentText())

        self._loading_font = False
        return wrapper

    def _install_font_completer(self) -> None:
        labels = sorted(self.fonts_data, key=str.casefold)
        completer = QCompleter(labels, self.font_combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.font_combo.setCompleter(completer)
        # Попап создаётся лениво; создаём его сейчас, чтобы успеть покрасить.
        style_popup(completer.popup(), self.property("theme") or "dark")

    def _on_font_text_changed(self, text: str) -> None:
        if self._loading_font:
            return
        self._apply_font_text(text)

    def _apply_font_text(self, text: str) -> None:
        """Приводит набранный текст к реальному шрифту и обновляет предпросмотр.

        Порядок: семейство из списка → путь к файлу → семейство из скана.
        Если ничего не совпало, последний валидный шрифт не меняется.
        """

        text = (text or "").strip()
        if not text:
            return

        index = self.font_combo.findText(text, Qt.MatchFixedString)
        if index >= 0 and self.font_combo.itemData(index):
            self._select_family(str(self.font_combo.itemData(index)))
            return

        path = Path(text)
        if path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
            self._select_file_font(str(path))
            return

        family = next(
            (name for name in self.fonts_data if name.casefold() == text.casefold()),
            None,
        )
        if family is None:
            return
        self._select_family(family)

    def _select_family(self, family: str, preferred: str | None = None) -> None:
        """Выбирает семейство и начертание; путь и предпросмотр обновляются."""

        styles = self.fonts_data.get(family, {})
        if not styles:
            return
        if preferred is None:
            preferred = self._selected_style
        self.font_family = family

        self.font_combo.blockSignals(True)
        index = self.font_combo.findText(family, Qt.MatchFixedString)
        if index >= 0:
            self.font_combo.setCurrentIndex(index)
        self.font_combo.blockSignals(False)

        self._populate_style_combo(family, preferred=preferred)
        style = self._selected_style or "Regular"
        self.font_path = str(styles[style])
        self.font_combo.setToolTip(
            family if style == "Regular" else f"{family} ({style})"
        )
        self._refresh_render_config()

    def _select_file_font(self, path: str) -> None:
        """Выбирает файл шрифта вне скана системных семейств."""

        self.font_family = None
        self._selected_style = None
        self.font_combo.blockSignals(True)
        for i in range(self.font_combo.count()):
            if self.font_combo.itemText(i).startswith("Файл:"):
                self.font_combo.removeItem(i)
                break
        self.font_combo.insertItem(0, f"Файл: {Path(path).name}", None)
        self.font_combo.setCurrentIndex(0)
        self.font_combo.blockSignals(False)
        self._populate_style_combo(None)
        self.font_path = str(path)
        self.font_combo.setToolTip(f"Файл: {Path(path).name}")
        self._refresh_render_config()

    def _normalize_font_text(self) -> None:
        """По Enter дополняет неполное название до ближайшего семейства."""

        if self._loading_font:
            return
        text = self.font_combo.currentText().strip()
        if not text:
            return

        resolved = self.font_combo.findText(text, Qt.MatchFixedString) >= 0
        path = Path(text)
        if not resolved and not (
            path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"}
        ):
            family = next(
                (name for name in self.fonts_data if name.casefold() == text.casefold()),
                None,
            )
            if family is None:
                prefix = text.casefold()
                matches = [
                    name for name in self.fonts_data if name.casefold().startswith(prefix)
                ]
                family = min(matches, key=len) if matches else None
            if family is not None:
                text = family
                self.font_combo.blockSignals(True)
                self.font_combo.setCurrentText(family)
                self.font_combo.blockSignals(False)

        self._apply_font_text(text)

    def _on_font_changed(self, index: int) -> None:
        if self._loading_font or index < 0:
            return
        family = self.font_combo.itemData(index)
        if not family:
            return
        self._select_family(str(family))

    def choose_font_file(self) -> None:
        if self.render_config is None:
            return
        path = get_open_file_name(
            self,
            tr("Выберите файл шрифта"),
            self.font_path or str(Path.home()),
            tr("Шрифты (*.ttf *.otf *.ttc)"),
        )
        if not path:
            return
        self._select_file_font(path)

    def _build_font_size_spin(self) -> QSpinBox:
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(1, 2000)
        self.font_size_spin.setValue(
            self.render_config.font_size if self.render_config is not None else 100
        )
        self.font_size_spin.setEnabled(self.render_config is not None)
        self.font_size_spin.valueChanged.connect(self._on_font_size_changed)
        return self.font_size_spin

    def _build_letter_spacing_spin(self) -> QSpinBox:
        self.letter_spacing_spin = QSpinBox()
        self.letter_spacing_spin.setRange(-20, 200)
        self.letter_spacing_spin.setValue(self.letter_spacing)
        self.letter_spacing_spin.setEnabled(self.render_config is not None)
        self.letter_spacing_spin.valueChanged.connect(self._on_letter_spacing_changed)
        return self.letter_spacing_spin

    def _build_color_row(self) -> ColorField:
        """Ряд «Цвет» в стиле Figma: плашка и hex в одной строке-инпуте."""

        self.text_color_field = ColorField(
            self.text_color,
            title="Выбрать цвет текста",
        )
        self.text_color_field.setEnabled(self.render_config is not None)
        self.text_color_field.changed.connect(self._on_text_color_changed)
        self.text_color_field.match_height(self.font_size_spin)
        return self.text_color_field

    def _on_text_color_changed(self, rgba) -> None:
        self.text_color = clamp_rgba(rgba)
        self._refresh_render_config()

    def _build_auto_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.auto_x_check = QCheckBox("Авто по X")
        self.auto_x_check.setToolTip(
            "Автопозиция по X: прижать блок к выбранному краю или центру"
        )
        self.auto_x_check.setChecked(self.auto_x)
        self.auto_x_check.toggled.connect(self._on_auto_changed)
        layout.addWidget(self.auto_x_check)

        self.auto_y_check = QCheckBox("Авто по Y")
        self.auto_y_check.setToolTip("Центрировать текст по вертикали, игнорируя Y точки")
        self.auto_y_check.setChecked(self.auto_y)
        self.auto_y_check.toggled.connect(self._on_auto_changed)
        layout.addWidget(self.auto_y_check)
        layout.addStretch()

        # Начальные координаты маркера должны соответствовать включённым авто-режимам.
        if self.auto_x_check.isChecked():
            self.marker_x = self._auto_x_anchor()
        if self.auto_y_check.isChecked():
            self.marker_y = self.img_height // 2
        return row

    def _build_coord_row(self) -> QWidget:
        """Точные координаты крестика: ввод вручную двигает метку."""

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.coord_x_spin = QSpinBox()
        self.coord_x_spin.setRange(0, max(0, self.img_width - 1))
        self.coord_x_spin.setValue(self.marker_x)
        self.coord_x_spin.setFixedWidth(96)
        self.coord_x_spin.setToolTip(
            "Крестик по X: левый/правый край блока или его центр "
            "в зависимости от выравнивания"
        )
        self.coord_x_spin.valueChanged.connect(self._on_coord_x_changed)
        layout.addWidget(QLabel("X:"))
        layout.addWidget(self.coord_x_spin)

        self.coord_y_spin = QSpinBox()
        self.coord_y_spin.setRange(0, max(0, self.img_height - 1))
        self.coord_y_spin.setValue(self.marker_y)
        self.coord_y_spin.setFixedWidth(96)
        self.coord_y_spin.setToolTip(
            "Крестик по Y: вертикальный центр текстового блока"
        )
        self.coord_y_spin.valueChanged.connect(self._on_coord_y_changed)
        layout.addWidget(QLabel("Y:"))
        layout.addWidget(self.coord_y_spin)
        layout.addStretch()
        return row

    def _on_coord_x_changed(self, value: int) -> None:
        if getattr(self, "_loading_coords", False):
            return
        self.auto_x_check.setChecked(False)
        self.marker_x = value
        self.point_changed = True
        self.draw_marker()

    def _on_coord_y_changed(self, value: int) -> None:
        if getattr(self, "_loading_coords", False):
            return
        self.auto_y_check.setChecked(False)
        self.marker_y = value
        self.point_changed = True
        self.draw_marker()

    def _build_marker_color_row(self) -> ColorField:
        return self._build_color_control(
            self.marker_color,
            "marker_color_field",
            "Выбрать цвет крестика",
            self._on_marker_color_changed,
        )

    def _build_safe_color_row(self) -> ColorField:
        return self._build_color_control(
            self.safe_area_color,
            "safe_color_field",
            "Выбрать цвет линии полей для печати",
            self._on_safe_color_changed,
        )

    def _build_color_control(
        self,
        color,
        attr_name: str,
        title: str,
        on_change,
    ) -> ColorField:
        field = ColorField(color, title=title)
        field.changed.connect(on_change)
        # Высота по соседнему ряду «Поля»: все ряды инспектора одинаковые.
        reference = getattr(self, "margin_spin", None) or getattr(
            self, "font_size_spin", None
        )
        if reference is not None:
            field.match_height(reference)
        setattr(self, attr_name, field)
        return field

    def _on_marker_color_changed(self, rgba) -> None:
        self.marker_color = clamp_rgba(rgba)
        self.marker_pen.setColor(QColor(*self.marker_color))
        self.draw_marker()

    def _on_safe_color_changed(self, rgba) -> None:
        self.safe_area_color = clamp_rgba(rgba)
        self._rebuild_safe_area()

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
        self.margin_spin.setValue(self.safe_margin)
        self.margin_spin.setToolTip(
            "Отступ от краёв, за который не должен выходить текст при печати. "
            "0 означает отсутствие ограничения."
        )
        self.margin_spin.valueChanged.connect(self._on_margin_changed)
        row.addWidget(self.margin_spin, 1)
        return row

    def _apply_theme_to_children(self) -> None:
        theme = self.property("theme")
        if not theme:
            return
        apply_theme_tree(self, str(theme))

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
        font_path = self.font_path or self.render_config.font_path
        self.render_config = replace(
            self.render_config,
            font_path=font_path,
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
        if self.auto_x_check.isChecked():
            self.marker_x = self._auto_x_anchor()
        self._rebuild_safe_area()
        self._refresh_render_config()
        self.draw_marker()

    def reset_style(self) -> None:
        if self.render_config is None:
            return
        self.font_size_spin.setValue(100)
        self.letter_spacing_spin.setValue(0)
        self.text_color = (0, 0, 0, 255)
        self.text_color_field.set_rgba(self.text_color)
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

    def get_text_color(self) -> tuple[int, int, int, int]:
        return tuple(self.text_color)  # type: ignore[return-value]

    def get_font_path(self) -> str:
        return self.font_path

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
            return tr("ПКМ: поставить крестик (левый край, середина по высоте)")
        if self.align == "right":
            return tr("ПКМ: поставить крестик (правый край, середина по высоте)")
        return tr("ПКМ: поставить крестик (центр по горизонтали и вертикали)")

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
        if self.auto_x_check.isChecked():
            self.marker_x = self._auto_x_anchor()
        self.view.setToolTip(self._align_hint())
        self.draw_marker()

    def _on_safe_area_toggled(self, checked: bool) -> None:
        set_safe_area_visible(self.safe_area_items, checked and self.safe_margin > 0)

    def _auto_x_anchor(self) -> int:
        if self.align == "left":
            return max(0, min(self.img_width, self.safe_margin))
        if self.align == "right":
            return max(0, min(self.img_width, self.img_width - self.safe_margin))
        return self.img_width // 2

    def _on_auto_changed(self, _checked: bool = False) -> None:
        if self.auto_x_check.isChecked():
            self.marker_x = self._auto_x_anchor()
        if self.auto_y_check.isChecked():
            self.marker_y = self.img_height // 2
        self.draw_marker()

    def get_align(self) -> str:
        return self.align

    def get_auto_x(self) -> bool:
        return self.auto_x_check.isChecked()

    def get_auto_y(self) -> bool:
        return self.auto_y_check.isChecked()

    def get_safe_area_color(self) -> tuple[int, int, int, int]:
        return tuple(self.safe_area_color)  # type: ignore[return-value]

    def get_marker_color(self) -> tuple[int, int, int, int]:
        return tuple(self.marker_color)  # type: ignore[return-value]

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
                    self._auto_x_anchor() * self.display_scale
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

        template = {
            "left": "Левый край: X={x}, Y={y}",
            "right": "Правый край: X={x}, Y={y}",
            "center": "Центр текста: X={x}, Y={y}",
        }.get(self.align, "Точка: X={x}, Y={y}")
        self.info_label.setText(
            tr(template).format(x=self.marker_x, y=self.marker_y)
        )
        # Точные координаты синхронизируются с крестиком в обе стороны.
        self._loading_coords = True
        try:
            if getattr(self, "coord_x_spin", None) is not None:
                self.coord_x_spin.setValue(self.marker_x)
            if getattr(self, "coord_y_spin", None) is not None:
                self.coord_y_spin.setValue(self.marker_y)
        finally:
            self._loading_coords = False
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
        # Протяжка ПКМ: крестик едет за курсором, пока кнопка удерживается.
        if event.buttons() & Qt.RightButton:
            scene_pos = self.view.mapToScene(event.position().toPoint())
            self.marker_x = int(scene_pos.x())
            self.marker_y = int(scene_pos.y())
            self.point_changed = True
            self.draw_marker()
            event.accept()
            return
        if event.modifiers() & Qt.AltModifier:
            scene_pos = self.view.mapToScene(event.position().toPoint())
            dx = scene_pos.x() - self.marker_x
            dy = scene_pos.y() - self.marker_y
            dist = (dx**2 + dy**2) ** 0.5
            self.info_label.setText(
                tr("X={x}, Y={y} | ΔX={dx} ΔY={dy} | Дистанция: {dist} px").format(
                    x=self.marker_x,
                    y=self.marker_y,
                    dx=int(dx),
                    dy=int(dy),
                    dist=int(dist),
                )
            )
        QGraphicsView.mouseMoveEvent(self.view, event)

    def get_point(self):
        return self.marker_x, self.marker_y
