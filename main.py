import faulthandler
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

import resources_rc  # noqa: F401  # регистрирует встроенные Qt-ресурсы
from core.i18n import install_qt_translations, set_language
from core.screen_utils import center_window
from core.settings import SettingsStore, app_data_dir
from core.version import APP_NAME, __version__
from ui.main_window import DiplomaGenerator

# Открытый файл для faulthandler: держим ссылку, иначе он закроется.
_crash_handle = None


def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    try:
        log_dir = app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError as exc:
        # Приложение должно запускаться даже при недоступном AppData.
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning("Файловый журнал недоступен: %s", exc)
        return
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    ))
    root.addHandler(handler)


def install_exception_hook() -> None:
    log = logging.getLogger("autofill")

    def handle(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.critical("Необработанное исключение", exc_info=(exc_type, exc_value, exc_tb))
        QMessageBox.critical(
            None,
            f"{APP_NAME}: ошибка",
            f"Произошла непредвиденная ошибка:\n\n{exc_value}\n\n"
            "Подробности записаны в журнал приложения.",
        )

    sys.excepthook = handle


def enable_faulthandler() -> None:
    """Пишет стек при жёстком падении процесса в logs/crash.log.

    Обычные исключения ловит excepthook, но если падает сам интерпретатор
    (например, внутри Qt), Python завершается без внятного сообщения.
    """

    global _crash_handle
    if _crash_handle is not None:
        return
    try:
        log_dir = app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        # Файл должен жить всё время работы приложения: faulthandler
        # пишет в него при аварийном завершении.
        _crash_handle = open(  # noqa: SIM115
            log_dir / "crash.log", "a", encoding="utf-8"
        )
    except OSError as exc:
        logging.getLogger(__name__).warning(
            "Файл crash.log недоступен: %s", exc
        )
        return
    _crash_handle.write(f"\n=== запуск {__version__} ===\n")
    _crash_handle.flush()
    faulthandler.enable(file=_crash_handle, all_threads=True)


def log_startup(settings) -> None:
    log = logging.getLogger("autofill")
    log.info(
        "Запуск %s %s: frozen=%s, язык=%s, тема=%s, python=%s",
        APP_NAME,
        __version__,
        getattr(sys, "frozen", False),
        settings.language,
        settings.theme,
        sys.version.split()[0],
    )


if __name__ == "__main__":
    configure_logging()
    enable_faulthandler()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("TWorker")
    install_exception_hook()

    loaded_settings = SettingsStore().load()
    log_startup(loaded_settings)
    set_language(loaded_settings.language)
    install_qt_translations(app, loaded_settings.language)

    from ui.color_picker import set_color_format

    set_color_format(loaded_settings.color_input_format)

    icon = QIcon(":/icons/app_icon.ico")
    if icon.isNull():
        icon_path = resource_path("icons/app_icon.ico")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
    if not icon.isNull():
        app.setWindowIcon(icon)

    style_path = resource_path("style.qss")
    if os.path.exists(style_path):
        with open(style_path, encoding="utf-8") as handle:
            app.setStyleSheet(handle.read())

    window = DiplomaGenerator()
    if not icon.isNull():
        window.setWindowIcon(icon)

    center_window(window)
    # При смене языка приложение перезапускает само себя.  Новый процесс
    # ненадолго задерживает показ окна, чтобы старый успел закрыться и два
    # окна не мелькали одновременно.
    restart_delay = int(os.environ.get("AUTOFILL_RESTART_DELAY_MS", "0") or 0)
    if restart_delay > 0:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(restart_delay, window.show)
    else:
        window.show()

    sys.exit(app.exec())
