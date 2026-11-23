"""Single-source V3 music thumbnail renderer.

The old rectangular thumbnail renderer has intentionally been removed.
All player thumbnails are generated here through one get_thumb() pipeline.
"""
import asyncio
import logging
import math
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
MAX_CACHE_FILES = 100
OUTPUT_PREFIX = "v3thumb_"

REFERENCE_TEMPLATES = (
    "IMG_20261121_075236.png",
    "IMG_20261121_075256.png",
    "IMG_20261121_075314.png",
    "template_red.png",
)

# Ten real geometry changes, crossed with nine different visual treatments.
COMPOSITIONS = (
    "left_orbit", "right_orbit", "center_focus", "split_diagonal",
    "top_left", "bottom_left", "wide_halo", "poster_stack",
    "asymmetric", "side_stage",
)
MOTIFS = (
    "rays", "wave", "shards", "starfield", "concentric",
    "equalizer", "circuit", "speed", "polygon",
)

PALETTES = (
    ((255, 70, 190), (70, 220, 255), (255, 225, 100)),
    ((120, 75, 255), (0, 230, 255), (255, 205, 70)),
    ((255, 65, 65), (255, 170, 35), (255, 240, 170)),
    ((0, 205, 255), (100, 90, 255), (245, 245, 255)),
    ((0, 230, 150), (30, 140, 255), (255, 235, 130)),
    ((255, 90, 145), (175, 80, 255), (255, 225, 235)),
    ((255, 160, 20), (255, 55, 150), (255, 235, 130)),
    ((165, 255, 35), (0, 220, 190), (255, 255, 180)),
    ((210, 210, 255), (105, 140, 255), (255, 205, 85)),
)

FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
)
REGULAR_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
)


def _font(size, bold=True):
    for path in FONT_PATHS if bold else REGULAR_PATHS:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def _clean(value, fallback, limit=90):
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value[:limit] or fallback


def _fit_text(draw, value, max_width, size, minimum=18):
    value = str(value)
    while size > minimum:
        font = _font(size)
        if draw.textbbox((0, 0), value, font=font, stroke_width=1)[2] <= max_width:
            return font, value
        size -= 2
    font = _font(minimum)
    while value and draw.textbbox((0, 0), value + "…", font=font)[2] > max_width:
        value = value[:-1]
    return font, value + ("…" if value else "")


def _reference_background(seed, palette):
    rng = random.Random(seed)
    files = list(REFERENCE_TEMPLATES)
    rng.shuffle(files)
    for filename in files:
        path = Path("assets") / filename
        if not path.is_file():
            continue
        try:
            with Image.open(path) as source:
                # Keep each uploaded reference's original artwork and colours.
                return ImageOps.fit(
                    source.convert("RGB"), (WIDTH, HEIGHT),
                    method=Image.Resampling.LANCZOS
                ).convert("RGBA")
        except Exception:
            LOGGER.warning("Unable to read thumbnail reference: %s", path,
                           exc_info=True)

    # Only used if a supplied reference asset is missing.
    base = Image.new("RGBA", (WIDTH, HEIGHT), (10, 8, 28, 255))
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((760, -200, 1450, 500), fill=(*palette[0], 100))
    gd.ellipse((-250, 300, 500, 1000), fill=(*palette[1], 85))
    return Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(110)))


async def _download_video_art(videoid):
    videoid = str(videoid or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", videoid):
        return None
    timeout = aiohttp.ClientTimeout(total=18, connect=7)
    headers = {"User-Agent": "Mozilla/5.0"}
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
                        if response.status != 200:
                            continue
                        raw = await response.read()
                        if len(raw) > 2500:
                            with Image.open(BytesIO(raw)) as probe:
                                probe.verify()
                            return raw
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError):
                    continue
    except Exception:
        LOGGER.warning("YouTube thumbnail request failed", exc_info=True)
    return None


