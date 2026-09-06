import os
from fontTools.ttLib import TTFont


def get_font_metadata(path):
    """
    Читает имя семейства и стиль из TTF/OTF файла.
    Возвращает (family, style).
    """
    try:
        font = TTFont(path)
        name_table = font["name"]

        family = None
        subfamily = None

        for record in name_table.names:
            # nameID 1 = Font Family, 2 = Font Subfamily, 4 = Full Name
            if record.nameID == 1:
                family = record.toUnicode()
            elif record.nameID == 2:
                subfamily = record.toUnicode()

        font.close()

        if family:
            return family, subfamily or "Regular"
    except:
        pass

    return None, None


def scan_fonts():
    fonts = {}

    fonts_dirs = [
        "C:/Windows/Fonts",
        os.path.expanduser("~") + "/AppData/Local/Microsoft/Windows/Fonts"
    ]

    for fonts_dir in fonts_dirs:
        if not os.path.exists(fonts_dir):
            continue

        for root, dirs, files in os.walk(fonts_dir):
            for file in files:
                if not file.lower().endswith((".ttf", ".otf")):
                    continue

                full_path = os.path.join(root, file)

                # Читаем реальное имя из метаданных
                family, style = get_font_metadata(full_path)

                if not family:
                    # Фолбэк — используем имя файла
                    name = os.path.splitext(file)[0]
                    family = name
                    style = "Regular"

                if family not in fonts:
                    fonts[family] = {}

                if style not in fonts[family]:
                    fonts[family][style] = full_path

    for family in list(fonts.keys()):
        if " " in family:
            first_word = family.split(" ")[0]
            if first_word in fonts and len(fonts[first_word]) > 1:
                style_from_name = family.split(" ", 1)[1]  # "Black", "Bold", etc.

                for style, path in fonts[family].items():
                    if style == "Regular":
                        # Montserrat Black + Regular → Black
                        final_style = style_from_name
                    elif style == "Italic":
                        # Montserrat Black + Italic → Black Italic
                        final_style = style_from_name + " Italic"
                    else:
                        final_style = style_from_name + " " + style

                    if final_style not in fonts[first_word]:
                        fonts[first_word][final_style] = path

                del fonts[family]

    return fonts

'''
def detect_family(name, root, fonts_dir):
    """
    Определяет семейство по имени файла и пути.
    """
    # Если файл в подпапке — имя подпапки = семейство
    if root != fonts_dir:
        rel = os.path.relpath(root, fonts_dir)
        return rel.split(os.sep)[0]

    # Пробуем известные стили
    style_keywords = [
        "regular", "bold", "italic", "light", "thin", "medium",
        "black", "extrabold", "extralight", "semibold",
        "bolditalic", "blackitalic", "lightitalic", "thinitalic",
        "mediumitalic", "extrabolditalic", "extralightitalic",
        "semibolditalic", "обычный", "полужирный", "курсив",
        "тонкий", "очень тонкий", "средний", "очень жирный",
        "сверхжирный", "сверхтонкий",
    ]

    name_lower = name.lower()

    # Ищем стиль в конце имени
    for keyword in style_keywords:
        if name_lower.endswith(keyword):
            family = name[: -len(keyword)].rstrip("- ").strip()
            return family

    # Ищем с дефисом
    for keyword in style_keywords:
        if name_lower.endswith("-" + keyword):
            family = name[: -len(keyword) - 1].rstrip("- ").strip()
            return family

    # Если не нашли — это одиночный шрифт
    return name


def detect_style(name):
    """
    Определяет стиль по имени файла.
    """
    style_map = {
        "regular": "Regular",
        "обычный": "Regular",
        "bold": "Bold",
        "полужирный": "Bold",
        "italic": "Italic",
        "курсив": "Italic",
        "light": "Light",
        "тонкий": "Light",
        "thin": "Thin",
        "очень тонкий": "Thin",
        "medium": "Medium",
        "средний": "Medium",
        "black": "Black",
        "очень жирный": "Black",
        "extrabold": "ExtraBold",
        "сверхжирный": "ExtraBold",
        "extralight": "ExtraLight",
        "сверхтонкий": "ExtraLight",
        "semibold": "SemiBold",
        "bolditalic": "Bold Italic",
        "blackitalic": "Black Italic",
    }

    name_lower = name.lower()

    for keyword, style in style_map.items():
        if name_lower.endswith(keyword) or name_lower.endswith("-" + keyword):
            return style

    return "Regular"
'''
