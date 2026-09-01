import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QCheckBox, QRadioButton,
    QButtonGroup, QFileDialog, QColorDialog, QFontDialog, QMessageBox,
    QTabWidget, QSpinBox, QDialog
)
from PySide6.QtGui import QFont, QColor
from PIL import Image, ImageDraw

from core.text_render import draw_text_block, check_text_bounds
from core.name_format import format_name_lines, resolve_auto_lines
from ui.point_picker import PointPickerDialog
from ui.preview import PreviewDialog


class DiplomaGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Генератор грамот")
        self.resize(900, 800)

        self.template_path = ""
        self.font_path = ""
        self.text_color = (0, 0, 0)
        self.selected_font_family = ""

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

        self.tabs.addTab(self.tab_main, "Основные")
        self.tabs.addTab(self.tab_position, "Позиция")
        self.tabs.addTab(self.tab_format, "Формат имени")
        self.tabs.addTab(self.tab_output, "Вывод")

        self.build_tab_main()
        self.build_tab_position()
        self.build_tab_format()
        self.build_tab_output()

        self.generate_btn = QPushButton("Сгенерировать грамоты")
        self.generate_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; padding: 12px; font-size: 14px; font-weight: bold; }"
        )
        self.generate_btn.clicked.connect(self.generate_all)
        main_layout.addWidget(self.generate_btn)

        self.status_label = QLabel("Готов к работе")
        main_layout.addWidget(self.status_label)

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
        row2.addWidget(self.font_edit)
        btn_font_file = QPushButton("Файл")
        btn_font_file.clicked.connect(self.choose_font_file)
        row2.addWidget(btn_font_file)
        btn_font_system = QPushButton("Системный")
        btn_font_system.clicked.connect(self.choose_system_font)
        row2.addWidget(btn_font_system)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Размер:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 500)
        self.font_size_spin.setValue(48)
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

        layout.addWidget(QLabel("Список ФИО (каждая строка — один человек):"))
        self.names_text = QTextEdit()
        self.names_text.setPlaceholderText("Иванов Иван Иванович\nПетров Пётр Петрович\n...")
        layout.addWidget(self.names_text)

        btn_row1 = QHBoxLayout()
        btn_load = QPushButton("Загрузить файл")
        btn_load.clicked.connect(self.load_names_file)
        btn_row1.addWidget(btn_load)
        btn_clear = QPushButton("Очистить")
        btn_clear.clicked.connect(lambda: self.names_text.clear())
        btn_row1.addWidget(btn_clear)
        layout.addLayout(btn_row1)

        layout.addWidget(QLabel("Исключения (сюда попадают те, кто не влез):"))
        self.excluded_text = QTextEdit()
        self.excluded_text.setPlaceholderText("Сюда попадут ФИО, которые не влезли в границы")
        layout.addWidget(self.excluded_text)

        btn_row2 = QHBoxLayout()
        btn_clear_excl = QPushButton("Очистить исключения")
        btn_clear_excl.clicked.connect(lambda: self.excluded_text.clear())
        btn_row2.addWidget(btn_clear_excl)
        btn_move = QPushButton("Перенести в основной")
        btn_move.clicked.connect(self.move_excluded_to_main)
        btn_row2.addWidget(btn_move)
        layout.addLayout(btn_row2)

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
        ok, font = QFontDialog.getFont(self)
        if ok:
            self.selected_font_family = font.family()
            self.font_path = ""
            self.font_edit.setText(f"[Системный] {font.family()}")

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.text_color = (color.red(), color.green(), color.blue())
            self.color_btn.setStyleSheet(f"QPushButton {{ background-color: {color.name()}; }}")

    def load_names_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбери файл со списком", "", "Текст (*.txt)")
        if path:
            with open(path, encoding="utf-8") as f:
                self.names_text.setPlainText(f.read())

    def get_names_list(self):
        text = self.names_text.toPlainText()
        return [line.strip().split() for line in text.split("\n") if line.strip()]

    def move_excluded_to_main(self):
        excluded = self.excluded_text.toPlainText().strip()
        if excluded:
            current = self.names_text.toPlainText()
            self.names_text.setPlainText(current.rstrip() + "\n" + excluded + "\n")
            self.excluded_text.clear()

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
        # Получаем текущие координаты
        try:
            current_x = int(self.x_edit.text()) if not self.x_auto_check.isChecked() else None
            current_y = int(self.y_edit.text()) if not self.y_auto_check.isChecked() else None
        except ValueError:
            current_x = None
            current_y = None

        dialog = PointPickerDialog(self.template_path, self, current_x, current_y)
        if dialog.exec() == QDialog.Accepted:
            x, y = dialog.get_point()
            if not self.x_auto_check.isChecked():
                self.x_edit.setText(str(x))
            if not self.y_auto_check.isChecked():
                self.y_edit.setText(str(y))

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
        self.pdf_name_edit = QLineEdit("все_грамоты")
        row3.addWidget(self.pdf_name_edit)
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Папка для сохранения:"))
        self.output_dir_edit = QLineEdit("Грамоты")
        row4.addWidget(self.output_dir_edit)
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

    # ============================================================
    # ШРИФТ
    # ============================================================

    def get_font(self):
        from PIL import ImageFont
        size = self.font_size_spin.value()
        if self.font_path:
            return ImageFont.truetype(self.font_path, size=size)
        else:
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
        result = dialog.exec()
        return result

    # ============================================================
    # ГЕНЕРАЦИЯ
    # ============================================================

    def generate_all(self):
        people = self.get_names_list()
        if not people:
            QMessageBox.warning(self, "Нет списка", "Добавь список имён.")
            return

        if not self.template_path:
            QMessageBox.warning(self, "Нет шаблона", "Выбери шаблон грамоты.")
            return

        if self.preview_check.isChecked():
            if not self.make_preview():
                return

            result = self.show_preview_dialog()
            if result == 0:
                self.status_label.setText("Отменено пользователем")
                return
            elif result == 2:
                self.pick_position()
                return

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

                choice = QMessageBox.question(
                    self,
                    "Текст выходит за границы",
                    msg + "\n\n«Да» — сделать все\n«Нет» — только корректные\n«Отмена» — остановить",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )

                if choice == QMessageBox.Cancel:
                    self.status_label.setText("Отменено пользователем")
                    return
                elif choice == QMessageBox.No:
                    problematic_names = {"_".join(p[0]) for p in problematic}
                    generated_people = [p for p in people if "_".join(p) not in problematic_names]
                    self.excluded_text.setPlainText("\n".join(" ".join(p[0]) for p in problematic))
                else:
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

            self.status_label.setText(f"Готово! {len(generated_people)} грамот в «{output_dir}»")
            QMessageBox.information(self, "Готово", f"Создано {len(generated_people)} грамот.\nИсключено: {len(problematic)}.")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))