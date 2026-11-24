"""Single-pass circular music thumbnail renderer.

Uses one clean reference template. The template already contains its neon
rings and branding, so this module ONLY inserts the video art and requester
avatar into the two circular cut-outs. No second panel/layout is drawn.
"""
import asyncio
import logging
import random
import re
import uuid
from io import BytesIO
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps

LOGGER = logging.getLogger(__name__)

WIDTH, HEIGHT = 1280, 720
CACHE_DIR = Path("cache")
OUTPUT_PREFIX = "v3thumb_"
TEMPLATE_PATH = Path("assets/IMG_20261121_075236.png")

# Coordinates are for the supplied 16:9 neon template at 1280x720.
# Keep the neon borders visible by placing the photos slightly inside them.
VIDEO_BOX = (431, 119, 849, 537)       # left, top, right, bottom
AVATAR_BOX = (773, 418, 919, 564)      # fixed 146x146 requester circle


def _font(size=42):
    for path in (
        "assets/font.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            if Path(path).is_file():
                return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _open_image(raw):
    if not raw:
        return None
    try:
        if isinstance(raw, (str, Path)) and Path(raw).is_file():
            return Image.open(raw).convert("RGBA")
        return Image.open(BytesIO(raw)).convert("RGBA")
    except Exception:
        LOGGER.warning("Invalid thumbnail image input", exc_info=True)
        return None


def _circle_crop(source, box, fallback_label="♪"):
    left, top, right, bottom = box
    size = min(right - left, bottom - top)
    if source is None:
        source = Image.new("RGBA", (size, size), (12, 8, 30, 255))
        draw = ImageDraw.Draw(source)
        draw.ellipse((size * .12, size * .12, size * .88, size * .88),
                     outline=(255, 255, 255, 180), width=max(3, size // 35))
        font = _font(max(24, size // 2))
        bounds = draw.textbbox((0, 0), fallback_label, font=font)
        draw.text(((size - (bounds[2] - bounds[0])) / 2,
                   (size - (bounds[3] - bounds[1])) / 2 - bounds[1]),
                  fallback_label, font=font, fill="white")
    source = ImageOps.fit(
        source.convert("RGBA"), (size, size),
        method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
    )
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(source, (0, 0), mask)
    return result


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
                        if len(raw) < 2500:
                            continue
                        with Image.open(BytesIO(raw)) as probe:
                            probe.verify()
                        return raw
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError):
                    continue
    except Exception:
        LOGGER.warning("Could not download YouTube artwork", exc_info=True)
    return None


def _load_template():
    if not TEMPLATE_PATH.is_file():
        raise FileNotFoundError(
            f"Required clean thumbnail template is missing: {TEMPLATE_PATH}"
        )
    with Image.open(TEMPLATE_PATH) as source:
        return ImageOps.fit(
            source.convert("RGBA"), (WIDTH, HEIGHT),
            method=Image.Resampling.LANCZOS
        )


def _render(video_art, requester_avatar):
    # Start from the finished artwork. Do NOT draw another panel, neon ring,
    # second video circle, title panel, or duplicate branding over it.
    image = _load_template()
    video = _circle_crop(video_art, VIDEO_BOX)
    avatar = _circle_crop(requester_avatar, AVATAR_BOX, fallback_label="👤")

    image.alpha_composite(video, (VIDEO_BOX[0], VIDEO_BOX[1]))
    image.alpha_composite(avatar, (AVATAR_BOX[0], AVATAR_BOX[1]))
    return image.convert("RGB")


def save_requester_avatar(raw, user_id):
    """Persist the requester DP once so thumbnail refresh uses the same image."""
    if not raw or not user_id:
        return None
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        target = CACHE_DIR / f"requester_{int(user_id)}.jpg"
        avatar = _open_image(raw)
        if avatar is None:
            return None
        avatar.convert("RGB").save(target, format="JPEG", quality=92, optimize=True)
        return str(target)
    except Exception:
        LOGGER.warning("Could not cache requester avatar", exc_info=True)
        return None


async def get_thumb(
    videoid, title, duration="Unknown", views=0, channel="YouTube",
    bot_name="GOVIND MUSIC", requested_by="Group member",
    requester_avatar=None, design_index=None,
):
    """Generate one clean thumbnail from the single circular template."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    video_art = _open_image(await _download_video_art(videoid))
    avatar = _open_image(requester_avatar)

    LOGGER.info(
        "Thumbnail assets: video_art=%s requester_avatar=%s template=%s",
        bool(video_art), bool(avatar), TEMPLATE_PATH
    )

    try:
        rendered = _render(video_art, avatar)
    except Exception:
        LOGGER.exception("Single-template thumbnail render failed")
        # Keep a valid image result rather than falling back to the old layout.
        rendered = Image.new("RGB", (WIDTH, HEIGHT), (8, 8, 20))

    output = CACHE_DIR / f"{OUTPUT_PREFIX}{uuid.uuid4().hex}.jpg"
    rendered.save(output, format="JPEG", quality=95, optimize=True)
    _cleanup_cache()
    LOGGER.info("Created single-layout thumbnail: %s", output)
    return str(output)


def _cleanup_cache():
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(
            CACHE_DIR.glob(OUTPUT_PREFIX + "*.jpg"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for old in files[100:]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError:
        LOGGER.warning("Thumbnail cache cleanup failed", exc_info=True)
