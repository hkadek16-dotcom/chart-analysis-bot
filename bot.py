
import os
import base64
import asyncio
from pathlib import Path

from openai import OpenAI
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AI_KEY = os.getenv("OPENAI_API_KEY")

SAVE_DIR = Path("received_charts")
SAVE_DIR.mkdir(exist_ok=True)


def analyze_chart(image_path):
    client = OpenAI(api_key=AI_KEY)

    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    prompt = """
أنت مساعد تعليمي لتحليل الرسوم البيانية المالية.
أجب باللغة العربية السورية المبسطة.

حلل صورة الشارت المرفقة، واستخدم هذا الترتيب:

1. وضوح الصورة وهل يمكن قراءة الشموع.
2. الفريم الظاهر بالصورة، وإذا لم يكن واضحاً قل غير معروف.
3. الاتجاه: صاعد أو هابط أو عرضي، مع السبب.
4. القمم والقيعان الظاهرة.
5. مناطق الدعم والمقاومة التقريبية إن أمكن.
6. هل توجد فرصة تستحق الانتظار أم أن الأفضل عدم الدخول؟
7. شروط محتملة للدخول، وما الذي يلغي الفكرة.
8. مدة الصفقة المحتملة، مع توضيح أنها تقديرية.
9. ما المعلومات الناقصة قبل اتخاذ أي قرار؟

اعتبر فريم التحليل المطلوب 5 دقائق، لكن لا تدّعِ
أن الصورة من هذا الفريم إن لم تستطع التأكد.
لا تخترع أسعاراً أو أوقات دخول أو بيانات غير ظاهرة.
إذا كانت الصورة غير كافية، اطلب صورة أوضح.
لا تضمن الربح، ولا تقدّم أي إشارة على أنها مؤكدة.
"""

    result = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": (
                            "data:image/jpeg;base64," + encoded
                        ),
                    },
                ],
            }
        ],
    )

    return result.output_text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً يا خيو! 👋\n"
        "أنا بوت تحليل الشارت.\n\n"
        "ابعت صورة واضحة للشارت، ويفضل أن يظهر "
        "اسم الأصل والفريم ومحور الوقت.\n"
        "رح أساعدك بتحليل الاتجاه والقمم والقيعان "
        "والدعم والمقاومة وشروط الدخول والإلغاء.\n\n"
        "التحليل احتمالي وليس ضماناً للربح."
    )


async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message = update.message
    await message.reply_text(
        "📷 وصلت الصورة يا خيو، عم حللها... "
        "اصبر شوي."
    )

    try:
        photo = message.photo[-1]
        tg_file = await photo.get_file()

        path = SAVE_DIR / (
            f"{message.from_user.id}_{message.message_id}.jpg"
        )

        await tg_file.download_to_drive(custom_path=str(path))

        if not AI_KEY:
            await message.reply_text(
                "الصورة انحفظت، بس التحليل مو مفعّل بعد.\n"
                "لازم نضيف مفتاح OPENAI_API_KEY "
                "بإعدادات الاستضافة."
            )
            return

        result = await asyncio.to_thread(analyze_chart, path)

        if not result:
            result = "ما قدرت أطلع نتيجة واضحة من الصورة."

        # تيليغرام يحدد طول الرسالة؛ نقسم الرد إذا كان طويلاً.
        for i in range(0, len(result), 3500):
            await message.reply_text(result[i:i + 3500])

    except Exception as e:
        print(f"Photo analysis error: {e}")
        await message.reply_text(
            "صار خطأ أثناء التحليل. تأكد من إعدادات "
            "مفتاح الذكاء الاصطناعي ورصيد الخدمة، "
            "وبعدين جرّب مرة ثانية."
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
    
  
