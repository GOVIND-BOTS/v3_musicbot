import ast
import asyncio
import logging
import operator
import os
import tempfile
import time
from html import escape

from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import OWNER_ID, SUDO_USERS

LOGGER = logging.getLogger(__name__)

TIMEOUT = 5
MAX_OUTPUT = 12000
MAX_CODE = 8000

BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

COMPARE_OPERATORS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


class SafeTestError(Exception):
    pass


class SafeRunner:
    def __init__(self):
        self.variables = {}
        self.output = []

    def evaluate(self, node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float, str, bool, type(None))):
                return node.value
            raise SafeTestError("Unsupported constant.")

        if isinstance(node, ast.Name):
            if node.id in self.variables:
                return self.variables[node.id]
            raise SafeTestError(f"Undefined variable: {node.id}")

        if isinstance(node, ast.BinOp):
            operation = BINARY_OPERATORS.get(type(node.op))
            if operation is None:
                raise SafeTestError("Unsupported operator.")

            left = self.evaluate(node.left)
            right = self.evaluate(node.right)

            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise SafeTestError("Power limit exceeded.")

            result = operation(left, right)

            if isinstance(result, (int, float)) and abs(result) > 10 ** 100:
                raise SafeTestError("Result limit exceeded.")

            if isinstance(result, str) and len(result) > 5000:
                raise SafeTestError("String limit exceeded.")

            return result

        if isinstance(node, ast.UnaryOp):
            operation = UNARY_OPERATORS.get(type(node.op))
            if operation is None:
                raise SafeTestError("Unsupported unary operator.")
            return operation(self.evaluate(node.operand))

        if isinstance(node, ast.Compare):
            left = self.evaluate(node.left)
            for operator_node, comparator in zip(node.ops, node.comparators):
                operation = COMPARE_OPERATORS.get(type(operator_node))
                if operation is None:
                    raise SafeTestError("Unsupported comparison.")
                right = self.evaluate(comparator)
                if not operation(left, right):
                    return False
                left = right
            return True

        if isinstance(node, ast.BoolOp):
            values = [self.evaluate(value) for value in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
            raise SafeTestError("Unsupported boolean operation.")

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise SafeTestError("Only print() is allowed.")
            if node.func.id != "print":
                raise SafeTestError("Only print() is allowed.")
            if node.keywords:
                raise SafeTestError("Print keyword arguments are disabled.")

            values = [self.evaluate(arg) for arg in node.args]
            self.output.append(" ".join(str(value) for value in values))
            return None

        raise SafeTestError(f"Unsupported syntax: {type(node).__name__}")

    def run(self, code):
        tree = ast.parse(code, mode="exec")

        if len(tree.body) > 100:
            raise SafeTestError("Too many statements.")

        for statement in tree.body:
            if isinstance(statement, ast.Expr):
                self.evaluate(statement.value)

            elif isinstance(statement, ast.Assign):
                if len(statement.targets) != 1:
                    raise SafeTestError("Multiple assignments are disabled.")

                target = statement.targets[0]
                if not isinstance(target, ast.Name):
                    raise SafeTestError("Only simple variables are allowed.")

                self.variables[target.id] = self.evaluate(statement.value)

            else:
                raise SafeTestError(
                    f"Unsupported statement: {type(statement).__name__}"
                )

        return "\n".join(self.output) or "Code executed successfully."


def get_allowed_ids():
    ids = set()

    try:
        if isinstance(OWNER_ID, (list, tuple, set)):
            ids.update(int(x) for x in OWNER_ID)
        elif OWNER_ID:
            ids.add(int(OWNER_ID))
    except Exception:
        pass

    try:
        if SUDO_USERS:
            ids.update(int(x) for x in SUDO_USERS)
    except Exception:
        pass

    return ids


def is_allowed(user_id):
    try:
        return int(user_id) in get_allowed_ids()
    except Exception:
        return False


async def run_test(code):
    start = time.monotonic()

    try:
        runner = SafeRunner()
        output = await asyncio.wait_for(
            asyncio.to_thread(runner.run, code),
            timeout=TIMEOUT,
        )
        return (
            "SUCCESS",
            str(output)[:MAX_OUTPUT],
            round(time.monotonic() - start, 3),
        )

    except asyncio.TimeoutError:
        return (
            "TIMEOUT",
            "Test exceeded the time limit.",
            round(time.monotonic() - start, 3),
        )

    except Exception as error:
        return (
            "FAILED",
            f"{type(error).__name__}: {error}",
            round(time.monotonic() - start, 3),
        )


def make_keyboard(runtime):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"⏱ {runtime}s",
                    callback_data="eval_runtime",
                ),
                InlineKeyboardButton(
                    "🗑 Delete",
                    callback_data="eval_delete",
                ),
            ]
        ]
    )


