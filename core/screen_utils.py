from PySide6.QtWidgets import QApplication, QWidget


def screen_of(widget: QWidget | None):
    """Возвращает экран виджета или основной экран."""

    if widget is not None:
        screen = widget.screen()
        if screen is not None:
            return screen
    return QApplication.primaryScreen()


def get_screen_size(widget=None):
    """Возвращает размер доступного экрана."""
    screen = screen_of(widget).availableGeometry()
    return screen.width(), screen.height()


def get_window_size(widget, width_ratio=0.6, height_ratio=0.7):
    """
    Возвращает размер окна относительно экрана.
    По умолчанию: 60% ширины, 70% высоты.
    """
    screen_w, screen_h = get_screen_size(widget)
    return int(screen_w * width_ratio), int(screen_h * height_ratio)


def center_window(window):
    """Центрирует окно на его экране.

    Координаты берутся от левого верхнего угла доступной области экрана, а не
    от (0, 0): при двух мониторах основной экран может начинаться не в начале
    виртуального рабочего стола, иначе окно уезжает на соседний монитор.
    """
    geometry = screen_of(window).availableGeometry()
    window.move(
        geometry.x() + max(0, (geometry.width() - window.width()) // 2),
        geometry.y() + max(0, (geometry.height() - window.height()) // 2),
    )


def place_window_on_screen(
    window,
    anchor: QWidget | None = None,
    *,
    width_ratio: float = 0.78,
    height_ratio: float = 0.82,
    min_width: int = 900,
    min_height: int = 600,
) -> None:
    """Подгоняет размер и позицию окна под экран якоря.

    Размер считается по экрану ``anchor`` (обычно родительское окно), потому
    что у ещё не показанного окна ``screen()`` возвращает основной монитор, а
    родитель может находиться на другом.  Итоговый размер ограничивается
    доступной областью, чтобы окно не выходило за границы небольшого второго
    монитора.
    """
    geometry = screen_of(anchor if anchor is not None else window).availableGeometry()
    width = min(max(min_width, int(geometry.width() * width_ratio)), geometry.width())
    height = min(max(min_height, int(geometry.height() * height_ratio)), geometry.height())
    window.resize(width, height)
    window.move(
        geometry.x() + max(0, (geometry.width() - width) // 2),
        geometry.y() + max(0, (geometry.height() - height) // 2),
    )
