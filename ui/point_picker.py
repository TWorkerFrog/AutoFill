from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import replace

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from core.generator import RenderConfig, render_page
from core.screen_utils import get_window_size

log = logging.getLogger(__name__)


class PointPickerDialog(QDialog):
    def __init__(
        self,
        image_path,
        parent=None,
        initial_x=None,
        initial_y=None,
        align="left",
        render_config: RenderConfig | None = None,
        preview_parts: Sequence[str] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Укажи точку")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self.align = align
        self.render_config = render_config
        self.preview_parts = list(preview_parts or [])

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
        self.preview_font = None
        if self.render_config is not None and self.preview_parts:
            try:
                self.preview_font = ImageFont.truetype(
                    self.render_config.font_path,
                    size=self.render_config.font_size,
                )
            except (OSError, ValueError):
                self.preview_font = None

        self.pixmap = self._pil_to_pixmap(self.base_image)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.view.setFocusPolicy(Qt.StrongFocus)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setMouseTracking(True)

        self.pixmap_item = QGraphicsPixmapItem(self.pixmap)
        self.scene.addItem(self.pixmap_item)

        w, h = get_window_size(self, 0.7, 0.75)
        self.resize(max(680, w), max(480, h))
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

        self.marker_pen = QPen(QColor(255, 0, 0))
        self.marker_pen.setWidth(3)
        self.marker_lines = []

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(60)
        self._preview_timer.timeout.connect(self._render_preview)

        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignCenter)

        zoom_layout = QHBoxLayout()
        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedWidth(40)
        btn_zoom_in.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(btn_zoom_in)

        btn_zoom_out = QPushButton("−")
        btn_zoom_out.setFixedWidth(40)
        btn_zoom_out.clicked.connect(self.zoom_out)
        zoom_layout.addWidget(btn_zoom_out)

        btn_fit = QPushButton("По размеру")
        btn_fit.clicked.connect(self.fit_to_view)
        zoom_layout.addWidget(btn_fit)

        btn_center = QPushButton("В центр")
        btn_center.clicked.connect(self.center_marker)
        zoom_layout.addWidget(btn_center)
        zoom_layout.addStretch()

        self.ok_btn = QPushButton("Готово")
        self.ok_btn.setObjectName("primary_btn")
        self.ok_btn.setMinimumHeight(40)
        self.ok_btn.setDefault(True)
        self.ok_btn.setAutoDefault(True)
        self.ok_btn.clicked.connect(self.accept)

        layout = QVBoxLayout()
        if self.align == "left":
            hint = "Правая кнопка мыши — поставить точку (левый край блока)"
        elif self.align == "right":
            hint = "Правая кнопка мыши — поставить точку (правый край блока)"
        else:
            hint = "Правая кнопка мыши — поставить точку (центр блока)"
        hint_label = QLabel(hint)
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
        help_label = QLabel(
            "Красная рамка — safe area. Текст рисуется в текущем шрифте и цвете. "
            "Левая кнопка — перемещать изображение | Колесо — зум | "
            "Стрелки — сдвиг | Shift — 10 px | Ctrl — 50 px | "
            "Alt + движение мыши — расстояние до точки"
        )
        help_label.setWordWrap(True)
        help_label.setObjectName("hint_label")
        layout.addWidget(help_label)
        layout.addWidget(self.view)
        layout.addLayout(zoom_layout)
        layout.addWidget(self.info_label)
        layout.addWidget(self.ok_btn)
        self.setLayout(layout)

        self.view.mousePressEvent = self.on_mouse_press
        self.view.keyPressEvent = self.on_key_press
        self.view.wheelEvent = self.on_wheel
        self.view.mouseMoveEvent = self.on_mouse_move

        self.draw_marker()
        self._render_preview()
        self.view.setFocus()

    def showEvent(self, event):
        super().showEvent(event)
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.scale_factor = self.view.transform().m11()

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

    def _schedule_preview(self) -> None:
        if self.render_config is not None:
            self._preview_timer.start()

    def _render_preview(self) -> None:
        image = self.base_image.copy()
        if self.render_config is not None:
            margin = max(0, int(self.render_config.margin))
            margin = min(margin, self.img_width // 2, self.img_height // 2)
            if margin:
                draw = ImageDraw.Draw(image)
                draw.rectangle(
                    (margin, margin, self.img_width - margin - 1, self.img_height - margin - 1),
                    outline=(220, 60, 60),
                    width=2,
                )
            if self.preview_font is not None and self.preview_parts:
                config = replace(
                    self.render_config,
                    x=self.marker_x,
                    y=self.marker_y,
                    align=self.align,
                )
                try:
                    image = render_page(image, self.preview_parts, self.preview_font, config)
                except Exception:
                    log.debug("Не удалось нарисовать предпросмотр в выборе точки", exc_info=True)
                    image = self.base_image.copy()
        self.pixmap_item.setPixmap(self._pil_to_pixmap(image))

    def center_marker(self) -> None:
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
            self.marker_x -= step
        elif event.key() == Qt.Key_Right:
            self.marker_x += step
        elif event.key() == Qt.Key_Up:
            self.marker_y -= step
        elif event.key() == Qt.Key_Down:
            self.marker_y += step
        else:
            QGraphicsView.keyPressEvent(self.view, event)
            return
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
        factor = new_scale / self.scale_factor if self.scale_factor else 1.0
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

        line1 = QGraphicsLineItem(self.marker_x - size, self.marker_y, self.marker_x + size, self.marker_y)
        line1.setPen(self.marker_pen)
        self.scene.addItem(line1)
        self.marker_lines.append(line1)

        line2 = QGraphicsLineItem(self.marker_x, self.marker_y - size, self.marker_x, self.marker_y + size)
        line2.setPen(self.marker_pen)
        self.scene.addItem(line2)
        self.marker_lines.append(line2)

        dot = QGraphicsEllipseItem(self.marker_x - 3, self.marker_y - 3, 6, 6)
        dot.setPen(self.marker_pen)
        dot.setBrush(QBrush(QColor(255, 0, 0)))
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
            scene_pos = self.view.mapToScene(event.position().toPoint())
            self.marker_x = int(scene_pos.x())
            self.marker_y = int(scene_pos.y())
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


