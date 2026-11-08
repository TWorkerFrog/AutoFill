"""Тематизация диалогов и «немодные» диалоги выбора файла/цвета.

QFileDialog и QColorDialog создаются после применения темы к основному окну,
поэтому без отдельной обработки они остаются в тёмных цветах даже в светлой
теме.  Здесь собраны помощники, которые навешивают свойство ``theme`` на всё
дерево диалога и открывают диалог уже оформленным.
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


def _first_selected(dialog: QFileDialog, theme: str) -> str:
    if exec_themed(dialog, theme) != int(QDialog.Accepted):
        return ""
    files = dialog.selectedFiles()
    return files[0] if files else ""


def get_open_file_name(
    parent: QWidget | None,
    theme: str,
    caption: str,
    directory: str,
    name_filter: str,
) -> str:
    """Открывает оформленный диалог выбора файла, возвращает путь или ""."""

    dialog = QFileDialog(parent, caption, directory, name_filter)
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    dialog.setFileMode(QFileDialog.ExistingFile)
    return _first_selected(dialog, theme)


def get_existing_directory(
    parent: QWidget | None,
    theme: str,
    caption: str,
    directory: str,
) -> str:
    """Открывает оформленный диалог выбора папки, возвращает путь или ""."""

    dialog = QFileDialog(parent, caption, directory)
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    dialog.setFileMode(QFileDialog.Directory)
    dialog.setOption(QFileDialog.ShowDirsOnly, True)
    return _first_selected(dialog, theme)


def get_color(
    parent: QWidget | None,
    theme: str,
    caption: str,
    current: tuple[int, int, int],
) -> tuple[int, int, int] | None:
    """Открывает оформленный диалог выбора цвета."""

    dialog = QColorDialog(QColor(*current), parent)
    dialog.setWindowTitle(caption)
    dialog.setOption(QColorDialog.DontUseNativeDialog, True)
    if exec_themed(dialog, theme) != int(QDialog.Accepted):
        return None
    color = dialog.selectedColor()
    if not color.isValid():
        return None
    return color.red(), color.green(), color.blue()
