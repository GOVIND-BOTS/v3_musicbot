import math
import os
import random

from PIL import Image, ImageDraw, ImageFont, ImageFilter


SIZE = 1024

# (background, main colour, highlight colour)
STYLES = {
    "neon": ("#080B1D", "#B84DFF", "#54F7FF"),
    "gold": ("#17110A", "#D99A24", "#FFF0A6"),
    "3d": ("#101020", "#FF4D9D", "#7C3AED"),
    "gaming": ("#080D20", "#00E5FF", "#7C3AED"),
    "anime": ("#FFF8FC", "#FF4FA3", "#8B5CF6"),
    "fire": ("#240900", "#FF4B00", "#FFD000"),
    "ice": ("#071D31", "#53D9FF", "#E0FFFF"),
    "royal": ("#F8F4EC", "#B88635", "#24143D"),
    "cyberpunk": ("#10051C", "#FF00C8", "#00FFFF"),
    "gradient": ("#11152B", "#FF5F9E", "#5B7CFA"),
    "chrome": ("#111820", "#E5F5FF", "#8295A8"),
    "shadow": ("#F5F5F5", "#171717", "#777777"),
    "emerald": ("#061C17", "#00E6A0", "#B8FFE4"),
    "ruby": ("#25060D", "#FF3158", "#FF9AAB"),
    "sapphire": ("#07152D", "#398BFF", "#A8D5FF"),
    "toxic": ("#111A05", "#B7FF00", "#E5FF8C"),
    "matrix": ("#020F08", "#00FF41", "#A5FFB8"),
    "sunset": ("#271020", "#FF6B35", "#FFB86B"),
    "minimal": ("#FFFFFF", "#191919", "#777777"),
    "vintage": ("#F5EEE2", "#76502B", "#C49A58"),
    "signature": ("#FFFFFF", "#111111", "#9B7A42"),
    "feather": ("#FAFAFA", "#171717", "#B68A35"),
    "butterfly": ("#F8FBFF", "#11A9B5", "#8B5CF6"),
    "love": ("#FFF7F8", "#D51D55", "#F6A6BC"),
    "angel": ("#F8F8FF", "#24243A", "#B6A0E8"),
    "luxury": ("#F5F0E7", "#B58A42", "#28201A"),
}


_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_PATHS = [
    os.path.join(_BASE_DIR, "assets", "signature.ttf"),
    os.path.join(_BASE_DIR, "assets", "font2.ttf"),
    os.path.join(_BASE_DIR, "assets", "font.ttf"),
    "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
]


def get_font(size):
    for path in FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def mix_color(a, b, amount):
    return tuple(int(a[i] * (1 - amount) + b[i] * amount) for i in range(3))


