"""Мини-локализация интерфейса без Qt-лингвистов.

Русский текст остаётся исходным в коде, а английский берётся из словаря
``core.i18n_en``.  Так проще поддерживать обе версии: при смене языка
приложение сохраняет настройку и перезапускается, а все подписи собираются
заново уже на нужном языке.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTabWidget,
    QWidget,
)

from core.i18n_en import EN

LANGUAGES = {"ru": "Русский", "en": "English"}
DEFAULT_LANGUAGE = "ru"

_current = DEFAULT_LANGUAGE
_translators: list[QTranslator] = []


def set_language(language: str) -> None:
    """Запоминает язык на время работы приложения."""

    global _current
    _current = language if language in LANGUAGES else DEFAULT_LANGUAGE


def language() -> str:
    return _current


def is_english() -> bool:
    return _current == "en"


def tr(text: str) -> str:
    """Переводит строку, если включён английский."""

    if _current == "ru":
        return text
    return EN.get(text, text)


def _translation_dirs() -> list[Path]:
    candidates = [
        Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)),
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "PySide6" / "translations")
    try:
        import PySide6

        candidates.append(Path(PySide6.__file__).parent / "translations")
    except Exception:
        pass
    return candidates


def install_qt_translations(app: QApplication, language_code: str) -> None:
    """Подключает штатные переводы Qt для диалогов цвета и файлов."""

    global _translators
    for translator in _translators:
        app.removeTranslator(translator)
    _translators = []
    names = (
        ("qtbase_ru", "qt_ru")
        if language_code == "ru"
        else ("qtbase_en", "qt_en")
    )
    for name in names:
        for directory in _translation_dirs():
            path = directory / f"{name}.qm"
            if not path.is_file():
                continue
            translator = QTranslator(app)
            if translator.load(str(path)):
                app.installTranslator(translator)
                _translators.append(translator)
            break


def translate_widget_tree(root: QWidget) -> None:
    """Переводит подписи уже собранного окна или диалога."""

    if not is_english():
        return

    def apply(widget: QWidget) -> None:
        title = widget.windowTitle()
        if title:
            widget.setWindowTitle(tr(title))
        tooltip = widget.toolTip()
        if tooltip:
            widget.setToolTip(tr(tooltip))
        status = widget.statusTip()
        if status:
            widget.setStatusTip(tr(status))
        whats = widget.whatsThis()
        if whats:
            widget.setWhatsThis(tr(whats))
        if isinstance(widget, QLabel):
            widget.setText(tr(widget.text()))
        if isinstance(widget, QAbstractButton):
            widget.setText(tr(widget.text()))
        if isinstance(widget, QGroupBox):
            widget.setTitle(tr(widget.title()))
        if isinstance(widget, QLineEdit):
            placeholder = widget.placeholderText()
            if placeholder:
                widget.setPlaceholderText(tr(placeholder))
        if isinstance(widget, QPlainTextEdit):
            placeholder = widget.placeholderText()
            if placeholder:
                widget.setPlaceholderText(tr(placeholder))
        if isinstance(widget, QComboBox):
            # Названия шрифтов и начертаний не переводим.  Переводим только
            # элементы, которые точно являются подписями интерфейса.
            for index in range(widget.count()):
                text = widget.itemText(index)
                translated = EN.get(text)
                if translated and widget.itemData(index) is None:
                    widget.setItemText(index, translated)
        if isinstance(widget, QTabWidget):
            for index in range(widget.count()):
                widget.setTabText(index, tr(widget.tabText(index)))

    apply(root)
    for widget in root.findChildren(QWidget):
        apply(widget)
    for action in root.findChildren(QAction):
        if action.text():
            action.setText(tr(action.text()))
        if action.toolTip():
            action.setToolTip(tr(action.toolTip()))
        if action.statusTip():
            action.setStatusTip(tr(action.statusTip()))
