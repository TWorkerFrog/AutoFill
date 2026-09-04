import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPropertyAnimation
from ui.main_window import DiplomaGenerator
from PySide6.QtCore import QTranslator, QLibraryInfo
from ui.result_dialog import ResultDialog
from ui.message_dialog import MessageDialog
from core.screen_utils import center_window

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    app = QApplication(sys.argv)

    translator = QTranslator()
    translator.load("qtbase_ru", QLibraryInfo.path(QLibraryInfo.TranslationsPath))
    app.installTranslator(translator)
    style_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.qss")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = DiplomaGenerator()
    window.show()
    center_window(window)
    sys.exit(app.exec())