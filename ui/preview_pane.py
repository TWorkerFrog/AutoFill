from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)


class PreviewPane(QFrame):
    """Компактный живой предпросмотр справа от настроек."""

    openRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("preview_pane")
        self._original: QPixmap | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(6)
        title = QLabel("Живой предпросмотр")
        title.setObjectName("preview_title")
        header.addWidget(title)
        header.addStretch()

        self.open_button = QPushButton("Редактировать")
        self.open_button.setObjectName("link_btn")
        self.open_button.setToolTip("Открыть редактор грамоты")
        self.open_button.setAutoDefault(False)
        self.open_button.clicked.connect(self.openRequested)
        header.addWidget(self.open_button)
        layout.addLayout(header)

        self.canvas = QFrame()
        self.canvas.setObjectName("preview_canvas")
        canvas_layout = QVBoxLayout(self.canvas)
        canvas_layout.setContentsMargins(8, 8, 8, 8)
        canvas_layout.setSpacing(0)

        self.image_label = QLabel("Выберите шаблон, шрифт и добавьте ФИО")
        self.image_label.setObjectName("preview_image")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setWordWrap(True)
        self.image_label.setMinimumSize(220, 220)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        canvas_layout.addWidget(self.image_label)
        layout.addWidget(self.canvas, 1)

        self.hint_label = QLabel("Двойной клик: открыть редактор")
        self.hint_label.setObjectName("hint_label")
        self.hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.hint_label)

    def set_image(self, pil_image) -> None:
        if pil_image.mode == "RGBA":
            data = pil_image.tobytes("raw", "RGBA")
            image = QImage(
                data,
                pil_image.width,
                pil_image.height,
                pil_image.width * 4,
                QImage.Format_RGBA8888,
            )
        else:
            rgb = pil_image.convert("RGB")
            data = rgb.tobytes("raw", "RGB")
            image = QImage(
                data,
                rgb.width,
                rgb.height,
                rgb.width * 3,
                QImage.Format_RGB888,
            )
        self._original = QPixmap.fromImage(image.copy())
        self.hint_label.show()
        self._rescale()

    def set_message(self, text: str) -> None:
        self._original = None
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText(text)
        self.hint_label.hide()

    def clear(self) -> None:
        self.set_message("Выберите шаблон, шрифт и добавьте ФИО")

    def _rescale(self) -> None:
        if self._original is None or self._original.isNull():
            return
        size = self.image_label.size()
        if size.width() <= 1 or size.height() <= 1:
            return
        self.image_label.setText("")
        self.image_label.setPixmap(
            self._original.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rescale()

    def mouseDoubleClickEvent(self, event) -> None:
        if self._original is not None:
            self.openRequested.emit()
        super().mouseDoubleClickEvent(event)
