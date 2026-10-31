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

# 10 layouts x 6 colour palettes = 60 branded combinations.
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
    for y in range(HEIGHT):
        t = y / HEIGHT
        color = tuple(int(a * (1-t) + b*t) for a, b in zip((4, 4, 13), (11, 7, 29)))
        for x in range(WIDTH):
            pixels[x, y] = color

    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for _ in range(10):
        x, y = rng.randint(-100, WIDTH+100), rng.randint(-100, HEIGHT+100)
        radius = rng.randint(100, 250)
        color = rng.choice((palette["accent"], palette["second"]))
        gd.ellipse((x-radius, y-radius, x+radius, y+radius),
                   fill=(*color, rng.randint(22, 55)))
    glow = glow.filter(ImageFilter.GaussianBlur(72))
    image = Image.alpha_composite(image.convert("RGBA"), glow)

    effects = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(effects)
    for _ in range(34):
        x, y = rng.randint(-100, WIDTH), rng.randint(0, HEIGHT)
        color = rng.choice((palette["accent"], palette["second"]))
        d.line((x, y, x+rng.randint(40, 190), y-rng.randint(5, 75)),
               fill=(*color, rng.randint(35, 110)), width=rng.randint(2, 6))
    for _ in range(100):
        x, y, r = rng.randrange(WIDTH), rng.randrange(HEIGHT), rng.randint(1, 3)
        color = rng.choice((palette["accent"], palette["second"], palette["gold"]))
        d.ellipse((x-r, y-r, x+r, y+r), fill=(*color, rng.randint(80, 200)))
    return Image.alpha_composite(image, effects)


def _crown(draw, cx, top, scale, gold):
    w, h = int(150*scale), int(88*scale)
    x = cx-w//2
    pts = [
        (x, top+h), (x+int(w*.08), top+int(h*.22)),
        (x+int(w*.28), top+int(h*.58)), (x+int(w*.43), top),
        (x+int(w*.57), top+int(h*.48)), (x+int(w*.76), top+int(h*.12)),
        (x+int(w*.91), top+int(h*.58)), (x+w, top+int(h*.22)),
        (x+int(w*.94), top+h), (x, top+h),
    ]
    draw.polygon(pts, fill=gold, outline=(255, 245, 160))
    draw.line(pts+[pts[0]], fill=(255, 245, 160), width=max(2, int(3*scale)))
    for px, py in (pts[1], pts[3], pts[5], pts[7]):
        r = max(3, int(7*scale))
        draw.ellipse((px-r, py-r, px+r, py+r), fill=(255, 255, 220))


def _equalizer(draw, palette, seed, height=100):
    rng = random.Random(seed+19)
    x = 18
    while x < WIDTH-18:
        h = rng.randint(12, height)
        color = rng.choice((palette["accent"], palette["second"]))
        draw.rounded_rectangle((x, HEIGHT-8-h, x+12, HEIGHT-8),
                               radius=4, fill=(*color, 190))
        x += 21


