import math
import os
import random

from PIL import Image, ImageDraw, ImageFont, ImageFilter


SIZE = 1024

STYLES = {
    "neon": ("#100A25", "#A855F7", "#22D3EE"),
    "gold": ("#17120A", "#FFD700", "#FFF1A6"),
    "3d": ("#101020", "#FF4D9D", "#7C3AED"),
    "gaming": ("#080D20", "#00E5FF", "#7C3AED"),
    "anime": ("#180B28", "#FF4FA3", "#8B5CF6"),
    "fire": ("#240900", "#FF4B00", "#FFD000"),
    "ice": ("#061C32", "#53D9FF", "#E0FFFF"),
    "royal": ("#160D25", "#D8AEFF", "#FFD700"),
    "cyberpunk": ("#10051C", "#FF00C8", "#00FFFF"),
    "gradient": ("#10152B", "#FF5F9E", "#5B7CFA"),
    "chrome": ("#111820", "#E5F5FF", "#8295A8"),
    "shadow": ("#101010", "#FFFFFF", "#888888"),
    "emerald": ("#061C17", "#00E6A0", "#B8FFE4"),
    "ruby": ("#25060D", "#FF3158", "#FF9AAB"),
    "sapphire": ("#07152D", "#398BFF", "#A8D5FF"),
    "toxic": ("#111A05", "#B7FF00", "#E5FF8C"),
    "matrix": ("#020F08", "#00FF41", "#A5FFB8"),
    "sunset": ("#271020", "#FF6B35", "#FFB86B"),
    "minimal": ("#171717", "#FFFFFF", "#BDBDBD"),
    "vintage": ("#21180F", "#D6A85F", "#F4D9A5"),
}


# Prefer project fonts, then Docker Noto, then common system fonts.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FONT_PATHS = [
    os.path.join(_BASE_DIR, "assets", "font.ttf"),
    os.path.join(_BASE_DIR, "assets", "font2.ttf"),
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDisplay-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def get_font(size):
    for path in FONT_PATHS:
        if not path or not os.path.exists(path):
            continue
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(
        int(value[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def mix_color(color1, color2, amount):
    return tuple(
        int(color1[i] * (1 - amount) + color2[i] * amount)
        for i in range(3)
    )


def make_background(style):
    bg, primary, secondary = STYLES[style]

    base_color = hex_rgb(bg)
    primary_color = hex_rgb(primary)
    secondary_color = hex_rgb(secondary)

    image = Image.new("RGB", (SIZE, SIZE), base_color)
    draw = ImageDraw.Draw(image)

    for y in range(0, SIZE, 4):
        amount = (y / SIZE) * 0.16
        color = mix_color(base_color, primary_color, amount)
        draw.rectangle(
            (0, y, SIZE, min(y + 3, SIZE)),
            fill=color
        )

    image = image.convert("RGBA")

    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        (190, 190, 834, 834),
        fill=(*primary_color, 65)
    )
    glow = glow.filter(ImageFilter.GaussianBlur(125))
    image = Image.alpha_composite(image, glow)

    draw = ImageDraw.Draw(image)

    if style != "minimal":
        for radius in (340, 395, 450):
            draw.ellipse(
                (
                    512 - radius,
                    512 - radius,
                    512 + radius,
                    512 + radius
                ),
                outline=(*primary_color, 140),
                width=2
            )

        for _ in range(95):
            x = random.randint(35, 989)
            y = random.randint(35, 989)
            r = random.randint(1, 3)
            draw.ellipse(
                (x - r, y - r, x + r, y + r),
                fill=(*secondary_color, 200)
            )

        for x, y in (
            (95, 95),
            (929, 95),
            (95, 929),
            (929, 929)
        ):
            draw.line(
                (x - 22, y, x + 22, y),
                fill=(*secondary_color, 220),
                width=3
            )
            draw.line(
                (x, y - 22, x, y + 22),
                fill=(*secondary_color, 220),
                width=3
            )

    return image


def generate_logo(name, style="neon"):
    style = style.lower().strip()

    if style not in STYLES:
        style = "neon"

    name = " ".join(str(name).split())[:28]

    if not name:
        name = "V3MUSIC"

    _, primary, secondary = STYLES[style]
    color1 = hex_rgb(primary)
    color2 = hex_rgb(secondary)

    image = make_background(style).convert("RGBA")

    font_size = 190
    while font_size >= 42:
        font = get_font(font_size)
        bbox = font.getbbox(name, stroke_width=2)
        if bbox[2] - bbox[0] <= 850:
            break
        font_size -= 5

    font = get_font(font_size)
    bbox = font.getbbox(name, stroke_width=2)

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (SIZE - text_width) // 2 - bbox[0]
    y = 475 - text_height // 2 - bbox[1]

    mask = Image.new("L", (SIZE, SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.text((x, y), name, font=font, fill=255)

    if style in ("neon", "cyberpunk", "gaming", "matrix", "ice"):
        for blur, opacity, color in (
            (32, 150, color1),
            (12, 180, color2)
        ):
            glow_mask = mask.filter(ImageFilter.GaussianBlur(blur))
            glow_layer = Image.new("RGBA", (SIZE, SIZE), (*color, 0))
            glow_layer.putalpha(
                glow_mask.point(lambda p: int(p * opacity / 255))
            )
            image = Image.alpha_composite(image, glow_layer)

    if style in ("3d", "gaming", "gold", "chrome"):
        for offset in range(20, 0, -1):
            shifted = Image.new("L", (SIZE, SIZE), 0)
            shifted.paste(mask, (offset, offset))
            depth_layer = Image.new("RGBA", (SIZE, SIZE), (*color2, 0))
            depth_layer.putalpha(
                shifted.point(lambda p: int(p * 0.85))
            )
            image = Image.alpha_composite(image, depth_layer)

    gradient = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gradient_draw = ImageDraw.Draw(gradient)

    for yy in range(SIZE):
        amount = yy / (SIZE - 1)
        color = mix_color(color1, color2, amount)
        gradient_draw.line(
            (0, yy, SIZE, yy),
            fill=(*color, 255)
        )

    gradient.putalpha(mask)
    image = Image.alpha_composite(image, gradient)

    outline = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    outline_draw = ImageDraw.Draw(outline)
    outline_draw.text(
        (x, y),
        name,
        font=font,
        fill=(0, 0, 0, 0),
        stroke_width=3,
        stroke_fill=(*color2, 255)
    )
    image = Image.alpha_composite(image, outline)

    draw = ImageDraw.Draw(image)
    small_font = get_font(27)
    subtitle = "V3MUSIC  |  LOGO DESIGN"
    subtitle_bbox = draw.textbbox((0, 0), subtitle, font=small_font)
    subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]

    draw.text(
        ((SIZE - subtitle_width) // 2, 790),
        subtitle,
        font=small_font,
        fill=(*color2, 235)
    )

    return image.convert("RGB")
