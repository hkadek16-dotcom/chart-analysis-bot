
import os
import csv
from pathlib import Path
from datetime import datetime
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
LOG_FILE = SAVE_DIR / "analysis_results.csv"


def detect_candles(path):
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((1000, 700))
        width, height = img.size
        pixels = img.load()

        # نبحث عن بكسلات الشموع الخضراء والحمراء
        columns = []
        for x in range(width):
            ys = []
            colors = Counter()

            for y in range(height):
                r, g, b = pixels[x, y]

                if g > 85 and g > r * 1.25 and g > b * 1.15:
                    ys.append(y)
                    colors["UP"] += 1
                elif r > 100 and r > g * 1.25 and r > b * 1.15:
                    ys.append(y)
                    colors["DOWN"] += 1

            if len(ys) >= 2:
                columns.append({
                    "x": x,
                    "top": min(ys),
                    "bottom": max(ys),
                    "color": colors.most_common(1)[0][0],
                    "count": len(ys),
                })

    # تجميع الأعمدة المتجاورة لتقدير مواقع الشموع
    groups = []
    for col in columns:
        if groups and col["x"] - groups[-1][-1]["x"] <= 3:
            groups[-1].append(col)
        else:
            groups.append([col])

    candles = []
    for group in groups:
        if len(group) > 24:
            continue

        top = min(c["top"] for c in group)
        bottom = max(c["bottom"] for c in group)
        if bottom - top < 3:
            continue

        counts = Counter()
        for c in group:
            counts[c["color"]] += c["count"]

        candles.append({
            "x": sum(c["x"] for c in group) / len(group),
            "high": top,
            "low": bottom,
            "color": counts.most_common(1)[0][0],
        })

    return candles, width, height


def analyse(path):
    candles, width, height = detect_candles(path)

    if len(candles) < 8:
        return (
            "⚠️ ما قدرت أميّز 8 شموع واضحة على الأقل.\n"
            "جرّب صورة للشارت أوضح، واقصّ القوائم "
            "والأزرار قدر الإمكان."
        ), "WAIT"

    recent = candles[-12:]
    highs = [c["high"] for c in recent]
    lows = [c["low"] for c in recent]
    colors = [c["color"] for c in recent]

    rising_highs = highs[-1] < highs[0]
    rising_lows = lows[-1] < lows[0]
    falling_highs = highs[-1] > highs[0]
    falling_lows = lows[-1] > lows[0]

    up_count = colors.count("UP")
    down_count = colors.count("DOWN")

    if rising_highs and rising_lows and up_count > down_count:
        direction = "UP"
        trend = "ميل صاعد مبدئي"
    elif falling_highs and falling_lows and down_count > up_count:
        direction = "DOWN"
        trend = "ميل هابط مبدئي"
    else:
        direction = "WAIT"
        trend = "الاتجاه غير واضح بما يكفي"

    # هاي إحداثيات بالصورة، مو أسعار فعلية
    support_y = max(lows[-6:])
    resistance_y = min(highs[-6:])

    report = (
        "📊 تحليل الشارت المجاني\n"
        "━━━━━━━━━━━━━━━\n"
        f"🕯️ شموع مرصودة تقريبياً: {len(candles)}\n"
        f"🟢 خضراء ضمن آخر 12 شمعة: {up_count}\n"
        f"🔴 حمراء ضمن آخر 12 شمعة: {down_count}\n\n"
        f"📈 الاتجاه: {trend}\n"
        f"🎯 القرار المبدئي: {direction}\n\n"
        "📍 مناطق تقريبية داخل الصورة:\n"
        f"• دعم بصري (إحداثي Y): {support_y}\n"
        f"• مقاومة بصرية (إحداثي Y): {resistance_y}\n\n"
        "⏱️ الفريم والسعر الحقيقي غير مقروءين "
        "بشكل موثوق من هالفحص.\n"
        "🛑 إلغاء الفكرة: أعد التقييم إذا تغيّر "
        "شكل القمم والقيعان أو ظهر اختراق واضح.\n\n"
        "⚠️ هاد تقدير بصري تجريبي، مو قراءة "
        "مضمونة للشموع ولا إشارة دخول مؤكدة.\n"
        "لا تعتبر إحداثيات الصورة أسعاراً، "
        "ولا تعتمد عليها وحدها لفتح صفقة."
    )

    return report, direction


def save_result(path, direction, report):
    new_file = not LOG_FILE.exists()
    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["time", "image", "direction", "analysis"])
        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            path.name,
            direction,
            report.replace("\n", " | "),
        ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً يا خيو! 👋\n"
        "أنا بوت فحص الشارت المجاني.\n\n"
        "📷 ابعت صورة واضحة للشموع.\n"
        "/start — بدء\n"
        "/results — تنزيل سجل التحليلات\n\n"
        "الفحص تجريبي ولا يضمن توقع الحركة أو الربح."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    path = SAVE_DIR / f"{message.from_user.id}_{message.message_id}.jpg"

    try:
        tg_file = await message.photo[-1].get_file()
        await tg_file.download_to_drive(custom_path=str(path))

        report, direction = analyse(path)
        save_result(path, direction, report)

        await message.reply_text("✅ وصلت الصورة وانحفظت.\n\n" + report)

    except Exception as error:
        print(f"Image error: {error}")
        await message.reply_text(
            "صار خطأ بفحص الصورة. تأكد إن Pillow مثبتة، "
            "وجرّب صورة ثانية."
        )


async def results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not LOG_FILE.exists():
        await update.message.reply_text("لسا ما في تحليلات محفوظة.")
        return

    await update.message.reply_document(
        document=str(LOG_FILE),
        filename="analysis_results.csv",
        caption="📁 سجل التحليلات المحفوظة"
    )


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("results", results))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("Free Chart Bot is running!")
    app.run_polling()


if __name__ == "__main__":
    main()
                
