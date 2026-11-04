from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from core.screen_utils import get_window_size


class MessageDialog(QDialog):
    """Единый диалог сообщений/подтверждений.

    Результат клика хранится в ``clicked_index``.  Атрибут ``result`` больше не
    перекрывается: ``exec()`` возвращает обычный ``QDialog.Accepted`` или
    ``QDialog.Rejected``, а Esc/крестик всегда означают отмену.
    """

    def __init__(
        self,
        parent=None,
        title: str = "",
        text: str = "",
        buttons: list[tuple[str, str]] | None = None,
        default_btn: int = 0,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        line_count = max(1, text.count("\n") + 1)
        width, _height = get_window_size(self, 0.36, 0.30)
        width = max(460, min(760, width))
        height = min(560, max(220, 150 + line_count * 22))
        self.setMinimumSize(440, 220)
        self.resize(width, height)

        self.clicked_index: int | None = None
        self.buttons: list[QPushButton] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(18)

        self.text_browser = QTextBrowser(self)
        self.text_browser.setObjectName("message_text")
        self.text_browser.setPlainText(text)
        self.text_browser.document().setDocumentMargin(0)
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setReadOnly(True)
        self.text_browser.setFrameShape(QTextBrowser.NoFrame)
        self.text_browser.setMinimumHeight(90)
        layout.addWidget(self.text_browser, 1)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.addStretch()

        button_specs = buttons or [("Закрыть", "primary")]
        default_index = max(0, min(int(default_btn), len(button_specs) - 1))

        for index, (button_text, role) in enumerate(button_specs):
            button = QPushButton(button_text, self)
            if role == "primary":
                button.setObjectName("primary_btn")
            button.setMinimumWidth(110)
            button.setAutoDefault(False)
            button.setDefault(index == default_index)
            button.clicked.connect(lambda _checked=False, idx=index: self.button_clicked(idx))
            button_layout.addWidget(button)
            self.buttons.append(button)

        layout.addLayout(button_layout)

        if self.buttons:
            self.buttons[default_index].setFocus()

    def button_clicked(self, index: int) -> None:
        self.clicked_index = index
        self.accept()
