from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from core.screen_utils import get_window_size
from ui.overlays import add_safe_area, set_safe_area_visible


class PreviewDialog(QDialog):
    """Полноэкранный предпросмотр с компактной панелью инструментов."""

    def __init__(self, pil_image, parent=None, *, margin: int = 0):
        super().__init__(parent)
        self.setObjectName("preview_dialog")
        self.setWindowTitle("Предпросмотр")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        width, height = get_window_size(self, 0.72, 0.82)
        self.resize(max(820, width), max(600, height))
        self.setMinimumSize(720, 520)

        self._margin = max(0, int(margin))
        self._scale_factor = 1.0

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel("Предпросмотр")
        title.setObjectName("dialog_title")
        header.addWidget(title)
        meta = QLabel(f"{pil_image.width} × {pil_image.height} px")
        meta.setObjectName("dialog_meta")
        header.addWidget(meta)
        header.addStretch()
        root.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        self.safe_check = QCheckBox("Safe area")
        self.safe_check.setObjectName("safe_area_check")
        self.safe_check.setToolTip("Показать границы safe area (не влияет на результат)")
        self.safe_check.setEnabled(self._margin > 0)
        if self._margin <= 0:
            self.safe_check.setToolTip("Safe area не задана: отступ равен 0 px")
        toolbar.addWidget(self.safe_check)
        toolbar.addStretch()

        self.btn_fit = self._tool_button("По размеру", "Вписать изображение в окно")
        self.btn_actual = self._tool_button("1:1", "Масштаб 100%")
        self.btn_out = self._tool_button("−", "Уменьшить", width=30)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("zoom_label")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setMinimumWidth(46)
        self.btn_in = self._tool_button("+", "Увеличить", width=30)

        toolbar.addWidget(self.btn_fit)
        toolbar.addWidget(self.btn_actual)
        toolbar.addWidget(self.btn_out)
        toolbar.addWidget(self.zoom_label)
        toolbar.addWidget(self.btn_in)
        root.addLayout(toolbar)

        canvas = QFrame()
        canvas.setObjectName("preview_canvas")
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(8, 8, 8, 8)
        canvas_layout.setSpacing(0)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setObjectName("preview_view")
        self.view.setFrameShape(QFrame.NoFrame)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setStyleSheet("QGraphicsView { background: transparent; border: none; }")
        self.view.viewport().setAutoFillBackground(False)
        canvas_layout.addWidget(self.view)
        root.addWidget(canvas, 1)

        pil_rgb = pil_image.convert("RGB")
        data = pil_rgb.tobytes("raw", "RGB")
        qimage = QImage(
            data,
            pil_rgb.width,
            pil_rgb.height,
            pil_rgb.width * 3,
            QImage.Format_RGB888,
        ).copy()
        pixmap = QPixmap.fromImage(qimage)
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)

        self.safe_area_items = add_safe_area(
            self.scene,
            pil_image.width,
            pil_image.height,
            self._margin,
            z=10,
        )
        set_safe_area_visible(self.safe_area_items, False)

        footer = QFrame()
        footer.setObjectName("dialog_footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 10, 0, 0)
        footer_layout.setSpacing(8)

        self.edit_btn = QPushButton("Редактировать позицию")
        self.edit_btn.setObjectName("secondary_btn")
        self.edit_btn.setAutoDefault(False)
        self.edit_btn.clicked.connect(self.edit_position)
        footer_layout.addWidget(self.edit_btn)
        footer_layout.addStretch()

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setObjectName("tertiary_btn")
        self.cancel_btn.setAutoDefault(False)
        self.cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.cancel_btn)

        self.continue_btn = QPushButton("Продолжить")
        self.continue_btn.setObjectName("primary_btn")
        self.continue_btn.setToolTip("Продолжить генерацию")
        self.continue_btn.setMinimumWidth(190)
        self.continue_btn.setMinimumHeight(36)
        self.continue_btn.setDefault(True)
        self.continue_btn.setAutoDefault(True)
        self.continue_btn.clicked.connect(self.accept)
        footer_layout.addWidget(self.continue_btn)

        root.addWidget(footer)

        self.btn_in.clicked.connect(self.zoom_in)
        self.btn_out.clicked.connect(self.zoom_out)
        self.btn_fit.clicked.connect(self.fit_to_view)
        self.btn_actual.clicked.connect(self.actual_size)
        self.safe_check.toggled.connect(self._set_safe_area_visible)
        self.view.wheelEvent = self.on_wheel

    @staticmethod
    def _tool_button(text: str, tooltip: str, *, width: int | None = None) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("tool_btn")
        button.setToolTip(tooltip)
        button.setAutoDefault(False)
        button.setMinimumHeight(28)
        if width is not None:
            button.setFixedWidth(width)
        return button

    def showEvent(self, event):
        super().showEvent(event)
        self.fit_to_view()

    def _set_safe_area_visible(self, visible: bool) -> None:
        set_safe_area_visible(self.safe_area_items, bool(visible) and self._margin > 0)

    def _update_zoom_label(self) -> None:
        self.zoom_label.setText(f"{max(1, round(self._scale_factor * 100))}%")

    def zoom_in(self):
        self.zoom_at_cursor(1.2)

    def zoom_out(self):
        self.zoom_at_cursor(1 / 1.2)

    def actual_size(self):
        self._scale_factor = 1.0
        self.view.resetTransform()
        self._update_zoom_label()

    def zoom_at_cursor(self, factor):
        cursor_pos = self.view.mapFromGlobal(self.view.cursor().pos())
        if not self.view.viewport().rect().contains(cursor_pos):
            cursor_pos = self.view.viewport().rect().center()
        scene_pos = self.view.mapToScene(cursor_pos)

        new_scale = max(0.01, min(50.0, self._scale_factor * factor))
        self._scale_factor = new_scale

        self.view.resetTransform()
        self.view.scale(self._scale_factor, self._scale_factor)

        new_cursor_pos = self.view.mapFromScene(scene_pos)
        delta = new_cursor_pos - cursor_pos

        h_bar = self.view.horizontalScrollBar()
        v_bar = self.view.verticalScrollBar()
        h_bar.setValue(h_bar.value() + delta.x())
        v_bar.setValue(v_bar.value() + delta.y())
        self._update_zoom_label()

    def fit_to_view(self):
        if self.pixmap_item is None:
            return
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self._scale_factor = self.view.transform().m11()
        self._update_zoom_label()

    def on_wheel(self, event):
        if event.angleDelta().y() > 0:
            self.zoom_at_cursor(1.2)
        else:
            self.zoom_at_cursor(1 / 1.2)
        event.accept()

    def edit_position(self):
        self.done(2)