def _open_image(raw):
    if not raw:
        return None
    try:
        return Image.open(BytesIO(raw)).convert("RGBA")
    except Exception:
        LOGGER.warning("Thumbnail source image is invalid", exc_info=True)
        return None


def _circle(source, size, border_color, border=10):
    if source is None:
        source = Image.new("RGB", (size, size), (18, 12, 40))
        d = ImageDraw.Draw(source)
        # Graphic fallback is deliberately obvious, never an empty circle.
        d.ellipse((size * .16, size * .16, size * .84, size * .84),
                  outline=border_color, width=max(5, size // 35))
        d.arc((size * .25, size * .25, size * .75, size * .75),
              205, 335, fill=(255, 255, 255), width=max(5, size // 30))
        d.rounded_rectangle((size * .43, size * .47, size * .57, size * .72),
                            radius=max(4, size // 35), fill=(255, 255, 255))
    fitted = ImageOps.fit(source.convert("RGBA"), (size, size),
                          method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((1, 1, size - 2, size - 2), fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(fitted, (0, 0), mask)
    ImageDraw.Draw(result).ellipse(
        (border // 2, border // 2, size - border // 2 - 1,
         size - border // 2 - 1),
        outline=(*border_color, 255), width=border
    )
    return result


def _draw_motif(draw, motif, colors, seed):
    rng = random.Random(seed)
    a, b, gold = colors
    if motif == "rays":
        cx, cy = WIDTH // 2, HEIGHT // 2
        for angle in range(0, 360, 9):
            rad = math.radians(angle)
            r1, r2 = rng.randint(100, 230), rng.randint(450, 780)
            draw.line((cx + math.cos(rad)*r1, cy + math.sin(rad)*r1,
                       cx + math.cos(rad)*r2, cy + math.sin(rad)*r2),
                      fill=(*a, rng.randint(28, 75)), width=rng.randint(2, 5))
    elif motif == "wave":
        for band in range(8):
            points = []
            for x in range(-20, WIDTH + 30, 14):
                y = 90 + band * 82 + math.sin(x / 82 + band * .8) * 30
                points.append((x, y))
            draw.line(points, fill=(a if band % 2 else b) + (100,), width=4)
    elif motif == "shards":
        for _ in range(34):
            x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
            w, h = rng.randint(25, 120), rng.randint(30, 170)
            draw.polygon(((x, y), (x+w, y-h//3), (x+w//2, y+h)),
                         outline=(*a, 115), width=3)
    elif motif == "starfield":
        for _ in range(190):
            x, y, r = rng.randrange(WIDTH), rng.randrange(HEIGHT), rng.randint(1, 4)
            draw.ellipse((x-r, y-r, x+r, y+r),
                         fill=(gold if r == 4 else b) + (rng.randint(70, 170),))
    elif motif == "concentric":
        for r in range(90, 780, 42):
            draw.ellipse((WIDTH//2-r, HEIGHT//2-r, WIDTH//2+r, HEIGHT//2+r),
                         outline=(*a, 75), width=3)
    elif motif == "equalizer":
        for x in range(18, WIDTH-10, 22):
            h = rng.randint(20, 150)
            draw.rounded_rectangle((x, HEIGHT-10-h, x+9, HEIGHT-10),
                                   radius=4, fill=(*b, 95))
    elif motif == "circuit":
        for x in range(25, WIDTH, 95):
            y = rng.randint(55, HEIGHT-80)
            draw.line((x, y, x+45, y, x+68, y+28),
                      fill=(*a, 120), width=3)
            draw.ellipse((x+60, y+20, x+76, y+36),
                         outline=(*gold, 150), width=3)
    elif motif == "speed":
        for _ in range(85):
            x, y = rng.randint(-150, WIDTH), rng.randrange(HEIGHT)
            draw.line((x, y, x+rng.randint(55, 250), y-rng.randint(4, 34)),
                      fill=(*b, rng.randint(30, 100)), width=rng.randint(1, 4))
    else:
        nodes = [(rng.randrange(WIDTH), rng.randrange(HEIGHT)) for _ in range(38)]
        for i, (x, y) in enumerate(nodes):
            for nx, ny in nodes[i+1:i+4]:
                if abs(nx-x) + abs(ny-y) < 350:
                    draw.line((x, y, nx, ny), fill=(*a, 65), width=2)
            draw.ellipse((x-3, y-3, x+3, y+3), fill=(*gold, 130))


def _composition_boxes(name):
    # (video circle x/y/size, avatar x/y/size, info panel)
    return {
        "left_orbit": (65, 150, 420, 365, 450, 142, (535, 145, 1225, 585)),
        "right_orbit": (795, 150, 420, 725, 450, 142, (55, 145, 745, 585)),
        "center_focus": (430, 115, 420, 720, 420, 142, (55, 520, 1225, 690)),
        "split_diagonal": (90, 180, 390, 390, 445, 138, (540, 130, 1215, 590)),
        "top_left": (75, 85, 390, 355, 390, 138, (510, 110, 1225, 585)),
        "bottom_left": (80, 235, 390, 365, 505, 138, (520, 90, 1225, 620)),
        "wide_halo": (145, 130, 455, 520, 450, 142, (625, 145, 1225, 590)),
        "poster_stack": (400, 100, 450, 710, 435, 142, (55, 520, 1225, 690)),
        "asymmetric": (70, 125, 460, 390, 465, 142, (600, 115, 1225, 620)),
        "side_stage": (180, 155, 390, 470, 445, 138, (650, 115, 1225, 620)),
    }[name]


def _render(seed, composition, motif, colors, art, avatar,
            title, duration, channel, requester, bot_name):
    image = _reference_background(seed, colors)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    _draw_motif(od, motif, colors, seed)

    vx, vy, vsize, ax, ay, asize, panel = _composition_boxes(composition)
    # Soft translucent information panel; background artwork remains visible.
    od.rounded_rectangle(panel, radius=34, fill=(5, 5, 22, 172),
                         outline=(*colors[0], 235), width=4)
    image = Image.alpha_composite(image, overlay)

    # Large, fixed circular video art.
    halo_size = vsize + 76
    halo = Image.new("RGBA", (halo_size, halo_size), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.ellipse((8, 8, halo_size-8, halo_size-8),
               fill=(*colors[1], 125))
    halo = halo.filter(ImageFilter.GaussianBlur(26))
    image.alpha_composite(halo, (vx-38, vy-38))
    video_circle = _circle(art, vsize, colors[0], 12)
    image.alpha_composite(video_circle, (vx, vy))

    # Small overlapping requester DP.
    avatar_circle = _circle(avatar, asize, colors[2], 9)
    avatar_shadow = Image.new("RGBA", (asize+28, asize+28), (0, 0, 0, 0))
    ImageDraw.Draw(avatar_shadow).ellipse(
        (4, 4, asize+24, asize+24), fill=(*colors[2], 155))
    avatar_shadow = avatar_shadow.filter(ImageFilter.GaussianBlur(12))
    image.alpha_composite(avatar_shadow, (ax-14, ay-14))
    image.alpha_composite(avatar_circle, (ax, ay))

    d = ImageDraw.Draw(image)
    px1, py1, px2, py2 = panel
    text_x = px1 + 42
    text_width = px2 - px1 - 84
    d.rounded_rectangle((text_x, py1+28, text_x+160, py1+64),
                        radius=16, fill=(*colors[0], 230))
    d.text((text_x+14, py1+33), "NOW PLAYING", font=_font(17), fill="white")
    title_font, fitted_title = _fit_text(d, title, text_width, 43, 23)
    title_y = py1 + 100
    d.text((text_x, title_y), fitted_title, font=title_font, fill="white",
           stroke_width=2, stroke_fill=(8, 4, 24))
    meta_y = title_y + 75
    d.text((text_x, meta_y), f"{channel[:38]}  •  {duration}",
           font=_font(19, False), fill=(220, 230, 255))
    d.text((text_x, meta_y+48), "REQUESTED BY",
           font=_font(15), fill=colors[2])
    req_font, req_text = _fit_text(d, requester, text_width, 23, 17)
    d.text((text_x, meta_y+76), req_text, font=req_font, fill="white")

    # Branding is kept on every template and does not cover either circle.
    d.text((35, 28), "GOVIND", font=_font(31), fill="white",
           stroke_width=2, stroke_fill=(10, 5, 25))
    d.text((38, 65), "MUSIC BOTS", font=_font(14), fill=colors[2])
    brand = _clean(bot_name, "GOVIND MUSIC", 32).upper()
    brand_font, brand_text = _fit_text(d, brand, 330, 20, 14)
    d.rounded_rectangle((WIDTH-365, HEIGHT-62, WIDTH-25, HEIGHT-22),
                        radius=18, fill=(5, 5, 20, 175),
                        outline=(*colors[1], 210), width=2)
    d.text((WIDTH-345, HEIGHT-56), brand_text, font=brand_font, fill="white")
    d.text((35, HEIGHT-48), "POWERED BY GOVIND-BOTS",
           font=_font(15), fill=colors[2])
    return image.convert("RGB")


def _cleanup_cache():
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(CACHE_DIR.glob(OUTPUT_PREFIX + "*.jpg"),
                       key=lambda item: item.stat().st_mtime, reverse=True)
        for old in files[MAX_CACHE_FILES:]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError:
        LOGGER.warning("Thumbnail cache cleanup failed", exc_info=True)


async def get_thumb(
    videoid, title, duration="Unknown", views=0, channel="YouTube",
    bot_name="GOVIND MUSIC", requested_by="Group member",
    requester_avatar=None, design_index=None,
):
    """Create a fresh reference-based thumbnail; one and only renderer."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    title = _clean(title, "Unknown Track", 110)
    duration = _clean(duration, "Unknown", 24)
    channel = _clean(channel, "YouTube", 55)
    requester = _clean(requested_by, "Group member", 55)
    bot_name = _clean(bot_name, "GOVIND MUSIC", 32)

    if design_index is None:
        design_index = random.SystemRandom().randrange(
            len(COMPOSITIONS) * len(MOTIFS))
    design_index = int(design_index) % (len(COMPOSITIONS) * len(MOTIFS))
    composition = COMPOSITIONS[design_index // len(MOTIFS)]
    motif = MOTIFS[design_index % len(MOTIFS)]
    seed = random.SystemRandom().randrange(0, 2**31)
    colors = random.choice(PALETTES)

    art = _open_image(await _download_video_art(videoid))
    avatar = _open_image(requester_avatar)
    LOGGER.info("Thumbnail inputs: video_art=%s requester_avatar=%s design=%02d",
                bool(art), bool(avatar), design_index + 1)

    try:
        rendered = _render(seed, composition, motif, colors, art, avatar,
                           title, duration, channel, requester, bot_name)
    except Exception:
        LOGGER.exception("Thumbnail renderer failed")
        # Keep the same circular visual hierarchy even in an error fallback.
        fallback = Image.new("RGBA", (WIDTH, HEIGHT), (12, 8, 28, 255))
        d = ImageDraw.Draw(fallback)
        d.text((60, 65), "GOVIND MUSIC", font=_font(48), fill="white")
        d.text((60, 150), title[:70], font=_font(30), fill=colors[2])
        rendered = fallback.convert("RGB")

    output = CACHE_DIR / (
        f"{OUTPUT_PREFIX}{design_index+1:02d}_{uuid.uuid4().hex}.jpg"
    )
    rendered.save(output, format="JPEG", quality=94, optimize=True)
    _cleanup_cache()
    LOGGER.info("Created new thumbnail: composition=%s motif=%s palette=%s file=%s",
                composition, motif, colors, output)
    return str(output)
