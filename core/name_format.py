from core.text_render import get_text_width
from PIL import Image, ImageDraw


def format_name_lines(parts, mode, split_after=1):
    if mode == "single_line":
        return [" ".join(parts)]
    elif mode == "split_surname":
        if len(parts) > 2:
            return [parts[0], " ".join(parts[1:])]
        return parts
    elif mode == "split_all":
        return parts
    elif mode == "custom":
        if len(parts) <= split_after:
            return [" ".join(parts)]
        return [" ".join(parts[:split_after]), " ".join(parts[split_after:])]
    elif mode == "auto":
        return None
    else:
        return [" ".join(parts)]


def resolve_auto_lines(parts, font, letter_spacing, img_width, margin):
    single_line = " ".join(parts)
    temp_img = Image.new("RGB", (img_width, 100))
    temp_draw = ImageDraw.Draw(temp_img)
    w = get_text_width(temp_draw, single_line, font, letter_spacing)

    safe_width = img_width - 2 * margin

    if w > safe_width and len(parts) > 1:
        return [parts[0], " ".join(parts[1:])]
    return [single_line]