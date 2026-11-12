import asyncio
import logging
import random
import re
import uuid
from io import BytesIO
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

LOGGER = logging.getLogger(__name__)

WIDTH, HEIGHT = 1280, 720
CACHE_DIR = Path("cache")
MAX_CACHE_FILES = 150

LAYOUTS = (
    "center-stage", "left-art", "right-art", "diagonal", "top-banner",
    "split-screen", "royal-frame", "equalizer-stage", "neon-card", "minimal-royal",
)

PALETTES = (
    {"name": "royal-purple", "accent": (174, 42, 255), "second": (0, 174, 255), "gold": (255, 204, 0)},
    {"name": "electric-blue", "accent": (0, 125, 255), "second": (0, 225, 255), "gold": (255, 196, 0)},
    {"name": "neon-magenta", "accent": (255, 0, 190), "second": (100, 50, 255), "gold": (255, 215, 30)},
    {"name": "cyber-gold", "accent": (255, 165, 0), "second": (0, 160, 255), "gold": (255, 220, 40)},
    {"name": "midnight-violet", "accent": (125, 45, 255), "second": (30, 90, 255), "gold": (255, 205, 25)},
    {"name": "laser-cyan", "accent": (0, 220, 255), "second": (180, 30, 255), "gold": (255, 205, 0)},
)

FONT_FILES = {
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ],
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ],
}


def _font(size, bold=True):
    for path in FONT_FILES["bold" if bold else "regular"]:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _clean(value, fallback, limit=90):
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return (value[:limit] or fallback)


def _fit(draw, text, max_width, size, minimum=22):
    text = str(text)
    while size > minimum:
        font = _font(size)
        if draw.textbbox((0, 0), text, font=font, stroke_width=1)[2] <= max_width:
            return font, text
        size -= 2
    font = _font(minimum)
    while text and draw.textbbox((0, 0), text + "…", font=font)[2] > max_width:
        text = text[:-1]
    return font, text + ("…" if text else "")


def _rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _background(palette, seed):
    rng = random.Random(seed)
    image = Image.new("RGB", (WIDTH, HEIGHT))
    pixels = image.load()

    # Deep gradient base
    for y in range(HEIGHT):
        t = y / HEIGHT
        color = tuple(int(a * (1 - t) + b * t) for a, b in zip((6, 4, 18), (14, 8, 36)))
        for x in range(WIDTH):
            pixels[x, y] = color

    # Soft colorful glows
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for _ in range(12):
        x = rng.randint(-120, WIDTH + 120)
        y = rng.randint(-120, HEIGHT + 120)
        radius = rng.randint(120, 280)
        color = rng.choice((palette["accent"], palette["second"]))
        gd.ellipse((x - radius, y - radius, x + radius, y + radius),
                   fill=(*color, rng.randint(18, 48)))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    image = Image.alpha_composite(image.convert("RGBA"), glow)

    # Light streaks + particles
    effects = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(effects)

    for _ in range(28):
        x = rng.randint(-80, WIDTH)
        y = rng.randint(0, HEIGHT)
        color = rng.choice((palette["accent"], palette["second"]))
        d.line((x, y, x + rng.randint(50, 220), y - rng.randint(8, 70)),
               fill=(*color, rng.randint(30, 95)), width=rng.randint(2, 5))

    for _ in range(90):
        x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
        r = rng.randint(1, 3)
        color = rng.choice((palette["accent"], palette["second"], palette["gold"]))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*color, rng.randint(70, 180)))

    return Image.alpha_composite(image, effects)


def _crown(draw, cx, top, scale, gold):
    w, h = int(150 * scale), int(88 * scale)
    x = cx - w // 2
    pts = [
        (x, top + h), (x + int(w * .08), top + int(h * .22)),
        (x + int(w * .28), top + int(h * .58)), (x + int(w * .43), top),
        (x + int(w * .57), top + int(h * .48)), (x + int(w * .76), top + int(h * .12)),
        (x + int(w * .91), top + int(h * .58)), (x + w, top + int(h * .22)),
        (x + int(w * .94), top + h), (x, top + h),
    ]
    draw.polygon(pts, fill=gold, outline=(255, 245, 160))
    draw.line(pts + [pts[0]], fill=(255, 245, 160), width=max(2, int(3 * scale)))
    for px, py in (pts[1], pts[3], pts[5], pts[7]):
        r = max(3, int(7 * scale))
        draw.ellipse((px - r, py - r, px + r, py + r), fill=(255, 255, 220))


def _equalizer(draw, palette, seed, height=100):
    rng = random.Random(seed + 19)
    x = 18
    while x < WIDTH - 18:
        h = rng.randint(12, height)
        color = rng.choice((palette["accent"], palette["second"]))
        draw.rounded_rectangle((x, HEIGHT - 8 - h, x + 12, HEIGHT - 8),
                               radius=4, fill=(*color, 180))
        x += 21


