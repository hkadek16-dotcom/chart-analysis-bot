
import os
from pathlib import Path
from collections import Counter

from PIL import Image
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SAVE_DIR = Path("received_charts")
SAVE_DIR.mkdir(exist_ok=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً يا خيو! 👋\n"
        "أنا بوت تحليل الشارت المجاني.\n"
        "ابعت صورة واضحة للشارت، ويفضل يظهر فيها "
        "الفريم والشموع ومحور الوقت.\n\n"
        "رح أفحص الصورة مبدئياً، لكن ما رح أعطيك "
        "إشارة دخول وهمية أو أضمن الربح."
    )


def inspect_image(path):
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((500, 500))
        pixels = list(image.getdata())

    green = 0
    red = 0

    for r, g, b in pixels:
        # تقدير الألوان فقط، وليس قراءة الشموع فعلياً
        if g > r * 1.25 and g > b * 1.15 and g > 70:
            green += 1
        elif r > g * 1.25 and r > b * 1.15 and r > 70:
            red += 1

    total = green + red

    if total < 100:
        color_result = (
            "ما قدرت أميّز ألوان كافية بالصورة. "
            "جرّب صورة أوضح."
        )
    else:
        green_pct = green / total * 100
        red_pct = red / total * 100

        color_result = (
            f"بكسلات خضراء تقريباً: {green_pct:.1f}%\n"
            f"بكسلات حمراء تقريباً: {red_pct:.1f}%\n"
            "هالنسب للألوان بالصورة فقط، مو نسبة "
            "الشموع الصاعدة والهابطة."
        )

    return (
        "📊 الفحص المبدئي للصورة\n\n"
        + color_result
        + "\n\n"
        "⏱️ الفريم المطلوب: 5 دقائق، لكن لازم "
        "نتأكد من الفريم الظاهر على الشارت.\n\n"
        "🎯 الدخول والإلغاء ومدة الصفقة: "
        "ما فيني أحددها من ألوان الصورة وحدها.\n\n"
        "⚠️ هاد فحص أولي مجاني، مو تحليل تداول "
        "كامل ولا إشارة دخول."
    )


async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message = update.message
    photo = message.photo[-1]

    path = SAVE_DIR / (
        f"{message.from_user.id}_{message.message_id}.jpg"
    )

    try:
        tg_file = await photo.get_file()
        await tg_file.download_to_drive(custom_path=str(path))

        result = inspect_image(path)
        await message.reply_text("✅ وصلت الصورة وانحفظت.\n\n" + result)

    except Exception as error:
        print(f"Image error: {error}")
        await message.reply_text(
            "صار خطأ بقراءة الصورة. جرّب تبعتها مرة ثانية."
        )


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("Free Chart Bot is running!")
    app.run_polling()


if __name__ == "__main__":
    main()
    
