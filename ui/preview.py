from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
)

from core.screen_utils import get_window_size


class PreviewDialog(QDialog):
    def __init__(self, pil_image, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Предпросмотр")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        width, height = get_window_size(self, 0.72, 0.82)
        self.resize(max(720, width), max(520, height))
        self.setMinimumSize(520, 420)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)

        # Конвертируем PIL Image в QPixmap
        pil_rgb = pil_image.convert("RGB")
        data = pil_rgb.tobytes("raw", "RGB")
        qimage = QImage(data, pil_rgb.width, pil_rgb.height, pil_rgb.width * 3, QImage.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(qimage)

        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)

        self.scale_factor = 1.0
        self.view.wheelEvent = self.on_wheel

        layout.addWidget(self.view)

        # Кнопки зума
        zoom_layout = QHBoxLayout()
        btn_in = QPushButton("+")
        btn_in.setFixedWidth(40)
        btn_in.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(btn_in)

        btn_out = QPushButton("−")
        btn_out.setFixedWidth(40)
        btn_out.clicked.connect(self.zoom_out)
        zoom_layout.addWidget(btn_out)

        btn_fit = QPushButton("По размеру")
        btn_fit.clicked.connect(self.fit_to_view)
        zoom_layout.addWidget(btn_fit)
        zoom_layout.addStretch()
        layout.addLayout(zoom_layout)

        # Кнопки
        btn_layout = QHBoxLayout()

        self.continue_btn = QPushButton("Продолжить генерацию")
        self.continue_btn.setObjectName("primary_btn")
        self.continue_btn.setDefault(True)
        self.continue_btn.setAutoDefault(True)
        self.continue_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.continue_btn)

        self.edit_btn = QPushButton("Редактировать позицию")
        self.edit_btn.clicked.connect(self.edit_position)
        btn_layout.addWidget(self.edit_btn)

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def showEvent(self, event):
        super().showEvent(event)
        self.fit_to_view()

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
        if self.pixmap_item is None:
            return
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.scale_factor = self.view.transform().m11()

    def on_wheel(self, event):
        if event.angleDelta().y() > 0:
            self.zoom_at_cursor(1.2)
        else:
            self.zoom_at_cursor(1 / 1.2)
        event.accept()

    def edit_position(self):
        self.done(2)