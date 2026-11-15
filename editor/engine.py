import asyncio
import os
import tempfile
from PIL import Image, ImageEnhance, ImageOps, ImageFilter, ImageDraw, ImageFont

MAX_SECONDS = 120

def parse_options(raw):
    result = {}
    for part in (raw or "").split():
        if "=" in part:
            key, value = part.split("=", 1)
            result[key.lower()] = value
        elif part.lower() in ("mute", "mirror"):
            result[part.lower()] = True
    return result

def number(value, name, low, high):
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(name + " must be numeric.")
    if not low <= value <= high:
        raise ValueError(name + " must be between " + str(low) + " and " + str(high) + ".")
    return value

async def run(*args, timeout=360):
    proc = await asyncio.create_subprocess_exec(*map(str, args), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise RuntimeError("Render timed out. Try shorter video or lower quality.")
    if proc.returncode:
        raise RuntimeError(err.decode("utf-8", "ignore")[-1500:] or "FFmpeg failed.")
    return out

async def get_duration(path):
    raw = await run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path, timeout=30)
    try:
        return float(raw.decode().strip())
    except ValueError:
        raise RuntimeError("Unable to detect video duration.")

def edit_photo(source, output, opts):
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    crop = opts.get("crop", "").lower()
    if crop in ("square", "portrait"):
        ratio = 1 if crop == "square" else 4 / 5
        w, h = image.size
        if w / h > ratio:
            nw = int(h * ratio)
            x = (w - nw) // 2
            image = image.crop((x, 0, x + nw, h))
        else:
            nh = int(w / ratio)
            y = (h - nh) // 2
            image = image.crop((0, y, w, y + nh))
    if opts.get("rotate"):
        image = image.rotate(-int(opts["rotate"]) % 360, expand=True)
    if opts.get("mirror"):
        image = ImageOps.mirror(image)
    image = ImageEnhance.Brightness(image).enhance(number(opts.get("brightness", 1), "brightness", .1, 3))
    image = ImageEnhance.Contrast(image).enhance(number(opts.get("contrast", 1), "contrast", .1, 3))
    image = ImageEnhance.Color(image).enhance(number(opts.get("saturation", 1), "saturation", 0, 3))
    preset = opts.get("filter", "").lower()
    if preset == "bw":
        image = ImageOps.grayscale(image).convert("RGB")
    elif preset == "warm":
        image = Image.blend(image, Image.new("RGB", image.size, (255, 190, 120)), .12)
    elif preset == "cool":
        image = Image.blend(image, Image.new("RGB", image.size, (100, 160, 255)), .10)
    elif preset == "blur":
        image = image.filter(ImageFilter.GaussianBlur(2))
    elif preset == "sharpen":
        image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=140, threshold=3))
    if opts.get("text"):
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", max(22, image.width // 22))
        except OSError:
            font = ImageFont.load_default()
        text = opts["text"].replace("_", " ")[:80]
        box = draw.textbbox((0, 0), text, font=font, stroke_width=2)
        x = max(10, (image.width - box[2] + box[0]) // 2)
        y = max(10, image.height - (box[3] - box[1]) - 30)
        draw.text((x, y), text, font=font, fill="white", stroke_width=2, stroke_fill="black")
    image.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
    image.save(output, "JPEG", quality=94, optimize=True)
    image.close()

async def edit_video(source, output, opts):
    total = await get_duration(source)
    start = number(opts.get("start", 0), "start", 0, max(0, total - .1))
    end = number(opts.get("end", min(total, MAX_SECONDS)), "end", .1, total)
    length = end - start
    if length < 1 or length > MAX_SECONDS:
        raise ValueError("Final video must be 1 second to 2 minutes.")
    speed = number(opts.get("speed", 1), "speed", .5, 2)
    brightness = number(opts.get("brightness", 0), "brightness", -.5, .5)
    contrast = number(opts.get("contrast", 1), "contrast", .5, 2)
    saturation = number(opts.get("saturation", 1), "saturation", 0, 2)
    quality = opts.get("quality", "720p").lower()
    width = {"360p": 640, "480p": 854, "720p": 1280, "1080p": 1920}.get(quality, 1280)
    vf = ["scale='min(" + str(width) + ",iw)':-2:force_original_aspect_ratio=decrease",
          "eq=brightness=" + str(brightness) + ":contrast=" + str(contrast) + ":saturation=" + str(saturation)]
    if opts.get("mirror"):
        vf.append("hflip")
    rotate = opts.get("rotate", "0")
    if rotate == "90":
        vf.append("transpose=1")
    elif rotate == "180":
        vf.extend(["hflip", "vflip"])
    elif rotate == "270":
        vf.append("transpose=2")
    if speed != 1:
        vf.append("setpts=PTS/" + str(speed))
    text_file = None
    if opts.get("text"):
        fd, text_file = tempfile.mkstemp(prefix="v3edit_", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(opts["text"].replace("_", " ")[:100])
        vf.append("drawtext=textfile='" + text_file + "':fontcolor=white:fontsize=34:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h-text_h-35")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start), "-i", source,
           "-t", str(length), "-vf", ",".join(vf), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
    if opts.get("mute"):
        cmd += ["-an"]
    elif speed != 1:
        factor = speed
        audio = []
        while factor > 2:
            audio.append("atempo=2")
            factor /= 2
        while factor < .5:
            audio.append("atempo=0.5")
            factor /= .5
        audio.append("atempo=" + str(factor))
        cmd += ["-af", ",".join(audio), "-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd += ["-movflags", "+faststart", output]
    try:
        await run(*cmd, timeout=420)
    finally:
        if text_file and os.path.exists(text_file):
            os.remove(text_file)

async def photo_to_video(source, output, seconds, opts):
    seconds = number(seconds, "duration", 1, MAX_SECONDS)
    quality = opts.get("quality", "720p").lower()
    width = {"360p": 640, "480p": 854, "720p": 1280, "1080p": 1920}.get(quality, 1280)
    await run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", source,
              "-t", str(seconds), "-vf", "scale='min(" + str(width) + ",iw)':-2:force_original_aspect_ratio=decrease,fps=30,format=yuv420p",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-an", "-movflags", "+faststart", output, timeout=300)
