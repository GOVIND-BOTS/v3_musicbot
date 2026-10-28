import asyncio
import os
from pathlib import Path
from io import BytesIO
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
FALLBACK_IMG = "https://placehold.co/1280x720/171717/FFFFFF.jpg"

def _font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

async def download_thumb(videoid):
    if not videoid:
        return FALLBACK_IMG
    target = CACHE_DIR / f"{videoid}.jpg"
    if target.exists():
        return str(target)
    urls = [
        f"https://i.ytimg.com/vi/{videoid}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{videoid}/hqdefault.jpg",
    ]
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for url in urls:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.read()
                        image = Image.open(BytesIO(data)).convert("RGB")
                        image.save(target, "JPEG", quality=90)
                        return str(target)
    except Exception:
        pass
    return FALLBACK_IMG

async def get_thumb(videoid, title, duration="Unknown", views=0, channel="YouTube", bot_name="V3 MUSIC"):
    source = await download_thumb(videoid)
    try:
        if source.startswith("http"):
            async with aiohttp.ClientSession() as session:
                async with session.get(source, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status != 200:
                        return source
                    data = await resp.read()
            img = Image.open(BytesIO(data)).convert("RGB")
        else:
            img = Image.open(source).convert("RGB")
        img = img.resize((1280, 720))
        img = img.filter(ImageFilter.GaussianBlur(2))
        overlay = Image.new("RGBA", img.size, (10, 10, 10, 155))
        img = Image.alpha_composite(img.convert("RGBA"), overlay)
        draw = ImageDraw.Draw(img)
        draw.text((60, 70), bot_name[:45], font=_font(38), fill="white")
        draw.text((60, 430), (title or "Unknown title")[:65], font=_font(34), fill="white")
        draw.text((60, 500), f"Duration: {duration}  |  Views: {views or 0}", font=_font(24), fill=(220,220,220))
        draw.text((60, 555), (channel or "YouTube")[:70], font=_font(24), fill=(220,220,220))
        target = CACHE_DIR / f"{videoid or 'track'}_card.jpg"
        img.convert("RGB").save(target, "JPEG", quality=90)
        return str(target)
    except Exception:
        return source
