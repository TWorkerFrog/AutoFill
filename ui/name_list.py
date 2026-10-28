"""Виджет списка ФИО с безопасным поиском.

Источник данных всегда хранится отдельно от отображаемого текста.  Пока поиск
активен, редактор доступен только для чтения — это исключает потерю скрытых
строк при редактировании отфильтрованного списка.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class NameListEditor(QWidget):
    changed = Signal()
    countChanged = Signal(int)

    def __init__(
        self,
        title: str,
        placeholder: str = "",
        parent=None,
        *,
        show_load: bool = False,
        show_clear: bool = True,
        search_placeholder: str = "Поиск по списку...",
    ):
        super().__init__(parent)
        self._source_text = ""
        self._filter_active = False
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.title_label = QLabel(title)
        header.addWidget(self.title_label)
        header.addStretch()
        self.count_label = QLabel("0")
        self.count_label.setObjectName("secondary_label")
        header.addWidget(self.count_label)
        layout.addLayout(header)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(search_placeholder)
        self.search_edit.setClearButtonEnabled(True)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._apply_filter)
        self.search_edit.textChanged.connect(lambda _text: self._search_timer.start())
        layout.addWidget(self.search_edit)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(placeholder)
        self.editor.setTabChangesFocus(True)
        self.editor.textChanged.connect(self._on_editor_changed)
        layout.addWidget(self.editor, 1)

        self.filter_hint = QLabel("")
        self.filter_hint.setObjectName("hint_label")
        self.filter_hint.setWordWrap(True)
        self.filter_hint.setVisible(False)
        layout.addWidget(self.filter_hint)

        buttons = QHBoxLayout()
        self.buttons_layout = buttons
        self.load_button = QPushButton("Загрузить файл")
        self.load_button.setVisible(show_load)
        buttons.addWidget(self.load_button)

        self.clear_button = QPushButton("Очистить")
        self.clear_button.setVisible(show_clear)
        self.clear_button.clicked.connect(self.clear)
        buttons.addWidget(self.clear_button)
        buttons.addStretch()
        layout.addLayout(buttons)

        self._update_count()

    # ------------------------------------------------------------------
    # Источник данных
    # ------------------------------------------------------------------
    def text(self) -> str:
        return self._source_text

    def people(self) -> list[list[str]]:
        return [line.strip().split() for line in self._source_text.splitlines() if line.strip()]

    def count(self) -> int:
        return sum(1 for line in self._source_text.splitlines() if line.strip())

    def set_text(self, text: str, *, emit: bool = True) -> None:
        self._source_text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        self._refresh_display()
        self._update_count()
        if emit:
            self.changed.emit()

    def clear(self) -> None:
        if self._source_text:
            self.set_text("")

    def append(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        current = self._source_text.rstrip()
        self.set_text(f"{current}\n{text}" if current else text)

    def append_lines(self, lines: list[str]) -> None:
        text = "\n".join(line.strip() for line in lines if line.strip())
        if text:
            self.append(text)

    def reload_from_source(self) -> None:
        self._refresh_display()

    # ------------------------------------------------------------------
    # Внутреннее
    # ------------------------------------------------------------------
    def _on_editor_changed(self) -> None:
        if self._loading or self._filter_active:
            return
        self._source_text = self.editor.toPlainText().replace("\r\n", "\n").replace("\r", "\n")
        self._update_count()
        self.changed.emit()

    def _apply_filter(self) -> None:
        query = self.search_edit.text().strip().casefold()
        self._filter_active = bool(query)
        self.editor.setReadOnly(self._filter_active)
        self.clear_button.setEnabled(not self._filter_active)
        self.filter_hint.setVisible(self._filter_active)
        self.filter_hint.setText(
            "Пока активен поиск, список доступен только для чтения. "
            "Очистите поиск, чтобы редактировать."
            if self._filter_active else ""
        )
        self._refresh_display()
        self._update_count()

    def _refresh_display(self) -> None:
        query = self.search_edit.text().strip().casefold()
        if query:
            lines = [
                line for line in self._source_text.splitlines()
                if query in line.casefold()
            ]
            display = "\n".join(lines)
        else:
            display = self._source_text

        self._loading = True
        try:
            self.editor.setPlainText(display)
        finally:
            self._loading = False

    def _update_count(self) -> None:
        total = self.count()
        query = self.search_edit.text().strip()
        if query:
            visible = sum(1 for line in self._source_text.splitlines() if query.casefold() in line.casefold())
            self.count_label.setText(f"{visible} из {total}")
        else:
            self.count_label.setText(str(total))
        self.countChanged.emit(total)