def _headphones(draw, x, y, scale, color):
    w, h = int(150 * scale), int(150 * scale)
    draw.arc((x, y, x + w, y + h), 185, 355, fill=color, width=max(7, int(13 * scale)))
    pw, ph = int(28 * scale), int(58 * scale)
    draw.rounded_rectangle((x - 3, y + h // 2 - 12, x + pw, y + h // 2 + ph),
                           radius=12, fill=color)
    draw.rounded_rectangle((x + w - pw, y + h // 2 - 12, x + w + 3, y + h // 2 + ph),
                           radius=12, fill=color)


def _load_art(data):
    if not data:
        return None
    try:
        return Image.open(BytesIO(data)).convert("RGB")
    except Exception:
        LOGGER.warning("Invalid YouTube thumbnail image")
        return None


def _paste_art(image, art, box, accent):
    x1, y1, x2, y2 = map(int, box)
    w, h = x2 - x1, y2 - y1

    if art is None:
        art = Image.new("RGB", (w, h), (14, 10, 32))
        _headphones(ImageDraw.Draw(art), w // 2 - 55, h // 2 - 70, .8, accent)
    else:
        art = ImageOps.fit(art, (w, h), method=Image.Resampling.LANCZOS)

    # Soft outer glow
    glow = Image.new("RGBA", (w + 30, h + 30), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle((0, 0, w + 29, h + 29), radius=40, fill=(*accent, 60))
    glow = glow.filter(ImageFilter.GaussianBlur(12))
    image.paste(glow, (x1 - 15, y1 - 15), glow)

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=28, fill=255)
    image.paste(art, (x1, y1), mask)

    # Clean border
    ImageDraw.Draw(image).rounded_rectangle(
        (x1 - 3, y1 - 3, x2 + 3, y2 + 3), radius=31, outline=accent, width=5
    )


def _brand_top(draw, palette):
    """Top-left corner branding - GOVIND"""
    # Small gold accent bar
    draw.rounded_rectangle((28, 28, 38, 72), radius=4, fill=palette["gold"])

    draw.text((52, 30), "GOVIND", font=_font(34), fill="white",
              stroke_width=2, stroke_fill=(20, 10, 40))
    draw.text((53, 68), "MUSIC BOTS", font=_font(14), fill=palette["gold"])


def _brand_bottom(draw, bot_name, palette):
    """Bottom-right corner - dynamic bot name"""
    text = bot_name.upper()
    font = _font(20)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]

    x = WIDTH - tw - 45
    y = HEIGHT - 52

    # Soft background pill
    _rounded(draw, (x - 18, y - 8, x + tw + 18, y + 32), 18,
             (0, 0, 0, 140), palette["accent"], 2)

    draw.text((x, y), text, font=font, fill="white")


def _track_info(draw, title, duration, channel, requester, x, y, width, size=42):
    font, fitted = _fit(draw, title, width, size, 24)
    draw.text((x, y), fitted, font=font, fill="white",
              stroke_width=2, stroke_fill=(20, 8, 40))

    draw.text((x, y + 62), f"{channel}  •  {duration}"[:95],
              font=_font(20, False), fill=(185, 205, 255))

    draw.text((x, y + 94), f"Requested by  {requester}"[:90],
              font=_font(17), fill=(255, 210, 70))


def _render(seed, layout, palette, art, title, duration, channel, requester, bot_name):
    rng = random.Random(seed)
    image = _background(palette, seed)
    d = ImageDraw.Draw(image)

    _equalizer(d, palette, seed, rng.randint(60, 105))

    # ========== TOP LEFT : GOVIND ==========
    _brand_top(d, palette)

    # ========== LAYOUTS ==========
    if layout == "center-stage":
        _paste_art(image, art, (55, 160, 400, 505), palette["accent"])
        d = ImageDraw.Draw(image)
        d.text((450, 195), "NOW PLAYING", font=_font(22), fill=palette["second"])
        _track_info(d, title, duration, channel, requester, 450, 250, 760, 52)

    elif layout == "left-art":
        _paste_art(image, art, (60, 155, 490, 585), palette["second"])
        d = ImageDraw.Draw(image)
        d.text((540, 200), "NOW PLAYING", font=_font(22), fill=palette["second"])
        _track_info(d, title, duration, channel, requester, 540, 265, 670, 42)

    elif layout == "right-art":
        _paste_art(image, art, (780, 155, 1210, 585), palette["accent"])
        d = ImageDraw.Draw(image)
        d.text((60, 200), "NOW PLAYING", font=_font(22), fill=palette["second"])
        _track_info(d, title, duration, channel, requester, 60, 265, 680, 42)

    elif layout == "diagonal":
        d.polygon([(0, 480), (820, 90), (1280, 90), (1280, 720), (0, 720)],
                  fill=(18, 8, 42, 155))
        _paste_art(image, art, (830, 165, 1175, 510), palette["gold"])
        d = ImageDraw.Draw(image)
        d.text((60, 210), "NOW PLAYING", font=_font(22), fill=palette["second"])
        _track_info(d, title, duration, channel, requester, 60, 275, 720, 46)

    elif layout == "top-banner":
        _paste_art(image, art, (65, 195, 415, 545), palette["accent"])
        d = ImageDraw.Draw(image)
        _rounded(d, (460, 175, 1210, 565), 36, (6, 6, 22, 210), palette["second"], 4)
        d.text((505, 215), "NOW PLAYING", font=_font(22), fill=palette["second"])
        _track_info(d, title, duration, channel, requester, 505, 280, 650, 42)

    elif layout == "split-screen":
        d.rectangle((0, 0, WIDTH // 2, HEIGHT), fill=(10, 6, 28, 220))
        _paste_art(image, art, (690, 145, 1165, 620), palette["second"])
        d = ImageDraw.Draw(image)
        d.text((60, 210), "NOW PLAYING", font=_font(22), fill=palette["second"])
        _track_info(d, title, duration, channel, requester, 60, 275, 540, 40)

    elif layout == "royal-frame":
        d.rounded_rectangle((24, 24, WIDTH - 24, HEIGHT - 24), radius=40,
                            outline=palette["gold"], width=4)
        _paste_art(image, art, (70, 185, 410, 525), palette["gold"])
        d = ImageDraw.Draw(image)
        d.text((470, 220), "NOW PLAYING", font=_font(22), fill=palette["second"])
        _track_info(d, title, duration, channel, requester, 470, 285, 720, 42)

    elif layout == "equalizer-stage":
        _paste_art(image, art, (460, 140, 820, 500), palette["second"])
        d = ImageDraw.Draw(image)
        d.text((80, 200), "NOW PLAYING", font=_font(22), fill=palette["second"])
        _track_info(d, title, duration, channel, requester, 80, 265, 350, 34)
        _headphones(d, 920, 230, 1.0, palette["accent"])

    elif layout == "neon-card":
        _rounded(d, (55, 135, 1225, 600), 46, (6, 6, 24, 215), palette["accent"], 6)
        _paste_art(image, art, (90, 175, 440, 525), palette["gold"])
        d = ImageDraw.Draw(image)
        d.text((490, 210), "NOW PLAYING", font=_font(22), fill=palette["second"])
        _track_info(d, title, duration, channel, requester, 490, 275, 670, 42)

    else:  # minimal-royal
        _paste_art(image, art, (820, 165, 1165, 510), palette["accent"])
        d = ImageDraw.Draw(image)
        d.text((70, 230), "NOW PLAYING", font=_font(22), fill=palette["second"])
        _track_info(d, title, duration, channel, requester, 70, 295, 700, 44)

    # ========== BOTTOM RIGHT : BOT NAME ==========
    d = ImageDraw.Draw(image)
    _brand_bottom(d, bot_name, palette)

    return image.convert("RGB")


async def _download_youtube_thumb(videoid):
    videoid = str(videoid or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", videoid):
        return None
    timeout = aiohttp.ClientTimeout(total=12)
    headers = {"User-Agent": "Mozilla/5.0"}
    urls = (
        f"https://i.ytimg.com/vi/{videoid}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{videoid}/hqdefault.jpg",
    )
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            for url in urls:
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.read()
                            if len(data) > 3000:
                                return data
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    continue
    except Exception:
        LOGGER.exception("YouTube thumbnail download failed")
    return None


def _cleanup_cache():
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(CACHE_DIR.glob("govind_music_*.png"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[MAX_CACHE_FILES:]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError:
        LOGGER.warning("Thumbnail cache cleanup failed", exc_info=True)


async def get_thumb(
    videoid,
    title,
    duration="Unknown",
    views=0,
    channel="YouTube",
    bot_name="GOVIND MUSIC",
    requested_by="Group member",
):
    """
    Generate a 1280x720 premium thumbnail.
    Top-left  → GOVIND
    Bottom-right → bot_name (dynamic)
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    title = _clean(title, "Unknown Track", 110)
    duration = _clean(duration, "Unknown", 24)
    channel = _clean(channel, "YouTube", 60)
    requester = _clean(requested_by, "Group member", 55)
    bot_name = _clean(bot_name, "GOVIND MUSIC", 32)

    seed = random.SystemRandom().randrange(0, 2**31)
    layout = random.choice(LAYOUTS)
    palette = random.choice(PALETTES)
    art = _load_art(await _download_youtube_thumb(videoid))

    try:
        image = _render(seed, layout, palette, art, title, duration,
                        channel, requester, bot_name)
    except Exception:
        LOGGER.exception("Thumbnail rendering failed; using fallback")
        image = Image.new("RGB", (WIDTH, HEIGHT), (10, 6, 24))
        d = ImageDraw.Draw(image)
        d.text((WIDTH // 2, 260), "GOVIND", font=_font(70),
               fill=(255, 210, 0), anchor="mm")
        d.text((WIDTH // 2, 360), title[:55], font=_font(34),
               fill="white", anchor="mm")

    output = CACHE_DIR / f"govind_music_{uuid.uuid4().hex}.png"
    image.save(output, format="PNG", optimize=True)
    _cleanup_cache()
    LOGGER.info("Generated thumbnail: layout=%s palette=%s path=%s",
                layout, palette["name"], output)
    return str(output)
