import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPropertyAnimation
from ui.main_window import DiplomaGenerator

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    app = QApplication(sys.argv)

    style_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.qss")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = DiplomaGenerator()
    window.show()
    sys.exit(app.exec())