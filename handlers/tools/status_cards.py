"""Generate lightweight, original V3 Music command-card images on first use."""
from pathlib import Path
import math

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = ROOT / "assets"

CARDS = {
    "ping": ("PING STATUS", "Latency, uptime and system health", (0, 220, 255)),
    "speedtest": ("SPEEDTEST", "Live network download and upload", (170, 95, 255)),
    "active": ("ACTIVE CHATS", "Live voice chat activity monitor", (0, 235, 160)),
}


def _font(size, bold=True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        str(ASSET_DIR / "font.ttf"),
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def get_status_image(kind):
    """Return a generated PNG path for ping, speedtest or active commands."""
    if kind not in CARDS:
        raise ValueError(f"Unknown status card: {kind}")
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / f"{kind}_status.png"
    if path.exists() and path.stat().st_size > 5000:
        return str(path)

    title, subtitle, accent = CARDS[kind]
    width, height = 960, 540
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        t = y / height
        color = (int(5 + 10 * t), int(10 + 12 * t), int(26 + 25 * t))
        for x in range(width):
            pixels[x, y] = color

    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((530, 25, 1000, 500), fill=(*accent, 90))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    image = Image.alpha_composite(image.convert("RGBA"), glow)
    draw = ImageDraw.Draw(image)

    for x in range(30, width, 48):
        draw.line((x, 0, x, height), fill=(70, 110, 160, 18), width=1)
    for y in range(30, height, 48):
        draw.line((0, y, width, y), fill=(70, 110, 160, 18), width=1)

    draw.rounded_rectangle((18, 18, width - 18, height - 18), radius=28,
                           outline=(*accent, 150), width=2)
    draw.rounded_rectangle((58, 60, 280, 101), radius=18,
                           fill=(*accent, 38), outline=(*accent, 170), width=2)
    draw.text((76, 68), "V3 MUSIC  /  SYSTEM", font=_font(18),
              fill=(230, 242, 255, 255))
    draw.text((58, 174), title, font=_font(57), fill=(250, 252, 255, 255))
    draw.rounded_rectangle((60, 250, 340, 257), radius=4, fill=(*accent, 230))
    draw.text((60, 290), subtitle, font=_font(22, False),
              fill=(185, 202, 230, 255))
    draw.text((60, 465), "FAST  •  STABLE  •  24/7", font=_font(17),
              fill=(140, 165, 200, 255))

    cx, cy = 700, 260
    for radius, alpha, stroke in ((170, 70, 4), (135, 130, 3), (100, 200, 3)):
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius),
                     outline=(*accent, alpha), width=stroke)
    for angle in range(0, 360, 30):
        rad = math.radians(angle)
        x, y = cx + 190 * math.cos(rad), cy + 190 * math.sin(rad)
        draw.ellipse((x-5, y-5, x+5, y+5), fill=(*accent, 230))

    if kind == "ping":
        draw.ellipse((cx-65, cy-65, cx+65, cy+65), fill=(10, 22, 48, 255),
                     outline=(*accent, 255), width=5)
        points = [(cx-50+i, cy+int(20*math.sin(i/5))) for i in range(100)]
        draw.line(points, fill=(255, 255, 255, 255), width=7)
        label = "PING"
    elif kind == "speedtest":
        draw.arc((cx-90, cy-90, cx+90, cy+90), 180, 360,
                 fill=(245, 248, 255, 240), width=14)
        for angle in range(190, 351, 20):
            rad = math.radians(angle)
            draw.line((cx+72*math.cos(rad), cy+72*math.sin(rad),
                       cx+87*math.cos(rad), cy+87*math.sin(rad)),
                      fill=(*accent, 255), width=5)
        rad = math.radians(305)
        draw.line((cx, cy, cx+72*math.cos(rad), cy+72*math.sin(rad)),
                  fill=(255, 255, 255, 255), width=8)
        draw.ellipse((cx-12, cy-12, cx+12, cy+12), fill=(*accent, 255))
        label = "SPEED"
    else:
        for angle in (0, 120, 240):
            rad = math.radians(angle)
            x, y = cx + 115*math.cos(rad), cy + 115*math.sin(rad)
            draw.line((cx+40*math.cos(rad), cy+40*math.sin(rad), x, y),
                      fill=(*accent, 240), width=6)
            draw.ellipse((x-26, y-26, x+26, y+26), fill=(10, 22, 48, 255),
                         outline=(*accent, 255), width=5)
        draw.ellipse((cx-38, cy-38, cx+38, cy+38), fill=(10, 22, 48, 255),
                     outline=(*accent, 255), width=5)
        label = "LIVE"

    bbox = draw.textbbox((0, 0), label, font=_font(19))
    text_width = bbox[2] - bbox[0]
    draw.rounded_rectangle((cx-text_width//2-22, cy+205,
                            cx+text_width//2+22, cy+245), radius=15,
                           fill=(*accent, 45), outline=(*accent, 180), width=2)
    draw.text((cx-text_width//2, cy+212), label, font=_font(19),
              fill=(245, 250, 255, 255))
    image.convert("RGB").save(path, "PNG", optimize=True)
    return str(path)
