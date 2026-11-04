
import asyncio
import logging
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import OWNER_ID

LOGGER = logging.getLogger(__name__)

TIMEOUT = 15
MAX_OUTPUT = 12000
MAX_CODE = 8000


def get_owner_ids():
    if isinstance(OWNER_ID, (list, tuple, set)):
        return {int(x) for x in OWNER_ID}
    return {int(OWNER_ID)}


def is_owner(user_id):
    return user_id in get_owner_ids()


def make_keyboard(runtime, message_id):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"⏱ {runtime}s",
                    callback_data="eval_runtime",
                ),
                InlineKeyboardButton(
                    "🗑 Delete",
                    callback_data=f"eval_delete:{message_id}",
                ),
            ]
        ]
    )


def make_test_script(code):
    return (
        "import asyncio\n"
        "import traceback\n"
        "\n"
        "async def __test__():\n"
        "    try:\n"
        "        exec(compile("
        + repr(code)
        + ", '<eval>', 'exec'), {})\n"
        "        print('\\n[EVAL_RESULT] SUCCESS')\n"
        "    except BaseException:\n"
        "        print('\\n[EVAL_RESULT] FAILED')\n"
        "        traceback.print_exc()\n"
        "\n"
        "asyncio.run(__test__())\n"
    )


async def run_test(code):
    start = time.monotonic()
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            encoding="utf-8",
            delete=False,
        ) as file:
            file.write(make_test_script(code))
            temp_path = file.name

        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            temp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=tempfile.gettempdir(),
        )

        try:
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=TIMEOUT,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()

            return (
                "TIMEOUT",
                f"Test stopped after {TIMEOUT} seconds.",
                round(time.monotonic() - start, 3),
            )

        output = stdout.decode(
            "utf-8",
            errors="replace",
        )

        success = (
            process.returncode == 0
            and "[EVAL_RESULT] SUCCESS" in output
        )

        return (
            "SUCCESS" if success else "FAILED",
            output.strip() or "No output.",
            round(time.monotonic() - start, 3),
        )

    except Exception:
        LOGGER.exception("Eval test failed")

        return (
            "FAILED",
            traceback.format_exc(),
            round(time.monotonic() - start, 3),
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                LOGGER.warning("Unable to remove eval temporary file")


async def send_result(message, code, status, output, runtime):
    text = (
        f"<b>V3MUSIC CODE TEST</b>\n\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Runtime:</b> {runtime}s\n\n"
        f"<b>Code:</b>\n"
        f"<pre>{code[:1000]}</pre>\n\n"
        f"<b>Output:</b>\n"
        f"<pre>{output[:2500]}</pre>"
    )

    if len(text) <= 4000:
        sent = await message.reply_text(text)

        if status in ("SUCCESS", "FAILED", "TIMEOUT"):
            await sent.edit_reply_markup(
                make_keyboard(runtime, sent.id)
            )

        return

    filename = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            encoding="utf-8",
            delete=False,
        ) as file:
            file.write(
                f"STATUS: {status}\n"
                f"RUNTIME: {runtime}s\n\n"
                f"CODE:\n{code}\n\n"
                f"OUTPUT:\n{output}"
            )
            filename = file.name

        await message.reply_document(
            filename,
            caption=(
                f"<b>Code Test: {status}</b>\n"
                f"Runtime: <code>{runtime}s</code>"
            ),
        )

    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)


def register_eval(app):

    @app.on_message(
        filters.command(["eval", "test"])
        & filters.user(list(get_owner_ids()))
    )
    async def eval_command(client, message: Message):
        if len(message.command) < 2:
            return await message.reply_text(
                "<b>Send Python code to test.</b>\n\n"
                "<code>/eval print('Hello V3Music')</code>"
            )

        code = message.text.split(None, 1)[1]

        if len(code) > MAX_CODE:
            return await message.reply_text(
                f"Code is too long. Maximum: {MAX_CODE} characters."
            )

        status_message = await message.reply_text(
            "<b>Testing Python code...</b>"
        )

        status, output, runtime = await run_test(code)

        try:
            await status_message.delete()
        except Exception:
            pass

        await send_result(
            message,
            code,
            status,
            output,
            runtime,
        )

    @app.on_callback_query(
        filters.regex(r"^eval_runtime$")
    )
    async def eval_runtime_callback(client, query):
        if not is_owner(query.from_user.id):
            return await query.answer(
                "Owner only.",
                show_alert=True,
            )

        await query.answer(
            "Runtime is shown in the test result.",
            show_alert=True,
        )

    @app.on_callback_query(
        filters.regex(r"^eval_delete:")
    )
    async def eval_delete_callback(client, query):
        if not is_owner(query.from_user.id):
            return await query.answer(
                "Owner only.",
                show_alert=True,
            )

        try:
            await query.message.delete()
            await query.answer("Deleted.")
        except Exception:
            await query.answer(
                "Unable to delete.",
                show_alert=True,
            )
