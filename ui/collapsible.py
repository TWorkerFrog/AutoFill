"""Сворачиваемая секция для второстепенных блоков интерфейса."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QToolButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    """Заголовок-кнопка и скрываемое содержимое."""

    toggled = Signal(bool)

    def __init__(self, title: str, content: QWidget, parent=None):
        super().__init__(parent)
        self._content = content
        self._title = title

        self.toggle_button = QToolButton()
        self.toggle_button.setObjectName("section_toggle")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setAutoRaise(True)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.DownArrow)
        self.toggle_button.setText(title)
        self.toggle_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.toggle_button.clicked.connect(self._on_toggled)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.toggle_button)
        layout.addWidget(content, 1)

    def _on_toggled(self, expanded: bool) -> None:
        self._content.setVisible(expanded)
        self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggled.emit(expanded)

    def set_title(self, title: str) -> None:
        self._title = title
        self.toggle_button.setText(title)

    def set_expanded(self, expanded: bool) -> None:
        if self.toggle_button.isChecked() == expanded:
            self._on_toggled(expanded)
            return
        self.toggle_button.setChecked(expanded)
        self._on_toggled(expanded)

    def is_expanded(self) -> bool:
        return self.toggle_button.isChecked()