def _headphones(draw, x, y, scale, color):
    w, h = int(150*scale), int(150*scale)
    draw.arc((x, y, x+w, y+h), 185, 355, fill=color, width=max(7, int(13*scale)))
    pw, ph = int(28*scale), int(58*scale)
    draw.rounded_rectangle((x-3, y+h//2-12, x+pw, y+h//2+ph),
                           radius=12, fill=color)
    draw.rounded_rectangle((x+w-pw, y+h//2-12, x+w+3, y+h//2+ph),
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
    w, h = x2-x1, y2-y1
    if art is None:
        art = Image.new("RGB", (w, h), (12, 8, 30))
        _headphones(ImageDraw.Draw(art), w//2-55, h//2-70, .8, accent)
    else:
        art = ImageOps.fit(art, (w, h), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w-1, h-1), radius=32, fill=255)
    image.paste(art, (x1, y1), mask)
    ImageDraw.Draw(image).rounded_rectangle(
        (x1-5, y1-5, x2+5, y2+5), radius=37, outline=accent, width=7
    )


def _brand(draw, palette):
    _crown(draw, 95, 35, .42, palette["gold"])
    draw.text((145, 48), "GOVIND MUSIC", font=_font(30), fill="white",
              stroke_width=2, stroke_fill=palette["accent"])
    draw.text((147, 83), "POWERED BY GOVIND BOTS",
              font=_font(13), fill=palette["gold"])


def _track_info(draw, title, duration, channel, requester, x, y, width, size=42):
    font, fitted = _fit(draw, title, width, size, 25)
    draw.text((x, y), fitted, font=font, fill="white",
              stroke_width=2, stroke_fill=(25, 8, 48))
    draw.text((x, y+65), f"{channel}  •  {duration}"[:100],
              font=_font(21, False), fill=(190, 210, 255))
    draw.text((x, y+98), f"Requested by: {requester}"[:100],
              font=_font(18), fill=(*((255, 210, 55)),))


def _render(seed, layout, palette, art, title, duration, channel, requester, bot_name):
    rng = random.Random(seed)
    image = _background(palette, seed)
    d = ImageDraw.Draw(image)
    _equalizer(d, palette, seed, rng.randint(65, 115))
    _brand(d, palette)

    if layout == "center-stage":
        _paste_art(image, art, (55, 175, 390, 510), palette["accent"])
        d = ImageDraw.Draw(image)
        d.text((440, 210), "NOW PLAYING", font=_font(25), fill=palette["second"])
        _track_info(d, title, duration, channel, requester, 440, 270, 770, 55)
        _crown(d, 930, 485, .65, palette["gold"])
    elif layout == "left-art":
        _paste_art(image, art, (65, 175, 500, 610), palette["second"])
        d = ImageDraw.Draw(image)
        d.text((555, 220), "GOVIND", font=_font(68), fill="white",
               stroke_width=3, stroke_fill=palette["accent"])
        d.text((555, 295), "MUSIC", font=_font(74), fill=palette["gold"])
        _track_info(d, title, duration, channel, requester, 560, 405, 650, 38)
    elif layout == "right-art":
        _paste_art(image, art, (790, 175, 1215, 600), palette["accent"])
        d = ImageDraw.Draw(image)
        d.text((65, 215), "ROYAL SOUND", font=_font(28), fill=palette["second"])
        d.text((65, 275), "GOVIND", font=_font(76), fill="white",
               stroke_width=3, stroke_fill=palette["accent"])
        d.text((65, 360), "MUSIC", font=_font(84), fill=palette["gold"])
        _track_info(d, title, duration, channel, requester, 75, 475, 680, 34)
    elif layout == "diagonal":
        d.polygon([(0, 500), (780, 110), (1280, 110), (1280, 720), (0, 720)],
                  fill=(20, 8, 48, 160))
        _paste_art(image, art, (820, 180, 1170, 530), palette["gold"])
        d = ImageDraw.Draw(image)
        d.text((65, 220), "GOVIND MUSIC", font=_font(76), fill="white",
               stroke_width=4, stroke_fill=palette["accent"])
        _track_info(d, title, duration, channel, requester, 75, 360, 700, 43)
    elif layout == "top-banner":
        _paste_art(image, art, (70, 220, 410, 560), palette["accent"])
        d = ImageDraw.Draw(image)
        _rounded(d, (465, 190, 1205, 575), 38, (5, 5, 20, 220), palette["second"], 5)
        d.text((510, 225), "GOVIND MUSIC", font=_font(58), fill=palette["gold"])
        _track_info(d, title, duration, channel, requester, 510, 325, 640, 42)
    elif layout == "split-screen":
        d.rectangle((0, 0, WIDTH//2, HEIGHT), fill=(8, 5, 24, 230))
        _paste_art(image, art, (690, 160, 1160, 630), palette["second"])
        d = ImageDraw.Draw(image)
        d.text((65, 205), "GOVIND", font=_font(78), fill="white",
               stroke_width=3, stroke_fill=palette["accent"])
        d.text((65, 290), "MUSIC", font=_font(86), fill=palette["gold"])
        _track_info(d, title, duration, channel, requester, 70, 420, 560, 37)
    elif layout == "royal-frame":
        d.rounded_rectangle((28, 28, WIDTH-28, HEIGHT-28), radius=42,
                            outline=palette["gold"], width=5)
        _paste_art(image, art, (75, 210, 405, 540), palette["gold"])
        d = ImageDraw.Draw(image)
        _crown(d, 820, 135, 1.0, palette["gold"])
        d.text((485, 260), "GOVIND MUSIC", font=_font(67), fill="white",
               stroke_width=3, stroke_fill=palette["accent"])
        _track_info(d, title, duration, channel, requester, 490, 365, 690, 39)
    elif layout == "equalizer-stage":
        _paste_art(image, art, (465, 155, 815, 505), palette["second"])
        d = ImageDraw.Draw(image)
        d.text((90, 190), "GOVIND", font=_font(67), fill="white",
               stroke_width=3, stroke_fill=palette["accent"])
        d.text((90, 265), "MUSIC", font=_font(76), fill=palette["gold"])
        _track_info(d, title, duration, channel, requester, 90, 390, 350, 30)
        _headphones(d, 930, 245, 1.0, palette["accent"])
    elif layout == "neon-card":
        _rounded(d, (65, 150, 1215, 610), 50, (5, 5, 22, 225), palette["accent"], 7)
        _paste_art(image, art, (95, 190, 445, 540), palette["gold"])
        d = ImageDraw.Draw(image)
        d.text((500, 205), "NOW PLAYING", font=_font(25), fill=palette["second"])
        d.text((500, 260), "GOVIND MUSIC", font=_font(56), fill="white",
               stroke_width=2, stroke_fill=palette["accent"])
        _track_info(d, title, duration, channel, requester, 505, 360, 650, 39)
    else:
        _paste_art(image, art, (825, 180, 1165, 520), palette["accent"])
        d = ImageDraw.Draw(image)
        _crown(d, 390, 185, .9, palette["gold"])
        d.text((75, 300), "GOVIND MUSIC", font=_font(70), fill="white",
               stroke_width=3, stroke_fill=palette["accent"])
        _track_info(d, title, duration, channel, requester, 85, 405, 690, 40)

    d = ImageDraw.Draw(image)
    footer = f"{bot_name}  •  PLAY  •  PAUSE  •  SKIP"
    d.text((WIDTH//2, HEIGHT-34), footer, font=_font(18), fill=(225, 225, 255), anchor="mm")
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
    Generate a 1280x720 GOVIND MUSIC PNG.
    Keeps the existing get_thumb() arguments and returns a file path.
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
        image = Image.new("RGB", (WIDTH, HEIGHT), (8, 5, 20))
        d = ImageDraw.Draw(image)
        d.text((WIDTH//2, 260), "GOVIND MUSIC", font=_font(72),
               fill=(255, 210, 0), anchor="mm")
        d.text((WIDTH//2, 370), title[:60], font=_font(36),
               fill="white", anchor="mm")

    output = CACHE_DIR / f"govind_music_{uuid.uuid4().hex}.png"
    image.save(output, format="PNG", optimize=True)
    _cleanup_cache()
    LOGGER.info("Generated thumbnail: layout=%s palette=%s path=%s",
                layout, palette["name"], output)
    return str(output)
