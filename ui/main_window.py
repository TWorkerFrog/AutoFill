from __future__ import annotations

import logging
from contextlib import suppress
from pathlib import Path

from PIL import ImageFont
from PySide6.QtCore import QByteArray, QStandardPaths, Qt, QThread, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QCompleter,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.font_utils import resolve_font_path, scan_fonts
from core.generator import (
    GenerationJob,
    OutputConfig,
    RenderConfig,
    load_template,
    render_page,
)
from core.name_format import format_name_lines, plural, resolve_auto_lines
from core.paths import (
    cleanup_manifest,
    ensure_output_dir,
    load_manifest,
    read_text_file,
    safe_pdf_stem,
    safe_stem_from_parts,
)
from core.screen_utils import get_window_size
from core.settings import AppSettings, SettingsStore
from core.text_render import check_text_bounds
from core.version import __version__
from core.windows_utils import is_windows_theme, set_title_bar_color, set_title_bar_light_theme
from ui.message_dialog import MessageDialog
from ui.name_list import NameListEditor
from ui.point_picker import PointPickerDialog
from ui.preview import PreviewDialog
from ui.preview_pane import PreviewPane
from ui.worker import GenerationWorker

log = logging.getLogger(__name__)


class DiplomaGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"AutoFill {__version__}")
        width, height = get_window_size(self, 0.68, 0.82)
        self.resize(max(980, width), max(720, height))
        self.setMinimumSize(900, 640)

        self.settings_store = SettingsStore()
        settings = self.settings_store.load()

        self.template_path = settings.template_path
        self.font_path = settings.font_path
        self.selected_font_family = settings.selected_font_family
        self.selected_font_style = settings.selected_font_style
        self.text_color = tuple(settings.text_color)
        self.current_theme = self._resolve_theme(settings.theme)

        self.fonts_data = scan_fonts()
        self._font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
        self._template_cache: tuple[tuple[str, int, int], object, float] | None = None
        self.preview_image = None

        self._worker: GenerationWorker | None = None
        self._thread: QThread | None = None
        self._loading_settings = False

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(220)
        self._preview_timer.timeout.connect(self.update_live_preview)

        self.create_ui()
        self.apply_settings(settings)
        self._connect_preview_signals()
        self._apply_theme(self.current_theme)
        self._update_generate_button()
        self._cancel_shortcut = QShortcut(QKeySequence("Esc"), self)
        self._cancel_shortcut.setContext(Qt.WindowShortcut)
        self._cancel_shortcut.activated.connect(self.cancel_generation)
        QTimer.singleShot(0, self.update_live_preview)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Нативный заголовок можно перекрасить только после создания HWND.
        self._apply_theme(self.current_theme)

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------
    def create_ui(self) -> None:
        self._build_menu()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(10)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.tabs = QTabWidget()
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
        self.main_splitter.addWidget(self.tabs)

        self.preview_pane = PreviewPane()
        self.preview_pane.openRequested.connect(self.open_preview)
        self.main_splitter.addWidget(self.preview_pane)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.setSizes([820, 340])
        main_layout.addWidget(self.main_splitter, 1)

        self.build_tab_main()
        self.build_tab_position()
        self.build_tab_format()
        self.build_tab_output()
        self.build_tab_settings()

        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(10)

        self.status_label = QLabel("Готов к работе")
        self.status_label.setObjectName("status_label")
        bottom_layout.addWidget(self.status_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(220)
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        bottom_layout.addWidget(self.progress_bar)

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setObjectName("danger_btn")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel_generation)
        bottom_layout.addWidget(self.cancel_btn)

        self.open_dir_btn = QPushButton("Открыть папку")
        self.open_dir_btn.setVisible(False)
        self.open_dir_btn.clicked.connect(self.open_output_dir)
        bottom_layout.addWidget(self.open_dir_btn)

        self.generate_btn = QPushButton("Сгенерировать грамоты")
        self.generate_btn.setObjectName("primary_btn")
        self.generate_btn.setMinimumWidth(230)
        self.generate_btn.clicked.connect(self.generate_all)
        bottom_layout.addWidget(self.generate_btn)

        main_layout.addWidget(bottom)

    def _build_menu(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("Файл")
        action_template = QAction("Выбрать шаблон…", self)
        action_template.setShortcut(QKeySequence("Ctrl+O"))
        action_template.triggered.connect(self.choose_template)
        file_menu.addAction(action_template)

        action_names = QAction("Загрузить список ФИО…", self)
        action_names.setShortcut(QKeySequence("Ctrl+Shift+O"))
        action_names.triggered.connect(self.load_names_file)
        file_menu.addAction(action_names)

        action_output = QAction("Выбрать папку сохранения…", self)
        action_output.triggered.connect(self.choose_output_dir)
        file_menu.addAction(action_output)
        file_menu.addSeparator()

        action_quit = QAction("Выход", self)
        action_quit.setShortcut(QKeySequence("Ctrl+Q"))
        action_quit.triggered.connect(self.close)
        file_menu.addAction(action_quit)

        generation_menu = menu.addMenu("Генерация")
        self.action_preview = QAction("Предпросмотр", self)
        self.action_preview.setShortcut(QKeySequence("F5"))
        self.action_preview.triggered.connect(self.open_preview)
        generation_menu.addAction(self.action_preview)

        self.action_generate = QAction("Сгенерировать", self)
        self.action_generate.setShortcut(QKeySequence("Ctrl+G"))
        self.action_generate.triggered.connect(self.generate_all)
        generation_menu.addAction(self.action_generate)

        help_menu = menu.addMenu("Справка")
        action_help = QAction("Инструкция", self)
        action_help.triggered.connect(self.show_help)
        help_menu.addAction(action_help)
        action_license = QAction("Лицензия", self)
        action_license.triggered.connect(self.show_license)
        help_menu.addAction(action_license)
        action_about = QAction("О программе", self)
        action_about.triggered.connect(self.show_about)
        help_menu.addAction(action_about)

    def build_tab_main(self) -> None:
        layout = QVBoxLayout(self.tab_main)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        source_group = QGroupBox("Шаблон и шрифт")
        grid = QFormLayout(source_group)
        grid.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        grid.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        template_row = QWidget()
        template_layout = QHBoxLayout(template_row)
        template_layout.setContentsMargins(0, 0, 0, 0)
        self.template_edit = QLineEdit()
        self.template_edit.setPlaceholderText("Путь до файла с грамотой (JPG/PNG)…")
        self.template_edit.textChanged.connect(self._on_template_changed)
        template_layout.addWidget(self.template_edit, 1)
        btn_template = QPushButton("Выбрать")
        btn_template.clicked.connect(self.choose_template)
        template_layout.addWidget(btn_template)
        grid.addRow("Шаблон:", template_row)

        font_row = QWidget()
        font_layout = QHBoxLayout(font_row)
        font_layout.setContentsMargins(0, 0, 0, 0)
        self.font_edit = QLineEdit()
        self.font_edit.setPlaceholderText("Название шрифта или путь к TTF/OTF…")
        self.font_edit.textChanged.connect(self._on_font_text_changed)
        self.font_edit.returnPressed.connect(self.normalize_font_input)
        self.font_edit.editingFinished.connect(self.normalize_font_input)
        font_layout.addWidget(self.font_edit, 1)

        self.style_combo = QComboBox()
        self.style_combo.setMinimumWidth(130)
        self.style_combo.currentTextChanged.connect(self._on_style_changed)
        font_layout.addWidget(self.style_combo)

        btn_font_file = QPushButton("Файл")
        btn_font_file.clicked.connect(self.choose_font_file)
        font_layout.addWidget(btn_font_file)
        grid.addRow("Шрифт:", font_row)

        self.completer = QCompleter(sorted(self.fonts_data.keys()))
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.font_edit.setCompleter(self.completer)
        self.apply_theme_to_completer(self.completer)

        style_row = QWidget()
        style_layout = QHBoxLayout(style_row)
        style_layout.setContentsMargins(0, 0, 0, 0)
        style_layout.addWidget(QLabel("Размер:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(1, 2000)
        self.font_size_spin.setValue(100)
        self.font_size_spin.setSuffix(" px")
        style_layout.addWidget(self.font_size_spin)

        style_layout.addSpacing(14)
        style_layout.addWidget(QLabel("Цвет:"))
        self.color_preview = QPushButton()
        self.color_preview.setFixedSize(32, 32)
        self.color_preview.setToolTip("Выбрать цвет текста")
        self.color_preview.clicked.connect(self.choose_color)
        self._set_color_preview(self.text_color)
        style_layout.addWidget(self.color_preview)

        style_layout.addSpacing(14)
        letter_label = QLabel("Интервал:")
        letter_label.setToolTip("Межбуквенный интервал")
        style_layout.addWidget(letter_label)
        self.letter_spacing_spin = QSpinBox()
        self.letter_spacing_spin.setRange(-20, 200)
        self.letter_spacing_spin.setValue(0)
        self.letter_spacing_spin.setSuffix(" px")
        style_layout.addWidget(self.letter_spacing_spin)
        style_layout.addStretch()
        grid.addRow("Параметры:", style_row)
        layout.addWidget(source_group)

        self.names_editor = NameListEditor(
            "Список ФИО (каждая строка — один человек)",
            "Иванов Иван Иванович\nПетров Пётр Петрович\n…",
            show_load=True,
        )
        self.names_editor.load_button.clicked.connect(self.load_names_file)
        self.names_editor.changed.connect(self._on_names_changed)

        self.excluded_editor = NameListEditor(
            "Исключения (не влезли в границы или пропущены)",
            "Иванов Иван Иванович",
            show_load=False,
        )
        move_button = QPushButton("Перенести в основной список")
        move_button.clicked.connect(self.move_excluded_to_main)
        self.excluded_editor.buttons_layout.addWidget(move_button)

        self.ask_before_move = QCheckBox("Спрашивать перед переносом исключений")
        self.ask_before_move.setChecked(True)
        self.excluded_editor.layout().addWidget(self.ask_before_move)

        self.names_splitter = QSplitter(Qt.Vertical)
        self.names_splitter.addWidget(self.names_editor)
        self.names_splitter.addWidget(self.excluded_editor)
        self.names_splitter.setSizes([390, 210])
        self.names_splitter.setChildrenCollapsible(False)
        layout.addWidget(self.names_splitter, 1)

    def build_tab_position(self) -> None:
        layout = QVBoxLayout(self.tab_position)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        align_group = QGroupBox("Привязка блока")
        align_layout = QVBoxLayout(align_group)
        align_row = QHBoxLayout()
        align_row.addWidget(QLabel("Выравнивание строк:"))
        self.align_group = QButtonGroup(self)
        self.rb_left = QRadioButton("По левому краю")
        self.rb_center = QRadioButton("По центру")
        self.rb_right = QRadioButton("По правому краю")
        self.rb_left.setChecked(True)
        for button in (self.rb_left, self.rb_center, self.rb_right):
            self.align_group.addButton(button)
            align_row.addWidget(button)
        align_row.addStretch()
        align_layout.addLayout(align_row)

        x_row = QHBoxLayout()
        x_row.addWidget(QLabel("X:"))
        self.x_edit = QSpinBox()
        self.x_edit.setRange(0, 100000)
        self.x_edit.setSuffix(" px")
        x_row.addWidget(self.x_edit)
        self.x_auto_check = QCheckBox("Автоцентр по X")
        self.x_auto_check.setChecked(True)
        self.x_auto_check.toggled.connect(self._on_auto_toggled)
        x_row.addWidget(self.x_auto_check)

        x_row.addSpacing(20)
        x_row.addWidget(QLabel("Y:"))
        self.y_edit = QSpinBox()
        self.y_edit.setRange(0, 100000)
        self.y_edit.setSuffix(" px")
        x_row.addWidget(self.y_edit)
        self.y_auto_check = QCheckBox("Автоцентр по Y")
        self.y_auto_check.setChecked(True)
        self.y_auto_check.toggled.connect(self._on_auto_toggled)
        x_row.addWidget(self.y_auto_check)
        x_row.addStretch()
        align_layout.addLayout(x_row)
        layout.addWidget(align_group)

        offset_group = QGroupBox("Смещение и интервалы")
        offset_form = QFormLayout(offset_group)
        offset_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        offset_row = QWidget()
        offset_layout = QHBoxLayout(offset_row)
        offset_layout.setContentsMargins(0, 0, 0, 0)
        offset_layout.addWidget(QLabel("X:"))
        self.x_offset_spin = QSpinBox()
        self.x_offset_spin.setRange(-100000, 100000)
        self.x_offset_spin.setSuffix(" px")
        offset_layout.addWidget(self.x_offset_spin)
        offset_layout.addSpacing(18)
        offset_layout.addWidget(QLabel("Y:"))
        self.y_offset_spin = QSpinBox()
        self.y_offset_spin.setRange(-100000, 100000)
        self.y_offset_spin.setSuffix(" px")
        offset_layout.addWidget(self.y_offset_spin)
        offset_layout.addStretch()
        offset_form.addRow("Сдвиг блока:", offset_row)

        self.line_spacing_spin = QSpinBox()
        self.line_spacing_spin.setRange(0, 500)
        self.line_spacing_spin.setValue(4)
        self.line_spacing_spin.setSuffix(" px")
        offset_form.addRow("Межстрочный интервал:", self.line_spacing_spin)
        layout.addWidget(offset_group)

        buttons = QHBoxLayout()
        pick_btn = QPushButton("Указать точку на грамоте")
        pick_btn.clicked.connect(self.pick_position)
        buttons.addWidget(pick_btn)
        reset_btn = QPushButton("Сбросить позицию")
        reset_btn.clicked.connect(self.reset_position)
        buttons.addWidget(reset_btn)
        buttons.addStretch()
        layout.addLayout(buttons)
        layout.addStretch()

    def build_tab_format(self) -> None:
        layout = QVBoxLayout(self.tab_format)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        mode_group = QGroupBox("Режим формирования ФИО")
        mode_layout = QVBoxLayout(mode_group)
        self.name_mode_group = QButtonGroup(self)
        modes = [
            ("В одну строку", "single_line"),
            ("Фамилия / Имя Отчество", "split_surname"),
            ("Каждое слово отдельно", "split_all"),
            ("Свой вариант (сколько слов на первой строке)", "custom"),
            ("Авто (по доступной ширине)", "auto"),
        ]
        for text, value in modes:
            radio = QRadioButton(text)
            radio.setProperty("mode", value)
            self.name_mode_group.addButton(radio)
            mode_layout.addWidget(radio)
            if value == "single_line":
                radio.setChecked(True)
        layout.addWidget(mode_group)

        params_group = QGroupBox("Параметры переноса")
        params_form = QFormLayout(params_group)
        self.split_after_spin = QSpinBox()
        self.split_after_spin.setRange(1, 30)
        self.split_after_spin.setValue(1)
        params_form.addRow("Слов на первой строке:", self.split_after_spin)
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 100000)
        self.margin_spin.setValue(36)
        self.margin_spin.setSuffix(" px")
        params_form.addRow("Отступ от краёв (safe area):", self.margin_spin)
        layout.addWidget(params_group)

        hint = QLabel(
            "В режиме «Авто» текст переносится по словам на любое число строк "
            "с учётом выбранного шрифта и отступа. Проверка границ учитывает "
            "смещения и вертикальные края."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint_label")
        layout.addWidget(hint)
        layout.addStretch()

    def build_tab_output(self) -> None:
        layout = QVBoxLayout(self.tab_output)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        format_group = QGroupBox("Формат")
        format_layout = QVBoxLayout(format_group)
        self.format_group = QButtonGroup(self)
        self.rb_png = QRadioButton("PNG — отдельный файл для каждого ФИО")
        self.rb_pdf = QRadioButton("PDF")
        self.rb_pdf.setChecked(True)
        self.format_group.addButton(self.rb_png)
        self.format_group.addButton(self.rb_pdf)
        format_layout.addWidget(self.rb_png)
        format_layout.addWidget(self.rb_pdf)

        pdf_row = QHBoxLayout()
        pdf_row.addWidget(QLabel("PDF:"))
        self.pdf_mode_group = QButtonGroup(self)
        self.rb_multi = QRadioButton("Каждому свой файл")
        self.rb_single = QRadioButton("Один общий PDF")
        self.rb_multi.setChecked(True)
        self.pdf_mode_group.addButton(self.rb_multi)
        self.pdf_mode_group.addButton(self.rb_single)
        pdf_row.addWidget(self.rb_multi)
        pdf_row.addWidget(self.rb_single)
        pdf_row.addStretch()
        format_layout.addLayout(pdf_row)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Имя общего PDF:"))
        self.pdf_name_edit = QLineEdit("Все_грамоты")
        name_row.addWidget(self.pdf_name_edit, 1)
        format_layout.addLayout(name_row)
        layout.addWidget(format_group)

        output_group = QGroupBox("Сохранение")
        output_layout = QVBoxLayout(output_group)
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Папка:"))
        self.output_dir_edit = QLineEdit(self._default_output_dir())
        dir_row.addWidget(self.output_dir_edit, 1)
        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(self.choose_output_dir)
        dir_row.addWidget(browse_btn)
        output_layout.addLayout(dir_row)

        self.cleanup_previous_check = QCheckBox(
            "Удалить ранее созданные AutoFill файлы (только по манифесту)"
        )
        self.cleanup_previous_check.setToolTip(
            "Удаляются только файлы, которые AutoFill создал ранее и записал в манифест. "
            "Чужие файлы и папки не затрагиваются."
        )
        output_layout.addWidget(self.cleanup_previous_check)

        self.preview_check = QCheckBox("Показывать окно предпросмотра перед генерацией")
        self.preview_check.setChecked(True)
        output_layout.addWidget(self.preview_check)
        layout.addWidget(output_group)

        preview_group = QGroupBox("Текст для предпросмотра")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_group = QButtonGroup(self)
        self.rb_preview_test = QRadioButton("Тестовое имя (Иванов Иван Иванович)")
        self.rb_preview_longest = QRadioButton("Самое длинное из списка")
        self.rb_preview_custom = QRadioButton("Свой текст:")
        self.rb_preview_test.setChecked(True)
        for button in (self.rb_preview_test, self.rb_preview_longest, self.rb_preview_custom):
            self.preview_group.addButton(button)
            preview_layout.addWidget(button)
        self.preview_custom_edit = QLineEdit()
        self.preview_custom_edit.setPlaceholderText("Иванов Иван Иванович")
        preview_layout.addWidget(self.preview_custom_edit)
        layout.addWidget(preview_group)
        layout.addStretch()

        self.rb_png.toggled.connect(self._update_output_controls)
        self.rb_pdf.toggled.connect(self._update_output_controls)
        self.rb_multi.toggled.connect(self._update_output_controls)
        self.rb_single.toggled.connect(self._update_output_controls)

    def build_tab_settings(self) -> None:
        layout = QVBoxLayout(self.tab_settings)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        theme_group = QGroupBox("Тема оформления")
        theme_layout = QVBoxLayout(theme_group)
        self.theme_group = QButtonGroup(self)
        self.rb_dark = QRadioButton("Тёмная")
        self.rb_light = QRadioButton("Светлая")
        self.rb_system = QRadioButton("Системная")
        for button in (self.rb_dark, self.rb_light, self.rb_system):
            self.theme_group.addButton(button)
            theme_layout.addWidget(button)
            button.toggled.connect(self.change_theme)
        layout.addWidget(theme_group)

        about_group = QGroupBox("О программе")
        about_layout = QVBoxLayout(about_group)
        about_layout.addWidget(QLabel(f"AutoFill {__version__}"))
        about_layout.addWidget(QLabel("Авторы: Alexey «TWorker» Zhaliy, Maxim «jojer» Odincov"))
        about_layout.addWidget(QLabel("Polyform Noncommercial License 1.0.0"))
        buttons = QHBoxLayout()
        help_btn = QPushButton("Инструкция")
        help_btn.clicked.connect(self.show_help)
        buttons.addWidget(help_btn)
        license_btn = QPushButton("Лицензия")
        license_btn.clicked.connect(self.show_license)
        buttons.addWidget(license_btn)
        buttons.addStretch()
        about_layout.addLayout(buttons)
        layout.addWidget(about_group)

        path_group = QGroupBox("Файлы настроек")
        path_layout = QVBoxLayout(path_group)
        path_label = QLabel(str(self.settings_store.path))
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_layout.addWidget(path_label)
        save_btn = QPushButton("Сохранить настройки сейчас")
        save_btn.clicked.connect(self.save_settings)
        path_layout.addWidget(save_btn)
        layout.addWidget(path_group)
        layout.addStretch()

    # ------------------------------------------------------------------
    # Настройки
    # ------------------------------------------------------------------
    @staticmethod
    def _set_path_text(edit: QLineEdit, text: str) -> None:
        """Показывает начало длинного пути, а не только его хвост."""

        edit.setText(text)
        edit.setCursorPosition(0)

    def apply_settings(self, settings: AppSettings) -> None:
        self._loading_settings = True
        try:
            self.template_path = settings.template_path
            self._set_path_text(self.template_edit, settings.template_path)

            self.font_path = settings.font_path
            self.selected_font_family = settings.selected_font_family
            self.selected_font_style = settings.selected_font_style
            self.font_edit.blockSignals(True)
            if settings.font_path:
                self._set_path_text(self.font_edit, settings.font_path)
                self.style_combo.clear()
                self.style_combo.setVisible(False)
            elif settings.selected_font_family:
                self.font_edit.setText(settings.selected_font_family)
                self.font_edit.setCursorPosition(0)
                self.apply_font_family(settings.selected_font_family, settings.selected_font_style)
            else:
                self.font_edit.clear()
            self.font_edit.blockSignals(False)

            self.font_size_spin.setValue(settings.font_size)
            self.letter_spacing_spin.setValue(settings.letter_spacing)
            self.text_color = tuple(settings.text_color)
            self._set_color_preview(self.text_color)

            self.x_edit.setValue(settings.x)
            self.y_edit.setValue(settings.y)
            self.x_auto_check.setChecked(settings.x_auto)
            self.y_auto_check.setChecked(settings.y_auto)
            self.x_offset_spin.setValue(settings.x_offset)
            self.y_offset_spin.setValue(settings.y_offset)
            self.line_spacing_spin.setValue(settings.line_spacing)
            self.margin_spin.setValue(settings.margin)

            align = {"left": self.rb_left, "center": self.rb_center, "right": self.rb_right}.get(settings.align, self.rb_left)
            align.setChecked(True)
            self._set_name_mode(settings.name_mode)
            self.split_after_spin.setValue(settings.split_after)

            output_dir = settings.output_dir
            if not output_dir or not Path(output_dir).is_absolute():
                output_dir = self._default_output_dir()
            self._set_path_text(self.output_dir_edit, output_dir)

            if settings.output_format == "png":
                self.rb_png.setChecked(True)
            else:
                self.rb_pdf.setChecked(True)
            if settings.pdf_mode == "single":
                self.rb_single.setChecked(True)
            else:
                self.rb_multi.setChecked(True)
            self.pdf_name_edit.setText(settings.pdf_name)

            self.preview_check.setChecked(settings.preview)
            self.cleanup_previous_check.setChecked(settings.cleanup_previous)
            if settings.preview_mode == "longest":
                self.rb_preview_longest.setChecked(True)
            elif settings.preview_mode == "custom":
                self.rb_preview_custom.setChecked(True)
            else:
                self.rb_preview_test.setChecked(True)
            self.preview_custom_edit.setText(settings.preview_custom)
            self.ask_before_move.setChecked(settings.ask_before_move)

            theme_button = {
                "dark": self.rb_dark,
                "light": self.rb_light,
                "system": self.rb_system,
            }.get(settings.theme, self.rb_system if settings.theme == "system" else self.rb_dark)
            theme_button.setChecked(True)
            self.current_theme = self._resolve_theme(settings.theme)

            if settings.window_geometry:
                geometry = QByteArray.fromBase64(settings.window_geometry.encode("ascii"))
                if not geometry.isEmpty():
                    self.restoreGeometry(geometry)
            if settings.main_splitter_sizes:
                self.main_splitter.setSizes(settings.main_splitter_sizes)
            if settings.splitter_sizes:
                self.names_splitter.setSizes(settings.splitter_sizes)

            self._on_auto_toggled()
            self._update_output_controls()
            self._update_generate_button()
        finally:
            self._loading_settings = False

    def save_settings(self) -> bool:
        def geometry_text(obj) -> str:
            return bytes(obj.saveGeometry().toBase64()).decode("ascii")

        settings = AppSettings(
            template_path=self.template_path,
            font_path=self.font_path,
            selected_font_family=self.selected_font_family,
            selected_font_style=self.selected_font_style,
            font_size=self.font_size_spin.value(),
            text_color=tuple(self.text_color),
            letter_spacing=self.letter_spacing_spin.value(),
            x=self.x_edit.value(),
            y=self.y_edit.value(),
            x_auto=self.x_auto_check.isChecked(),
            y_auto=self.y_auto_check.isChecked(),
            x_offset=self.x_offset_spin.value(),
            y_offset=self.y_offset_spin.value(),
            line_spacing=self.line_spacing_spin.value(),
            margin=self.margin_spin.value(),
            align=self.get_align(),
            name_mode=self.get_name_mode(),
            split_after=self.split_after_spin.value(),
            output_dir=self.output_dir_edit.text().strip(),
            output_format=self.get_output_format(),
            pdf_mode=self.get_pdf_mode(),
            pdf_name=self.pdf_name_edit.text().strip(),
            preview=self.preview_check.isChecked(),
            preview_mode=self.get_preview_mode(),
            preview_custom=self.preview_custom_edit.text().strip(),
            theme=self.get_theme_choice(),
            ask_before_move=self.ask_before_move.isChecked(),
            cleanup_previous=self.cleanup_previous_check.isChecked(),
            window_geometry=geometry_text(self),
            splitter_sizes=self.names_splitter.sizes(),
            main_splitter_sizes=self.main_splitter.sizes(),
        )
        try:
            self.settings_store.save(settings)
            self.status_label.setText("Настройки сохранены")
            return True
        except OSError as exc:
            self._message("Ошибка сохранения", str(exc), [("ОК", "primary")])
            return False

    def closeEvent(self, event) -> None:
        if self._thread is not None and self._thread.isRunning():
            answer = self._message(
                "Генерация выполняется",
                "Генерация ещё не завершена. Отменить её и выйти?",
                [("Отменить и выйти", ""), ("Не выходить", "primary")],
                default_btn=1,
            )
            if answer != 0:
                event.ignore()
                return
            if self._worker:
                self._worker.cancel()
            if self._thread:
                self._thread.quit()
                if not self._thread.wait(15000):
                    self._message(
                        "Генерация",
                        "Не удалось остановить генерацию за 15 секунд. Окно останется открытым.",
                        [("ОК", "primary")],
                    )
                    event.ignore()
                    return
            self._thread = None
            self._worker = None
            self._set_generating(False)

        answer = self._message(
            "Выход",
            "Сохранить настройки перед выходом?",
            [("Сохранить", "primary"), ("Не сохранять", ""), ("Отмена", "")],
            default_btn=0,
        )
        if answer == 0:
            if not self.save_settings():
                event.ignore()
                return
            event.accept()
        elif answer == 1:
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------
    # Тема
    # ------------------------------------------------------------------
    def _resolve_theme(self, choice: str) -> str:
        if choice == "system":
            return "dark" if is_windows_theme() else "light"
        return "light" if choice == "light" else "dark"

    def get_theme_choice(self) -> str:
        if self.rb_system.isChecked():
            return "system"
        return "light" if self.rb_light.isChecked() else "dark"

    def change_theme(self, _checked: bool = False) -> None:
        if self._loading_settings:
            return
        self._apply_theme(self._resolve_theme(self.get_theme_choice()))

    def _apply_theme(self, theme: str) -> None:
        theme = "light" if theme == "light" else "dark"
        self.current_theme = theme
        self.setProperty("theme", theme)
        for widget in self.findChildren(QWidget):
            widget.setProperty("theme", theme)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.style().unpolish(self)
        self.style().polish(self)

        if theme == "dark":
            set_title_bar_color(self, "#222222")
            set_title_bar_light_theme(self, False)
        else:
            set_title_bar_color(self, "#F2F2F2")
            set_title_bar_light_theme(self, True)

        if hasattr(self, "completer"):
            self.apply_theme_to_completer(self.completer)

    def apply_theme_to_dialog(self, dialog, theme: str | None = None) -> None:
        theme = theme or self.current_theme
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

    def apply_theme_to_completer(self, completer: QCompleter) -> None:
        popup = completer.popup()
        if popup:
            popup.setProperty("theme", self.current_theme)
            popup.style().unpolish(popup)
            popup.style().polish(popup)

    # ------------------------------------------------------------------
    # Источники и параметры
    # ------------------------------------------------------------------
    def _default_output_dir(self) -> str:
        location = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        base = Path(location) if location else Path.home() / "Documents"
        return str(base / "AutoFill")

    def choose_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите шаблон грамоты",
            self.template_path or str(Path.home()),
            "Изображения (*.jpg *.jpeg *.png)",
            options=QFileDialog.DontUseNativeDialog,
        )
        if path:
            self._set_path_text(self.template_edit, path)

    def _on_template_changed(self, text: str) -> None:
        self.template_path = text.strip()
        self._template_cache = None
        self._schedule_preview()

    def choose_font_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл шрифта",
            self.font_path or str(Path.home()),
            "Шрифты (*.ttf *.otf *.ttc)",
            options=QFileDialog.DontUseNativeDialog,
        )
        if path:
            self.font_path = path
            self.selected_font_family = ""
            self.font_edit.blockSignals(True)
            self._set_path_text(self.font_edit, path)
            self.font_edit.blockSignals(False)
            self.style_combo.clear()
            self.style_combo.setVisible(False)
            self._schedule_preview()

    def _set_color_preview(self, color: tuple[int, int, int]) -> None:
        value = QColor(*color).name()
        self.color_preview.setStyleSheet(
            f"background-color: {value}; border: 1px solid #555555; border-radius: 5px;"
        )

    def choose_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(*self.text_color),
            self,
            "Цвет текста",
            QColorDialog.DontUseNativeDialog,
        )
        if color.isValid():
            self.text_color = (color.red(), color.green(), color.blue())
            self._set_color_preview(self.text_color)
            self._schedule_preview()

    def _on_font_text_changed(self, text: str) -> None:
        if self._loading_settings:
            return
        text = text.strip()
        if not text:
            self.font_path = ""
            self.selected_font_family = ""
            self.style_combo.clear()
            self.style_combo.setVisible(False)
            self._schedule_preview()
            return

        path = Path(text)
        if path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
            self.font_path = str(path)
            self.selected_font_family = ""
            self.style_combo.clear()
            self.style_combo.setVisible(False)
            self._schedule_preview()
            return

        family = next((name for name in self.fonts_data if name.casefold() == text.casefold()), None)
        if family:
            self.apply_font_family(family)
        else:
            # Пока введённое имя не совпало с реальным семейством, не
            # используем старый выбор шрифта неявно.
            self.selected_font_family = ""
            self.font_path = ""
            self.style_combo.blockSignals(True)
            self.style_combo.clear()
            self.style_combo.blockSignals(False)
            self.style_combo.setVisible(False)
        self._schedule_preview()

    def _on_style_changed(self, style: str) -> None:
        if style and self.selected_font_family:
            self.selected_font_style = style
        self._schedule_preview()

    def apply_font_family(self, family: str, preferred_style: str | None = None) -> None:
        styles = self.fonts_data.get(family, {})
        if not styles:
            return
        self.selected_font_family = family
        self.font_path = ""
        style_order = [
            "Thin", "ExtraLight", "Light", "Regular", "Medium",
            "SemiBold", "Bold", "ExtraBold", "Black",
            "Thin Italic", "ExtraLight Italic", "Light Italic", "Italic",
            "Medium Italic", "SemiBold Italic", "Bold Italic", "ExtraBold Italic", "Black Italic",
        ]
        sorted_styles = sorted(
            styles,
            key=lambda value: (style_order.index(value) if value in style_order else len(style_order), value.casefold()),
        )
        self.style_combo.blockSignals(True)
        self.style_combo.clear()
        self.style_combo.addItems(sorted_styles)
        preferred = preferred_style or self.selected_font_style
        if preferred in styles:
            self.selected_font_style = preferred
        else:
            self.selected_font_style = sorted_styles[0]
        self.style_combo.setCurrentText(self.selected_font_style)
        self.style_combo.setVisible(len(sorted_styles) > 1)
        self.style_combo.blockSignals(False)
        self._schedule_preview()

    def normalize_font_input(self) -> None:
        if self._loading_settings:
            return
        text = self.font_edit.text().strip()
        if not text:
            return
        if Path(text).is_file():
            return
        family = next((name for name in self.fonts_data if name.casefold() == text.casefold()), None)
        if family is None:
            prefix = text.casefold()
            matches = [name for name in self.fonts_data if name.casefold().startswith(prefix)]
            family = min(matches, key=len) if matches else None
        if family:
            self.font_edit.blockSignals(True)
            self.font_edit.setText(family)
            self.font_edit.blockSignals(False)
            self.apply_font_family(family)
        else:
            # Не позволяем старому выбору молча использоваться при генерации.
            self.font_path = ""
            self.selected_font_family = ""
            self.selected_font_style = "Regular"
            self.style_combo.clear()
            self.style_combo.setVisible(False)
            self.status_label.setText(f"Шрифт «{text}» не найден")
            self._schedule_preview()

    def _on_auto_toggled(self, _checked: bool = False) -> None:
        auto_x = self.x_auto_check.isChecked()
        auto_y = self.y_auto_check.isChecked()
        self.x_edit.setEnabled(not auto_x)
        self.y_edit.setEnabled(not auto_y)
        self._schedule_preview()

    def _set_name_mode(self, mode: str) -> None:
        for button in self.name_mode_group.buttons():
            if button.property("mode") == mode:
                button.setChecked(True)
                self._update_name_controls()
                return
        buttons = self.name_mode_group.buttons()
        if buttons:
            buttons[0].setChecked(True)
        self._update_name_controls()

    def _update_name_controls(self, _checked: bool = False) -> None:
        self.split_after_spin.setEnabled(self.get_name_mode() == "custom")

    def get_name_mode(self) -> str:
        for button in self.name_mode_group.buttons():
            if button.isChecked():
                return str(button.property("mode"))
        return "single_line"

    def get_align(self) -> str:
        if self.rb_center.isChecked():
            return "center"
        if self.rb_right.isChecked():
            return "right"
        return "left"

    def get_output_format(self) -> str:
        return "png" if self.rb_png.isChecked() else "pdf"

    def get_pdf_mode(self) -> str:
        return "multi" if self.rb_multi.isChecked() else "single"

    def get_preview_mode(self) -> str:
        if self.rb_preview_longest.isChecked():
            return "longest"
        if self.rb_preview_custom.isChecked():
            return "custom"
        return "test"

    def _update_output_controls(self, _checked: bool = False) -> None:
        is_pdf = self.rb_pdf.isChecked()
        is_single = self.rb_single.isChecked()
        self.rb_multi.setEnabled(is_pdf)
        self.rb_single.setEnabled(is_pdf)
        self.pdf_name_edit.setEnabled(is_pdf and is_single)
        self.preview_custom_edit.setEnabled(self.rb_preview_custom.isChecked())
        self._schedule_preview()

    def choose_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для сохранения",
            self.output_dir_edit.text() or self._default_output_dir(),
            options=QFileDialog.DontUseNativeDialog,
        )
        if path:
            self._set_path_text(self.output_dir_edit, path)

    # ------------------------------------------------------------------
    # Шрифт и шаблон
    # ------------------------------------------------------------------
    def get_font_path(self) -> str:
        if self.font_path and Path(self.font_path).is_file():
            return self.font_path
        if self.selected_font_family:
            path = resolve_font_path(self.fonts_data, self.selected_font_family, self.selected_font_style)
            if path:
                return path
        text = self.font_edit.text().strip()
        if text and Path(text).is_file() and Path(text).suffix.lower() in {".ttf", ".otf", ".ttc"}:
            self.font_path = text
            self.selected_font_family = ""
            return text
        if text:
            path = resolve_font_path(self.fonts_data, text, self.selected_font_style)
            if path:
                return path
        raise ValueError("Шрифт не выбран или файл шрифта не найден.")

    def get_font(self) -> ImageFont.FreeTypeFont:
        path = self.get_font_path()
        size = self.font_size_spin.value()
        key = (path, size)
        font = self._font_cache.get(key)
        if font is None:
            try:
                font = ImageFont.truetype(path, size=size)
            except Exception as exc:
                raise ValueError(f"Не удалось загрузить шрифт «{Path(path).name}»: {exc}") from exc
            if len(self._font_cache) > 24:
                self._font_cache.clear()
            self._font_cache[key] = font
        return font

    def _get_template(self):
        if not self.template_path or not Path(self.template_path).is_file():
            raise ValueError("Выберите существующий шаблон грамоты.")
        stat = Path(self.template_path).stat()
        key = (str(Path(self.template_path).resolve()), stat.st_mtime_ns, stat.st_size)
        if self._template_cache is not None and self._template_cache[0] == key:
            return self._template_cache[1], self._template_cache[2]
        template, dpi = load_template(self.template_path)
        self._template_cache = (key, template, dpi)
        return template, dpi

    def get_render_config(self) -> RenderConfig:
        return RenderConfig(
            font_path=self.get_font_path(),
            font_size=self.font_size_spin.value(),
            text_color=tuple(self.text_color),
            x="center" if self.x_auto_check.isChecked() else self.x_edit.value(),
            y="center" if self.y_auto_check.isChecked() else self.y_edit.value(),
            x_offset=self.x_offset_spin.value(),
            y_offset=self.y_offset_spin.value(),
            align=self.get_align(),
            line_spacing=self.line_spacing_spin.value(),
            letter_spacing=self.letter_spacing_spin.value(),
            margin=self.margin_spin.value(),
            name_mode=self.get_name_mode(),
            split_after=self.split_after_spin.value(),
        )

    def get_names_list(self) -> list[list[str]]:
        return self.names_editor.people()

    def is_person_in_list(self, person_parts: list[str], people_list: list[list[str]]) -> bool:
        key = " ".join(person_parts).casefold()
        return any(" ".join(item).casefold() == key for item in people_list)

    # ------------------------------------------------------------------
    # Предпросмотр
    # ------------------------------------------------------------------
    def _schedule_preview(self) -> None:
        if not self._loading_settings and not self._is_generating():
            self._preview_timer.start()

    def _connect_preview_signals(self) -> None:
        self.font_size_spin.valueChanged.connect(self._schedule_preview)
        self.letter_spacing_spin.valueChanged.connect(self._schedule_preview)
        self.x_edit.valueChanged.connect(self._schedule_preview)
        self.y_edit.valueChanged.connect(self._schedule_preview)
        self.x_offset_spin.valueChanged.connect(self._schedule_preview)
        self.y_offset_spin.valueChanged.connect(self._schedule_preview)
        self.line_spacing_spin.valueChanged.connect(self._schedule_preview)
        self.split_after_spin.valueChanged.connect(self._schedule_preview)
        self.margin_spin.valueChanged.connect(self._schedule_preview)
        for button in self.align_group.buttons():
            button.toggled.connect(self._schedule_preview)
        for button in self.name_mode_group.buttons():
            button.toggled.connect(self._schedule_preview)
            button.toggled.connect(self._update_name_controls)
        for button in self.preview_group.buttons():
            button.toggled.connect(self._schedule_preview)
        self.preview_custom_edit.textChanged.connect(self._schedule_preview)
        self.names_editor.changed.connect(self._schedule_preview)
        self.style_combo.currentTextChanged.connect(self._schedule_preview)
        for button in (self.rb_png, self.rb_pdf, self.rb_multi, self.rb_single):
            button.toggled.connect(self._schedule_preview)

        # Системная тема может меняться на лету.
        with suppress(AttributeError, TypeError):
            QApplication.instance().styleHints().colorSchemeChanged.connect(self._on_system_theme_changed)

    def _on_system_theme_changed(self, _scheme=None) -> None:
        if self.rb_system.isChecked():
            self._apply_theme(self._resolve_theme("system"))

    def _on_names_changed(self) -> None:
        self._update_generate_button()

    def _update_generate_button(self) -> None:
        count = self.names_editor.count()
        generating = self._is_generating()
        if count:
            self.generate_btn.setText(f"Сгенерировать {count} {plural(count, ('грамоту', 'грамоты', 'грамот'))}")
        else:
            self.generate_btn.setText("Сгенерировать грамоты")
        self.generate_btn.setEnabled(count > 0 and not generating)
        self.generate_btn.setToolTip("" if count else "Добавьте хотя бы одно ФИО")
        if hasattr(self, "action_generate"):
            self.action_generate.setEnabled(count > 0 and not generating)
        self.preview_pane.open_button.setEnabled(count > 0 and not generating)

    def get_preview_parts(self, people: list[list[str]]) -> list[str]:
        mode = self.get_preview_mode()
        if mode == "longest" and people:
            return max(people, key=lambda item: sum(len(word) for word in item))
        if mode == "custom":
            text = self.preview_custom_edit.text().strip()
            if text:
                return text.split()
        return ["Иванов", "Иван", "Иванович"]

    def _make_preview_image(self, people: list[list[str]] | None = None, *, allow_empty: bool = False):
        if not self.template_path or not Path(self.template_path).is_file():
            raise ValueError("Выберите шаблон грамоты.")
        template, _dpi = self._get_template()
        font = self.get_font()
        people = people if people is not None else self.get_names_list()
        if not people:
            if not allow_empty:
                raise ValueError("Добавьте список ФИО.")
            people = [["Иванов", "Иван", "Иванович"]]
        parts = self.get_preview_parts(people)
        config = self.get_render_config()
        return render_page(template, parts, font, config)

    def update_live_preview(self) -> None:
        if self._is_generating():
            return
        if not self.template_path or not Path(self.template_path).is_file():
            self.preview_pane.set_message("Выберите шаблон грамоты")
            return
        try:
            self.get_font_path()
        except ValueError:
            self.preview_pane.set_message("Выберите шрифт")
            return
        try:
            image = self._make_preview_image(allow_empty=True)
        except Exception as exc:
            log.debug("Живой предпросмотр недоступен: %s", exc)
            self.preview_pane.set_message(str(exc))
            return
        self.preview_pane.set_image(image)

    def make_preview(self, people: list[list[str]] | None = None) -> bool:
        try:
            image = self._make_preview_image(people)
        except Exception as exc:
            self._message("Ошибка предпросмотра", str(exc), [("ОК", "primary")])
            return False
        self.preview_image = image
        self.status_label.setText("Предпросмотр создан")
        return True

    def show_preview_dialog(self) -> int:
        if self.preview_image is None and not self.make_preview():
            return QDialog.Rejected
        dialog = PreviewDialog(self.preview_image, self)
        self.apply_theme_to_dialog(dialog, self.current_theme)
        return int(dialog.exec())

    def open_preview(self) -> None:
        if not self.get_names_list():
            self._message("Предпросмотр", "Добавьте хотя бы одно ФИО.", [("ОК", "primary")])
            return
        if not self.make_preview():
            return
        dialog = PreviewDialog(self.preview_image, self)
        self.apply_theme_to_dialog(dialog, self.current_theme)
        result = dialog.exec()
        if result == 2:
            self.pick_position()
            if self.make_preview():
                self.show_preview_dialog()

    def pick_position(self) -> None:
        if not self.template_path or not Path(self.template_path).is_file():
            self._message("Ошибка", "Сначала выберите шаблон грамоты.", [("ОК", "primary")])
            return
        initial_x = None if self.x_auto_check.isChecked() else self.x_edit.value()
        initial_y = None if self.y_auto_check.isChecked() else self.y_edit.value()
        try:
            render_config = self.get_render_config()
        except ValueError:
            render_config = None
        preview_parts = self.get_preview_parts(self.get_names_list())
        try:
            dialog = PointPickerDialog(
                self.template_path,
                self,
                initial_x,
                initial_y,
                self.get_align(),
                render_config=render_config,
                preview_parts=preview_parts,
            )
        except Exception as exc:
            self._error(f"Не удалось открыть шаблон: {exc}")
            return
        self.apply_theme_to_dialog(dialog, self.current_theme)
        if dialog.exec() == QDialog.Accepted:
            x, y = dialog.get_point()
            # Выбор точки — это явное указание позиции, поэтому автоцентр
            # отключаем: иначе выбранные координаты молча игнорировались бы.
            self.x_auto_check.setChecked(False)
            self.y_auto_check.setChecked(False)
            self.x_edit.setValue(max(0, x))
            self.y_edit.setValue(max(0, y))
            self._schedule_preview()

    def reset_position(self) -> None:
        self.x_auto_check.setChecked(True)
        self.y_auto_check.setChecked(True)
        self.x_edit.setValue(0)
        self.y_edit.setValue(0)
        self.x_offset_spin.setValue(0)
        self.y_offset_spin.setValue(0)
        self.line_spacing_spin.setValue(4)
        self.rb_left.setChecked(True)
        self._schedule_preview()

    # ------------------------------------------------------------------
    # Списки
    # ------------------------------------------------------------------
    def load_names_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл со списком",
            str(Path.home()),
            "Текст (*.txt *.csv);;Все файлы (*)",
            options=QFileDialog.DontUseNativeDialog,
        )
        if not path:
            return
        try:
            new_content = read_text_file(path).replace("\r\n", "\n").replace("\r", "\n").strip()
        except (OSError, UnicodeError) as exc:
            self._message("Ошибка чтения", str(exc), [("ОК", "primary")])
            return
        if not new_content:
            self._message("Загрузка списка", "Файл пуст.", [("ОК", "primary")])
            return

        if self.names_editor.count():
            answer = self._message(
                "Загрузка списка",
                "Текущий список не пуст. Что сделать?",
                [("Заменить", "primary"), ("Добавить в конец", ""), ("Отмена", "")],
            )
            if answer == 0:
                self.names_editor.set_text(new_content)
            elif answer == 1:
                self.names_editor.append(new_content)
            else:
                return
        else:
            self.names_editor.set_text(new_content)
        self.names_editor.search_edit.clear()
        self.status_label.setText(f"Загружен список: {Path(path).name}")

    def move_excluded_to_main(self) -> None:
        excluded = self.excluded_editor.people()
        if not excluded:
            return
        # Снимаем фильтр, иначе добавленные строки останутся скрытыми.
        self.names_editor.search_edit.clear()
        current = self.names_editor.people()
        if self.ask_before_move.isChecked():
            answer = self._message(
                "Перенос исключений",
                "Как перенести исключения в основной список?",
                [
                    ("Добавить отсутствующие", "primary"),
                    ("Заменить основной список", ""),
                    ("Отмена", ""),
                ],
            )
            if answer == 0:
                missing = [parts for parts in excluded if not self.is_person_in_list(parts, current)]
                if missing:
                    self.names_editor.append("\n".join(" ".join(parts) for parts in missing))
                self.excluded_editor.clear()
                self.status_label.setText("Исключения перенесены")
                return
            if answer == 1:
                self.names_editor.set_text("\n".join(" ".join(parts) for parts in excluded))
                self.excluded_editor.clear()
                self.status_label.setText("Основной список заменён исключениями")
                return
            return

        missing = [parts for parts in excluded if not self.is_person_in_list(parts, current)]
        if missing:
            self.names_editor.append("\n".join(" ".join(parts) for parts in missing))
        self.excluded_editor.clear()

    def _merge_excluded(self, people: list[list[str]]) -> None:
        existing = self.excluded_editor.people()
        keys = {" ".join(item).casefold() for item in existing}
        for parts in people:
            key = " ".join(parts).casefold()
            if key not in keys:
                existing.append(parts)
                keys.add(key)
        self.excluded_editor.set_text("\n".join(" ".join(parts) for parts in existing))
        self.excluded_editor.search_edit.clear()

    # ------------------------------------------------------------------
    # Генерация
    # ------------------------------------------------------------------
    def _validate_before_generation(self) -> bool:
        if not self.template_path or not Path(self.template_path).is_file():
            return self._error("Выберите существующий шаблон грамоты.")
        if not self.get_names_list():
            return self._error("Добавьте список ФИО.")
        if self.font_size_spin.value() <= 0:
            return self._error("Укажите положительный размер шрифта.")
        try:
            self.get_font_path()
        except ValueError as exc:
            return self._error(str(exc))
        return True

    def _collect_lines(self, people: list[list[str]], font, img_width: int) -> dict[tuple[str, ...], list[str]]:
        config = self.get_render_config()
        result: dict[tuple[str, ...], list[str]] = {}
        for parts in people:
            lines = format_name_lines(parts, config.name_mode, config.split_after)
            if lines is None:
                lines = resolve_auto_lines(
                    parts,
                    font,
                    config.letter_spacing,
                    img_width,
                    config.margin,
                )
            result[tuple(parts)] = lines
        return result

    def _find_problematic(self, people: list[list[str]], font, img_width: int, img_height: int):
        config = self.get_render_config()
        lines_by_key = self._collect_lines(people, font, img_width)
        problematic = []
        for parts in people:
            lines = lines_by_key[tuple(parts)]
            problems = check_text_bounds(
                lines,
                font,
                config.x,
                config.align,
                config.letter_spacing,
                img_width,
                config.margin,
                img_height=img_height,
                y=config.y,
                x_offset=config.x_offset,
                y_offset=config.y_offset,
                line_spacing=config.line_spacing,
            )
            if problems:
                problematic.append((parts, problems))
        return problematic, lines_by_key

    def _existing_output_count(self, people: list[list[str]], output_dir: Path, fmt: str) -> int:
        suffix = ".png" if fmt == "png" else ".pdf"
        seen: dict[str, Path] = {}
        for parts in people:
            path = output_dir / f"{safe_stem_from_parts(parts)}{suffix}"
            seen.setdefault(path.name.casefold(), path)
        return sum(1 for path in seen.values() if path.exists())

    def generate_all(self) -> None:
        if self._is_generating():
            return
        if not self._validate_before_generation():
            return

        try:
            template, _dpi = self._get_template()
            font = self.get_font()
            output_dir = ensure_output_dir(self.output_dir_edit.text().strip() or self._default_output_dir())
        except Exception as exc:
            self._error(str(exc))
            return
        self._set_path_text(self.output_dir_edit, str(output_dir))

        people = self.get_names_list()
        seen: set[str] = set()
        duplicates: list[list[str]] = []
        unique: list[list[str]] = []
        for parts in people:
            key = " ".join(parts).casefold()
            if key in seen:
                duplicates.append(parts)
            else:
                seen.add(key)
                unique.append(parts)

        if duplicates:
            message = f"Найдены дубликаты ({len(duplicates)}):\n\n"
            message += "\n".join(f"• {' '.join(parts)}" for parts in duplicates[:12])
            if len(duplicates) > 12:
                message += f"\n…и ещё {len(duplicates) - 12}"
            answer = self._message(
                "Дубликаты в списке",
                message,
                [("Продолжить", "primary"), ("Удалить дубликаты", ""), ("Отмена", "")],
            )
            if answer == 1:
                people = unique
                self.names_editor.set_text("\n".join(" ".join(parts) for parts in people))
            elif answer != 0:
                self.status_label.setText("Отменено пользователем")
                return

        try:
            font = self.get_font()
            img_width, img_height = template.size
            problematic, _lines = self._find_problematic(people, font, img_width, img_height)
        except Exception as exc:
            self._error(str(exc))
            return

        generated_people = people
        if problematic:
            message = f"Текст выходит за границы safe area у {len(problematic)} грамот:\n\n"
            for parts, problems in problematic[:12]:
                details = "; ".join(
                    f"{text or 'блок'}: +{overflow}px ({side})"
                    for text, overflow, side in problems
                )
                message += f"• {' '.join(parts)} — {details}\n"
            if len(problematic) > 12:
                message += f"\n…и ещё {len(problematic) - 12}"
            answer = self._message(
                "Текст выходит за границы",
                message,
                [("Сделать все", "primary"), ("Только корректные", ""), ("Отмена", "")],
            )
            if answer == 1:
                bad_keys = {tuple(parts) for parts, _ in problematic}
                generated_people = [parts for parts in people if tuple(parts) not in bad_keys]
                self._merge_excluded([parts for parts, _ in problematic])
                if not generated_people:
                    self._error("Нет ни одной грамоты, которая помещается в границы.")
                    return
            elif answer != 0:
                self.status_label.setText("Отменено пользователем")
                return

        if self.preview_check.isChecked():
            while True:
                if not self.make_preview(generated_people):
                    return
                result = self.show_preview_dialog()
                if result == QDialog.Rejected:
                    self.status_label.setText("Отменено пользователем")
                    return
                if result == 2:
                    self.pick_position()
                    continue
                break

        policy = "number"
        fmt = self.get_output_format()
        if fmt == "pdf" and self.get_pdf_mode() == "single":
            stem = safe_pdf_stem(self.pdf_name_edit.text())
            target = output_dir / f"{stem}.pdf"
            if target.exists():
                answer = self._message(
                    "Файл уже существует",
                    f"Файл «{target.name}» уже существует. Что сделать?",
                    [
                        ("Заменить", "primary"),
                        ("Создать с номером", ""),
                        ("Пропустить", ""),
                        ("Отмена", ""),
                    ],
                )
                if answer == 0:
                    policy = "replace"
                elif answer == 1:
                    policy = "number"
                elif answer == 2:
                    policy = "skip"
                else:
                    self.status_label.setText("Отменено пользователем")
                    return
            else:
                policy = "replace"
        else:
            existing = self._existing_output_count(generated_people, output_dir, fmt)
            if existing:
                answer = self._message(
                    "Файлы уже существуют",
                    f"В папке уже есть {existing} файл(ов) с такими именами.\n"
                    "Что сделать со всеми?",
                    [
                        ("Заменить все", "primary"),
                        ("Создать с номерами", ""),
                        ("Пропустить существующие", ""),
                        ("Отмена", ""),
                    ],
                )
                if answer == 0:
                    policy = "replace"
                elif answer == 1:
                    policy = "number"
                elif answer == 2:
                    policy = "skip"
                else:
                    self.status_label.setText("Отменено пользователем")
                    return

        # Очистка выполняется только после всех подтверждений, чтобы отмена
        # предпросмотра или выбора конфликта не удаляла старые файлы.
        if self.cleanup_previous_check.isChecked():
            managed = load_manifest(output_dir)
            try:
                template_resolved = Path(self.template_path).resolve()
                managed = [
                    item for item in managed
                    if (output_dir / item).resolve() != template_resolved
                ]
            except OSError:
                pass
            if managed:
                answer = self._message(
                    "Очистка предыдущих файлов",
                    f"Удалить {len(managed)} файл(ов), созданных AutoFill ранее?\n"
                    "Чужие файлы и папки не затрагиваются.",
                    [("Удалить", ""), ("Отмена", "primary")],
                    default_btn=1,
                )
                if answer != 0:
                    self.status_label.setText("Отменено пользователем")
                    return
                removed, errors = cleanup_manifest(output_dir, exclude=self.template_path)
                if errors:
                    self._message("Очистка", "\n".join(errors[:15]), [("ОК", "primary")])
                self.status_label.setText(f"Удалено ранее созданных файлов: {removed}")
            self.cleanup_previous_check.setChecked(False)

        try:
            render_config = self.get_render_config()
            output_config = OutputConfig(
                output_dir=str(output_dir),
                output_format=fmt,
                pdf_mode=self.get_pdf_mode(),
                pdf_name=self.pdf_name_edit.text().strip() or "Все_грамоты",
                conflict_policy=policy,
                cleanup_previous=False,
            )
            job = GenerationJob(
                template_path=str(self.template_path),
                people=tuple(tuple(parts) for parts in generated_people),
                render=render_config,
                output=output_config,
            )
        except Exception as exc:
            self._error(str(exc))
            return
        self._start_generation(job)

    def _start_generation(self, job: GenerationJob) -> None:
        self._thread = QThread(self)
        self._worker = GenerationWorker(job)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_generation_progress)
        self._worker.finished.connect(self._on_generation_finished)
        self._worker.failed.connect(self._on_generation_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._set_generating(True)
        self.progress_bar.setRange(0, len(job.people))
        self.progress_bar.setValue(0)
        self.status_label.setText("Генерация…")
        self._thread.start()

    def _set_generating(self, active: bool) -> None:
        self.tabs.setEnabled(not active)
        self.generate_btn.setEnabled(not active)
        self.action_generate.setEnabled(not active)
        self.action_preview.setEnabled(not active)
        self.cancel_btn.setVisible(active)
        self.progress_bar.setVisible(active)
        self.open_dir_btn.setEnabled(not active)
        self.preview_pane.setEnabled(not active)
        if not active:
            self.cancel_btn.setEnabled(True)

    def _on_generation_progress(self, done: int, total: int, name: str) -> None:
        self.progress_bar.setRange(0, max(1, total))
        self.progress_bar.setValue(min(done, total))
        if name:
            self.status_label.setText(f"Генерация: {done}/{total} — {name}")
        else:
            self.status_label.setText(f"Генерация: {done}/{total}")

    def _stop_worker_thread(self) -> None:
        thread = self._thread
        if thread is not None:
            thread.quit()
            if thread.isRunning():
                thread.wait(15000)
            thread.deleteLater()
        self._thread = None
        self._worker = None

    def _on_generation_finished(self, result) -> None:
        self._stop_worker_thread()
        self._set_generating(False)
        self.generate_btn.setEnabled(True)
        self._update_generate_button()

        if getattr(result, "cancelled", False):
            self.status_label.setText("Генерация отменена")
            self._message("Генерация", "Генерация отменена.", [("ОК", "primary")])
            self._schedule_preview()
            return

        output_dir = getattr(result, "output_dir", self.output_dir_edit.text())
        self.open_dir_btn.setVisible(True)
        word = plural(result.created, ("грамота", "грамоты", "грамот"))
        self.status_label.setText(f"Готово: {result.created} {word} — {output_dir}")

        lines = [
            f"Создано: {result.created} {plural(result.created, ('грамота', 'грамоты', 'грамот'))}",
            f"Пропущено: {result.skipped}",
        ]
        if result.errors:
            lines.append(f"Ошибок: {len(result.errors)}")
            lines.append("")
            for name, error in result.errors[:10]:
                lines.append(f"• {name}: {error}")
            if len(result.errors) > 10:
                lines.append(f"…и ещё {len(result.errors) - 10}")
        if result.files:
            lines.append("")
            lines.append(f"Файлов создано: {len(result.files)}")
            if len(result.files) == 1:
                lines.append(Path(result.files[0]).name)
        lines.append("")
        lines.append(f"Папка: {output_dir}")

        answer = self._message(
            "Готово",
            "\n".join(lines),
            [("Открыть папку", "primary"), ("Закрыть", "")],
        )
        if answer == 0:
            self.open_output_dir()
        self._schedule_preview()

    def _on_generation_failed(self, details: str) -> None:
        self._stop_worker_thread()
        self._set_generating(False)
        self._update_generate_button()
        self.status_label.setText("Ошибка генерации")
        self._message("Ошибка генерации", details, [("ОК", "primary")])
        self._schedule_preview()

    def cancel_generation(self) -> None:
        if self._worker:
            self._worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.status_label.setText("Отмена…")

    def _is_generating(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    # ------------------------------------------------------------------
    # Вспомогательные диалоги
    # ------------------------------------------------------------------
    def _message(
        self,
        title: str,
        text: str,
        buttons: list[tuple[str, str]] | None = None,
        default_btn: int = 0,
    ) -> int | None:
        dialog = MessageDialog(self, title, text, buttons=buttons, default_btn=default_btn)
        self.apply_theme_to_dialog(dialog, self.current_theme)
        dialog.exec()
        return dialog.clicked_index

    def _error(self, text: str) -> bool:
        self._message("Ошибка", text, [("ОК", "primary")])
        return False

    def open_output_dir(self) -> None:
        try:
            path = ensure_output_dir(self.output_dir_edit.text().strip() or self._default_output_dir())
        except Exception as exc:
            self._error(str(exc))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # ------------------------------------------------------------------
    # Справка
    # ------------------------------------------------------------------
    def show_help(self) -> None:
        text = """КАК РАБОТАТЬ С ПРОГРАММОЙ

1. Выберите шаблон грамоты (JPG или PNG).
2. Выберите шрифт из списка или укажите TTF/OTF/TTC-файл.
3. Задайте размер, цвет и межбуквенный интервал.
4. Вставьте список ФИО — каждая строка один человек.
5. Настройте позицию во вкладке «Позиция» или укажите точку на шаблоне.
6. Нажмите «Сгенерировать».

ПРЕДПРОСМОТР

Справа всегда показывается живой предпросмотр. Двойной клик по нему или F5
открывает окно с масштабом. Перед генерацией можно включить отдельное окно
подтверждения.

ПОИСК В СПИСКЕ

Поиск показывает только совпавшие строки. Пока поиск активен, список доступен
только для чтения — это защищает скрытые строки от потери. Очистите поиск,
чтобы редактировать.

ИСКЛЮЧЕНИЯ

ФИО, не влезшие в границы, можно перенести обратно в основной список.
Перенос не стирает основной список без явного выбора.

БЕЗОПАСНОСТЬ ФАЙЛОВ

AutoFill никогда не очищает всю папку. Удаляются только файлы, перечисленные
в манифесте предыдущих запусков. Существующие файлы можно заменить, пронумеровать
или пропустить — решение принимается один раз для всей пачки.

Горячие клавиши: Ctrl+O — шаблон, Ctrl+Shift+O — список, Ctrl+G — генерация,
F5 — предпросмотр, Esc — отмена генерации.

Настройки сохраняются при выходе (или кнопкой в разделе «Настройки»)."""
        self._message("Инструкция", text, [("Понятно", "primary")])

    def show_license(self) -> None:
        text = """AutoFill

Required Notice: Copyright (c) 2026 TWorker and Maxim Odincov. All rights reserved.

Polyform Noncommercial License 1.0.0
https://polyformproject.org/licenses/noncommercial/1.0.0"""
        self._message("Лицензия", text, [("Закрыть", "primary")])

    def show_about(self) -> None:
        text = f"""AutoFill {__version__}

Массовое заполнение грамот ФИО.

Авторы:
Alexey «TWorker» Zhaliy
Maxim «jojer» Odincov

Polyform Noncommercial License 1.0.0"""
        self._message("О программе", text, [("Закрыть", "primary")])
