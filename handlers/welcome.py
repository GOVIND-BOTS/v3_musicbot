
def get_font(size):
    paths = [
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]

    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def fit_font(draw, text, max_width, size=27):
    while size >= 13:
        font = get_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)

        if bbox[2] - bbox[0] <= max_width:
            return font

        size -= 1

    return get_font(13)


def create_welcome_image(user_photo, user, chat):
    image = Image.open(WELCOME_IMAGE).convert("RGBA")

    # Scale all coordinates according to original template.
    base_w, base_h = 1536, 1024
    sx = image.width / base_w
    sy = image.height / base_h

    def pos(x, y):
        return (int(x * sx), int(y * sy))

    def rect(coords):
        return tuple(
            int(value * (sx if i % 2 == 0 else sy))
            for i, value in enumerate(coords)
        )

    draw = ImageDraw.Draw(image)

    # --------------------------------
    # MEMBER PROFILE PHOTO - FULL CIRCLE
    # --------------------------------
    if user_photo and os.path.isfile(user_photo):
        avatar = Image.open(user_photo).convert("RGB")

        w, h = avatar.size
        crop = min(w, h)

        left = (w - crop) // 2
        top = (h - crop) // 2

        avatar = avatar.crop((
            left, top, left + crop, top + crop
        ))

        diameter = int(460 * sx)
        avatar = avatar.resize(
            (diameter, diameter),
            Image.Resampling.LANCZOS,
        )

        mask = Image.new("L", (diameter, diameter), 0)
        ImageDraw.Draw(mask).ellipse(
            (0, 0, diameter - 1, diameter - 1),
            fill=255,
        )

        # Center of the neon circular frame.
        center_x, center_y = pos(440, 445)

        x = center_x - diameter // 2
        y = center_y - diameter // 2

        image.paste(avatar, (x, y), mask)

    # --------------------------------
    # MEMBER DETAILS
    # --------------------------------
    name = " ".join(
        p for p in (user.first_name, user.last_name) if p
    ) or "Unknown"

    user_id = str(user.id)
    username = f"@{user.username}" if user.username else "Not set"
    group_name = chat.title or "Unknown Group"

    from datetime import datetime
    from zoneinfo import ZoneInfo

    joined = datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%d %b %Y")

    values = [
        (name, 299, (0, 210, 255, 255)),
        (user_id, 364, (255, 45, 230, 255)),
        (username, 429, (0, 255, 210, 255)),
        (group_name, 494, (255, 190, 30, 255)),
        (joined, 559, (255, 65, 220, 255)),
    ]

    # Cover ONLY the value column, not the labels.
    for _, y, _ in values:
        x1, y1 = pos(1080, y - 5)
        x2, y2 = pos(1460, y + 48)

        draw.rounded_rectangle(
            (x1, y1, x2, y2),
            radius=int(5 * sx),
            fill=(5, 3, 24, 255),
        )

    # Draw dynamic values in their own column.
    draw = ImageDraw.Draw(image)

    for text, y, color in values:
        x, y_pos = pos(1095, y)

        font = fit_font(
            draw,
            text,
            max_width=int(345 * sx),
            size=int(27 * sx),
        )

        draw.text(
            (x, y_pos),
            text,
            font=font,
            fill=color,
            stroke_width=0,
        )

    output = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
    )

    output_path = output.name
    output.close()

    image.convert("RGB").save(output_path, "PNG")

    return output_path
