from PySide6.QtWidgets import QApplication


def get_screen_size(widget=None):
    """Возвращает размер доступного экрана."""
    if widget and widget.screen():
        screen = widget.screen().availableGeometry()
    else:
        screen = QApplication.primaryScreen().availableGeometry()
    return screen.width(), screen.height()


def get_window_size(widget, width_ratio=0.6, height_ratio=0.7):
    """
    Возвращает размер окна относительно экрана.
    По умолчанию: 60% ширины, 70% высоты.
    """
    screen_w, screen_h = get_screen_size(widget)
    return int(screen_w * width_ratio), int(screen_h * height_ratio)


def center_window(window):
    """Центрирует окно относительно экрана."""
    screen_w, screen_h = get_screen_size(window)
    window.move(
        (screen_w - window.width()) // 2,
        (screen_h - window.height()) // 2
    )