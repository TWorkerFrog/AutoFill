"""Английские строки интерфейса AutoFill.

Ключ - исходная русская строка, значение - английский перевод.  Строки с
фигурными скобками используются как шаблоны вместе с ``str.format``.
"""

EN: dict[str, str] = {
    # Общие подписи и кнопки
    "Авто (по доступной ширине)": "Auto (fit available width)",
    "Авто по X": "Auto X",
    "Авто по Y": "Auto Y",
    "Автопозиция по X: прижать блок к выбранному краю или центру": (
        "Auto X: align the block to the selected edge or center"
    ),
    "Авторы: Alexey «TWorker» Zhaliy, Maxim «jojer» Odincov": (
        "Authors: Alexey «TWorker» Zhaliy, Maxim «jojer» Odincov"
    ),
    "Автоцентр по X": "Auto center X",
    "Автоцентр по Y": "Auto center Y",
    "В одну строку": "Single line",
    "В режиме «Авто» текст переносится по словам на любое число строк с учётом "
    "выбранного шрифта и полей для печати. Проверка границ учитывает смещения и "
    "вертикальные края.": (
        "In Auto mode the text wraps by words to any number of lines using the "
        "selected font and print margins. Bounds checking takes offsets and "
        "vertical edges into account."
    ),
    "В центр": "Center",
    "Выбрать папку сохранения": "Choose output folder",
    "Выбрать папку сохранения…": "Choose output folder…",
    "Выбрать файл шрифта": "Choose font file",
    "Выбрать цвет крестика": "Choose marker color",
    "Выбрать цвет линии полей для печати": "Choose print margin line color",
    "Выбрать цвет текста": "Choose text color",
    "Выбрать шаблон": "Choose template",
    "Выбрать шаблон…": "Choose template…",
    "Изображения (*.jpg *.jpeg *.png)": "Images (*.jpg *.jpeg *.png)",
    "Шрифты (*.ttf *.otf *.ttc)": "Fonts (*.ttf *.otf *.ttc)",
    "Выберите папку для сохранения": "Choose an output folder",
    "Выберите файл со списком": "Choose a name list file",
    "Выберите файл шрифта": "Choose a font file",
    "Выберите шаблон грамоты": "Choose a diploma template",
    "Формат ввода цвета": "Color input format",
    "Текст (*.txt *.csv);;Все файлы (*)": "Text (*.txt *.csv);;All files (*)",
    "PNG: отдельный файл для каждого ФИО": "PNG: a separate file for each name",
    "AutoFill запоминает созданные им файлы в манифесте "
    ".autofill-manifest.json внутри папки вывода. Удаляются только они: "
    "шаблон, ваши и чужие файлы, а также папки не затрагиваются.": (
        "AutoFill remembers the files it creates in the .autofill-manifest.json "
        "manifest inside the output folder. Only those files are deleted: the "
        "template, your files, other files and folders are left untouched."
    ),
    "Вывод": "Output",
    "Выравнивание строк:": "Line alignment:",
    "Выход": "Exit",
    "Готов к работе": "Ready",
    "Двойной клик: открыть редактор": "Double click: open editor",
    "Живой предпросмотр": "Live preview",
    "Загрузить список ФИО": "Load name list",
    "Загрузить список ФИО…": "Load name list…",
    "Загрузить файл": "Load file",
    "Имя": "Name",
    "Имя общего PDF:": "Shared PDF name:",
    "Инструкция": "Help",
    "Интервал": "Spacing",
    "Интервал:": "Spacing:",
    "Исключения": "Excluded",
    "Каждое слово отдельно": "Each word separately",
    "Каждому свой файл": "One file per person",
    "Крестик": "Marker",
    "Линия": "Line",
    "Лицензия": "License",
    "Межбуквенный интервал": "Letter spacing",
    "Межстрочный интервал:": "Line spacing:",
    "Название шрифта или путь к TTF/OTF…": "Font family or TTF/OTF path…",
    "Настройки": "Settings",
    "Начертание": "Style",
    "Начертание выбранного семейства": "Style of the selected family",
    "О программе": "About",
    "Обзор": "Browse",
    "Один общий PDF": "One shared PDF",
    "Основные": "Main",
    "Открывать редактор перед генерацией": "Open editor before generation",
    "Открыть папку": "Open folder",
    "Открыть редактор": "Open editor",
    "Открыть редактор грамоты": "Open diploma editor",
    "Отмена": "Cancel",
    "Отступ от краёв, за который не должен выходить текст при печати. "
    "0 означает отсутствие ограничения.": (
        "Margin from the edges that printed text must not cross. "
        "0 means no limit."
    ),
    "Очистить": "Clear",
    "ПЕЧАТЬ": "PRINT",
    "ПОЛОЖЕНИЕ": "POSITION",
    "Папка:": "Folder:",
    "Параметры переноса": "Wrap settings",
    "Перенести в основной список": "Move to main list",
    "По левому краю": "Left",
    "По правому краю": "Right",
    "По размеру": "Fit",
    "По центру": "Center",
    "Позиция": "Position",
    "Поиск по списку...": "Search list...",
    "Показывает границу полей для печати. Текст не должен выходить за неё.": (
        "Shows the print margin line. Text must stay inside it."
    ),
    "Показывать поля для печати": "Show print margins",
    "Поля": "Margin",
    "Поля для печати:": "Print margins:",
    "Привязка блока": "Block anchor",
    "Применить": "Apply",
    "Путь до файла с грамотой (JPG/PNG)…": "Path to the diploma file (JPG/PNG)…",
    "Размер": "Size",
    "Размер:": "Size:",
    "Редактировать": "Edit",
    "Редактор грамоты": "Diploma editor",
    "Режим формирования ФИО": "Name layout mode",
    "Самое длинное из списка": "Longest from the list",
    "Сбросить оформление": "Reset style",
    "Сбросить позицию": "Reset position",
    "Светлая": "Light",
    "Свой вариант (сколько слов на первой строке)": "Custom (words on first line)",
    "Свой текст:": "Custom text:",
    "Сгенерировать": "Generate",
    "Сдвиг блока:": "Block offset:",
    "Системная": "System",
    "Сколько ФИО в списке": "Number of names in the list",
    "Слева": "Left",
    "Слов на первой строке:": "Words on first line:",
    "Смещение и интервалы": "Offset and spacing",
    "Сохранение": "Saving",
    "Сохранить настройки сейчас": "Save settings now",
    "Сброс настроек": "Reset settings",
    "Сбросить": "Reset",
    "Сбросить настройки": "Reset settings",
    "Настройки изменились. Сохранить их перед выходом?": (
        "Settings changed. Save them before exiting?"
    ),
    "Настройки сброшены": "Settings reset",
    "Вернуть все настройки к значениям по умолчанию?": (
        "Restore all settings to their defaults?"
    ),
    "Непрозрачность в процентах": "Opacity in percent",
    "Список ФИО (каждая строка: один человек)": "Name list (one person per line)",
    "Справа": "Right",
    "Спрашивать перед переносом исключений": "Ask before moving excluded names",
    "ТЕКСТ": "TEXT",
    "Текст в редакторе": "Text in editor",
    "Тема оформления": "Theme",
    "Тестовое имя (Иванов Иван Иванович)": "Test name (Ivanov Ivan Ivanovich)",
    "Тёмная": "Dark",
    "Увеличить": "Zoom in",
    "Удалить файлы, созданные AutoFill при прошлых генерациях": (
        "Delete files created by AutoFill in previous runs"
    ),
    "Уменьшить": "Zoom out",
    "Файлы настроек": "Settings files",
    "Фамилия / Имя Отчество": "Surname / First Patronymic",
    "Формат": "Format",
    "Цвет": "Color",
    "Цвет:": "Color:",
    "Центр": "Center",
    "Центрировать текст по вертикали, игнорируя Y точки": (
        "Center text vertically, ignoring marker Y"
    ),
    "Шаблон и шрифт": "Template and font",
    "Шаблон:": "Template:",
    "Шрифт": "Font",
    "Шрифт:": "Font:",
    "Язык интерфейса": "Interface language",
    "Русский": "Russian",
    "Английский": "English",
    "Язык": "Language",
    "Перезапустить сейчас": "Restart now",
    "Позже": "Later",
    "Смена языка": "Language change",
    "Чтобы применить язык, приложение нужно перезапустить.": (
        "The application must restart to apply the language."
    ),
    "Не удалось перезапустить приложение. Закройте и откройте его вручную.": (
        "Could not restart the application. Close and open it manually."
    ),
    # Подсказки редактора
    "ПКМ: поставить и тянуть крестик": "Right click: place and drag marker",
    "ЛКМ + перетаскивание: двигать изображение": "Left drag: move image",
    "Колесо: масштаб": "Wheel: zoom",
    "Стрелки: сдвиг на 1 px": "Arrows: move by 1 px",
    "Shift + стрелки: 10 px": "Shift + arrows: 10 px",
    "Ctrl + стрелки: 50 px": "Ctrl + arrows: 50 px",
    "Alt: расстояние до крестика": "Alt: distance to marker",
    "Правый клик: поставить точку (левый край блока)": (
        "Right click: place marker (left edge of block)"
    ),
    "Правый клик: поставить точку (правый край блока)": (
        "Right click: place marker (right edge of block)"
    ),
    "Правый клик: поставить точку (центр блока)": (
        "Right click: place marker (center of block)"
    ),
    # Динамические шаблоны
    "ФИО: {count}": "Names: {count}",
    "Найдено: {visible} из {total}": "Found: {visible} of {total}",
    "Сгенерировать {count} грамот": "Generate {count} diplomas",
    "Сгенерировать грамоты": "Generate diplomas",
    "Шрифт «{name}» не найден": "Font «{name}» not found",
    "Загружен список: {name}": "List loaded: {name}",
    "Удалено ранее созданных файлов: {removed}": (
        "Previously created files deleted: {removed}"
    ),
    "Генерация: {done}/{total}, {name}": "Generating: {done}/{total}, {name}",
    "Генерация: {done}/{total}": "Generating: {done}/{total}",
    "Готово: {created} {word} ({output_dir})": "Done: {created} {word} ({output_dir})",
    "Создано: {created} {word}": "Created: {created} {word}",
    "Пропущено: {count}": "Skipped: {count}",
    "Ошибок: {count}": "Errors: {count}",
    "Файлов создано: {count}": "Files created: {count}",
    "Папка: {path}": "Folder: {path}",
    "…и ещё {count}": "…and {count} more",
    "Цвет текста": "Text color",
    "Цвет крестика": "Marker color",
    "Цвет полей для печати": "Print margin color",
    "ПКМ: поставить крестик (левый край, середина по высоте)": (
        "Right click: place marker (left edge, vertical center)"
    ),
    "ПКМ: поставить крестик (правый край, середина по высоте)": (
        "Right click: place marker (right edge, vertical center)"
    ),
    "ПКМ: поставить крестик (центр по горизонтали и вертикали)": (
        "Right click: place marker (horizontal and vertical center)"
    ),
    "Левый край: X={x}, Y={y}": "Left edge: X={x}, Y={y}",
    "Правый край: X={x}, Y={y}": "Right edge: X={x}, Y={y}",
    "Центр текста: X={x}, Y={y}": "Text center: X={x}, Y={y}",
    "Точка: X={x}, Y={y}": "Point: X={x}, Y={y}",
    "X={x}, Y={y} | ΔX={dx} ΔY={dy} | Дистанция: {dist} px": (
        "X={x}, Y={y} | ΔX={dx} ΔY={dy} | Distance: {dist} px"
    ),
    # Сообщения и статусы
    "Готово": "Done",
    "Генерация…": "Generating…",
    "Отмена…": "Cancelling…",
    "Настройки сохранены": "Settings saved",
    "Предпросмотр создан": "Preview created",
    "Ошибка": "Error",
    "Ошибка сохранения": "Save error",
    "Ошибка генерации": "Generation error",
    "Ошибка предпросмотра": "Preview error",
    "Ошибка чтения": "Read error",
    "Генерация": "Generation",
    "Генерация отменена": "Generation cancelled",
    "Генерация отменена.": "Generation cancelled.",
    "Генерация выполняется": "Generation is running",
    "Генерация ещё не завершена. Отменить её и выйти?": (
        "Generation is not finished. Cancel it and exit?"
    ),
    "Сохранить настройки перед выходом?": "Save settings before exit?",
    "Сохранить": "Save",
    "Не сохранять": "Don't save",
    "Отменить и выйти": "Cancel and exit",
    "Не выходить": "Stay",
    "Не удалось остановить генерацию за 15 секунд. Окно останется открытым.": (
        "Could not stop generation within 15 seconds. The window will stay open."
    ),
    "Закрыть": "Close",
    "ОК": "OK",
    "Понятно": "Got it",
    "Продолжить": "Continue",
    "Редактор": "Editor",
    "Сначала выберите шаблон грамоты.": "Choose a diploma template first.",
    "Выберите шаблон грамоты.": "Choose a diploma template.",
    "Выберите существующий шаблон грамоты.": "Choose an existing diploma template.",
    "Добавьте хотя бы одно ФИО": "Add at least one name",
    "Добавьте хотя бы одно ФИО.": "Add at least one name.",
    "Добавьте список ФИО.": "Add a name list.",
    "Укажите положительный размер шрифта.": "Enter a positive font size.",
    "Шрифт не выбран или файл шрифта не найден.": (
        "No font selected or the font file was not found."
    ),
    "Выберите шрифт": "Choose a font",
    "Шаблон": "Template",
    "Файл пуст.": "The file is empty.",
    "Текущий список не пуст. Что сделать?": "The current list is not empty. What to do?",
    "Заменить": "Replace",
    "Добавить в конец": "Append",
    "Загрузка списка": "Loading list",
    "Загружен список:": "List loaded:",
    "Перенос исключений": "Move excluded names",
    "Как перенести исключения в основной список?": (
        "How should excluded names be moved to the main list?"
    ),
    "Добавить отсутствующие": "Add missing",
    "Заменить основной список": "Replace main list",
    "Исключения перенесены": "Excluded names moved",
    "Основной список заменён исключениями": "Main list replaced with excluded names",
    "Дубликаты в списке": "Duplicate names",
    "Найдены дубликаты (": "Duplicates found (",
    "Удалить дубликаты": "Remove duplicates",
    "Текст выходит за поля для печати": "Text exceeds print margins",
    "Текст выходит за поля для печати у": "Text exceeds print margins for",
    "грамот:": "diplomas:",
    "Сделать все": "Do all",
    "Только корректные": "Only valid",
    "Нет ни одной грамоты, которая помещается в поля для печати.": (
        "No diploma fits inside the print margins."
    ),
    "Файл уже существует": "File already exists",
    "Файлы уже существуют": "Files already exist",
    "Файл «": "File «",
    "» уже существует. Что сделать?": "» already exists. What to do?",
    "Найдены дубликаты ({count}):\n\n": "Duplicates found ({count}):\n\n",
    "Текст выходит за поля для печати у {count} грамот:\n\n": (
        "Text exceeds print margins for {count} diplomas:\n\n"
    ),
    "{text}: +{overflow}px ({side})": "{text}: +{overflow}px ({side})",
    "блок": "block",
    "Файл «{name}» уже существует. Что сделать?": (
        "File «{name}» already exists. What to do?"
    ),
    "В папке уже есть {count} файл(ов) с такими именами.\n"
    "Что сделать со всеми?\n\n"
    "«Оставить существующие»: старые файлы не пересоздаются, "
    "остальные ФИО будут сгенерированы.": (
        "The folder already has {count} file(s) with these names.\n"
        "What should be done with all of them?\n\n"
        "Keep existing: old files are not recreated, the remaining names "
        "are still generated."
    ),
    "Удалить {count} файл(ов), созданных AutoFill ранее?\n"
    "Чужие файлы и папки не затрагиваются.": (
        "Delete {count} file(s) created by AutoFill earlier?\n"
        "Other files and folders are left untouched."
    ),
    "В папке уже есть": "The folder already has",
    "файл(ов) с такими именами.": "file(s) with these names.",
    "Создать с номером": "Create with number",
    "Оставить существующий": "Keep existing",
    "Заменить все": "Replace all",
    "Создать с номерами": "Create with numbers",
    "Оставить существующие": "Keep existing",
    "Очистка предыдущих файлов": "Cleaning previous files",
    "Очистка": "Cleanup",
    "Удалить": "Delete",
    "файл(ов), созданных AutoFill ранее?": "file(s) created by AutoFill earlier?",
    "Удалено ранее созданных файлов:": "Previously created files deleted:",
    "Создано:": "Created:",
    "Пропущено:": "Skipped:",
    "Ошибок:": "Errors:",
    "Файлов создано:": "Files created:",
    "грамота": "diploma",
    "грамоты": "diplomas",
    "грамот": "diplomas",
    "…и ещё": "…and more",
    "Отменено пользователем": "Cancelled by user",
    "Не удалось открыть шаблон:": "Could not open template:",
    "Не удалось загрузить шрифт «": "Could not load font «",
    "» не найден": "» not found",
    "Шрифт «": "Font «",
    "Исключения (": "Excluded (",
    "Живой предпросмотр недоступен: %s": "Live preview is unavailable: %s",
    "Сохранение настроек": "Saving settings",
    # Справка
    "КАК РАБОТАТЬ": "HOW TO USE",
    "1. Выберите шаблон грамоты (JPG или PNG).\n"
    "2. Выберите шрифт из списка или укажите файл TTF, OTF или TTC.\n"
    "3. Настройте размер, цвет и интервал текста.\n"
    "4. Вставьте список ФИО: каждая строка соответствует одному человеку.\n"
    "5. Откройте вкладку «Позиция» и настройте место текста. Можно открыть\n"
    "   редактор и указать точку прямо на шаблоне.\n"
    "6. Нажмите «Сгенерировать».": (
        "1. Choose a diploma template (JPG or PNG).\n"
        "2. Pick a font from the list or specify a TTF, OTF or TTC file.\n"
        "3. Set the text size, color and spacing.\n"
        "4. Paste the name list: each line is one person.\n"
        "5. Open the Position tab and set where the text goes. You can open\n"
        "   the editor and place the point directly on the template.\n"
        "6. Click Generate."
    ),
    "РЕДАКТОР": "EDITOR",
    "Справа показан живой предпросмотр. Двойной клик по нему или клавиша F5\n"
    "открывает редактор. В редакторе можно изменить шрифт, размер, цвет,\n"
    "положение, выравнивание и поля для печати. Перед генерацией редактор\n"
    "можно открывать автоматически.": (
        "The live preview is shown on the right. Double click it or press F5\n"
        "to open the editor. In the editor you can change the font, size, color,\n"
        "position, alignment and print margins. The editor can open\n"
        "automatically before generation."
    ),
    "ПОИСК": "SEARCH",
    "Поиск показывает только подходящие строки. Пока поиск включён, список\n"
    "нельзя редактировать, чтобы не потерять скрытые строки. Очистите поиск,\n"
    "чтобы вернуться к редактированию.": (
        "Search shows only matching lines. While search is active the list\n"
        "cannot be edited so hidden lines are not lost. Clear the search\n"
        "to return to editing."
    ),
    "ИСКЛЮЧЕНИЯ": "EXCLUDED",
    "Сюда попадают ФИО, которые не помещаются в поля для печати. Их можно\n"
    "вернуть в основной список. Перед переносом приложение спросит подтверждение.": (
        "Names that do not fit inside the print margins land here. You can\n"
        "move them back to the main list. The app asks for confirmation first."
    ),
    "ФАЙЛЫ": "FILES",
    "AutoFill не удаляет всю папку. Он убирает только свои старые файлы,\n"
    "которые создал сам (по манифесту .autofill-manifest.json). Если файл\n"
    "с таким именем уже есть, выберите: заменить, добавить номер или\n"
    "оставить существующие (старые файлы не пересоздаются, остальные\n"
    "грамоты будут созданы). Решение применяется ко всей пачке.": (
        "AutoFill never deletes the whole folder. It only removes its own old\n"
        "files listed in .autofill-manifest.json. If a file with the same name\n"
        "already exists, choose: replace, add a number or keep existing files\n"
        "(old files are not recreated, the remaining diplomas are still made).\n"
        "The choice applies to the whole batch."
    ),
    "ГОРЯЧИЕ КЛАВИШИ": "SHORTCUTS",
    "Ctrl+O: шаблон\n"
    "Ctrl+Shift+O: список\n"
    "Ctrl+G: генерация\n"
    "F5: редактор\n"
    "Esc: отмена генерации": (
        "Ctrl+O: template\n"
        "Ctrl+Shift+O: name list\n"
        "Ctrl+G: generate\n"
        "F5: editor\n"
        "Esc: cancel generation"
    ),
    "Настройки сохраняются при выходе или кнопкой в разделе «Настройки».": (
        "Settings are saved on exit or with the button in the Settings tab."
    ),
    "Массовое заполнение грамот ФИО.": "Bulk filling of diplomas with names.",
    "Авторы:": "Authors:",
    "Пока активен поиск, список доступен только для чтения. "
    "Очистите поиск, чтобы редактировать.": (
        "While search is active the list is read-only. "
        "Clear the search to edit."
    ),
    "Сколько строк подходит под поиск": "How many lines match the search",
    "ФИО: 0": "Names: 0",
    "Выберите шаблон, шрифт и добавьте ФИО": (
        "Choose a template and font, then add names"
    ),
}
