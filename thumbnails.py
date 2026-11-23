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
    {"name": "crimson-ice", "accent": (255, 35, 75), "second": (45, 210, 255), "gold": (255, 220, 120)},
    {"name": "emerald-flare", "accent": (0, 255, 155), "second": (40, 120, 255), "gold": (255, 235, 120)},
    {"name": "sunset-blaze", "accent": (255, 95, 35), "second": (255, 35, 155), "gold": (255, 225, 90)},
    {"name": "arctic-luxe", "accent": (110, 235, 255), "second": (190, 150, 255), "gold": (255, 255, 255)},
    {"name": "toxic-lime", "accent": (190, 255, 0), "second": (0, 220, 175), "gold": (255, 255, 170)},
    {"name": "rose-chrome", "accent": (255, 90, 170), "second": (185, 190, 255), "gold": (255, 225, 235)},
    {"name": "inferno", "accent": (255, 55, 15), "second": (255, 170, 0), "gold": (255, 240, 150)},
    {"name": "ocean-depth", "accent": (0, 100, 210), "second": (0, 235, 220), "gold": (180, 245, 255)},
    {"name": "cyber-lime", "accent": (165, 255, 30), "second": (40, 175, 255), "gold": (255, 255, 180)},
    {"name": "ultraviolet", "accent": (145, 35, 255), "second": (255, 45, 205), "gold": (255, 215, 120)},
    {"name": "monochrome-gold", "accent": (235, 235, 245), "second": (130, 145, 175), "gold": (255, 190, 55)},
    {"name": "candy-pop", "accent": (255, 65, 180), "second": (80, 225, 255), "gold": (255, 245, 120)},
    {"name": "jade-purple", "accent": (0, 220, 165), "second": (155, 75, 255), "gold": (255, 220, 110)},
    {"name": "blue-flame", "accent": (35, 135, 255), "second": (0, 245, 255), "gold": (255, 190, 75)},
    {"name": "ruby-noir", "accent": (220, 20, 65), "second": (110, 25, 145), "gold": (255, 205, 100)},
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
    # YouTube does not provide max-resolution art for every video.
    # Try every standard thumbnail size before falling back to generated artwork.
    urls = (
        f"https://i.ytimg.com/vi/{videoid}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{videoid}/sddefault.jpg",
        f"https://i.ytimg.com/vi/{videoid}/hqdefault.jpg",
        f"https://i.ytimg.com/vi/{videoid}/mqdefault.jpg",
        f"https://i.ytimg.com/vi/{videoid}/default.jpg",
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


# ---------------------------------------------------------------------------
# V3 PREMIUM 90-DESIGN ENGINE
# Ten genuinely different compositions multiplied by nine visual treatments.
# Each preset changes geometry/composition/effects, not just the colour palette.
# ---------------------------------------------------------------------------
DESIGN_COMPOSITIONS = (
    "left_orbit", "right_orbit", "center_poster", "split_diagonal",
    "top_stage", "bottom_stage", "corner_focus", "double_panel",
    "wide_halo", "asymmetric",
)
DESIGN_MOTIFS = (
    "circuit", "radial_rays", "wave_ribbons", "shards", "starfield",
    "concentric", "equalizer", "speed_lines", "polygon_mesh",
)
DESIGN_PRESETS = tuple(
    (f"design_{index + 1:02d}", composition, motif)
    for index, (composition, motif) in enumerate(
        ( (composition, motif) for composition in DESIGN_COMPOSITIONS
          for motif in DESIGN_MOTIFS )
    )
)


def _circle_crop(source, size, border=0, border_color=(255, 255, 255)):
    source = ImageOps.fit(source.convert("RGBA"), (size, size),
                          method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((1, 1, size - 2, size - 2), fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(source, (0, 0), mask)
    if border:
        ImageDraw.Draw(result).ellipse(
            (border // 2, border // 2, size - border // 2 - 1,
             size - border // 2 - 1),
            outline=(*border_color, 255), width=border
        )
    return result


def _avatar_image(data):
    if not data:
        return None
    try:
        return Image.open(BytesIO(data)).convert("RGBA")
    except Exception:
        LOGGER.debug("Requester avatar could not be decoded", exc_info=True)
        return None


def _draw_motif(draw, motif, accent, second, seed):
    rng = random.Random(seed)
    a, b = (*accent, 48), (*second, 42)
    if motif == "circuit":
        for x in range(35, WIDTH, 105):
            y = rng.randint(90, HEIGHT - 90)
            draw.line((x, y, x + 55, y, x + 75, y + 35), fill=a, width=3)
            draw.ellipse((x + 68, y + 28, x + 82, y + 42), outline=b, width=3)
    elif motif == "radial_rays":
        cx, cy = WIDTH // 2, HEIGHT // 2
        for angle in range(0, 360, 12):
            import math
            r1, r2 = rng.randint(90, 230), rng.randint(430, 760)
            x1, y1 = cx + int(math.cos(math.radians(angle))*r1), cy + int(math.sin(math.radians(angle))*r1)
            x2, y2 = cx + int(math.cos(math.radians(angle))*r2), cy + int(math.sin(math.radians(angle))*r2)
            draw.line((x1, y1, x2, y2), fill=a, width=rng.randint(2, 5))
    elif motif == "wave_ribbons":
        for band in range(7):
            points = []
            for x in range(-20, WIDTH + 40, 18):
                import math
                y = 110 + band * 78 + int(math.sin(x / 85 + band) * 34)
                points.append((x, y))
            draw.line(points, fill=a if band % 2 else b, width=5)
    elif motif == "shards":
        for _ in range(30):
            x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
            w, h = rng.randint(18, 90), rng.randint(25, 150)
            draw.polygon([(x, y), (x+w, y-h//3), (x+w//2, y+h)], outline=a, width=3)
    elif motif == "starfield":
        for _ in range(170):
            x, y, r = rng.randrange(WIDTH), rng.randrange(HEIGHT), rng.randint(1, 4)
            draw.ellipse((x-r, y-r, x+r, y+r), fill=a if r % 2 else b)
    elif motif == "concentric":
        for r in range(80, 760, 48):
            draw.ellipse((WIDTH//2-r, HEIGHT//2-r, WIDTH//2+r, HEIGHT//2+r),
                         outline=a if r % 2 else b, width=3)
    elif motif == "equalizer":
        for x in range(28, WIDTH-20, 24):
            h = rng.randint(22, 160)
            draw.rounded_rectangle((x, HEIGHT-18-h, x+10, HEIGHT-18),
                                   radius=5, fill=a if x % 2 else b)
    elif motif == "speed_lines":
        for _ in range(70):
            x, y = rng.randint(-100, WIDTH), rng.randrange(HEIGHT)
            draw.line((x, y, x+rng.randint(60, 260), y-rng.randint(4, 30)),
                      fill=a, width=rng.randint(1, 4))
    else:
        nodes = [(rng.randrange(WIDTH), rng.randrange(HEIGHT)) for _ in range(34)]
        for i, (x, y) in enumerate(nodes):
            for nx, ny in nodes[i+1:i+4]:
                if abs(nx-x) + abs(ny-y) < 360:
                    draw.line((x, y, nx, ny), fill=a, width=2)
            draw.ellipse((x-4, y-4, x+4, y+4), fill=b)


REFERENCE_TEMPLATES = (
    "IMG_20261121_075236.png",
    "IMG_20261121_075256.png",
    "IMG_20261121_075314.png",
    "template_red.png",
)


def _reference_canvas(palette, seed):
    """Use the four user-uploaded artwork references as real visual bases."""
    rng = random.Random(seed ^ 0x35A91)
    candidates = [Path("assets") / name for name in REFERENCE_TEMPLATES]
    rng.shuffle(candidates)
    for path in candidates:
        if not path.is_file():
            continue
        try:
            with Image.open(path) as source:
                base = ImageOps.fit(source.convert("RGB"), (WIDTH, HEIGHT),
                                    method=Image.Resampling.LANCZOS).convert("RGBA")
            # Preserve the uploaded template at full brightness and original colour.
            # No tint, dark wash, blur, or vignette: the reference artwork stays clear.
            return base
        except Exception:
            LOGGER.warning("Could not load thumbnail reference %s", path, exc_info=True)
    return _background(palette, seed)


def _render_premium(seed, composition, motif, palette, art, avatar,
                    title, duration, channel, requester, bot_name):
    """Keep the YouTube artwork and requester avatar in fixed, unmistakable circles."""
    image = _reference_canvas(palette, seed).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    _draw_motif(d, motif, palette["accent"], palette["second"], seed)

    # A restrained panel keeps the artwork visible instead of covering it.
    panel_box = (535, 145, 1225, 585)
    d.rounded_rectangle(
        panel_box, radius=38, fill=(5, 5, 22, 205),
        outline=(*palette["accent"], 245), width=5
    )
    image.alpha_composite(overlay)

    # Large circle: actual YouTube video thumbnail.
    video_size = 410
    vx, vy = 75, 155
    if art is None:
        art = Image.new("RGB", (video_size, video_size), (15, 12, 35))
        ad = ImageDraw.Draw(art)
        _headphones(ad, 130, 115, 1.0, palette["second"])
        LOGGER.warning("YouTube artwork unavailable; using visible fallback art")
    video_circle = _circle_crop(
        art, video_size, border=12, border_color=palette["accent"]
    )

    halo = Image.new("RGBA", (video_size + 100, video_size + 100), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.ellipse(
        (8, 8, video_size + 92, video_size + 92),
        fill=(*palette["second"], 85)
    )
    halo = halo.filter(ImageFilter.GaussianBlur(28))
    image.alpha_composite(halo, (vx - 50, vy - 50))
    image.alpha_composite(video_circle, (vx, vy))

    # Small overlapping circle: the person who requested the song.
    avatar_size = 142
    ax, ay = 365, 445
    if avatar is None:
        LOGGER.warning("Requester avatar unavailable; displaying initials fallback")
        avatar_circle = Image.new("RGBA", (avatar_size, avatar_size), (0, 0, 0, 0))
        avd = ImageDraw.Draw(avatar_circle)
        avd.ellipse(
            (5, 5, avatar_size - 5, avatar_size - 5),
            fill=(18, 12, 42, 255), outline=(*palette["gold"], 255), width=8
        )
        initials = (requester or "U").strip()[:1].upper()
        avd.text((avatar_size // 2, avatar_size // 2), initials,
                 font=_font(58), fill="white", anchor="mm")
    else:
        avatar_circle = _circle_crop(
            avatar, avatar_size, border=9, border_color=palette["gold"]
        )

    shadow = Image.new("RGBA", (avatar_size + 32, avatar_size + 32), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(
        (4, 4, avatar_size + 28, avatar_size + 28),
        fill=(*palette["gold"], 130)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    image.alpha_composite(shadow, (ax - 16, ay - 16))
    image.alpha_composite(avatar_circle, (ax, ay))

    d = ImageDraw.Draw(image)
    _brand_top(d, palette)
    d.text((585, 195), "NOW PLAYING", font=_font(25), fill=palette["second"])
    font, fitted = _fit(d, title, 585, 45, 25)
    d.text((585, 265), fitted, font=font, fill="white",
           stroke_width=2, stroke_fill=(8, 4, 24))
    d.text((585, 355), f"{channel[:42]}  •  {duration}",
           font=_font(21, False), fill=(205, 220, 255))
    d.text((585, 410), "REQUESTED BY",
           font=_font(17), fill=palette["gold"])
    requester_font, requester_text = _fit(d, requester, 570, 24, 18)
    d.text((585, 445), requester_text, font=requester_font, fill="white")
    _brand_bottom(d, bot_name, palette)

    # Distinct frame treatment remains independent of the chosen colour palette.
    if motif in ("concentric", "radial_rays"):
        d.ellipse((22, 22, WIDTH - 22, HEIGHT - 22),
                  outline=(*palette["gold"], 190), width=4)
    elif motif in ("shards", "polygon_mesh"):
        d.polygon([(0, 0), (WIDTH, 0), (WIDTH, 38), (0, 180)],
                  outline=(*palette["second"], 210))
    elif motif == "circuit":
        d.rounded_rectangle((18, 18, WIDTH - 18, HEIGHT - 18), radius=18,
                            outline=(*palette["second"], 190), width=3)
    return image.convert("RGB")

async def get_thumb(
    videoid, title, duration="Unknown", views=0, channel="YouTube",
    bot_name="GOVIND MUSIC", requested_by="Group member",
    requester_avatar=None, design_index=None,
):
    """Render one of 90 distinct 1280x720 compositions as a PNG."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    title = _clean(title, "Unknown Track", 110)
    duration = _clean(duration, "Unknown", 24)
    channel = _clean(channel, "YouTube", 60)
    requester = _clean(requested_by, "Group member", 55)
    bot_name = _clean(bot_name, "GOVIND MUSIC", 32)

    if design_index is None:
        design_index = random.SystemRandom().randrange(90)
    design_index = int(design_index) % 90
    design_name, composition, motif = DESIGN_PRESETS[design_index]
    seed = random.SystemRandom().randrange(0, 2**31)
    palette = random.choice(PALETTES)
    art_data = await _download_youtube_thumb(videoid)
    art = _load_art(art_data)
    avatar = _avatar_image(requester_avatar)
    LOGGER.info(
        "Thumbnail source status: video_id=%s video_art=%s requester_avatar=%s",
        videoid, bool(art), bool(avatar)
    )

    try:
        image = _render_premium(
            seed, composition, motif, palette, art, avatar,
            title, duration, channel, requester, bot_name,
        )
    except Exception:
        LOGGER.exception("Premium thumbnail rendering failed; using fallback")
        image = Image.new("RGB", (WIDTH, HEIGHT), (10, 6, 24))
        d = ImageDraw.Draw(image)
        d.text((WIDTH//2, 250), "GOVIND MUSIC", font=_font(58),
               fill=(255, 210, 0), anchor="mm")
        d.text((WIDTH//2, 360), title[:55], font=_font(34),
               fill="white", anchor="mm")

    output = CACHE_DIR / f"govind_music_d{design_index + 1:02d}_{uuid.uuid4().hex}.png"
    image.save(output, format="PNG", optimize=True)
    _cleanup_cache()
    LOGGER.info("Generated %s (preset %d/90, %s + %s): %s",
                design_name, design_index + 1, composition, motif, output)
    return str(output)
