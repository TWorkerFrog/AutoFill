import os
import json

from PySide6.QtCore import QUrl, Qt, QStringListModel
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QCheckBox, QRadioButton,
    QButtonGroup, QFileDialog, QColorDialog, QFontDialog, QMessageBox,
    QTabWidget, QSpinBox, QDialog, QSplitter, QCompleter, QComboBox
)
from PySide6.QtGui import QFont, QColor, QDesktopServices, QFontDatabase
from PySide6.QtWidgets import QFrame
from PIL import Image, ImageDraw

from core.text_render import draw_text_block, check_text_bounds
from core.name_format import format_name_lines, resolve_auto_lines, plural
from core.name_format import plural_instrumental
from core.screen_utils import get_window_size
from core.font_utils import scan_fonts
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
        self.settings_file = "settings.json"
        self.load_settings()
        self.fonts_data = scan_fonts()

        self.template_path = ""
        self.font_path = ""
        self.text_color = (0, 0, 0)
        self.selected_font_family = ""
        self.current_theme = "dark"
        self.all_names = ""
        self.all_excluded = ""
        self.selected_font_style = "Regular"

        self.create_ui()


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
        """Загружает настройки при запуске."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)

                # Применяем настройки после создания UI
                self.apply_settings(settings)
            except:
                pass

    def apply_settings(self, settings):
        """Применяет загруженные настройки."""
        if "font_size" in settings:
            self.font_size_spin.setValue(settings["font_size"])
        if "template_path" in settings:
            self.template_path = settings["template_path"]
            self.template_edit.setText(settings["template_path"])
        if "font_path" in settings:
            self.font_path = settings["font_path"]
            self.font_edit.setText(settings["font_path"])
        if "output_dir" in settings:
            self.output_dir_edit.setText(settings["output_dir"])
        if "theme" in settings:
            if settings["theme"] == "light":
                self.rb_light.setChecked(True)
            else:
                self.rb_dark.setChecked(True)
        # ... и т.д.

    def save_settings(self):
        """Сохраняет текущие настройки."""
        settings = {
            "font_size": self.font_size_spin.value(),
            "template_path": self.template_path,
            "font_path": self.font_path,
            "output_dir": self.output_dir_edit.text(),
            "theme": self.current_theme,
            # ... и т.д.
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
        row1.addWidget(self.template_edit)
        btn_template = QPushButton("Выбрать")
        btn_template.clicked.connect(self.choose_template)
        row1.addWidget(btn_template)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Шрифт:"))
        self.font_edit = QLineEdit()
        self.font_edit.setPlaceholderText("Начни вводить название...")
        self.font_edit.setMinimumWidth(250)  # ← минимальная ширина
        row2.addWidget(self.font_edit, stretch=1)  # ← растягивается
        self.style_combo = QComboBox()
        self.style_combo.setFixedWidth(150)
        row2.addWidget(self.style_combo)
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

        # При выборе шрифта обновляем начертания
        self.font_edit.textChanged.connect(self.on_font_changed)


        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Размер:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setSpecialValueText(" ")
        self.font_size_spin.setRange(0, 500)
        self.font_size_spin.setValue(0)
        row3.addWidget(self.font_size_spin)

        row3.addWidget(QLabel("Цвет:"))
        self.color_btn = QPushButton("Выбрать")
        self.color_btn.clicked.connect(self.choose_color)
        row3.addWidget(self.color_btn)

        row3.addWidget(QLabel("Межбуквенный:"))
        self.letter_spacing_spin = QSpinBox()
        self.letter_spacing_spin.setRange(0, 50)
        self.letter_spacing_spin.setValue(0)
        row3.addWidget(self.letter_spacing_spin)
        layout.addLayout(row3)

        # Подпись + поле + кнопки для основного списка
        self.names_widget = QWidget()
        names_layout = QVBoxLayout(self.names_widget)
        names_layout.addWidget(QLabel("Список ФИО (каждая строка — один человек):"))

        # Поиск
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по списку...")
        self.search_edit.textChanged.connect(
            lambda: self.filter_list(self.search_edit, self.names_text, "all_names")
        )
        names_layout.addWidget(self.search_edit)

        self.names_text = QTextEdit()
        self.names_text.setPlaceholderText("Иванов Иван Иванович\nПетров Пётр Петрович\n...")
        self.names_text.textChanged.connect(
            lambda: self.update_all_data(self.search_edit, self.names_text, "all_names")
        )
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
        excluded_layout.addWidget(QLabel("Исключения (сюда попадают те, кто не влез):"))

        self.excluded_search_edit = QLineEdit()
        self.excluded_search_edit.setPlaceholderText("Поиск по исключениям...")
        self.excluded_search_edit.textChanged.connect(
            lambda: self.filter_list(self.excluded_search_edit, self.excluded_text, "all_excluded")
        )
        excluded_layout.addWidget(self.excluded_search_edit)

        self.excluded_text = QTextEdit()
        self.excluded_text.setPlaceholderText("Сюда попадут ФИО, которые не влезли в границы")
        self.excluded_text.textChanged.connect(
            lambda: self.update_all_data(self.excluded_search_edit, self.excluded_text, "all_excluded")
        )
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
        self.ask_before_move.setChecked(False)
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
            self.color_btn.setStyleSheet(f"QPushButton {{ background-color: {color.name()}; }}")

    def load_names_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбери файл со списком", "", "Текст (*.txt)")
        if path:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.all_names = content
            self.names_text.setPlainText(content)
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
            # Если Нет — проверяем, кого нет в основном списке
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
            # Не спрашиваем — просто очищаем и вставляем
            self.names_text.setPlainText("\n".join(" ".join(p) for p in excluded_people))

        self.excluded_text.clear()

    def update_all_names(self):
        """Сохраняет полный список при изменении текста."""
        if not self.search_edit.text().strip():
            self.all_names = self.names_text.toPlainText()

    def filter_list(self, search_edit, text_edit, all_data_attr):
        """Универсальный фильтр для списков."""
        search_text = search_edit.text().strip().lower()
        all_data = getattr(self, all_data_attr)

        if not search_text:
            if all_data:
                text_edit.setPlainText(all_data)
            return

        if not all_data:
            all_data = text_edit.toPlainText()
            setattr(self, all_data_attr, all_data)

        lines = all_data.split("\n")
        filtered = [line for line in lines if search_text in line.lower()]
        text_edit.setPlainText("\n".join(filtered))

    def update_all_data(self, search_edit, text_edit, all_data_attr):
        search_text = search_edit.text().strip()

        if not search_text:
            # Если поиск пуст — сохраняем как есть
            setattr(self, all_data_attr, text_edit.toPlainText())
        else:
            # Если поиск активен — обновляем all_data с учётом изменений
            all_data = getattr(self, all_data_attr, "")
            if not all_data:
                return

            # Получаем отфильтрованные строки (которые сейчас в text_edit)
            visible_lines = text_edit.toPlainText().split("\n")
            visible_set = set(line.strip() for line in visible_lines if line.strip())

            # Обновляем all_data: убираем удалённые, оставляем всё остальное
            all_lines = all_data.split("\n")
            updated_lines = []
            for line in all_lines:
                if line.strip() in visible_set or search_text.lower() not in line.lower():
                    updated_lines.append(line)

            setattr(self, all_data_attr, "\n".join(updated_lines))

    def apply_theme_to_dialog(self, dialog, theme):
        """Применяет тему к диалогу и всем его дочерним виджетам."""
        dialog.setProperty("theme", theme)
        for widget in dialog.findChildren(QWidget):
            widget.setProperty("theme", theme)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        dialog.style().unpolish(dialog)
        dialog.style().polish(dialog)

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
        row2.addWidget(QLabel("X:"))
        self.x_edit = QLineEdit("732")
        row2.addWidget(self.x_edit)
        self.x_auto_check = QCheckBox("Автоцентр по X")
        row2.addWidget(self.x_auto_check)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Y:"))
        self.y_edit = QLineEdit("828")
        row3.addWidget(self.y_edit)
        self.y_auto_check = QCheckBox("Автоцентр по Y")
        row3.addWidget(self.y_auto_check)
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Сдвиг X:"))
        self.x_offset_spin = QSpinBox()
        self.x_offset_spin.setRange(-500, 500)
        row4.addWidget(self.x_offset_spin)
        row4.addWidget(QLabel("Сдвиг Y:"))
        self.y_offset_spin = QSpinBox()
        self.y_offset_spin.setRange(-500, 500)
        row4.addWidget(self.y_offset_spin)
        layout.addLayout(row4)

        row5 = QHBoxLayout()
        row5.addWidget(QLabel("Межстрочный интервал:"))
        self.line_spacing_spin = QSpinBox()
        self.line_spacing_spin.setRange(0, 100)
        self.line_spacing_spin.setValue(4)
        row5.addWidget(self.line_spacing_spin)
        layout.addLayout(row5)

        btn_pick = QPushButton("Указать точку на грамоте")
        btn_pick.clicked.connect(self.pick_position)
        layout.addWidget(btn_pick)

        layout.addStretch()

    def pick_position(self):
        if not self.template_path:
            QMessageBox.warning(self, "Нет шаблона", "Сначала выбери шаблон грамоты.")
            return

        try:
            current_x = int(self.x_edit.text()) if not self.x_auto_check.isChecked() else None
            current_y = int(self.y_edit.text()) if not self.y_auto_check.isChecked() else None
        except ValueError:
            current_x = None
            current_y = None

        align = "left" if self.rb_left.isChecked() else "center"
        dialog = PointPickerDialog(self.template_path, self, current_x, current_y, align)
        self.apply_theme_to_dialog(dialog, self.current_theme)
        if dialog.exec() == QDialog.Accepted:
            x, y = dialog.get_point()
            if not self.x_auto_check.isChecked():
                self.x_edit.setText(str(x))
            if not self.y_auto_check.isChecked():
                self.y_edit.setText(str(y))

    def on_font_changed(self):
        family = self.font_edit.text().strip()

        if not family:
            return

        styles = self.fonts_data.get(family, {})

        if styles:
            self.selected_font_family = family
            self.font_path = ""

            self.style_combo.blockSignals(True)
            self.style_combo.clear()
            style_order = [
                "Thin", "ExtraLight", "Light", "Regular", "Medium",
                "SemiBold", "Bold", "ExtraBold", "Black", "Thin Italic", "ExtraLight Italic", "Light Italic",
                "Italic", "Medium Italic", "SemiBold Italic", "Bold Italic", "ExtraBold Italic", "Black Italic"
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
        self.margin_spin.setRange(0, 200)
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
        layout.addWidget(self.rb_preview_custom)

        self.preview_custom_edit = QLineEdit()
        layout.addWidget(self.preview_custom_edit)

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
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # О программе
        layout.addWidget(QLabel("О программе"))
        layout.addWidget(QLabel("AutoFillSurnames"))
        layout.addWidget(QLabel("Версия 1.0.0"))

        # Авторы
        layout.addWidget(QLabel("Авторы:"))
        layout.addWidget(QLabel("Alexey «TWorker» Zhaliy"))
        layout.addWidget(QLabel("Maxim «jojer» Odincov"))

        # Кнопка лицензии
        btn_license = QPushButton("Лицензия")
        btn_license.clicked.connect(self.show_license)
        layout.addWidget(btn_license)

    def show_license(self):
        text = """AutoFillSurnames

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

        self.setProperty("theme", theme)
        self.style().unpolish(self)
        self.style().polish(self)

        # Сохраняем текущую тему
        self.current_theme = theme
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
            QMessageBox.warning(self, "Нет списка", "Добавь список имён.")
            return False

        if not self.template_path:
            QMessageBox.warning(self, "Нет шаблона", "Выбери шаблон грамоты.")
            return False

        try:
            template = Image.open(self.template_path)
            font = self.get_font()
            img_w, img_h = template.size

            parts = self.get_preview_parts(people)

            x = "center" if self.x_auto_check.isChecked() else int(self.x_edit.text() or 0)
            y = "center" if self.y_auto_check.isChecked() else int(self.y_edit.text() or 0)

            lines = format_name_lines(parts, self.get_name_mode(), self.split_after_spin.value())
            if lines is None:
                lines = resolve_auto_lines(parts, font, self.letter_spacing_spin.value(), img_w, self.margin_spin.value())

            problems = check_text_bounds(
                lines, font, x,
                "left" if self.rb_left.isChecked() else "center",
                self.letter_spacing_spin.value(), img_w, self.margin_spin.value()
            )
            if problems:
                msg = "\n".join(f"{text} — на {overflow}px ({side})" for text, overflow, side in problems)
                QMessageBox.warning(self, "Текст выходит за границы", msg)

            img = template.copy()
            d = ImageDraw.Draw(img)
            draw_text_block(
                d, lines, font, self.text_color, x, y,
                self.x_offset_spin.value(), self.y_offset_spin.value(),
                "left" if self.rb_left.isChecked() else "center",
                self.line_spacing_spin.value(), self.letter_spacing_spin.value(),
                img_w, img_h
            )

            preview_path = "_preview.png"
            if os.path.exists(preview_path):
                os.remove(preview_path)
            img.save(preview_path)

            self.status_label.setText("Превью создано")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
            return False

    def show_preview_dialog(self):
        preview_path = "_preview.png"
        if not os.path.exists(preview_path):
            return 0

        dialog = PreviewDialog(preview_path, self)
        self.apply_theme_to_dialog(dialog, self.current_theme)
        result = dialog.exec()
        return result

    # ============================================================
    # ГЕНЕРАЦИЯ
    # ============================================================

    def generate_all(self):
        people = self.get_names_list()
        if not self.template_path:
            QMessageBox.warning(self, "Нет шаблона", "Выбери шаблон грамоты.")
            return
        if not self.font_path and not self.selected_font_family:
            QMessageBox.warning(self, "Нет шрифта", "Выбери файл шрифта или системный шрифт.")
            return
        if self.font_size_spin.value() == 0:
            QMessageBox.warning(self, "Нет размера", "Укажи размер шрифта.")
            return
        if not people:
            QMessageBox.warning(self, "Нет списка", "Добавь список имён.")
            return
        if self.preview_check.isChecked():
            while True:
                if not self.make_preview():
                    return

                result = self.show_preview_dialog()

                if result == 0:  # Отмена
                    self.status_label.setText("Отменено пользователем")
                    return
                elif result == 2:  # Редактировать позицию
                    self.pick_position()
                    # После выбора точки — снова показываем превью
                    continue
                else:  # Продолжить (accept)
                    break

        try:
            template = Image.open(self.template_path)
            font = self.get_font()
            img_w, img_h = template.size

            x = "center" if self.x_auto_check.isChecked() else int(self.x_edit.text() or 0)
            y = "center" if self.y_auto_check.isChecked() else int(self.y_edit.text() or 0)

            output_dir = self.output_dir_edit.text() or "Грамоты"
            os.makedirs(output_dir, exist_ok=True)

            problematic = []
            people_lines = {}

            for parts in people:
                lines = format_name_lines(parts, self.get_name_mode(), self.split_after_spin.value())
                if lines is None:
                    lines = resolve_auto_lines(parts, font, self.letter_spacing_spin.value(), img_w, self.margin_spin.value())
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
                    msg += f"• {name} — {overflow_info}\n"
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

                if dialog.result == 2:  # Отмена
                    self.status_label.setText("Отменено пользователем")
                    return
                elif dialog.result == 1:  # Только корректные
                    problematic_names = {"_".join(p[0]) for p in problematic}
                    generated_people = [p for p in people if "_".join(p) not in problematic_names]
                    self.excluded_text.setPlainText("\n".join(" ".join(p[0]) for p in problematic))
                else:  # Сделать все
                    generated_people = people
            else:
                generated_people = people

            pdf_pages = [] if (self.get_output_format() == "pdf" and self.get_pdf_mode() == "single") else None

            for idx, parts in enumerate(generated_people, 1):
                lines = people_lines.get("_".join(parts))
                if lines is None:
                    lines = format_name_lines(parts, self.get_name_mode(), self.split_after_spin.value())
                    if lines is None:
                        lines = resolve_auto_lines(parts, font, self.letter_spacing_spin.value(), img_w, self.margin_spin.value())

                img = template.copy()
                d = ImageDraw.Draw(img)
                draw_text_block(
                    d, lines, font, self.text_color, x, y,
                    self.x_offset_spin.value(), self.y_offset_spin.value(),
                    "left" if self.rb_left.isChecked() else "center",
                    self.line_spacing_spin.value(), self.letter_spacing_spin.value(),
                    img_w, img_h
                )

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

            # Финальное сообщение
            count = len(generated_people)
            word = plural(count, ("грамота", "грамоты", "грамот"))
            excluded_count = len(problematic)

            self.status_label.setText(f"Готово! {count} {word} в папке «{output_dir}»")
            self.open_dir_btn.setVisible(True)

            # Текст с учётом режима PDF
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