from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QPushButton, QSpinBox, QListWidgetItem, QComboBox
)
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtCore import Qt
from core.screen_utils import get_window_size

class FontPickerDialog(QDialog):
    def __init__(self, parent=None, current_family="", current_size=48, current_style="Regular"):
        super().__init__(parent)
        self.setWindowTitle("Выбор шрифта")
        w, h = get_window_size(self, 0.35, 0.55)
        self.resize(w, h)

        self.selected_family = current_family
        self.selected_size = current_size
        self.selected_style = current_style

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Поиск
        layout.addWidget(QLabel("Поиск шрифта:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Введите название шрифта...")
        self.search_edit.textChanged.connect(self.filter_fonts)
        layout.addWidget(self.search_edit)

        # Список шрифтов
        self.font_list = QListWidget()
        layout.addWidget(self.font_list)

        # Получаем шрифты
        db = QFontDatabase()
        all_fonts = db.families()

        # Фильтруем: убираем стили, оставляем только семейства
        self.base_families = []
        for font in all_fonts:
            if " " in font:
                first_word = font.split(" ")[0]
                if first_word in all_fonts:
                    first_styles = db.styles(first_word)
                    if len(first_styles) > 1:
                        continue  # это стиль
            self.base_families.append(font)

        # Сразу заполняем список
        self.update_font_list(self.base_families)

        # Начертание
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("Начертание:"))
        self.style_combo = QComboBox()
        style_layout.addWidget(self.style_combo)
        style_layout.addStretch()
        layout.addLayout(style_layout)

        self.font_list.currentItemChanged.connect(self.update_styles)

        # Размер
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Размер:"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 500)
        self.size_spin.setValue(current_size)
        size_layout.addWidget(self.size_spin)
        size_layout.addStretch()
        layout.addLayout(size_layout)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Выбрать")
        btn_ok.setObjectName("primary_btn")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        # Выделяем текущий шрифт, если он есть
        if current_family:
            for i in range(self.font_list.count()):
                if self.font_list.item(i).text() == current_family:
                    self.font_list.setCurrentRow(i)
                    self.font_list.scrollToItem(self.font_list.item(i))
                    break

        # Обновляем стили для выбранного шрифта
        self.update_styles()

    def filter_fonts(self):
        search_text = self.search_edit.text().strip().lower()
        if not search_text:
            self.update_font_list(self.base_families)
            return

        filtered = [f for f in self.base_families if search_text in f.lower()]
        self.update_font_list(filtered)

    def update_font_list(self, fonts):
        self.font_list.clear()
        for font in fonts:
            item = QListWidgetItem(font)
            item.setFont(QFont(font, 12))
            self.font_list.addItem(item)

    def update_styles(self):
        current_item = self.font_list.currentItem()
        if not current_item:
            return

        family = current_item.text()
        db = QFontDatabase()
        styles = db.styles(family)

        self.style_combo.clear()
        self.style_combo.addItems(styles)

        # Выделяем текущий стиль, если есть
        if self.selected_style in styles:
            self.style_combo.setCurrentText(self.selected_style)

    def get_selected_font(self):
        current_item = self.font_list.currentItem()
        if current_item:
            self.selected_family = current_item.text()
        self.selected_size = self.size_spin.value()
        self.selected_style = self.style_combo.currentText()
        return self.selected_family, self.selected_size, self.selected_style