def _curve(points, count=80):
    # Catmull-Rom-like smooth interpolation through control points.
    result = []
    for i in range(len(points) - 1):
        p0 = points[max(0, i - 1)]
        p1 = points[i]
        p2 = points[i + 1]
        p3 = points[min(len(points) - 1, i + 2)]
        for step in range(count // (len(points) - 1)):
            t = step / max(1, count // (len(points) - 1))
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2*p1[0]) + (-p0[0]+p2[0])*t +
                       (2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2 +
                       (-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3)
            y = 0.5 * ((2*p1[1]) + (-p0[1]+p2[1])*t +
                       (2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2 +
                       (-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3)
            result.append((int(x), int(y)))
    result.append(tuple(map(int, points[-1])))
    return result


def _draw_feather(draw, cx, cy, scale, color):
    stem = _curve([
        (cx - 105*scale, cy + 115*scale),
        (cx - 35*scale, cy + 35*scale),
        (cx + 10*scale, cy - 55*scale),
        (cx + 90*scale, cy - 135*scale),
    ])
    draw.line(stem, fill=color, width=max(2, int(4*scale)))
    for i in range(1, 17):
        t = i / 18
        x = cx - 105*scale + 195*scale*t
        y = cy + 115*scale - 250*scale*t
        spread = math.sin(t * math.pi) * 62 * scale
        for side in (-1, 1):
            end = (int(x + spread*side), int(y - spread*0.55))
            draw.line((int(x), int(y), *end), fill=color, width=max(1, int(2*scale)))
    draw.ellipse((cx + 48*scale, cy - 180*scale,
                  cx + 112*scale, cy - 115*scale),
                 outline=color, width=max(2, int(3*scale)))


def _draw_crown(draw, cx, cy, scale, color):
    w, h = 190*scale, 100*scale
    left, top = cx-w/2, cy-h/2
    pts = [
        (left, top+h), (left+15*scale, top+18*scale),
        (left+58*scale, top+58*scale), (cx, top),
        (left+132*scale, top+58*scale), (left+175*scale, top+18*scale),
        (left+w, top+h), (left, top+h)
    ]
    draw.polygon(pts, outline=color)
    draw.line(pts, fill=color, width=max(2, int(5*scale)))
    for x in (left+15*scale, cx, left+175*scale):
        r = 7*scale
        draw.ellipse((x-r, top-r, x+r, top+r), fill=color)


def _draw_wings(draw, cx, cy, scale, color):
    for side in (-1, 1):
        pts = _curve([
            (cx, cy+20*scale),
            (cx+side*75*scale, cy-75*scale),
            (cx+side*165*scale, cy-125*scale),
            (cx+side*115*scale, cy-25*scale),
            (cx+side*65*scale, cy+38*scale),
        ])
        draw.line(pts, fill=color, width=max(3, int(5*scale)))
        for i in range(4):
            y = cy - 75*scale + i*25*scale
            draw.line((cx, cy+15*scale, cx+side*(95+i*17)*scale, y),
                      fill=color, width=max(2, int(3*scale)))


def _draw_butterfly(draw, cx, cy, scale, color):
    draw.line((cx, cy-35*scale, cx, cy+40*scale), fill=color, width=max(3, int(5*scale)))
    draw.arc((cx-95*scale, cy-85*scale, cx+4*scale, cy+5*scale),
             180, 350, fill=color, width=max(3, int(5*scale)))
    draw.arc((cx-4*scale, cy-85*scale, cx+95*scale, cy+5*scale),
             190, 360, fill=color, width=max(3, int(5*scale)))
    draw.arc((cx-75*scale, cy-5*scale, cx+4*scale, cy+80*scale),
             180, 350, fill=color, width=max(3, int(5*scale)))
    draw.arc((cx-4*scale, cy-5*scale, cx+75*scale, cy+80*scale),
             190, 360, fill=color, width=max(3, int(5*scale)))


def _draw_heart(draw, cx, cy, scale, color):
    r = 42*scale
    draw.arc((cx-r, cy-r, cx, cy+r), 135, 315, fill=color, width=max(3, int(5*scale)))
    draw.arc((cx, cy-r, cx+r, cy+r), 225, 45, fill=color, width=max(3, int(5*scale)))
    draw.line((cx-r*0.72, cy+r*0.15, cx, cy+r*1.05,
               cx+r*0.72, cy+r*0.15), fill=color, width=max(3, int(5*scale)))


def make_background(style):
    bg, primary, secondary = STYLES[style]
    base, accent, light = hex_rgb(bg), hex_rgb(primary), hex_rgb(secondary)
    image = Image.new("RGB", (SIZE, SIZE), base)
    draw = ImageDraw.Draw(image)

    # Soft, premium radial glow.
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((220, 170, 804, 754), fill=(*accent, 45))
    glow = glow.filter(ImageFilter.GaussianBlur(135))
    image = Image.alpha_composite(image.convert("RGBA"), glow)

    draw = ImageDraw.Draw(image)
    if style in ("neon", "gaming", "cyberpunk", "matrix", "ice", "3d"):
        for radius in (370, 420, 468):
            draw.ellipse((512-radius, 512-radius, 512+radius, 512+radius),
                         outline=(*accent, 90), width=2)
        for _ in range(75):
            x, y = random.randint(25, 999), random.randint(25, 999)
            r = random.randint(1, 3)
            draw.ellipse((x-r, y-r, x+r, y+r), fill=(*light, 170))
    else:
        # Fine ornamental border for signature / luxury logo looks.
        draw.rounded_rectangle((34, 34, 990, 990), radius=42,
                               outline=(*light, 115), width=3)
        draw.rounded_rectangle((48, 48, 976, 976), radius=34,
                               outline=(*light, 65), width=1)
    return image


def _fit_font(name):
    size = 190
    while size >= 42:
        font = get_font(size)
        box = font.getbbox(name, stroke_width=2)
        if box[2] - box[0] <= 850:
            return font, box
        size -= 5
    font = get_font(42)
    return font, font.getbbox(name, stroke_width=2)


def generate_logo(name, style="neon"):
    style = str(style).lower().strip()
    if style not in STYLES:
        style = "neon"
    name = " ".join(str(name).split())[:28] or "V3MUSIC"

    bg, primary, secondary = STYLES[style]
    c1, c2 = hex_rgb(primary), hex_rgb(secondary)
    image = make_background(style).convert("RGBA")
    draw = ImageDraw.Draw(image)

    # Decorative symbol is selected by style; name remains the main focus.
    motif_y = 235
    if style in ("gold", "royal", "luxury", "vintage"):
        _draw_crown(draw, 512, motif_y, 0.72, (*c1, 235))
    elif style in ("feather", "signature", "minimal", "shadow"):
        _draw_feather(draw, 512, motif_y, 0.72, (*c2, 225))
    elif style in ("butterfly", "anime"):
        _draw_butterfly(draw, 512, motif_y, 0.82, (*c1, 230))
    elif style in ("love", "ruby"):
        _draw_heart(draw, 512, motif_y, 0.85, (*c1, 230))
    elif style in ("angel", "ice"):
        _draw_wings(draw, 512, motif_y, 0.78, (*c2, 225))
    elif style in ("gaming", "cyberpunk", "neon", "3d"):
        _draw_wings(draw, 512, motif_y, 0.68, (*c1, 220))
    else:
        _draw_feather(draw, 512, motif_y, 0.62, (*c2, 220))

    font, bbox = _fit_font(name)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    x = (SIZE-tw)//2 - bbox[0]
    y = 535 - th//2 - bbox[1]

    mask = Image.new("L", (SIZE, SIZE), 0)
    md = ImageDraw.Draw(mask)
    md.text((x, y), name, font=font, fill=255)

    # Soft shadow and thick extrusion create a raised 3D lettering effect.
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shadow_mask = Image.new("L", (SIZE, SIZE), 0)
    shadow_mask.paste(mask, (9, 17))
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(13))
    shadow.putalpha(shadow_mask.point(lambda p: int(p * 0.58)))
    image = Image.alpha_composite(image, shadow)

    depth_color = c2 if style not in ("minimal", "shadow", "signature") else (65, 65, 65)
    for offset in range(18, 0, -1):
        shifted = Image.new("L", (SIZE, SIZE), 0)
        shifted.paste(mask, (offset, offset))
        layer = Image.new("RGBA", (SIZE, SIZE), (*depth_color, 0))
        layer.putalpha(shifted.point(lambda p: int(p * 0.88)))
        image = Image.alpha_composite(image, layer)

    # Metallic vertical gradient clipped to the lettering.
    gradient = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gradient)
    stops = [mix_color(c1, (255,255,255), 0.62),
             c1, mix_color(c1, c2, 0.45),
             mix_color(c2, (255,255,255), 0.72)]
    for yy in range(SIZE):
        t = yy / (SIZE-1)
        seg = min(2, int(t*3))
        local = t*3-seg
        col = mix_color(stops[seg], stops[seg+1], local)
        gd.line((0, yy, SIZE, yy), fill=(*col, 255))
    gradient.putalpha(mask)
    image = Image.alpha_composite(image, gradient)

    # Bright edge and subtle inner highlight.
    edge = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ed = ImageDraw.Draw(edge)
    ed.text((x, y), name, font=font, fill=(0,0,0,0),
            stroke_width=4, stroke_fill=(*c2, 255))
    image = Image.alpha_composite(image, edge)

    draw = ImageDraw.Draw(image)
    # Small ornamental flourishes around the wordmark.
    flourish_y = min(720, y + th + 55)
    draw.line((190, flourish_y, 365, flourish_y), fill=(*c2, 210), width=3)
    draw.line((659, flourish_y, 834, flourish_y), fill=(*c2, 210), width=3)
    for cx in (180, 844):
        draw.ellipse((cx-6, flourish_y-6, cx+6, flourish_y+6), fill=(*c1, 240))

    label = "SIGNATURE  •  3D NAME ART"
    small = get_font(25)
    lb = draw.textbbox((0, 0), label, font=small)
    draw.text(((SIZE-(lb[2]-lb[0]))//2, 835), label,
              font=small, fill=(*c2, 235))

    # Keep the generated PNG lightweight for Telegram.
    return image.convert("RGB")
