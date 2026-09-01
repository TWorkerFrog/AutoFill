from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsLineItem, QGraphicsEllipseItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QColor, QPen, QBrush
from PIL import Image


class PointPickerDialog(QDialog):
    def __init__(self, image_path, parent=None, initial_x=None, initial_y=None):
        super().__init__(parent)
        self.setWindowTitle("Укажи точку — центр текста")

        self.image_path = image_path
        self.pil_image = Image.open(image_path)
        self.img_width = self.pil_image.width
        self.img_height = self.pil_image.height

        if initial_x is not None and initial_y is not None:
            self.marker_x = initial_x
            self.marker_y = initial_y
        else:
            self.marker_x = self.img_width // 2
            self.marker_y = self.img_height // 2

        self.pil_image_rgb = self.pil_image.convert("RGB")
        data = self.pil_image_rgb.tobytes("raw", "RGB")
        qimage = QImage(data, self.img_width, self.img_height, self.img_width * 3, QImage.Format_RGB888)
        self.pixmap = QPixmap.fromImage(qimage)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(self.view.renderHints())
        self.view.setFocusPolicy(Qt.StrongFocus)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)

        self.pixmap_item = QGraphicsPixmapItem(self.pixmap)
        self.scene.addItem(self.pixmap_item)

        screen = self.screen().availableGeometry()
        self.view_w = int(screen.width() * 0.85)
        self.view_h = int(screen.height() * 0.8)
        self.view.setFixedSize(self.view_w, self.view_h)

        self.scale_factor = 1.0
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.scale_factor = self.view.transform().m11()

        pen = QPen(QColor(255, 0, 0, 100))
        pen.setWidth(1)
        pen.setStyle(Qt.DashLine)

        line_v = QGraphicsLineItem(self.img_width // 2, 0, self.img_width // 2, self.img_height)
        line_v.setPen(pen)
        self.scene.addItem(line_v)

        line_h = QGraphicsLineItem(0, self.img_height // 2, self.img_width, self.img_height // 2)
        line_h.setPen(pen)
        self.scene.addItem(line_h)

        self.marker_pen = QPen(QColor(255, 0, 0))
        self.marker_pen.setWidth(3)

        self.marker_lines = []

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
        zoom_layout.addStretch()

        self.ok_btn = QPushButton("Готово")
        self.ok_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; padding: 12px; font-size: 14px; font-weight: bold; }"
        )
        self.ok_btn.setMinimumHeight(40)
        self.ok_btn.clicked.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Правая кнопка мыши — поставить точку (центр текста)"))
        layout.addWidget(QLabel("Левая кнопка — перетаскивание | Колесо мыши — зум | Стрелки — сдвиг | Shift — 10px | Ctrl — 50px | Alt — расстояние"))
        layout.addWidget(self.view, alignment=Qt.AlignCenter)
        layout.addLayout(zoom_layout)
        layout.addWidget(self.info_label)
        layout.addWidget(self.ok_btn)
        self.setLayout(layout)

        self.view.mousePressEvent = self.on_mouse_press
        self.view.keyPressEvent = self.on_key_press
        self.view.wheelEvent = self.on_wheel
        self.view.mouseMoveEvent = self.on_mouse_move

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
        self.draw_marker()

    def fit_to_view(self):
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.scale_factor = self.view.transform().m11()

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

    def on_wheel(self, event):
        if event.angleDelta().y() > 0:
            self.zoom_at_cursor(1.2)
        else:
            self.zoom_at_cursor(1 / 1.2)

    def draw_marker(self):
        for item in self.marker_lines:
            self.scene.removeItem(item)
        self.marker_lines.clear()

        size = 14

        line1 = QGraphicsLineItem(self.marker_x - size, self.marker_y, self.marker_x + size, self.marker_y)
        line1.setPen(self.marker_pen)
        self.scene.addItem(line1)
        self.marker_lines.append(line1)

        line2 = QGraphicsLineItem(self.marker_x, self.marker_y - size, self.marker_x, self.marker_y + size)
        line2.setPen(self.marker_pen)
        self.scene.addItem(line2)
        self.marker_lines.append(line2)

        dot = QGraphicsEllipseItem(self.marker_x - 2, self.marker_y - 2, 4, 4)
        dot.setPen(self.marker_pen)
        dot.setBrush(QBrush(QColor(255, 0, 0)))
        self.scene.addItem(dot)
        self.marker_lines.append(dot)

        self.info_label.setText(f"Центр текста: X={self.marker_x}, Y={self.marker_y}")

    def on_mouse_press(self, event):
        if event.button() == Qt.RightButton:
            scene_pos = self.view.mapToScene(event.position().toPoint())
            self.marker_x = int(scene_pos.x())
            self.marker_y = int(scene_pos.y())
            self.draw_marker()
        else:
            QGraphicsView.mousePressEvent(self.view, event)

    def on_mouse_move(self, event):
        if event.modifiers() & Qt.AltModifier:
            scene_pos = self.view.mapToScene(event.position().toPoint())
            dx = scene_pos.x() - self.marker_x
            dy = scene_pos.y() - self.marker_y
            dist = (dx**2 + dy**2) ** 0.5
            self.info_label.setText(
                f"Центр: X={self.marker_x}, Y={self.marker_y} | "
                f"ΔX={int(dx)} ΔY={int(dy)} | Дистанция: {int(dist)}px"
            )
        else:
            self.draw_marker()
        QGraphicsView.mouseMoveEvent(self.view, event)

    def get_point(self):
        return self.marker_x, self.marker_y