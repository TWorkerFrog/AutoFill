from PIL import Image, ImageDraw, ImageFont


def get_text_width(draw, text, font, letter_spacing=0):
    if letter_spacing == 0:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]
    total = 0
    for ch in text:
        bbox = draw.textbbox((0, 0), ch, font=font)
        total += bbox[2] - bbox[0] + letter_spacing
    return total - letter_spacing if text else 0


def draw_text_line(draw, text, font, color, x, y, anchor, letter_spacing=0):
    if letter_spacing == 0:
        draw.text((x, y), text, fill=color, font=font, anchor=anchor)
        return
    total_width = get_text_width(draw, text, font, letter_spacing)
    if anchor == "lm":
        start_x = x - total_width // 2
    else:
        start_x = x
    current_x = start_x
    for ch in text:
        draw.text((current_x, y), ch, fill=color, font=font, anchor=anchor)
        bbox = draw.textbbox((current_x, y), ch, font=font, anchor=anchor)
        w = bbox[2] - bbox[0]
        current_x += w + letter_spacing


def draw_text_block(draw, lines, font, color, x, y, x_offset, y_offset, align, line_spacing, letter_spacing, img_width, img_height):
    heights = []
    total_h = 0
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        h = bbox[3] - bbox[1]
        heights.append(h)
        total_h += h
        if i < len(lines) - 1:
            total_h += line_spacing

    widths = [get_text_width(draw, line, font, letter_spacing) for line in lines]

    if x == "center":
        x_pos = img_width // 2 + x_offset
    else:
        x_pos = x + x_offset

    if y == "center":
        start_y = (img_height - total_h) // 2 + y_offset
    else:
        start_y = y + y_offset

    anchor = "lm" if align == "left" else "mm"

    current_y = start_y
    for i, line in enumerate(lines):
        line_x = x_pos

        draw_text_line(draw, line, font, color, line_x, current_y, anchor, letter_spacing)
        current_y += heights[i] + line_spacing


def check_text_bounds(lines, font, x, align, letter_spacing, img_width, margin):
    temp_img = Image.new("RGB", (img_width, 100))
    temp_draw = ImageDraw.Draw(temp_img)

    problems = []

    for line in lines:
        w = get_text_width(temp_draw, line, font, letter_spacing)

        if x == "center":
            left = img_width // 2 - w // 2
            right = img_width // 2 + w // 2
        elif align == "center":
            left = x - w // 2
            right = x + w // 2
        else:
            left = x
            right = x + w

        if left < margin:
            overflow = margin - left
            problems.append((line, overflow, "left"))
        if right > img_width - margin:
            overflow = right - (img_width - margin)
            problems.append((line, overflow, "right"))

    return problems