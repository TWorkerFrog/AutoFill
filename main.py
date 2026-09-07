import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from core.screen_utils import center_window
from core.windows_utils import set_title_bar_color, set_title_bar_light_theme
from ui.main_window import DiplomaGenerator
import resources_rc

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    icon = QIcon(":/icons/app_icon.ico")
    if not icon.isNull():
        app.setWindowIcon(icon)
    else:
        # Фолбек: пробуем из файла
        icon_path = resource_path("icons/app_icon.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))


    # Стили
    style_path = resource_path("style.qss")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    # Окно
    window = DiplomaGenerator()

    # Иконка для окна (из ресурсов)
    if not icon.isNull():
        window.setWindowIcon(icon)

    window.show()

    # Настройки заголовка
    set_title_bar_color(window, "#222222")
    set_title_bar_light_theme(window, False)
    center_window(window)

    sys.exit(app.exec())