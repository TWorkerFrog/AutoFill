import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

import resources_rc  # noqa: F401  # регистрирует встроенные Qt-ресурсы
from core.screen_utils import center_window
from core.settings import app_data_dir
from core.version import APP_NAME
from ui.main_window import DiplomaGenerator


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


if __name__ == "__main__":
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("TWorker")
    install_exception_hook()

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
    window.show()

    sys.exit(app.exec())
