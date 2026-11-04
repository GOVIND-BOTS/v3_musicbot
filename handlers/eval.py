import ast
import asyncio
import logging
import operator
import time
from html import escape

from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import OWNER_ID

LOGGER = logging.getLogger(__name__)

TIMEOUT = 5
MAX_CODE = 8000
MAX_OUTPUT = 12000


# --------------------------------------------------
# OWNER CONFIGURATION
# --------------------------------------------------

def get_owner_ids():
    try:
        if isinstance(OWNER_ID, (list, tuple, set)):
            return {int(x) for x in OWNER_ID}

        if isinstance(OWNER_ID, str):
            return {
                int(x.strip())
                for x in OWNER_ID.split(",")
                if x.strip()
            }

        return {int(OWNER_ID)}

    except (TypeError, ValueError):
        LOGGER.exception("Invalid OWNER_ID configuration")
        return set()


def is_owner(user_id):
    return user_id is not None and user_id in get_owner_ids()


# --------------------------------------------------
# SAFE TEST ENGINE
# --------------------------------------------------

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

            if isinstance(node.op, ast.Pow):
                if not isinstance(right, (int, float)) or abs(right) > 100:
                    raise SafeTestError("Power limit exceeded.")

            result = operation(left, right)

            if isinstance(result, (int, float)) and abs(result) > 10**100:
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

            for op_node, comparator in zip(node.ops, node.comparators):
                operation = COMPARE_OPERATORS.get(type(op_node))

                if operation is None:
                    raise SafeTestError("Unsupported comparison.")

                right = self.evaluate(comparator)

                if not operation(left, right):
                    return False

                left = right

            return True

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for value in node.values:
                    if not self.evaluate(value):
                        return False
                return True

            if isinstance(node.op, ast.Or):
                for value in node.values:
                    if self.evaluate(value):
                        return True
                return False

            raise SafeTestError("Unsupported boolean operation.")

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id != "print":
                raise SafeTestError("Only print() is allowed.")

            if node.keywords:
                raise SafeTestError("Print keyword arguments are disabled.")

            values = [self.evaluate(arg) for arg in node.args]
            self.output.append(" ".join(str(value) for value in values))

            if sum(len(line) for line in self.output) > MAX_OUTPUT:
                raise SafeTestError("Output limit exceeded.")

            return None

        raise SafeTestError(
            f"Unsupported syntax: {type(node).__name__}"
        )

    def run(self, code):
        tree = ast.parse(code, mode="exec")

        if len(tree.body) > 100:
            raise SafeTestError("Too many statements.")

        for statement in tree.body:

            if isinstance(statement, ast.Expr):
                self.evaluate(statement.value)

            elif isinstance(statement, ast.Assign):
                if len(statement.targets) != 1:
                    raise SafeTestError(
                        "Multiple assignments are disabled."
                    )

                target = statement.targets[0]

                if not isinstance(target, ast.Name):
                    raise SafeTestError(
                        "Only simple variables are allowed."
                    )

                self.variables[target.id] = self.evaluate(
                    statement.value
                )

            else:
                raise SafeTestError(
                    f"Unsupported statement: {type(statement).__name__}"
                )

        return "\n".join(self.output) or "Code executed successfully."


# --------------------------------------------------
# RUN TEST
# --------------------------------------------------

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
            output[:MAX_OUTPUT],
            round(time.monotonic() - start, 3),
        )

    except asyncio.TimeoutError:
        return (
            "TIMEOUT",
            "Test exceeded the time limit.",
            round(time.monotonic() - start, 3),
        )

    except Exception as error:
        LOGGER.exception("Eval test error")

        return (
            "FAILED",
            f"{type(error).__name__}: {error}",
            round(time.monotonic() - start, 3),
        )


# --------------------------------------------------
# KEYBOARD
# --------------------------------------------------

def make_keyboard(runtime):
    return InlineKeyboardMarkup([
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
    ])


# --------------------------------------------------
# SEND RESULT
# --------------------------------------------------

async def send_result(message, code, status, output, runtime):

    text = (
        "<b>V3MUSIC CODE TEST</b>\n\n"
        f"<b>Status:</b> {escape(status)}\n"
        f"<b>Runtime:</b> {runtime}s\n\n"
        "<b>Code:</b>\n"
        f"<pre>{escape(code[:1000])}</pre>\n\n"
        "<b>Output:</b>\n"
        f"<pre>{escape(output[:2000])}</pre>"
    )

    await message.reply_text(
        text,
        reply_markup=make_keyboard(runtime),
    )


# --------------------------------------------------
# REGISTER HANDLERS
# --------------------------------------------------

def register_eval(app):

    @app.on_message(
        filters.command(
            ["eval", "test"],
            prefixes=["/", ".", "?", "-"],
        )
    )
    async def eval_command(client, message: Message):

        # COMMAND RECEIVED LOG
        LOGGER.warning(
            "EVAL RECEIVED | TEXT=%r | USER=%s | CHAT=%s",
            message.text,
            message.from_user.id if message.from_user else None,
            message.chat.type if message.chat else None,
        )

        sender_id = (
            message.from_user.id
            if message.from_user
            else None
        )

        # OWNER DEBUG LOG
        LOGGER.info(
            "EVAL CHECK | OWNER_ID=%r | PARSED_OWNER_IDS=%r | MESSAGE_USER_ID=%r | CHAT_TYPE=%s",
            OWNER_ID,
            get_owner_ids(),
            sender_id,
            message.chat.type if message.chat else None,
        )

        if not is_owner(sender_id):
            return await message.reply_text(
                "You are not authorized to use Eval."
            )

        if not message.text:
            return

        parts = message.text.split(None, 1)

        if len(parts) < 2 or not parts[1].strip():
            return await message.reply_text(
                "<b>Send Python code to test.</b>\n\n"
                "<code>/eval print('Hello V3Music')</code>"
            )

        code = parts[1].strip()

        if len(code) > MAX_CODE:
            return await message.reply_text(
                f"Code too long. Maximum: {MAX_CODE} characters."
            )

        status_message = await message.reply_text(
            "<b>Testing Python code...</b>"
        )

        status, output, runtime = await run_test(code)

        try:
            await status_message.delete()
        except Exception:
            LOGGER.exception(
                "Unable to delete eval status message"
            )

        await send_result(
            message,
            code,
            status,
            output,
            runtime,
        )

    # --------------------------------------------------
    # RUNTIME BUTTON
    # --------------------------------------------------

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
            "Runtime is displayed in the result.",
            show_alert=True,
        )

    # --------------------------------------------------
    # DELETE BUTTON
    # --------------------------------------------------

    @app.on_callback_query(
        filters.regex(r"^eval_delete$")
    )
    async def eval_delete_callback(client, query):

        if not is_owner(query.from_user.id):
            return await query.answer(
                "Owner only.",
                show_alert=True,
            )

        try:
            await query.message.delete()
            await query.answer("Result deleted.")

        except Exception:
            await query.answer(
                "Unable to delete result.",
                show_alert=True,
            )

    LOGGER.info(
        "Eval handlers registered successfully. Owners: %s",
        get_owner_ids(),
    )
