import os
import random
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
import numpy as np

FALLBACK_IMG = "https://telegra.ph/file/5f3ee7a2b1e0a0b0c0e0e.jpg"


def make_col():
    return (random.randint(40, 220), random.randint(40, 220), random.randint(40, 220))


def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    return image.resize((newWidth, newHeight))


def truncate(text, limit=28):
    words = text.split(" ")
    line1, line2 = "", ""
    for w in words:
        if len(line1) + len(w) < limit:
            line1 += " " + w
        elif len(line2) + len(w) < limit:
            line2 += " " + w
    return [line1.strip(), line2.strip()]


def get_font(size):
    paths = [
        "assets/font2.ttf",
        "assets/font.ttf",
        "assets/adisa.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    return ImageFont.load_default()


async def download_thumb(videoid: str):
    os.makedirs("cache", exist_ok=True)
    path = f"cache/raw_{videoid}.jpg"
    if os.path.isfile(path):
        return path

    urls = [
        f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg",
        f"https://img.youtube.com/vi/{videoid}/mqdefault.jpg",
    ]
    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        async with aiofiles.open(path, "wb") as f:
                            await f.write(data)
                        return path
            except:
                continue
    return None


async def get_thumb(videoid, title="Unknown", duration="00:00", views="Unknown", channel="Unknown", bot_name="V3 MUSIC"):
    os.makedirs("cache", exist_ok=True)
    final_path = f"cache/{videoid}.jpg"
    if os.path.isfile(final_path):
        return final_path

    try:
        raw = await download_thumb(videoid)
        if not raw or not os.path.isfile(raw):
            return FALLBACK_IMG

        title = re.sub(r"\W+", " ", title).title().strip() or "Unknown Title"

        youtube = Image.open(raw).convert("RGBA")
        image1 = changeImageSize(1280, 720, youtube)
        background = image1.filter(ImageFilter.BoxBlur(28))
        background = ImageEnhance.Brightness(background).enhance(0.55)

        image3 = image1.crop((280, 0, 1000, 720))
        lum_img = Image.new("L", [720, 720], 0)
        ImageDraw.Draw(lum_img).pieslice([(0, 0), (720, 720)], 0, 360, fill=255)
        img_arr = np.array(image3.resize((720, 720)))
        final_arr = np.dstack((img_arr, np.array(lum_img)))
        circle_thumb = Image.fromarray(final_arr).resize((580, 580))
        background.paste(circle_thumb, (60, 70), mask=circle_thumb)

        if os.path.exists("assets/zedzex.png"):
            try:
                circle = Image.open("assets/zedzex.png").convert("RGBA")
                data = np.array(circle)
                r, g, b, a = data.T
                white = (r > 240) & (g > 240) & (b > 240)
                data[..., :-1][white.T] = make_col()
                background.paste(Image.fromarray(data), (0, 0), mask=circle)
            except:
                pass

        draw = ImageDraw.Draw(background)
        draw.text((18, 14), f"♡ {bot_name}", fill="white", font=get_font(28))
        draw.text((680, 130), "NOW PLAYING", fill="white", font=get_font(62), stroke_width=2, stroke_fill="#111")
        
        t1, t2 = truncate(title)
        draw.text((680, 250), t1, fill="white", font=get_font(36), stroke_width=1, stroke_fill="#111")
        if t2:
            draw.text((680, 300), t2, fill="white", font=get_font(36), stroke_width=1, stroke_fill="#111")

        y = 400
        for line in [f"⏱  Duration : {duration}", f"👁  Views    : {views}", f"📢  Channel  : {channel[:28]}"]:
            draw.text((680, y), line, fill="#EEEEEE", font=get_font(30))
            y += 48

        background = ImageOps.expand(background.convert("RGB"), border=18, fill=make_col())
        background.save(final_path, quality=92)
        return final_path
    except Exception as e:
        print(f"[thumb] {e}")
        return FALLBACK_IMG