async def send_result(message, code, status, output, runtime):
    text = (
        "<b>V3MUSIC CODE TEST</b>\n\n"
        f"<b>Status:</b> {escape(str(status))}\n"
        f"<b>Runtime:</b> {runtime}s\n\n"
        "<b>Code:</b>\n"
        f"<pre>{escape(code[:1000])}</pre>\n\n"
        "<b>Output:</b>\n"
        f"<pre>{escape(str(output)[:2000])}</pre>"
    )

    if len(text) <= 4000:
        await message.reply_text(text, reply_markup=make_keyboard(runtime))
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
                f"<b>Code Test: {escape(str(status))}</b>\n"
                f"Runtime: <code>{runtime}s</code>"
            ),
            reply_markup=make_keyboard(runtime),
        )
    finally:
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception:
                pass


def register_eval(app):
    allowed = get_allowed_ids()
    LOGGER.info("Eval allowed IDs: %s", allowed)

    if not allowed:
        LOGGER.warning("Eval disabled: No OWNER_ID / SUDO_USERS configured.")
        return

    @app.on_message(
        filters.regex(r"(?i)^/(eval|test)(@\w+)?(\s|$)")
        & filters.private
    )
    async def eval_command(client, message: Message):
        try:
            uid = message.from_user.id if message.from_user else None
            text = message.text or ""

            LOGGER.info(
                "EVAL HIT | user=%s | text=%r | allowed=%s",
                uid,
                text,
                allowed,
            )

            await message.reply_text(
                f"✅ Eval received\n"
                f"User: `{uid}`\n"
                f"Allowed: `{allowed}`"
            )

            if not uid or not is_allowed(uid):
                return await message.reply_text("❌ Owner/Sudo only.")

            code = None
            parts = (message.text or "").split(None, 1)
            if len(parts) >= 2:
                code = parts[1].strip()

            if not code and message.reply_to_message:
                code = (
                    message.reply_to_message.text
                    or message.reply_to_message.caption
                    or ""
                ).strip()

            if not code:
                return await message.reply_text(
                    "<b>Usage:</b>\n"
                    "<code>/eval print('Hello')</code>"
                )

            if len(code) > MAX_CODE:
                return await message.reply_text(
                    f"Code too long. Maximum: {MAX_CODE} characters."
                )

            status_message = await message.reply_text("<b>Testing...</b>")
            status, output, runtime = await run_test(code)

            try:
                await status_message.delete()
            except Exception:
                pass

            await send_result(message, code, status, output, runtime)

        except Exception:
            LOGGER.exception("EVAL HANDLER CRASH")
            try:
                await message.reply_text("❌ Eval crashed. Check logs.")
            except Exception:
                pass

    @app.on_callback_query(filters.regex(r"^eval_runtime$"))
    async def eval_runtime_callback(client, query):
        if not query.from_user or not is_allowed(query.from_user.id):
            return await query.answer("Owner only.", show_alert=True)
        await query.answer("Runtime is displayed in the result.", show_alert=True)

    @app.on_callback_query(filters.regex(r"^eval_delete$"))
    async def eval_delete_callback(client, query):
        if not query.from_user or not is_allowed(query.from_user.id):
            return await query.answer("Owner only.", show_alert=True)

        try:
            await query.message.delete()
            await query.answer("Result deleted.")
        except Exception:
            await query.answer("Unable to delete.", show_alert=True)

    LOGGER.info("Safe Eval/Test handlers registered successfully.")
