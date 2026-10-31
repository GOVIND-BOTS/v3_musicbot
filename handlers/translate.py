from pyrogram import filters
from gpytranslate import Translator

trans = Translator()


def register_translate_handlers(app):
    @app.on_message(filters.command("tr"))
    async def translate_cmd(client, message):
        reply = message.reply_to_message
        if not reply:
            return await message.reply("Kisi message pe reply karke `/tr` likho.\nExample: `/tr hi`")

        text = reply.text or reply.caption
        if not text:
            return await message.reply("Text message pe reply karo.")

        try:
            args = message.text.split()[1].lower() if len(message.command) > 1 else "en"
            if "//" in args:
                source, dest = args.split("//")
            else:
                source = await trans.detect(text)
                dest = args

            result = await trans(text, sourcelang=source, targetlang=dest)
            await message.reply_text(
                f"**Translated** ({source} → {dest}):\n\n{result.text}"
            )
        except Exception as e:
            await message.reply(f"Error: {e}")
