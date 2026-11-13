"""Тематизация Qt-диалогов и выбор файлов/цвета нативными диалогами Windows.

Нативные диалоги (в стиле проводника) привычнее пользователю и сами следуют
системной теме Windows, поэтому для выбора файлов и цвета они используются
без оформления Qt.  Помощники темизации здесь нужны для остальных диалогов
приложения (MessageDialog, редактор грамоты).
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QLineEdit,
    QWidget,
)

from core.windows_utils import set_title_bar_color, set_title_bar_light_theme


def style_popup(popup: QWidget | None, theme: str) -> None:
    """Красит всплывающий виджет (список комбобокса, попап автодополнения)."""

    if popup is None:
        return
    popup.setProperty("theme", theme)
    popup.style().unpolish(popup)
    popup.style().polish(popup)


def apply_theme_tree(root: QWidget, theme: str) -> None:
    """Вешает свойство ``theme`` на корень и всех его детей.

    Выпадающие списки и попапы автодополнения создаются лениво и не входят в
    ``findChildren`` до первого показа, поэтому их приходится создавать
    принудительно и красить отдельно.
    """

    root.setProperty("theme", theme)
    for widget in root.findChildren(QWidget):
        widget.setProperty("theme", theme)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
    root.style().unpolish(root)
    root.style().polish(root)

    for combo in root.findChildren(QComboBox):
        style_popup(combo.view(), theme)
    for edit in root.findChildren(QLineEdit):
        completer = edit.completer()
        if completer is not None:
            style_popup(completer.popup(), theme)


def apply_title_bar(window: QWidget, theme: str) -> None:
    """Красит заголовок окна и повторяет попытку после появления HWND."""

    is_light = theme != "dark"
    color = "#F5F6FA" if is_light else "#1E1E1E"

    def apply() -> None:
        set_title_bar_color(window, color)
        set_title_bar_light_theme(window, is_light)

    apply()
    QTimer.singleShot(0, window, apply)
    QTimer.singleShot(150, window, apply)


def exec_themed(dialog: QDialog, theme: str) -> int:
    """Применяет тему к диалогу и показывает его модально."""

    apply_theme_tree(dialog, theme)
    apply_title_bar(dialog, theme)
    return dialog.exec()


def get_open_file_name(
    parent: QWidget | None,
    caption: str,
    directory: str,
    name_filter: str,
) -> str:
    """Нативный диалог выбора файла, возвращает путь или ""."""

    path, _selected = QFileDialog.getOpenFileName(parent, caption, directory, name_filter)
    return path


def get_existing_directory(
    parent: QWidget | None,
    caption: str,
    directory: str,
) -> str:
    """Нативный диалог выбора папки, возвращает путь или ""."""

    return QFileDialog.getExistingDirectory(parent, caption, directory)


def get_color(
    parent: QWidget | None,
    caption: str,
    current: tuple[int, int, int],
) -> tuple[int, int, int] | None:
    """Нативный диалог выбора цвета."""

    color = QColorDialog.getColor(QColor(*current), parent, caption)
    if not color.isValid():
        return None
    return color.red(), color.green(), color.blue()
