import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps, ImageFilter, ImageDraw, ImageFont

MAX_SECONDS = 120
MAX_TIMELINE_CLIPS = 10
MAX_TELEGRAM_VIDEO_BYTES = 49 * 1024 * 1024


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
    try:
        proc = await asyncio.create_subprocess_exec(
            *map(str, args),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as error:
        command = str(args[0]) if args else "media tool"
        raise RuntimeError(command + " is not installed. Install FFmpeg and ffprobe.") from error
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise RuntimeError("Render timed out. Try shorter clips or lower quality.")
    if proc.returncode:
        raise RuntimeError(err.decode("utf-8", "ignore")[-1500:] or "FFmpeg failed.")
    return out


async def get_duration(path):
    raw = await run(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path, timeout=30
    )
    try:
        duration = float(raw.decode().strip())
    except ValueError:
        raise RuntimeError("Unable to detect media duration.")
    if duration <= 0:
        raise RuntimeError("The media has no usable duration.")
    return duration


async def has_audio(path):
    raw = await run(
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=index", "-of", "csv=p=0", path, timeout=30
    )
    return bool(raw.decode("utf-8", "ignore").strip())


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


def _timeline_dimensions(quality):
    dimensions = {
        "360p": (640, 360),
        "480p": (854, 480),
        "720p": (1280, 720),
        "1080p": (1920, 1080),
    }
    quality = (quality or "720p").lower()
    if quality not in dimensions:
        raise ValueError("Timeline quality must be 360p, 480p, 720p, or 1080p.")
    return dimensions[quality]


async def create_timeline(
    clips,
    output,
    music=None,
    order=None,
    durations=None,
    photo_duration=3,
    trims=None,
    original_audio=True,
    music_volume=0.25,
    quality="720p",
):
    """Join 2–10 photo/video clips, optionally mixing a looping background track.

    Order and duration-map keys are 1-based indexes in upload order.
    A duration override sets a photo's display time or trims a video from its start.
    """
    if not isinstance(clips, (list, tuple)) or not 2 <= len(clips) <= MAX_TIMELINE_CLIPS:
        raise ValueError("Timeline needs 2 to 10 clips. Add at least two photos/videos.")

    photo_duration = number(photo_duration, "photo_duration", 1, MAX_SECONDS)
    music_volume = number(music_volume, "music_volume", 0, 2)
    width, height = _timeline_dimensions(quality)
    durations = durations or {}
    trims = trims or {}
    indexes = list(range(1, len(clips) + 1))
    if order is None:
        order = indexes
    if sorted(order) != indexes:
        raise ValueError("Timeline order must list every clip number exactly once, e.g. 3,1,2.")

    planned = []
    total_duration = 0.0
    for index in order:
        clip = clips[index - 1]
        path = clip.get("path")
        kind = clip.get("kind")
        if kind not in ("photo", "video") or not path or not os.path.isfile(path):
            raise ValueError("Clip " + str(index) + " is missing or has an unsupported format.")
        override = durations.get(index)
        trim = trims.get(index)
        if kind == "photo":
            if trim is not None:
                raise ValueError("Clip " + str(index) + " is a photo; use a duration such as 1=5, not a video trim range.")
            start = 0.0
            duration = number(override if override is not None else photo_duration,
                              "clip " + str(index) + " duration", .5, MAX_SECONDS)
            audio_present = False
        else:
            source_duration = await get_duration(path)
            if trim is not None:
                if override is not None:
                    raise ValueError("Clip " + str(index) + " cannot use both a duration and a trim range.")
                start = number(trim[0], "clip " + str(index) + " start", 0, max(0, source_duration - .5))
                end = number(trim[1], "clip " + str(index) + " end", start + .5, source_duration)
                duration = end - start
            else:
                start = 0.0
                duration = number(override if override is not None else source_duration,
                                  "clip " + str(index) + " duration", .5, MAX_SECONDS)
            if start + duration > source_duration + .05:
                raise ValueError("Clip " + str(index) + " is only " + str(round(source_duration, 2)) + "s long.")
            audio_present = await has_audio(path) if original_audio else False
        total_duration += duration
        if total_duration > MAX_SECONDS + .001:
            raise ValueError("Timeline is " + str(round(total_duration, 1)) + "s. Final video must be 1–120 seconds.")
        planned.append({
            "index": index,
            "path": path,
            "kind": kind,
            "duration": duration,
            "start": start,
            "audio": audio_present,
        })

    if total_duration < 1:
        raise ValueError("Final timeline must be at least 1 second.")
    if music:
        if not os.path.isfile(music) or not await has_audio(music):
            raise ValueError("The selected background music file has no audio stream.")

    output = os.path.abspath(output)
    parent = os.path.dirname(output) or "."
    os.makedirs(parent, exist_ok=True)
    workdir = tempfile.mkdtemp(prefix="v3_timeline_render_", dir=parent)
    completed = False
    try:
        width_height = str(width) + ":" + str(height)
        vf = (
            "scale=" + width_height + ":force_original_aspect_ratio=decrease,"
            "pad=" + width_height + ":(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p"
        )
        segment_paths = []
        for position, clip in enumerate(planned, 1):
            segment = os.path.join(workdir, "segment_" + str(position).zfill(2) + ".mp4")
            duration = str(clip["duration"])
            if clip["kind"] == "photo":
                command = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-loop", "1", "-framerate", "30", "-i", clip["path"],
                    "-f", "lavfi", "-t", duration, "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-map", "0:v:0", "-map", "1:a:0", "-vf", vf,
                ]
            elif clip["audio"]:
                command = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", str(clip["start"]), "-i", clip["path"], "-map", "0:v:0", "-map", "0:a:0",
                    "-vf", vf, "-af",
                    "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad",
                ]
            else:
                command = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", str(clip["start"]), "-i", clip["path"], "-f", "lavfi", "-t", duration, "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-map", "0:v:0", "-map", "1:a:0", "-vf", vf,
                ]
            command += [
                "-t", duration, "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "25", "-pix_fmt", "yuv420p", "-r", "30",
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart", segment,
            ]
            await run(*command, timeout=420)
            if not os.path.isfile(segment) or os.path.getsize(segment) == 0:
                raise RuntimeError("FFmpeg did not create timeline segment " + str(position) + ".")
            segment_paths.append(segment)

        concat_file = os.path.join(workdir, "timeline.txt")
        with open(concat_file, "w", encoding="utf-8") as handle:
            for segment in segment_paths:
                # Generated paths contain no quotes; this keeps concat demuxer input safe.
                handle.write("file '" + segment.replace("\\", "/") + "'\n")
        joined = os.path.join(workdir, "joined.mp4")
        await run(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c", "copy", "-movflags", "+faststart", joined, timeout=420
        )

        if music:
            mixed = os.path.join(workdir, "mixed.mp4")
            volume = format(music_volume, ".4f")
            duration_text = format(total_duration, ".4f")
            filter_graph = (
                "[0:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[base];"
                "[1:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                "volume=" + volume + ",atrim=duration=" + duration_text + ",asetpts=PTS-STARTPTS[music];"
                "[base][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
            await run(
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", joined, "-stream_loop", "-1", "-i", music,
                "-filter_complex", filter_graph, "-map", "0:v:0", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
                "-t", duration_text, "-movflags", "+faststart", mixed, timeout=420
            )
            shutil.copyfile(mixed, output)
        else:
            await run(
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", joined, "-t", format(total_duration, ".4f"),
                "-c", "copy", "-movflags", "+faststart", output, timeout=120
            )

        final_duration = await get_duration(output)
        if final_duration > MAX_SECONDS + .1:
            raise ValueError("Rendered output exceeded the 120-second limit.")
        if os.path.getsize(output) > MAX_TELEGRAM_VIDEO_BYTES:
            raise ValueError("Output is over Telegram's 49 MB safe upload limit. Retry with quality=480p or shorter clips.")
        completed = True
        return {"duration": final_duration, "clips": len(planned), "size": os.path.getsize(output)}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        if not completed and os.path.exists(output):
            try:
                os.remove(output)
            except OSError:
                pass
