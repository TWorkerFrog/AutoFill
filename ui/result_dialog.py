from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from core.screen_utils import get_window_size

class ResultDialog(QDialog):
    def __init__(self, parent=None, text="", open_folder_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Готово")
        w, h = get_window_size(self, 0.3, 0.25)
        self.resize(w, h)

        self.open_folder_callback = open_folder_callback

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.label = QLabel(text)
        self.label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.label)

        btn_layout = QHBoxLayout()

        if open_folder_callback:
            self.open_btn = QPushButton("Открыть папку")
            self.open_btn.setObjectName("primary_btn")
            self.open_btn.clicked.connect(self.open_folder)
            btn_layout.addWidget(self.open_btn)

        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def open_folder(self):
        if self.open_folder_callback:
            self.open_folder_callback()
        self.accept()