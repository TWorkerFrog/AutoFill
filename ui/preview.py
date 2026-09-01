from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


class PreviewDialog(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Предпросмотр")

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(self.view.renderHints())
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)

        screen = self.screen().availableGeometry()
        self.view_w = int(screen.width() * 0.85)
        self.view_h = int(screen.height() * 0.8)
        self.view.setFixedSize(self.view_w, self.view_h)

        pixmap = QPixmap(image_path)
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)

        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.scale_factor = self.view.transform().m11()

        self.view.wheelEvent = self.on_wheel

        layout.addWidget(self.view)

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

        btn_layout = QHBoxLayout()

        self.continue_btn = QPushButton("Продолжить генерацию")
        self.continue_btn.setObjectName("primary_btn")
        self.continue_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.continue_btn)

        self.edit_btn = QPushButton("Редактировать позицию")
        self.edit_btn.clicked.connect(self.edit_position)
        btn_layout.addWidget(self.edit_btn)

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def zoom_in(self):
        self.zoom_at_cursor(1.2)

    def zoom_out(self):
        self.zoom_at_cursor(1 / 1.2)

    def zoom_at_cursor(self, factor):
        cursor_pos = self.view.mapFromGlobal(self.view.cursor().pos())
        scene_pos = self.view.mapToScene(cursor_pos)

        self.scale_factor *= factor
        if self.scale_factor < 0.01:
            self.scale_factor = 0.01
        if self.scale_factor > 50:
            self.scale_factor = 50

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

    def edit_position(self):
        self.done(2)