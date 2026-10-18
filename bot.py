
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


def read_chart(path):
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((900, 650))
        width, height = img.size
        px = img.load()

        # اكتشاف الألوان القوية فقط لتخفيف ضجيج الخلفية
        mask = {}
        for x in range(width):
            for y in range(height):
                r, g, b = px[x, y]
                if g > 95 and g > r * 1.20 and g > b * 1.10:
                    mask[(x, y)] = "UP"
                elif r > 100 and r > g * 1.20 and r > b * 1.10:
                    mask[(x, y)] = "DOWN"

        # تجميع البكسلات المتجاورة أفقياً إلى أجسام محتملة للشموع
        by_x = {}
        for (x, y), color in mask.items():
            by_x.setdefault(x, []).append((y, color))

        active_columns = []
        for x in sorted(by_x):
            items = by_x[x]
            ys = [item[0] for item in items]
            colors = Counter(item[1] for item in items)

            if len(ys) < 3:
                continue

            active_columns.append({
                "x": x,
                "top": min(ys),
                "bottom": max(ys),
                "color": colors.most_common(1)[0][0],
                "pixels": len(ys),
            })

    groups = []
    for col in active_columns:
        if groups and col["x"] - groups[-1][-1]["x"] <= 2:
            groups[-1].append(col)
        else:
            groups.append([col])

    candles = []
    for group in groups:
        if len(group) > 18:
            continue

        top = min(c["top"] for c in group)
        bottom = max(c["bottom"] for c in group)
        if bottom - top < 4:
            continue

        colors = Counter()
        for c in group:
            colors[c["color"]] += c["pixels"]

        candles.append({
            "x": sum(c["x"] for c in group) / len(group),
            "high": top,
            "low": bottom,
            "color": colors.most_common(1)[0][0],
        })

    return candles, width, height


def analyse_chart(path):
    candles, width, height = read_chart(path)

    if len(candles) < 6:
        return (
            "⚠️ ما قدرت أميّز شموع كافية.\n"
            "جرّب صورة يظهر فيها الشارت بشكل أكبر، "
            "وتأكد أن الشموع خضرا وحمرا وواضحة."
        ), "WAIT"

    recent = candles[-12:]
    highs = [c["high"] for c in recent]
    lows = [c["low"] for c in recent]
    colors = [c["color"] for c in recent]

    up = colors.count("UP")
    down = colors.count("DOWN")

    # إحداثيات الصورة ليست أسعاراً فعلية
    lower_highs = highs[-1] < highs[0]
    lower_lows = lows[-1] < lows[0]
    higher_highs = highs[-1] > highs[0]
    higher_lows = lows[-1] > lows[0]

    if higher_highs and higher_lows and up > down:
        decision = "UP"
        trend = "ميل صاعد مبدئي"
    elif lower_highs and lower_lows and down > up:
        decision = "DOWN"
        trend = "ميل هابط مبدئي"
    else:
        decision = "WAIT"
        trend = "الاتجاه غير واضح"

    support_y = max(lows[-6:])
    resistance_y = min(highs[-6:])

    report = (
        "📊 تحليل مبدئي للشارت\n"
        "━━━━━━━━━━━━━━━\n"
        f"🕯️ الشموع المكتشفة تقريبياً: {len(candles)}\n"
        f"🟢 أعمدة خضراء ضمن آخر 12: {up}\n"
        f"🔴 أعمدة حمراء ضمن آخر 12: {down}\n\n"
        f"📈 الاتجاه: {trend}\n"
        f"🎯 القرار المبدئي: {decision}\n\n"
        "📍 مناطق مرئية تقريبية بالصورة:\n"
        f"• دعم بصري (Y): {support_y}\n"
        f"• مقاومة بصرية (Y): {resistance_y}\n\n"
        "⏱️ الفريم والسعر الحقيقي لازم يتأكدا من الشارت.\n"
        "🛑 أعد التقييم إذا تغيّر ترتيب القمم والقيعان.\n\n"
        "⚠️ إحداثيات Y هي مواقع داخل الصورة وليست أسعاراً.\n"
        "هذا تقدير تجريبي وليس إشارة دخول مضمونة."
    )
    return report, decision


def save_result(path, decision, report):
    is_new = not LOG_FILE.exists()
    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["time", "image", "decision", "report"])
        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            path.name,
            decision,
            report.replace("\n", " | "),
        ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً يا خيو! 👋\n"
        "ابعت صورة واضحة للشارت حتى أجرّب تحليلها.\n"
        "الفحص مجاني وتجريبي، وما بيضمن اتجاه السوق."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    path = SAVE_DIR / f"{message.from_user.id}_{message.message_id}.jpg"

    try:
        tg_file = await message.photo[-1].get_file()
        await tg_file.download_to_drive(custom_path=str(path))
        report, decision = analyse_chart(path)
        save_result(path, decision, report)
        await message.reply_text("✅ وصلت الصورة وانحفظت.\n\n" + report)
    except Exception as error:
        print(f"Photo error: {error}")
        await message.reply_text(
            "صار خطأ أثناء فحص الصورة. جرّب مرة ثانية."
        )


async def results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not LOG_FILE.exists():
        await update.message.reply_text("لسا ما في نتائج محفوظة.")
        return

    await update.message.reply_document(
        document=str(LOG_FILE),
        filename="analysis_results.csv",
        caption="📁 سجل التحليلات"
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
                
