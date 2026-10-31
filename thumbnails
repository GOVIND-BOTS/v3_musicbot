
import asyncio
import logging
from pathlib import Path
from io import BytesIO

import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance


LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"

WIDTH = 1280
HEIGHT = 720


def get_font(size, bold=False):
    """Load a readable system font."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]

    for font_path in font_paths:
        if Path(font_path).exists():
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass

    return ImageFont.load_default()


def shorten(text, limit):
    text = str(text or "")
    if len(text) > limit:
        return text[:limit - 3] + "..."
    return text


def format_duration(duration):
    if isinstance(duration, str):
        return duration

    try:
        duration = int(duration or 0)
    except (ValueError, TypeError):
        return "Unknown"

    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    return f"{minutes:02}:{seconds:02}"


async def download_thumb(videoid):
    if not videoid:
        return None

    urls = [
        f"https://i.ytimg.com/vi/{videoid}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{videoid}/hqdefault.jpg",
    ]

    timeout = aiohttp.ClientTimeout(total=12)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for url in urls:
                try:
                    async with session.get(url) as response:
                        if response.status != 200:
                            continue

                        data = await response.read()

                        image = Image.open(BytesIO(data))
                        image.load()

                        if image.width < 100 or image.height < 100:
                            continue

                        return image.convert("RGB")

                except Exception as error:
                    LOGGER.warning("Thumbnail download failed: %s", error)

    except Exception as error:
        LOGGER.warning("Thumbnail session failed: %s", error)

    return None


def create_circle(image, size):
    image = image.copy().convert("RGB")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)

    background = Image.new("RGB", (size, size), (20, 20, 30))
    x = (size - image.width) // 2
    y = (size - image.height) // 2
    background.paste(image, (x, y))

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size - 1, size - 1), fill=255)

    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(background, (0, 0), mask)

    return result


def create_thumbnail(
    source,
    title,
    duration,
    requested_by,
    bot_name,
):
    if source:
        background = source.resize(
            (WIDTH, HEIGHT),
            Image.Resampling.LANCZOS
        )
        background = background.filter(
            ImageFilter.GaussianBlur(28)
        )
        background = ImageEnhance.Brightness(
            background
        ).enhance(0.35)
    else:
        background = Image.new(
            "RGB",
            (WIDTH, HEIGHT),
            (13, 17, 30)
        )

    background = background.convert("RGBA")

    overlay = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (5, 8, 20, 115)
    )
    background = Image.alpha_composite(background, overlay)

    draw = ImageDraw.Draw(background)

    # Top branding
    brand_font = get_font(48, True)
    brand = shorten(bot_name or "GOVIND MUSIC", 24)

    bbox = draw.textbbox((0, 0), brand, font=brand_font)
    brand_width = bbox[2] - bbox[0]

    draw.text(
        ((WIDTH - brand_width) // 2, 35),
        brand,
        font=brand_font,
        fill=(255, 255, 255, 255),
        stroke_width=2,
        stroke_fill=(20, 20, 35, 255)
    )

    # Started playing label
    label_font = get_font(27, True)
    label = "NOW PLAYING"

    bbox = draw.textbbox((0, 0), label, font=label_font)
    label_width = bbox[2] - bbox[0]

    draw.text(
        ((WIDTH - label_width) // 2, 105),
        label,
        font=label_font,
        fill=(90, 210, 255, 255)
    )

    # Circular artist/song image
    if source:
        circle = create_circle(source, 310)
    else:
        circle = create_circle(
            Image.new("RGB", (310, 310), (30, 40, 65)),
            310
        )

    circle_x = (WIDTH - 310) // 2
    circle_y = 165

    draw.ellipse(
        (
            circle_x - 9,
            circle_y - 9,
            circle_x + 319,
            circle_y + 319
        ),
        fill=(255, 255, 255, 255)
    )

    background.alpha_composite(circle, (circle_x, circle_y))

    draw = ImageDraw.Draw(background)

    # Song title
    title = shorten(title or "Unknown Track", 65)
    title_font = get_font(38, True)

    bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = bbox[2] - bbox[0]

    draw.text(
        ((WIDTH - title_width) // 2, 515),
        title,
        font=title_font,
        fill=(255, 255, 255, 255)
    )

    # Requested by
    requester = shorten(requested_by or "Group member", 35)
    requester_font = get_font(25)

    requester_text = f"Requested by: {requester}"
    bbox = draw.textbbox(
        (0, 0),
        requester_text,
        font=requester_font
    )
    requester_width = bbox[2] - bbox[0]

    draw.text(
        ((WIDTH - requester_width) // 2, 575),
        requester_text,
        font=requester_font,
        fill=(185, 205, 230, 255)
    )

    # Duration
    duration_text = f"Duration: {format_duration(duration)}"
    duration_font = get_font(23)

    bbox = draw.textbbox(
        (0, 0),
        duration_text,
        font=duration_font
    )
    duration_width = bbox[2] - bbox[0]

    draw.text(
        ((WIDTH - duration_width) // 2, 635),
        duration_text,
        font=duration_font,
        fill=(225, 225, 235, 255)
    )

    return background.convert("RGB")


async def get_thumb(
    videoid,
    title,
    duration="Unknown",
    views=0,
    channel="YouTube",
    bot_name="GOVIND MUSIC",
    requested_by="Group member",
):
    """Generate and return a GOVIND MUSIC thumbnail path."""

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    safe_id = "".join(
        char for char in str(videoid or "track")
        if char.isalnum() or char in ("-", "_")
    )

    output_path = CACHE_DIR / f"{safe_id}_govind.jpg"

    try:
        source = await download_thumb(videoid)

        image = await asyncio.to_thread(
            create_thumbnail,
            source,
            title,
            duration,
            requested_by,
            bot_name,
        )

        await asyncio.to_thread(
            image.save,
            output_path,
            "JPEG",
            quality=92,
            optimize=True,
        )

        return str(output_path)

    except Exception:
        LOGGER.exception("Failed to generate GOVIND MUSIC thumbnail")

        if source is not None:
            fallback_path = CACHE_DIR / f"{safe_id}_fallback.jpg"
            try:
                await asyncio.to_thread(
                    source.save,
                    fallback_path,
                    "JPEG",
                    quality=90,
                )
                return str(fallback_path)
            except Exception:
                pass

        return None
