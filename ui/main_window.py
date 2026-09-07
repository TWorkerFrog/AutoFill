import os
import json

from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QCheckBox, QRadioButton,
    QButtonGroup, QFileDialog, QColorDialog, QMessageBox,
    QTabWidget, QSpinBox, QDialog, QSplitter, QCompleter, QComboBox
)
from PySide6.QtGui import QDesktopServices, QFontDatabase, QIntValidator
from PySide6.QtWidgets import QFrame
from PIL import Image, ImageDraw

from core.text_render import draw_text_block, check_text_bounds
from core.name_format import format_name_lines, resolve_auto_lines, plural
from core.name_format import plural_instrumental
from core.screen_utils import get_window_size
from core.font_utils import scan_fonts
from core.windows_utils import set_title_bar_color, set_title_bar_light_theme, is_windows_theme

from ui.point_picker import PointPickerDialog
from ui.preview import PreviewDialog
from ui.font_picker import FontPickerDialog
from ui.message_dialog import MessageDialog




class DiplomaGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Генератор грамот")
        w, h = get_window_size(self, 0.55, 0.75)
        self.resize(w, h)


        self.template_path = ""
        self.font_path = ""
        self.text_color = (0, 0, 0)
        self.selected_font_family = ""
        self.current_theme = "dark"
        self.all_names = ""
        self.all_excluded = ""
        self.filter_state = {
            "all_names": {"is_filtering": False, "indices": []},
            "all_excluded": {"is_filtering": False, "indices": []},
        }
        self.selected_font_style = "Regular"
        self.fonts_data = scan_fonts()
        self.all_names_list = []  # Полный список строк
        self.filtered_indices = []  # Индексы отфильтрованных
        self.is_filtering = False

        self.create_ui()

        appdata = os.path.join(os.path.expanduser("~"), "AppData", "Local", "AutoFill")
        os.makedirs(appdata, exist_ok=True)
        self.settings_file = os.path.join(appdata, "settings.json")
        self.load_settings()

        if "theme" not in self.loaded_settings:
            if is_windows_theme():
                self.rb_dark.setChecked(True)
            else:
                self.rb_light.setChecked(True)

    def create_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_main = QWidget()
        self.tab_position = QWidget()
        self.tab_format = QWidget()
        self.tab_output = QWidget()
        self.tab_settings = QWidget()

        self.tabs.addTab(self.tab_main, "Основные")
        self.tabs.addTab(self.tab_position, "Позиция")
        self.tabs.addTab(self.tab_format, "Формат имени")
        self.tabs.addTab(self.tab_output, "Вывод")
        self.tabs.addTab(self.tab_settings, "Настройки")

        self.build_tab_main()
        self.build_tab_position()
        self.build_tab_format()
        self.build_tab_output()
        self.build_tab_settings()

        # Кнопка генерации
        self.generate_btn = QPushButton("Сгенерировать грамоты")
        self.generate_btn.setObjectName("primary_btn")
        self.generate_btn.clicked.connect(self.generate_all)
        main_layout.addWidget(self.generate_btn)

        # Нижняя панель: статус + кнопка открытия папки
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("Готов к работе")
        bottom_layout.addWidget(self.status_label)

        bottom_layout.addStretch()

        self.open_dir_btn = QPushButton("Открыть папку")
        self.open_dir_btn.setVisible(False)
        self.open_dir_btn.clicked.connect(self.open_output_dir)
        bottom_layout.addWidget(self.open_dir_btn)


        main_layout.addLayout(bottom_layout)

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                self.loaded_settings = settings
                self.apply_settings(settings)
            except:
                self.loaded_settings = {}
        else:
            self.loaded_settings = {}

    def apply_settings(self, settings):
        if "font_size" in settings:
            self.font_size_spin.setValue(settings["font_size"])
        if "template_path" in settings:
            self.template_path = settings["template_path"]
            self.template_edit.setText(settings["template_path"])
        if "font_path" in settings:
            self.font_path = settings["font_path"]
            self.font_edit.setText(settings["font_path"])
        if "selected_font_family" in settings:
            self.selected_font_family = settings["selected_font_family"]
            if self.selected_font_family:
                self.font_edit.setText(self.selected_font_family)
        if "selected_font_style" in settings:
            self.selected_font_style = settings["selected_font_style"]
        if "output_dir" in settings:
            self.output_dir_edit.setText(settings["output_dir"])
        if "output_format" in settings:
            if settings["output_format"] == "png":
                self.rb_png.setChecked(True)
            else:
                self.rb_pdf.setChecked(True)
        if "pdf_mode" in settings:
            if settings["pdf_mode"] == "single":
                self.rb_single.setChecked(True)
            else:
                self.rb_multi.setChecked(True)
        if "pdf_name" in settings:
            self.pdf_name_edit.setText(settings["pdf_name"])
        if "theme" in settings:
            if settings["theme"] == "light":
                self.rb_light.setChecked(True)
            else:
                self.rb_dark.setChecked(True)

    def save_settings(self):
        """Сохраняет текущие настройки."""
        settings = {
            "font_size": self.font_size_spin.value(),
            "template_path": self.template_path,
            "font_path": self.font_path,
            "selected_font_family": self.selected_font_family,
            "selected_font_style": self.selected_font_style,
            "output_dir": self.output_dir_edit.text(),
            "output_format": self.get_output_format(),
            "pdf_mode": self.get_pdf_mode(),
            "pdf_name": self.pdf_name_edit.text(),
            "theme": self.current_theme
        }
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)

    def closeEvent(self, event):
        """Вызывается при закрытии окна."""
        dialog = MessageDialog(
            self,
            "Выход",
            "Сохранить настройки перед выходом?",
            buttons=[("Сохранить", "primary"), ("Не сохранять", ""), ("Отмена", "")]
        )
        self.apply_theme_to_dialog(dialog, self.current_theme)
        dialog.exec()

        if dialog.result == 0:  # Сохранить
            self.save_settings()
            event.accept()
        elif dialog.result == 1:  # Не сохранять
            event.accept()
        else:  # Отмена
            event.ignore()
    # ============================================================
    # ОТКРЫТИЕ ПАПКИ
    # ============================================================

    def open_output_dir(self):
        output_dir = self.output_dir_edit.text() or "Грамоты"
        full_path = os.path.abspath(output_dir)
        if not os.path.exists(full_path):
            os.makedirs(full_path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(full_path))

    # ============================================================
    # ВКЛАДКА: ОСНОВНЫЕ
    # ============================================================

    def build_tab_main(self):
        layout = QVBoxLayout(self.tab_main)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Шаблон грамоты:"))
        self.template_edit = QLineEdit()
        self.template_edit.setPlaceholderText("Путь до файла с грамотой...")
        self.template_edit.setMinimumWidth(250)
        self.template_edit.textChanged.connect(self.on_template_changed)
        row1.addWidget(self.template_edit, stretch=1)
        btn_template = QPushButton("Выбрать")
        btn_template.clicked.connect(self.choose_template)
        row1.addWidget(btn_template)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Шрифт:"))
        self.font_edit = QLineEdit()
        self.font_edit.setPlaceholderText("Введите название шрифта...")
        self.font_edit.setMinimumWidth(250)  # ← минимальная ширина
        row2.addWidget(self.font_edit, stretch=1)  # ← растягивается
        self.style_combo = QComboBox()
        self.style_combo.setFixedWidth(150)
        row2.addWidget(self.style_combo)
        self.style_combo.currentTextChanged.connect(self.on_style_changed)
        self.font_edit.textChanged.connect(self.on_font_changed)
        self.font_edit.returnPressed.connect(self.normalize_font_input)
        self.font_edit.editingFinished.connect(self.normalize_font_input)
        self.style_combo.currentTextChanged.connect(self.on_style_changed)
        # Файл
        btn_font_file = QPushButton("Файл")
        btn_font_file.clicked.connect(self.choose_font_file)
        row2.addWidget(btn_font_file)
        layout.addLayout(row2)

        self.font_db = QFontDatabase()
        # Используем только реальные семейства из метаданных
        self.all_fonts = sorted(self.fonts_data.keys())

        self.completer = QCompleter(self.all_fonts)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)  # ← поиск по подстроке
        self.font_edit.setCompleter(self.completer)
        self.apply_theme_to_completer(self.completer)
        # При выборе шрифта обновляем начертания
        self.font_edit.textChanged.connect(self.on_font_changed)

        row3 = QHBoxLayout()

        # Блок: Размер шрифта
        size_widget = QWidget()
        size_layout = QHBoxLayout(size_widget)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.addWidget(QLabel("Размер шрифта (px):"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(0, 1000)
        self.font_size_spin.setValue(0)
        size_layout.addWidget(self.font_size_spin)
        row3.addWidget(size_widget)

        # Отступ между блоками
        row3.addStretch()

        # Блок: Цвет
        color_widget = QWidget()
        color_layout = QHBoxLayout(color_widget)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(QLabel("Цвет текста:"))
        #self.color_btn = QPushButton("Выбрать")
        #self.color_btn.clicked.connect(self.choose_color)
        #color_layout.addWidget(self.color_btn)
        row3.addWidget(color_widget)
        self.color_preview = QPushButton()
        self.color_preview.clicked.connect(self.choose_color)
        self.color_preview.setFixedSize(30, 30)
        self.color_preview.setStyleSheet("background-color: #000000; border-radius: 4px;")
        row3.addWidget(self.color_preview)

        # Отступ
        row3.addStretch()

        # Блок: Межбуквенный
        spacing_widget = QWidget()
        spacing_layout = QHBoxLayout(spacing_widget)
        spacing_layout.setContentsMargins(0, 0, 0, 0)
        spacing_layout.addWidget(QLabel("Межбуквенный интервал (px):"))
        self.letter_spacing_spin = QSpinBox()
        self.letter_spacing_spin.setRange(0, 50)
        self.letter_spacing_spin.setValue(0)
        spacing_layout.addWidget(self.letter_spacing_spin)
        row3.addWidget(spacing_widget)

        layout.addLayout(row3)

        # Подпись + поле + кнопки для основного списка
        self.names_widget = QWidget()
        names_layout = QVBoxLayout(self.names_widget)
        names_layout.addWidget(QLabel("Список ФИО (каждая строка – один человек):"))

        # Поиск
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по списку...")
        self.search_edit.textChanged.connect(
            lambda: self.filter_list(self.search_edit, self.names_text, "all_names")
        )
        names_layout.addWidget(self.search_edit)

        self.names_text = QTextEdit()
        self.names_text.setPlaceholderText("Иванов Иван Иванович\nПетров Пётр Петрович\n...")
        self.names_text.textChanged.connect(self.on_text_edited)
        names_layout.addWidget(self.names_text)



        # Кнопки
        btn_row1 = QHBoxLayout()
        btn_load = QPushButton("Загрузить файл")
        btn_load.clicked.connect(self.load_names_file)
        btn_row1.addWidget(btn_load)
        btn_clear = QPushButton("Очистить")
        btn_clear.clicked.connect(lambda: self.names_text.clear())
        btn_row1.addWidget(btn_clear)
        names_layout.addLayout(btn_row1)

        # Подпись + поле + кнопки для исключений
        self.excluded_widget = QWidget()
        excluded_layout = QVBoxLayout(self.excluded_widget)
        excluded_layout.addWidget(QLabel("Исключения (сюда попадают ФИО, которые не влезли в границы грамоты):"))

        self.excluded_search_edit = QLineEdit()
        self.excluded_search_edit.setPlaceholderText("Поиск по исключениям...")
        self.excluded_search_edit.textChanged.connect(
            lambda: self.filter_list(self.excluded_search_edit, self.excluded_text, "all_excluded")
        )
        excluded_layout.addWidget(self.excluded_search_edit)

        self.excluded_text = QTextEdit()
        self.excluded_text.setPlaceholderText("Иванов Иван Иванович")
        self.excluded_text.textChanged.connect(self.on_text_edited)
        excluded_layout.addWidget(self.excluded_text)
        # Кнопки
        btn_row2 = QHBoxLayout()
        btn_clear_excl = QPushButton("Очистить исключения")
        btn_clear_excl.clicked.connect(lambda: self.excluded_text.clear())
        btn_row2.addWidget(btn_clear_excl)
        btn_move = QPushButton("Перенести в основной")
        btn_move.clicked.connect(self.move_excluded_to_main)
        btn_row2.addWidget(btn_move)
        excluded_layout.addLayout(btn_row2)

        self.ask_before_move = QCheckBox("Спрашивать перед переносом исключений")
        self.ask_before_move.setChecked(True)
        excluded_layout.addWidget(self.ask_before_move)

        # Сплиттер
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.names_widget)
        splitter.addWidget(self.excluded_widget)
        splitter.setSizes([350, 200])
        layout.addWidget(splitter)

    def choose_template(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбери шаблон", "", "Изображения (*.jpg *.jpeg *.png)")
        if path:
            self.template_path = path
            self.template_edit.setText(path)

    def choose_font_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбери файл шрифта", "", "Шрифты (*.ttf *.otf)")
        if path:
            self.font_path = path
            self.font_edit.setText(path)
            self.selected_font_family = ""

    def choose_system_font(self):
        dialog = FontPickerDialog(
            self,
            self.selected_font_family,
            self.font_size_spin.value(),
            self.selected_font_style
        )
        self.apply_theme_to_dialog(dialog, self.current_theme)

        if dialog.exec() == QDialog.Accepted:
            family, size, style = dialog.get_selected_font()
            if family:
                self.selected_font_family = family
                self.selected_font_style = style
                self.font_path = ""
                self.font_edit.setText(f"[Системный] {family} {style}")
                self.font_size_spin.setValue(size)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.text_color = (color.red(), color.green(), color.blue())
            self.color_preview.setStyleSheet(f"background-color: {color.name()}; border-radius: 4px;")

    def load_names_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбери файл со списком", "", "Текст (*.txt)")
        if not path:
            return

        with open(path, encoding="utf-8") as f:
            new_content = f.read()

        current = self.names_text.toPlainText().strip()

        if current:
            dialog = MessageDialog(
                self,
                "Загрузка списка",
                "Текущий список не пуст. Что сделать?",
                buttons=[
                    ("Заменить", "primary"),
                    ("Добавить в конец", ""),
                    ("Отмена", "")
                ]
            )
            self.apply_theme_to_dialog(dialog, self.current_theme)
            dialog.exec()

            if dialog.result == 0:  # Заменить
                self.all_names = new_content
                self.names_text.setPlainText(new_content)
            elif dialog.result == 1:  # Добавить
                self.all_names = current + "\n" + new_content
                self.names_text.setPlainText(self.all_names)
            # Отмена – ничего не делаем
        else:
            self.all_names = new_content
            self.names_text.setPlainText(new_content)

        self.search_edit.clear()

    def get_names_list(self):
        text = self.all_names if self.all_names else self.names_text.toPlainText()
        return [line.strip().split() for line in text.split("\n") if line.strip()]

    def move_excluded_to_main(self):
        excluded = self.excluded_text.toPlainText().strip()
        if not excluded:
            return

        excluded_people = [line.strip().split() for line in excluded.split("\n") if line.strip()]
        current_people = self.get_names_list()

        if self.ask_before_move.isChecked():
            # Спрашиваем
            dialog = MessageDialog(
                self,
                "Перенос исключений",
                "Очистить основной список перед переносом?",
                buttons=[("Да", "primary"), ("Нет", ""), ("Отмена", "")]
            )
            self.apply_theme_to_dialog(dialog, self.current_theme)
            dialog.exec()

            if dialog.result == 2:  # Отмена
                return
            elif dialog.result == 0:  # Да
                # Очищаем и вставляем все исключения
                self.names_text.setPlainText("\n".join(" ".join(p) for p in excluded_people))
                self.excluded_text.clear()
                return
            # Если Нет – проверяем, кого нет в основном списке
            missing = [
                p for p in excluded_people
                if not self.is_person_in_list(p, current_people)
            ]

            if missing:
                # Добавляем отсутствующих в конец
                current_text = self.names_text.toPlainText().strip()
                if current_text:
                    self.names_text.setPlainText(
                        current_text + "\n" + "\n".join(" ".join(p) for p in missing)
                    )
                else:
                    self.names_text.setPlainText("\n".join(" ".join(p) for p in missing))
        else:
            # Не спрашиваем – просто очищаем и вставляем
            self.names_text.setPlainText("\n".join(" ".join(p) for p in excluded_people))

        self.excluded_text.clear()

    def update_all_names(self):
        """Сохраняет полный список при изменении текста."""
        if not self.search_edit.text().strip():
            self.all_names = self.names_text.toPlainText()

    def filter_list(self, search_edit, text_edit, all_data_attr):
        search_text = search_edit.text().strip().lower()
        all_data = getattr(self, all_data_attr, "")

        if not search_text:
            # Очистка фильтра
            self.is_filtering = False
            self.filtered_indices = []
            text_edit.blockSignals(True)
            text_edit.setPlainText(all_data)
            text_edit.blockSignals(False)
            return

        if not all_data:
            all_data = text_edit.toPlainText()
            setattr(self, all_data_attr, all_data)

        self.is_filtering = True
        all_lines = all_data.split("\n")

        self.filtered_indices = [
            i for i, line in enumerate(all_lines)
            if search_text in line.lower()
        ]

        filtered = [all_lines[i] for i in self.filtered_indices]

        text_edit.blockSignals(True)
        text_edit.setPlainText("\n".join(filtered))
        text_edit.blockSignals(False)

    def on_text_edited(self):
        """Обработчик изменения текста пользователем."""
        if self.names_text.signalsBlocked():
            return

        current_lines = self.names_text.toPlainText().split("\n")

        if self.is_filtering:
            # Режим фильтрации
            all_lines = self.all_names.split("\n")

            if len(current_lines) == len(self.filtered_indices):
                # Только редактирование
                for idx, new_line in zip(self.filtered_indices, current_lines):
                    all_lines[idx] = new_line
            else:
                # Добавление или удаление
                old_filtered = [all_lines[i] for i in self.filtered_indices]

                if len(current_lines) > len(self.filtered_indices):
                    # Добавлены строки
                    added = [l for l in current_lines if l not in old_filtered]
                    all_lines.extend(added)
                elif len(current_lines) < len(self.filtered_indices):
                    # Удалены строки
                    removed = [l for l in old_filtered if l not in current_lines]
                    indices_to_remove = []
                    for i, line in enumerate(all_lines):
                        if line in removed:
                            indices_to_remove.append(i)

                    indices_to_remove.sort(reverse=True)
                    for idx in indices_to_remove:
                        del all_lines[idx]

                # Обновляем содержимое
                for idx, new_line in zip(self.filtered_indices, current_lines):
                    if idx < len(all_lines):
                        all_lines[idx] = new_line

            self.all_names = "\n".join(all_lines)
        else:
            # Без фильтра
            self.all_names = "\n".join(current_lines)

    def update_filtered_buffer(self, text_edit):
        """Обновляет буфер при редактировании."""
        if not self.filtered_indices:
            return

        current_lines = text_edit.toPlainText().split("\n")

        for i, idx in enumerate(self.filtered_indices):
            if i < len(current_lines):
                self.filtered_buffer[i] = (idx, current_lines[i])

    def on_search_text_changed(self, text, search_edit, text_edit, all_data_attr):
        print(f"=== on_search_text_changed ===")
        print(f"text: '{text}'")

        if not text.strip():
            # Поиск очищен
            all_data = getattr(self, all_data_attr, "")
            current_text = text_edit.toPlainText()

            # Если current_text – это отфильтрованный список (одна строка),
            # а all_data – полный, то надо слить
            if all_data and current_text:
                all_lines = all_data.split("\n")
                current_lines = current_text.split("\n")
                current_stripped = [line.strip() for line in current_lines if line.strip()]

                updated = []
                current_idx = 0

                for line in all_lines:
                    stripped = line.strip()

                    # Проверяем: была ли эта строка видима в фильтре?
                    if current_idx < len(current_stripped) and stripped == current_stripped[current_idx]:
                        # Строка видима – берём из current (возможно изменена)
                        updated.append(current_lines[current_idx])
                        current_idx += 1
                    else:
                        # Не видима – оставляем как есть
                        updated.append(line)

                # Добавляем оставшиеся новые строки
                while current_idx < len(current_lines):
                    if current_lines[current_idx].strip():
                        updated.append(current_lines[current_idx].strip())
                    current_idx += 1

                final = "\n".join(updated)
                setattr(self, all_data_attr, final)
                text_edit.blockSignals(True)
                text_edit.setPlainText(final)
                text_edit.blockSignals(False)
            else:
                setattr(self, all_data_attr, current_text)
        else:
            self.filter_list(search_edit, text_edit, all_data_attr)

    def save_on_search_finish(self, search_edit, text_edit, all_data_attr):
        search_text = search_edit.text().strip()
        all_data = getattr(self, all_data_attr, "")

        if not search_text and all_data:
            # Сохраняем изменения
            all_lines = all_data.split("\n")
            current_lines = text_edit.toPlainText().split("\n")

            # Заменяем строки, которые были в фильтре
            result = []
            for line in all_lines:
                if search_text.lower() in line.lower():
                    # Эта строка была видима – берём из current
                    if current_lines:
                        result.append(current_lines.pop(0).strip())
                else:
                    result.append(line)

            # Добавляем оставшиеся
            result.extend([l.strip() for l in current_lines if l.strip()])

            final = "\n".join(result)
            setattr(self, all_data_attr, final)
            text_edit.blockSignals(True)
            text_edit.setPlainText(final)
            text_edit.blockSignals(False)

    def apply_theme_to_dialog(self, dialog, theme):
        """Применяет тему к диалогу и всем его дочерним виджетам."""
        dialog.setProperty("theme", theme)
        for widget in dialog.findChildren(QWidget):
            widget.setProperty("theme", theme)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        dialog.style().unpolish(dialog)
        dialog.style().polish(dialog)

        if theme == "dark":
            set_title_bar_color(dialog, "#222222")
            set_title_bar_light_theme(dialog, False)
        else:
            set_title_bar_color(dialog, "#F2F2F2")
            set_title_bar_light_theme(dialog, True)

    def is_person_in_list(self, person_parts, people_list):
        """Проверяет, есть ли человек в списке."""
        person_key = "_".join(person_parts)

        for existing_parts in people_list:
            existing_key = "_".join(existing_parts)
            if person_key == existing_key:
                return True

        return False

    def update_styles_for_font(self):
        family = self.font_edit.text().strip()
        styles = self.font_db.styles(family)

        self.style_combo.clear()
        self.style_combo.addItems(styles)

        if self.selected_font_style in styles:
            self.style_combo.setCurrentText(self.selected_font_style)

    def apply_selected_font(self):
        family = self.font_edit.text().strip()
        style = self.style_combo.currentText()

        if family:
            self.selected_font_family = family
            self.selected_font_style = style
            self.font_path = ""

    def on_style_changed(self):
        self.selected_font_style = self.style_combo.currentText()
        print(f"Выбран стиль: {self.selected_font_style}")  # ← для отладки

    def apply_theme_to_completer(self, completer):
        """Применяет текущую тему к выпадающему списку."""
        popup = completer.popup()
        if popup:
            popup.setProperty("theme", self.current_theme)
            popup.style().unpolish(popup)
            popup.style().polish(popup)

    def on_template_changed(self):
        self.template_path = self.template_edit.text().strip()

    # ============================================================
    # ВКЛАДКА: ПОЗИЦИЯ
    # ============================================================

    def build_tab_position(self):
        layout = QVBoxLayout(self.tab_position)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Выравнивание строк:"))
        self.align_group = QButtonGroup(self)
        self.rb_left = QRadioButton("По левому краю")
        self.rb_center = QRadioButton("По центру")
        self.rb_left.setChecked(True)
        self.align_group.addButton(self.rb_left)
        self.align_group.addButton(self.rb_center)
        row1.addWidget(self.rb_left)
        row1.addWidget(self.rb_center)
        layout.addLayout(row1)


        row2 = QHBoxLayout()
        x_edit = QWidget()
        x_edit_layout = QHBoxLayout(x_edit)
        x_edit_layout.setContentsMargins(0, 0, 0, 0)
        x_edit_layout.addWidget(QLabel("X (px):"))
        self.x_edit = QSpinBox()
        self.x_edit.setRange(0, 100000)
        self.x_edit.setSpecialValueText("0")

        row2.addWidget(x_edit)
        x_edit_layout.addWidget(self.x_edit)
        self.x_auto_check = QCheckBox("Автоцентр по X")
        row2.addWidget(self.x_auto_check)
        row2.addStretch()
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        y_edit = QWidget()
        y_edit_layout = QHBoxLayout(y_edit)
        y_edit_layout.setContentsMargins(0, 0, 0, 0)
        y_edit_layout.addWidget(QLabel("Y (px):"))
        self.y_edit = QSpinBox()
        self.y_edit.setRange(0, 100000)
        self.y_edit.setSpecialValueText("0")

        row3.addWidget(y_edit)
        y_edit_layout.addWidget(self.y_edit)
        self.y_auto_check = QCheckBox("Автоцентр по Y")
        row3.addWidget(self.y_auto_check)
        row3.addStretch()
        layout.addLayout(row3)

        # Блок: Сдвиг X
        row4 = QHBoxLayout()

        shift_x_widget = QWidget()
        shift_x_layout = QHBoxLayout(shift_x_widget)
        shift_x_layout.setContentsMargins(0, 0, 0, 0)
        shift_x_layout.addWidget(QLabel("Сдвиг X (px):"))
        self.x_offset_spin = QSpinBox()
        self.x_offset_spin.setRange(-1000, 1000)
        shift_x_layout.addWidget(self.x_offset_spin)
        row4.addWidget(shift_x_widget)

        row4.addStretch()
        layout.addLayout(row4)

        # Блок: Сдвиг Y
        row5 = QHBoxLayout()
        shift_y_widget = QWidget()
        shift_y_layout = QHBoxLayout(shift_y_widget)
        shift_y_layout.setContentsMargins(0, 0, 0, 0)
        shift_y_layout.addWidget(QLabel("Сдвиг Y (px):"))
        self.y_offset_spin = QSpinBox()
        self.y_offset_spin.setRange(-1000, 1000)
        shift_y_layout.addWidget(self.y_offset_spin)
        row5.addWidget(shift_y_widget)
        row5.addStretch()
        layout.addLayout(row5)

        row6 = QHBoxLayout()

        # Блок: Межстрочный интервал
        spacing_widget = QWidget()
        spacing_layout = QHBoxLayout(spacing_widget)
        spacing_layout.setContentsMargins(0, 0, 0, 0)
        spacing_layout.addWidget(QLabel("Межстрочный интервал (px):"))
        self.line_spacing_spin = QSpinBox()
        self.line_spacing_spin.setRange(0, 100)
        self.line_spacing_spin.setValue(4)
        spacing_layout.addWidget(self.line_spacing_spin)
        row6.addWidget(spacing_widget)

        row6.addStretch()
        layout.addLayout(row6)

        btn_pick = QPushButton("Указать точку на грамоте")
        btn_pick.clicked.connect(self.pick_position)
        layout.addWidget(btn_pick)

        layout.addStretch()

    def pick_position(self):
        if not self.template_path:
            dialog = MessageDialog(self, "Ошибка", "Сначала выбери шаблон грамоты.", buttons=[("ОК", "primary")])
            self.apply_theme_to_dialog(dialog, self.current_theme)
            dialog.exec()
            return

        try:
            current_x = self.x_edit.value() if self.x_edit.value() > 0 and not self.x_auto_check.isChecked() else None
            current_y = self.y_edit.value() if self.y_edit.value() > 0 and not self.y_auto_check.isChecked() else None
        except ValueError:
            current_x = None
            current_y = None

        align = "left" if self.rb_left.isChecked() else "center"
        print(f"x_edit.value() = {self.x_edit.value()}")
        print(f"current_x = {current_x}")
        print(f"current_y = {current_y}")
        dialog = PointPickerDialog(self.template_path, self, current_x, current_y, align)
        self.apply_theme_to_dialog(dialog, self.current_theme)
        if dialog.exec() == QDialog.Accepted:
            x, y = dialog.get_point()
            if not self.x_auto_check.isChecked():
                self.x_edit.setValue(x)  # ← setValue для QSpinBox
            if not self.y_auto_check.isChecked():
                self.y_edit.setValue(y)  # ← setValue для QSpinBox

    def on_font_changed(self):
        """Вызывается при каждом изменении текста в поле шрифта."""
        text = self.font_edit.text().strip()

        if not text:
            return

        # Точное совпадение
        if text in self.fonts_data:
            self.apply_font_family(text)
            return

        # Путь к файлу
        if os.path.exists(text) and text.lower().endswith((".ttf", ".otf")):
            self.font_path = text
            self.selected_font_family = ""
            self.style_combo.setVisible(False)
            return

    def apply_font_family(self, family):
        """Применяет выбранное семейство шрифта."""
        styles = self.fonts_data.get(family, {})

        if styles:
            self.selected_font_family = family
            self.font_path = ""

            self.style_combo.blockSignals(True)
            self.style_combo.clear()

            style_order = [
                "Thin", "ExtraLight", "Light", "Regular", "Medium",
                "SemiBold", "Bold", "ExtraBold", "Black",
                "Thin Italic", "ExtraLight Italic", "Light Italic",
                "Italic", "Medium Italic", "SemiBold Italic",
                "Bold Italic", "ExtraBold Italic", "Black Italic"
            ]
            sorted_styles = sorted(
                styles.keys(),
                key=lambda s: style_order.index(s) if s in style_order else len(style_order)
            )
            self.style_combo.addItems(sorted_styles)

            if len(styles) == 1:
                self.style_combo.setVisible(False)
                self.selected_font_style = list(styles.keys())[0]
            else:
                self.style_combo.setVisible(True)
                if self.selected_font_style in styles:
                    self.style_combo.setCurrentText(self.selected_font_style)
                else:
                    self.selected_font_style = list(styles.keys())[0]
                    self.style_combo.setCurrentText(self.selected_font_style)

            self.style_combo.blockSignals(False)

    def normalize_font_input(self):
        """Вызывается при Enter или потере фокуса."""
        text = self.font_edit.text().strip()

        if not text:
            return

        # Точное совпадение
        if text in self.fonts_data:
            self.apply_font_family(text)
            return

        # Путь к файлу
        if os.path.exists(text) and text.lower().endswith((".ttf", ".otf")):
            self.font_path = text
            self.selected_font_family = ""
            self.style_combo.setVisible(False)
            return

        # Ищем ближайшее
        text_lower = text.lower()
        best_match = None

        for family in self.fonts_data.keys():
            family_lower = family.lower()
            if family_lower.startswith(text_lower):
                if best_match is None or len(family) < len(best_match):
                    best_match = family

        if best_match:
            self.font_edit.blockSignals(True)
            self.font_edit.setText(best_match)
            self.font_edit.blockSignals(False)
            self.apply_font_family(best_match)
    # ============================================================
    # ВКЛАДКА: ФОРМАТ ИМЕНИ
    # ============================================================

    def build_tab_format(self):
        layout = QVBoxLayout(self.tab_format)

        self.name_mode_group = QButtonGroup(self)
        modes = [
            ("В одну строку", "single_line"),
            ("Фамилия / Имя Отчество", "split_surname"),
            ("Каждое слово отдельно", "split_all"),
            ("Свой вариант (сколько слов на первой строке)", "custom"),
            ("Авто (по отступу)", "auto")
        ]
        for text, value in modes:
            rb = QRadioButton(text)
            rb.setProperty("mode", value)
            self.name_mode_group.addButton(rb)
            layout.addWidget(rb)
            if value == "single_line":
                rb.setChecked(True)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Слов на первой строке:"))
        self.split_after_spin = QSpinBox()
        self.split_after_spin.setRange(1, 10)
        self.split_after_spin.setValue(1)
        row1.addWidget(self.split_after_spin)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Отступ от краёв (px):"))
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 100000)
        self.margin_spin.setValue(36)
        row2.addWidget(self.margin_spin)
        layout.addLayout(row2)

        layout.addStretch()

    def get_name_mode(self):
        for btn in self.name_mode_group.buttons():
            if btn.isChecked():
                return btn.property("mode")
        return "single_line"

    # ============================================================
    # ВКЛАДКА: ВЫВОД
    # ============================================================

    def build_tab_output(self):
        layout = QVBoxLayout(self.tab_output)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Формат:"))
        self.format_group = QButtonGroup(self)
        self.rb_png = QRadioButton("PNG")
        self.rb_pdf = QRadioButton("PDF")
        self.rb_pdf.setChecked(True)
        self.format_group.addButton(self.rb_png)
        self.format_group.addButton(self.rb_pdf)
        row1.addWidget(self.rb_png)
        row1.addWidget(self.rb_pdf)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("PDF:"))
        self.pdf_mode_group = QButtonGroup(self)
        self.rb_multi = QRadioButton("Каждому свой файл")
        self.rb_single = QRadioButton("Один общий")
        self.rb_multi.setChecked(True)
        self.pdf_mode_group.addButton(self.rb_multi)
        self.pdf_mode_group.addButton(self.rb_single)
        row2.addWidget(self.rb_multi)
        row2.addWidget(self.rb_single)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Имя общего PDF:"))
        self.pdf_name_edit = QLineEdit("Все_грамоты")
        row3.addWidget(self.pdf_name_edit)
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Папка для сохранения:"))
        self.output_dir_edit = QLineEdit("Грамоты")
        row4.addWidget(self.output_dir_edit)
        btn_browse = QPushButton("Обзор")
        btn_browse.clicked.connect(self.choose_output_dir)
        row4.addWidget(btn_browse)
        layout.addLayout(row4)

        self.preview_check = QCheckBox("Превью перед генерацией")
        self.preview_check.setChecked(True)
        layout.addWidget(self.preview_check)

        layout.addWidget(QLabel("Текст для превью:"))
        self.preview_group = QButtonGroup(self)
        self.rb_preview_test = QRadioButton("Тестовое имя (Иванов Иван Иванович)")
        self.rb_preview_longest = QRadioButton("Самое длинное из списка")
        self.rb_preview_custom = QRadioButton("Свой текст:")
        self.rb_preview_test.setChecked(True)
        self.preview_group.addButton(self.rb_preview_test)
        self.preview_group.addButton(self.rb_preview_longest)
        self.preview_group.addButton(self.rb_preview_custom)
        layout.addWidget(self.rb_preview_test)
        layout.addWidget(self.rb_preview_longest)

        # Блок: Свой текст + поле
        custom_widget = QWidget()
        custom_layout = QHBoxLayout(custom_widget)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.addWidget(self.rb_preview_custom)
        self.preview_custom_edit = QLineEdit()
        custom_layout.addWidget(self.preview_custom_edit)
        layout.addWidget(custom_widget)

        layout.addStretch()

    def get_output_format(self):
        return "png" if self.rb_png.isChecked() else "pdf"

    def get_pdf_mode(self):
        return "multi" if self.rb_multi.isChecked() else "single"

    def choose_output_dir(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Выбери папку для сохранения",
            self.output_dir_edit.text() or "."
        )
        if path:
            self.output_dir_edit.setText(path)

    # ============================================================
    # ВКЛАДКА: НАСТРОЙКИ
    # ============================================================

    def build_tab_settings(self):
        layout = QVBoxLayout(self.tab_settings)

        layout.addWidget(QLabel("Тема оформления:"))

        self.theme_group = QButtonGroup(self)
        self.rb_dark = QRadioButton("Тёмная")
        self.rb_light = QRadioButton("Светлая")
        self.rb_dark.setChecked(True)
        self.theme_group.addButton(self.rb_dark)
        self.theme_group.addButton(self.rb_light)

        layout.addWidget(self.rb_dark)
        layout.addWidget(self.rb_light)

        self.rb_dark.toggled.connect(self.change_theme)
        self.rb_light.toggled.connect(self.change_theme)

        layout.addStretch()


        # Разделитель

        # О программе
        layout.addWidget(QLabel("О программе"))
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        layout.addWidget(QLabel("AutoFill"))
        layout.addWidget(QLabel("Версия 1.0"))

        # Авторы
        layout.addWidget(QLabel("Авторы:"))
        layout.addWidget(QLabel("Alexey «TWorker» Zhaliy"))
        layout.addWidget(QLabel("Maxim «jojer» Odincov"))

        btn_help = QPushButton("Инструкция")
        btn_help.clicked.connect(self.show_help)
        layout.addWidget(btn_help)

        # Кнопка лицензии
        btn_license = QPushButton("Лицензия")
        btn_license.clicked.connect(self.show_license)
        layout.addWidget(btn_license)



    def show_license(self):
        text = """AutoFill

    Required Notice: Copyright (c) 2026 TWorker and Maxim Odincov. All rights reserved.

    Polyform Noncommercial License 1.0.0
    https://polyformproject.org/licenses/noncommercial/1.0.0"""

        dialog = MessageDialog(
            self,
            "Лицензия",
            text,
            buttons=[("Закрыть", "primary")]
        )
        self.apply_theme_to_dialog(dialog, self.current_theme)
        dialog.exec()

    def change_theme(self):
        theme = "light" if self.rb_light.isChecked() else "dark"

        for widget in self.findChildren(QWidget):
            widget.setProperty("theme", theme)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

        if theme == "dark":
            set_title_bar_color(self, "#222222")
            set_title_bar_light_theme(self, False)
        else:
            set_title_bar_color(self, "#F2F2F2")
            set_title_bar_light_theme(self, True)

        if hasattr(self, 'completer'):
            self.apply_theme_to_completer(self.completer)

        self.setProperty("theme", theme)
        self.style().unpolish(self)
        self.style().polish(self)

        # Сохраняем текущую тему
        self.current_theme = theme

    def show_help(self):
        text = """КАК РАБОТАТЬ С ПРОГРАММОЙ

    1. Выберите шаблон грамоты (JPG или PNG)
    2. Выберите шрифт из списка или загрузите свой файл
    3. Укажите размер шрифта в пикселях
    4. Вставьте список ФИО (каждое имя с новой строки)
    5. Настройте позицию текста во вкладке «Позиция»

    ОКНО ВЫБОРА ТОЧКИ

    • Правая кнопка мыши – установить точку в месте клика
    • Левая кнопка мыши – перемещать изображение
    • Колесо мыши – приблизить/отдалить
    • Стрелки на клавиатуре – сдвиг точки на 1 пиксель
    • Shift + стрелки – сдвиг на 10 пикселей
    • Ctrl + стрелки – сдвиг на 50 пикселей
    • Alt (зажать) + навести курсор + клик левой мышью (зажать) – показывает расстояние от точки до курсора

    ИСКЛЮЧЕНИЯ

    Сюда попадают ФИО, которые не влезли в границы грамоты.
    Их можно:
    • Перенести обратно в основной список
    • Очистить
    • Сгенерировать отдельно с меньшим шрифтом

    НАСТРОЙКИ СОХРАНЯЮТСЯ АВТОМАТИЧЕСКИ

    При закрытии программы выберите «Сохранить» – и все настройки сохранятся до следующего запуска."""

        dialog = MessageDialog(self, "Инструкция", text, buttons=[("Понятно", "primary")])
        self.apply_theme_to_dialog(dialog, self.current_theme)
        dialog.exec()
    # ============================================================
    # ШРИФТ
    # ============================================================

    def get_font(self):
        from PIL import ImageFont
        size = self.font_size_spin.value()

        print(f"=== get_font ===")
        print(f"font_path: {self.font_path}")
        print(f"selected_font_family: {self.selected_font_family}")
        print(f"selected_font_style: {getattr(self, 'selected_font_style', None)}")

        if self.font_path:
            print(f"Использую файл: {self.font_path}")
            return ImageFont.truetype(self.font_path, size=size)

        if self.selected_font_family:
            family_fonts = self.fonts_data.get(self.selected_font_family, {})
            print(f"Доступные стили для '{self.selected_font_family}': {list(family_fonts.keys())}")
            if family_fonts:
                path = family_fonts.get(self.selected_font_style)
                if path:
                    return ImageFont.truetype(path, size=size)

            for fam, styles in self.fonts_data.items():
                if self.selected_font_family in fam:
                    if styles:
                        first_style = list(styles.keys())[0]
                        print(f"Стиль не найден, беру первый: '{first_style}' → {first_style}")
                        return ImageFont.truetype(styles[first_style], size=size)

        print("Использую arial.ttf")
        return ImageFont.truetype("arial.ttf", size=size)

    # ============================================================
    # ПРЕВЬЮ
    # ============================================================

    def get_preview_parts(self, people):
        if self.rb_preview_test.isChecked():
            return ["Иванов", "Иван", "Иванович"]
        elif self.rb_preview_longest.isChecked():
            return max(people, key=lambda p: sum(len(w) for w in p))
        else:
            custom = self.preview_custom_edit.text().strip()
            if custom:
                return custom.split()
            return ["Иванов", "Иван", "Иванович"]

    def make_preview(self):
        people = self.get_names_list()
        if not people:
            dialog = MessageDialog(self, "Ошибка", "Добавь список имён.", buttons=[("ОК", "primary")])
            self.apply_theme_to_dialog(dialog, self.current_theme)
            dialog.exec()
            return False

        if not self.template_path:
            dialog = MessageDialog(self, "Ошибка", "Выбери шаблон грамоты.", buttons=[("ОК", "primary")])
            self.apply_theme_to_dialog(dialog, self.current_theme)
            dialog.exec()
            return False

        try:
            template = Image.open(self.template_path)
            font = self.get_font()
            img_w, img_h = template.size

            parts = self.get_preview_parts(people)

            x = "center" if (self.x_auto_check.isChecked() or self.x_edit.value() == 0) else self.x_edit.value()
            y = "center" if (self.y_auto_check.isChecked() or self.y_edit.value() == 0) else self.y_edit.value()

            lines = format_name_lines(parts, self.get_name_mode(), self.split_after_spin.value())
            if lines is None:
                lines = resolve_auto_lines(parts, font, self.letter_spacing_spin.value(), img_w, self.margin_spin.value())

            problems = check_text_bounds(
                lines, font, x,
                "left" if self.rb_left.isChecked() else "center",
                self.letter_spacing_spin.value(), img_w, self.margin_spin.value()
            )
            if problems:
                msg = "\n".join(f"{text} – на {overflow}px ({side})" for text, overflow, side in problems)
                dialog = MessageDialog(self, "Текст выходит за границы", msg, buttons=[("ОК", "primary")])
                self.apply_theme_to_dialog(dialog, self.current_theme)
                dialog.exec()

            img = template.copy()
            d = ImageDraw.Draw(img)
            draw_text_block(
                d, lines, font, self.text_color, x, y,
                self.x_offset_spin.value(), self.y_offset_spin.value(),
                "left" if self.rb_left.isChecked() else "center",
                self.line_spacing_spin.value(), self.letter_spacing_spin.value(),
                img_w, img_h
            )

            self.preview_image = img  # сохраняем в памяти
            self.status_label.setText("Превью создано")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
            return False

    def show_preview_dialog(self):
        dialog = PreviewDialog(self.preview_image, self)
        self.apply_theme_to_dialog(dialog, self.current_theme)
        result = dialog.exec()
        return result

    # ============================================================
    # ГЕНЕРАЦИЯ
    # ============================================================

    def generate_all(self):
        people = self.get_names_list()
        if not self.template_path:
            dialog = MessageDialog(self, "Ошибка", "Выбери шаблон грамоты.",
                                   buttons=[("ОК", "primary")])
            self.apply_theme_to_dialog(dialog, self.current_theme)
            dialog.exec()
            return
        if not self.font_path and not self.selected_font_family:
            dialog = MessageDialog(self, "Ошибка", "Выбери файл шрифта или системный шрифт.", buttons=[("ОК", "primary")])
            self.apply_theme_to_dialog(dialog, self.current_theme)
            dialog.exec()
            return
        if self.selected_font_family and self.selected_font_family not in self.fonts_data:
            dialog = MessageDialog(self, "Ошибка", f"Шрифт «{self.selected_font_family}» не найден. Выбери из списка.",
                                   buttons=[("ОК", "primary")])
            self.apply_theme_to_dialog(dialog, self.current_theme)
            dialog.exec()
            return
        if self.font_size_spin.value() == 0:
            dialog = MessageDialog(self, "Ошибка", "Укажи размер шрифта.",
                                   buttons=[("ОК", "primary")])
            self.apply_theme_to_dialog(dialog, self.current_theme)
            dialog.exec()
            return
        if not people:
            dialog = MessageDialog(self, "Ошибка", "Добавь список имён.", buttons=[("ОК", "primary")])
            self.apply_theme_to_dialog(dialog, self.current_theme)
            dialog.exec()
            return

        # Проверка дубликатов
        seen = {}
        duplicates = []
        for parts in people:
            key = "_".join(parts)
            if key in seen:
                duplicates.append(parts)
            else:
                seen[key] = True

        if duplicates:
            msg = f"Найдены дубликаты ({len(duplicates)}):\n\n"
            for dup in duplicates[:15]:
                msg += f"• {' '.join(dup)}\n"
            if len(duplicates) > 15:
                msg += f"\n...и ещё {len(duplicates) - 15}\n"

            dialog = MessageDialog(
                self,
                "Дубликаты в списке",
                msg,
                buttons=[
                    ("Продолжить", "primary"),
                    ("Удалить дубликаты", ""),
                    ("Отмена", "")
                ]
            )
            self.apply_theme_to_dialog(dialog, self.current_theme)
            dialog.exec()

            if dialog.result == 2:  # Отмена
                self.status_label.setText("Отменено пользователем")
                return
            elif dialog.result == 1:  # Удалить дубликаты
                seen_keys = set()
                unique_people = []
                for p in people:
                    key = "_".join(p)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        unique_people.append(p)
                people = unique_people
                self.names_text.setPlainText("\n".join(" ".join(p) for p in people))
                self.all_names = "\n".join(" ".join(p) for p in people)

        # Вопрос про очистку папки
        if os.path.exists(self.output_dir_edit.text() or "Грамоты"):
            dialog = MessageDialog(
                self,
                "Очистка папки",
                f"Очистить папку «{self.output_dir_edit.text() or 'Грамоты'}» перед генерацией?",
                buttons=[
                    ("Очистить", "primary"),
                    ("Не очищать", ""),
                    ("Отмена", "")
                ]
            )
            self.apply_theme_to_dialog(dialog, self.current_theme)
            dialog.exec()

            if dialog.result == 2:
                self.status_label.setText("Отменено пользователем")
                return
            elif dialog.result == 0:
                output_dir = self.output_dir_edit.text() or "Грамоты"
                for file in os.listdir(output_dir):
                    file_path = os.path.join(output_dir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)

        if self.preview_check.isChecked():
            while True:
                if not self.make_preview():
                    return

                result = self.show_preview_dialog()

                if result == 0:
                    self.status_label.setText("Отменено пользователем")
                    return
                elif result == 2:
                    self.pick_position()
                    continue
                else:
                    break

        try:
            template = Image.open(self.template_path)
            font = self.get_font()
            img_w, img_h = template.size

            x = "center" if (self.x_auto_check.isChecked() or self.x_edit.value() == 0) else self.x_edit.value()
            y = "center" if (self.y_auto_check.isChecked() or self.y_edit.value() == 0) else self.y_edit.value()

            output_dir = self.output_dir_edit.text() or "Грамоты"
            os.makedirs(output_dir, exist_ok=True)

            # Для single PDF – проверяем только общий файл
            if self.get_output_format() == "pdf" and self.get_pdf_mode() == "single":
                pdf_filename = f"{self.pdf_name_edit.text()}.pdf"
                pdf_path = os.path.join(output_dir, pdf_filename)
                if os.path.exists(pdf_path):
                    dialog = MessageDialog(
                        self,
                        "Файл существует",
                        f"Файл «{pdf_filename}» уже существует.\nЗаменить?",
                        buttons=[("Заменить", "primary"), ("Отмена", "")]
                    )
                    self.apply_theme_to_dialog(dialog, self.current_theme)
                    dialog.exec()
                    if dialog.result == 1:
                        self.status_label.setText("Отменено пользователем")
                        return

            problematic = []
            people_lines = {}

            for parts in people:
                lines = format_name_lines(parts, self.get_name_mode(), self.split_after_spin.value())
                if lines is None:
                    lines = resolve_auto_lines(parts, font, self.letter_spacing_spin.value(), img_w,
                                               self.margin_spin.value())
                people_lines["_".join(parts)] = lines

                problems = check_text_bounds(
                    lines, font, x,
                    "left" if self.rb_left.isChecked() else "center",
                    self.letter_spacing_spin.value(), img_w, self.margin_spin.value()
                )
                if problems:
                    problematic.append((parts, problems))

            if problematic:
                msg = f"Найдено {len(problematic)} грамот с выходом за границы:\n\n"
                for parts, problems in problematic[:15]:
                    name = " ".join(parts)
                    overflow_info = "; ".join(f"{text}: +{overflow}px" for text, overflow, _ in problems)
                    msg += f"• {name} – {overflow_info}\n"
                if len(problematic) > 15:
                    msg += f"\n...и ещё {len(problematic) - 15}\n"

                dialog = MessageDialog(
                    self,
                    "Текст выходит за границы",
                    msg,
                    buttons=[("Сделать все", "primary"), ("Только корректные", ""), ("Отмена", "")]
                )
                self.apply_theme_to_dialog(dialog, self.current_theme)
                dialog.exec()

                if dialog.result == 2:
                    self.status_label.setText("Отменено пользователем")
                    return
                elif dialog.result == 1:
                    problematic_names = {"_".join(p[0]) for p in problematic}
                    generated_people = [p for p in people if "_".join(p) not in problematic_names]
                    self.excluded_text.setPlainText("\n".join(" ".join(p[0]) for p in problematic))
                else:
                    generated_people = people
            else:
                generated_people = people

            pdf_pages = [] if (self.get_output_format() == "pdf" and self.get_pdf_mode() == "single") else None



            # Для single PDF – не проверяем каждый файл
            skip_individual_check = (self.get_output_format() == "pdf" and self.get_pdf_mode() == "single")

            for idx, parts in enumerate(generated_people, 1):
                lines = people_lines.get("_".join(parts))
                if lines is None:
                    lines = format_name_lines(parts, self.get_name_mode(), self.split_after_spin.value())
                    if lines is None:
                        lines = resolve_auto_lines(parts, font, self.letter_spacing_spin.value(), img_w,
                                                   self.margin_spin.value())

                img = template.copy()
                d = ImageDraw.Draw(img)
                draw_text_block(
                    d, lines, font, self.text_color, x, y,
                    self.x_offset_spin.value(), self.y_offset_spin.value(),
                    "left" if self.rb_left.isChecked() else "center",
                    self.line_spacing_spin.value(), self.letter_spacing_spin.value(),
                    img_w, img_h
                )

                if not skip_individual_check:
                    filename = "_".join(parts)
                    ext = ".pdf" if self.get_output_format() == "pdf" else ".png"
                    base_path = os.path.join(output_dir, filename + ext)

                    if os.path.exists(base_path):
                        dialog = MessageDialog(
                            self,
                            "Файл существует",
                            f"Файл «{filename}{ext}» уже существует.\nЧто сделать?",
                            buttons=[
                                ("Заменить", "primary"),
                                ("Создать с номером", ""),
                                ("Отмена", "")
                            ]
                        )
                        self.apply_theme_to_dialog(dialog, self.current_theme)
                        dialog.exec()

                        if dialog.result == 2:
                            continue
                        elif dialog.result == 1:
                            counter = 1
                            while os.path.exists(os.path.join(output_dir, f"{filename}_{counter}{ext}")):
                                counter += 1
                            filename = f"{filename}_{counter}"
                else:
                    filename = "_".join(parts)

                if self.get_output_format() == "pdf":
                    if pdf_pages is not None:
                        pdf_pages.append(img.convert("RGB"))
                    else:
                        img.convert("RGB").save(os.path.join(output_dir, f"{filename}.pdf"), "PDF", resolution=100.0)
                else:
                    img.save(os.path.join(output_dir, f"{filename}.png"))

                self.status_label.setText(f"Готово: {idx}/{len(generated_people)}")

            if self.get_output_format() == "pdf" and self.get_pdf_mode() == "single" and pdf_pages:
                pdf_path = os.path.join(output_dir, f"{self.pdf_name_edit.text()}.pdf")
                pdf_pages[0].save(pdf_path, "PDF", resolution=100.0, save_all=True, append_images=pdf_pages[1:])

            count = len(generated_people)
            word = plural(count, ("грамота", "грамоты", "грамот"))
            excluded_count = len(problematic)

            self.status_label.setText(f"Готово! {count} {word} в папке «{output_dir}»")
            self.open_dir_btn.setVisible(True)

            if self.get_output_format() == "pdf" and self.get_pdf_mode() == "single":
                pdf_filename = f"{self.pdf_name_edit.text()}.pdf"
                word_instr = plural_instrumental(count, ("грамотой", "грамотами", "грамотами"))
                result_text = f"Создан файл «{pdf_filename}» с {count} {word_instr}.\nИсключено: {excluded_count}."
            else:
                result_text = f"Создано {count} {word}.\nИсключено: {excluded_count}."

            dialog = MessageDialog(
                self,
                "Готово",
                result_text,
                buttons=[("Открыть папку", "primary"), ("Закрыть", "")]
            )
            self.apply_theme_to_dialog(dialog, self.current_theme)
            dialog.exec()

            if dialog.result == 0:
                self.open_output_dir()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))