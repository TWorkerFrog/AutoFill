import sys
import os
from PySide6.QtWidgets import QApplication

from core.windows_utils import set_title_bar_color, set_title_bar_light_theme
from ui.main_window import DiplomaGenerator
from core.screen_utils import center_window

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    app = QApplication(sys.argv)

    # Определяем base_path
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    style_path = os.path.join(base_path, "style.qss")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            style_content = f.read()

        # Заменяем относительные пути на абсолютные
        style_content = style_content.replace('url("icons/', f'url("{base_path}/icons/')
        app.setStyleSheet(style_content)

    window = DiplomaGenerator()
    window.show()
    set_title_bar_color(window, "#222222")
    set_title_bar_light_theme(window, False)
    center_window(window)
    sys.exit(app.exec())