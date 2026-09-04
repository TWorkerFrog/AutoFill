from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from core.screen_utils import get_window_size

class MessageDialog(QDialog):
    def __init__(self, parent=None, title="", text="", buttons=None, default_btn=0):
        super().__init__(parent)
        self.setWindowTitle(title)
        w, h = get_window_size(self, 0.3, 0.25)
        self.resize(w, h)

        self.result = None

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.label = QLabel(text)
        self.label.setAlignment(Qt.AlignLeft)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        btn_layout = QHBoxLayout()
        self.buttons = []

        if buttons:
            for i, (text_btn, role) in enumerate(buttons):
                btn = QPushButton(text_btn)
                if role == "primary":
                    btn.setObjectName("primary_btn")
                btn.clicked.connect(lambda checked, idx=i: self.button_clicked(idx))
                btn_layout.addWidget(btn)
                self.buttons.append(btn)
        else:
            btn = QPushButton("Закрыть")
            btn.setObjectName("primary_btn")
            btn.clicked.connect(lambda: self.button_clicked(0))
            btn_layout.addWidget(btn)
            self.buttons.append(btn)

        layout.addLayout(btn_layout)

    def button_clicked(self, idx):
        self.result = idx
        self.accept()