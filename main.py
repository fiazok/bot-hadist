# main.py (v2)
# Bot hadist HadeethEnc - terpisah dari bot toko.
import fcntl
import logging
import sys
from pathlib import Path

from telegram import BotCommand, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          MessageHandler, filters)

import api_client
import handlers as h
from config import TELEGRAM_BOT_TOKEN

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# httpx mencatat URL permintaan yang berisi token bot; matikan di level INFO.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class _RedactToken(logging.Filter):
    """Lapisan pengaman: ganti token jika sampai tertulis di log."""
    def filter(self, record: logging.LogRecord) -> bool:
        if TELEGRAM_BOT_TOKEN:
            msg = record.getMessage()
            if TELEGRAM_BOT_TOKEN in msg:
                record.msg = msg.replace(TELEGRAM_BOT_TOKEN, "<token>")
                record.args = ()
        return True


for _handler in logging.getLogger().handlers:
    _handler.addFilter(_RedactToken())

logger = logging.getLogger(__name__)
_LOCK = None


def _singleton() -> None:
    """Satu instance saja, memakai flock (otomatis lepas saat proses mati)."""
    global _LOCK
    _LOCK = open(Path(__file__).resolve().parent / "bot.lock", "w")
    try:
        fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("Bot sudah berjalan (bot.lock terkunci).")


async def on_error(update, context) -> None:
    err = context.error
    logger.error("Error: %s: %s", type(err).__name__, err)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Terjadi kesalahan. Silakan coba lagi.")
        except Exception:
            pass


async def post_init(app: Application) -> None:
    await app.bot.set_my_commands([
        BotCommand("start", "Menu utama"),
        BotCommand("kategori", "Daftar kategori"),
        BotCommand("daftar", "Daftar hadist di kategori"),
        BotCommand("hadist", "Baca hadist berdasarkan ID"),
        BotCommand("arab", "Teks Arab hadist"),
        BotCommand("cari", "Cari hadist berdasarkan judul"),
    ])


async def post_shutdown(app: Application) -> None:
    await api_client.close()


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        sys.exit("TELEGRAM_BOT_TOKEN tidak diatur (variabel lingkungan atau .env).")
    _singleton()

    app = (Application.builder().token(TELEGRAM_BOT_TOKEN)
           .post_init(post_init).post_shutdown(post_shutdown).build())

    app.add_handler(CommandHandler(["start", "help", "hadist_start"], h.cmd_start))
    app.add_handler(CommandHandler(["kategori", "hadist_kategori"], h.cmd_kategori))
    app.add_handler(CommandHandler(["daftar", "hadist_list"], h.cmd_daftar))
    app.add_handler(CommandHandler(["hadist", "hadist_detail"], h.cmd_hadist))
    app.add_handler(CommandHandler("arab", h.cmd_arab))
    app.add_handler(CommandHandler("cari", h.cmd_cari))
    app.add_handler(CommandHandler("perbarui", h.cmd_perbarui))
    app.add_handler(CallbackQueryHandler(h.on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, h.on_text))
    app.add_error_handler(on_error)

    logger.info("Bot Hadeeth v2 mulai berjalan...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
