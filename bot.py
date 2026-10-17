

import os
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SAVE_DIR = Path("received_charts")
SAVE_DIR.mkdir(exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً يا خيو! 👋 ابعتلي صورة الشارت، ورح استقبلها واحفظها."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    path = SAVE_DIR / f"{update.message.from_user.id}_{update.message.message_id}.jpg"
    await file.download_to_drive(custom_path=str(path))
    await update.message.reply_photo(
        photo=photo.file_id,
        caption="✅ وصلت صورة الشارت! انحفظت على الاستضافة."
    )

def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Chart Analysis Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
  
