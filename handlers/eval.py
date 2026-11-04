
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

from config import OWNER_ID

LOGGER = logging.getLogger(__name__)

TIMEOUT = 5
MAX_OUTPUT = 12000
MAX_CODE = 8000

# --------------------------------------------------
# OWNER CONFIGURATION
# --------------------------------------------------

def get_owner_ids():
    if isinstance(OWNER_ID, (list, tuple, set)):
        return {int(x) for x in OWNER_ID}

    return {int(OWNER_ID)}


def is_owner(user_id):
    return user_id in get_owner_ids()


# --------------------------------------------------
# SAFE PYTHON OPERATIONS
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

            raise SafeTestError(
                f"Undefined variable: {node.id}"
            )

        if isinstance(node, ast.BinOp):
            operation = BINARY_OPERATORS.get(type(node.op))

            if operation is None:
                raise SafeTestError("Unsupported operator.")

            left = self.evaluate(node.left)
            right = self.evaluate(node.right)

            if isinstance(node.op, ast.Pow) and abs(right) > 100:
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

            for operator_node, comparator in zip(
                node.ops,
                node.comparators,
            ):
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

            self.output.append(
                " ".join(str(value) for value in values)
            )

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
# TEST RUNNER
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

        LOGGER.exception("Code test failed")

        return (
            "FAILED",
            f"{type(error).__name__}: {error}",
            round(time.monotonic() - start, 3),
        )


# --------------------------------------------------
# RESULT BUTTONS
# --------------------------------------------------

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


# --------------------------------------------------
# SEND RESULT
# --------------------------------------------------

async def send_result(
    message,
    code,
    status,
    output,
    runtime,
):

    text = (
        "<b>V3MUSIC CODE TEST</b>\n\n"
        f"<b>Status:</b> {escape(str(status))}\n"
        f"<b>Runtime:</b> {runtime}s\n\n"
        "<b>Code:</b>\n"
        f"<pre>{escape(code[:1000])}</pre>\n\n"
        "<b>Output:</b>\n"
        f"<pre>{escape(output[:2000])}</pre>"
    )

    if len(text) <= 4000:

        sent = await message.reply_text(
            text,
            reply_markup=make_keyboard(runtime),
        )

        return sent

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
                f"<b>Code Test: {escape(status)}</b>\n"
                f"Runtime: <code>{runtime}s</code>"
            ),
            reply_markup=make_keyboard(runtime),
        )

    finally:

        if filename and os.path.exists(filename):
            os.remove(filename)


# --------------------------------------------------
# REGISTER EVAL HANDLERS
# --------------------------------------------------

def register_eval(app):

    owner_ids = list(get_owner_ids())

    if not owner_ids:
        LOGGER.warning("Eval disabled: No owner IDs configured.")
        return

    @app.on_message(
        filters.command(
            ["eval", "test"],
            prefixes=["/", ".", "?", "-"],
        )
        & filters.user(owner_ids)
    )
    async def eval_command(client, message: Message):

        if not message.from_user:
            return

        if not is_owner(message.from_user.id):
            return

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
            pass

        await send_result(
            message,
            code,
            status,
            output,
            runtime,
        )

    # Runtime callback
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

    # Delete callback
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

    LOGGER.info("Safe Eval/Test handlers registered successfully.")
