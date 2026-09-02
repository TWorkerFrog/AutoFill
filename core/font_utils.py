import os


def get_system_font_path(family, style=None):
    """
    Рекурсивно ищет файл шрифта по названию семейства и начертанию.
    """
    fonts_dir = "C:/Windows/Fonts"

    family_lower = family.lower()

    style_map = {
        "Regular": "regular",
        "Bold": "bold",
        "SemiBold": "semibold",
        "Italic": "italic",
        "Bold Italic": "bolditalic",
        "Light": "light",
        "Thin": "thin",
        "Medium": "medium",
        "Black": "black",
        "ExtraBold": "extrabold",
        "ExtraLight": "extralight",
        "Black Italic": "blackitalic",
        "Bold Italic": "bolditalic",
        "ExtraBold Italic": "extrabolditalic",
        "SemiBold Italic": "semibolditalic",
        "Light Italic": "lightitalic",
        "ExtraLight Italic": "extralightitalic",
        "Thin Italic": "thinitalic",
        "Medium Italic": "mediumitalic",
    }

    all_font_files = []
    for root, dirs, files in os.walk(fonts_dir):
        for file in files:
            if file.lower().endswith((".ttf", ".otf")):
                all_font_files.append(os.path.join(root, file))

    # Если стиль указан
    if style:
        # Нормализуем стиль: убираем пробелы, приводим к нижнему регистру
        style_normalized = style_map.get(style, style.replace(" ", "").lower())

        # 1. Точное совпадение: family-style.ttf (стиль без пробелов)
        for path in all_font_files:
            file_name = os.path.basename(path).lower()
            file_base = file_name.rsplit(".", 1)[0]  # без расширения

            # Montserrat-BlackItalic.ttf
            if file_base == f"{family_lower}-{style_normalized}":
                return path

            # MontserratBlackItalic.ttf
            if file_base == f"{family_lower}{style_normalized}":
                return path

        # 2. Файл содержит и семейство, и стиль (без пробелов)
        for path in all_font_files:
            file_name = os.path.basename(path).lower()
            if family_lower in file_name and style_normalized in file_name:
                return path

        # 3. Стиль с пробелом — пробуем частями
        style_parts = style.lower().split()
        for path in all_font_files:
            file_name = os.path.basename(path).lower()
            if family_lower in file_name:
                if all(part in file_name for part in style_parts):
                    return path

        # 4. Первая часть стиля (Black из Black Italic)
        if style_parts:
            first_part = style_parts[0]
            for path in all_font_files:
                file_name = os.path.basename(path).lower()
                if family_lower in file_name and first_part in file_name:
                    return path

    # Без стиля — просто по семейству
    for path in all_font_files:
        file_name = os.path.basename(path).lower()
        if family_lower in file_name:
            return path

    return None