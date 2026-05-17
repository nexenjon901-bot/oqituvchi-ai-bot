import os
import logging
import asyncio
import sqlite3
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from google import genai
from google.genai import types as ai_types
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = 8407085035  # O'zingizning Telegram ID raqamingizni yozing

if not TOKEN or not AI_API_KEY:
    raise ValueError("XATOLIK: .env faylida tokenlar to'liq emas!")

client = genai.Client(api_key=AI_API_KEY)
dp = Dispatcher()

# Ma'lumotlar bazasini sozlash
conn = sqlite3.connect("oqituvchi_premium_v4.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT
    )
""")
conn.commit()

class BotStates(StatesGroup):
    waiting_for_ad = State()

SYSTEM_PROMPT = """
Siz dunyo darajasidagi "O‘QITUVCHI AI" (World-Class Teacher, Senior Mentor, Productivity Coach, Professional Guide) yordamchisiz.
Asosiy maqsad: Foydalanuvchilarni chalkash boshlovchidan bilimli, intizomli, produktiv va muvaffaqiyatli inson darajasiga olib chiqish.

JAVOB BERISH USLUBI:
- Har doim toza format, sarlavhalar va bullet pointlardan foydalaning.
- Javoblar aniq, tartibli, juda uzun bo'lmagan va insondek tabiiy bo'lsin. Robotga o'xshash quruq gaplardan qoching.
- Emoji'larni professional va juda kam ishlating.
- Har doim foydalanuvchini harakatga undang (action), keyingi qadamni ko'rsating (next step) va motivatsiya bering.

STARTUP MENTOR REJIMI:
- Startup g'oyalar topish, validatsiya, MVP qurish, branding, monetizatsiya, marketing va o'sish strategiyalarida amaliy strategiyalar bering.
- Eng samarali AI vositalarini tavsiya qiling.

TIL QOIDASI:
- Har doim foydalanuvchi yozgan tilda javob bering (O'zbekcha bo'lsa -> o'zbekcha, Inglizcha bo'lsa -> inglizcha).

XAVFSIZLIK:
- Hech qachon zararli, noqonuniy yoki axloqsiz maslahatlar bermang. Faqat educational va foydali bo'ling.
"""

def clean_markdown(text: str) -> str:
    """Telegramda xatolik bermasligi uchun matndagi barcha xunuk markdown belgilarni tozalash"""
    if not text:
        return ""
    # Ortiqcha yulduzcha va teglarni oddiy matnga aylantirish
    text = text.replace("**", "").replace("*", "").replace("`", "")
    return text.strip()

# Tugmalardan "Tarixni tozalash" butunlay olib tashlandi
def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton(text="📝 Test / Quiz yaratish"), KeyboardButton(text="📚 Referat / Insho yozish")],
        [KeyboardButton(text="🧮 Matematika & Masalalar"), KeyboardButton(text="🚀 AI Startup Mentor")],
        [KeyboardButton(text="💡 AI Ustozdan so'rash")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Foydalanuvchilar statistikasi")],
            [KeyboardButton(text="📢 Hammasiga xabar yuborish")],
            [KeyboardButton(text="⬅️ Bosh menyuga qaytish")]
        ],
        resize_keyboard=True
    )

@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)", 
                   (user_id, message.from_user.username, message.from_user.full_name))
    conn.commit()
    
    welcome_text = (
        f"Assalomu alaykum, hurmatli {message.from_user.full_name}!\n\n"
        f"Men — O‘QITUVCHI AI professional sun'iy intellekt ekotizimiga xush kelibsiz.\n\n"
        f"Sizga quyidagi yo'nalishlarda professional yordam bera olaman:\n"
        f"• Ta'lim: Testlar, insholar, referatlar va tillar o'rganish\n"
        f"• Biznes: Startup g'oyalar, MVP qurish va marketing strategiyalari\n"
        f"• Fayllar: PDF, rasm va hujjatlarni tahlil qilish va xulosalash\n"
        f"• Ovoz: Ovozli savollarga insondek tabiiy javob olish\n\n"
        f"Keling, hoziroq boshlaymiz. Quyidagi menyudan o'zingizga kerakli bo'limni tanlang:"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(user_id))

# AI FILE ANALYZER (Rasm tahlili)
@dp.message(F.photo)
async def photo_handler(message: types.Message):
    user_id = message.from_user.id
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    photo = message.photo[-1]
    file_info = await message.bot.get_file(photo.file_id)
    destination = f"photo_{user_id}.jpg"
    await message.bot.download_file(file_info.file_path, destination)
    
    caption = message.caption if message.caption else "Ushbu faylni tahlil qil, tushuntir va asosiy g'oyalarini chiqarib soddalashtir."
    await message.answer("📥 Tasvir qabul qilindi. AI tahlil qilmoqda...")
    
    try:
        with open(destination, "rb") as f:
            image_bytes = f.read()
            
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                ai_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                caption
            ],
            config=ai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
        )
        await message.answer(clean_markdown(response.text))
    except Exception as e:
        await message.answer(f"Xatolik yuz berdi: {e}")
    finally:
        if os.path.exists(destination):
            os.remove(destination)

# AI FILE ANALYZER (PDF tahlili)
@dp.message(F.document)
async def document_handler(message: types.Message):
    user_id = message.from_user.id
    file_name = message.document.file_name
    
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    await message.answer(f"📥 {file_name} qabul qilindi. AI hujjatni tahlil qilmoqda...")
    
    file_info = await message.bot.get_file(message.document.file_id)
    destination = f"doc_{user_id}_{file_name}"
    await message.bot.download_file(file_info.file_path, destination)
    
    try:
        with open(destination, "rb") as f:
            doc_bytes = f.read()
            
        mime_type = "application/pdf" if file_name.lower().endswith('.pdf') else "text/plain"
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                ai_types.Part.from_bytes(data=doc_bytes, mime_type=mime_type),
                "Ushbu hujjatni tahlil qil, qisqacha mazmunini yoz, asosiy g'oyalarni chiqar va soddalashtirib tushuntir."
            ],
            config=ai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
        )
        await message.answer(clean_markdown(response.text))
    except Exception as e:
        await message.answer("Hujjatni tahlil qilishda xatolik bo'ldi. PDF formatida yuborib ko'ring.")
    finally:
        if os.path.exists(destination):
            os.remove(destination)

# AI VOICE MODE (Ovozli xabarlar)
@dp.message(F.voice)
async def voice_handler(message: types.Message):
    user_id = message.from_user.id
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    file_info = await message.bot.get_file(message.voice.file_id)
    destination = f"voice_{user_id}.ogg"
    await message.bot.download_file(file_info.file_path, destination)
    
    try:
        with open(destination, "rb") as f:
            voice_bytes = f.read()
            
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                ai_types.Part.from_bytes(data=voice_bytes, mime_type="audio/ogg"),
                "Foydalanuvchining ovozli savolini tingla va unga juda tabiiy, insondek va professional javob ber. Agar inglizcha gapirgan bo'lsa talaffuz mashqlariga yordam ber."
            ],
            config=ai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
        )
        await message.answer(clean_markdown(response.text))
    except Exception as e:
        await message.answer("Ovozli xabarni tahlil qilishda xatolik yuz berdi.")
    finally:
        if os.path.exists(destination):
            os.remove(destination)

# Matnli xabarlar boshqaruvi
@dp.message()
async def main_handler(message: types.Message, state: FSMContext) -> None:
    user_text = message.text
    user_id = message.from_user.id
    
    if user_text == "⚙️ Admin Panel" and user_id == ADMIN_ID:
        await message.answer("Admin panel bo'limi:", reply_markup=get_admin_keyboard())
        return
    elif user_text == "📊 Foydalanuvchilar statistikasi" and user_id == ADMIN_ID:
        cursor.execute("SELECT COUNT(*) FROM users")
        await message.answer(f"Jami foydalanuvchilar: {cursor.fetchone()[0]} ta")
        return
    elif user_text == "📢 Hammasiga xabar yuborish" and user_id == ADMIN_ID:
        await message.answer("Foydalanuvchilarga yubormoqchi bo'lgan xabarni yozing:")
        await state.set_state(BotStates.waiting_for_ad)
        return
    elif user_text == "⬅️ Bosh menyuga qaytish":
        await message.answer("Bosh menyu:", reply_markup=get_main_keyboard(user_id))
        return

    current_state = await state.get_state()
    if current_state == BotStates.waiting_for_ad.state and user_id == ADMIN_ID:
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        for u in users:
            try: await message.copy_to(chat_id=u[0]); await asyncio.sleep(0.05)
            except: pass
        await message.answer("Xabar barcha foydalanuvchilarga tarqatildi.", reply_markup=get_admin_keyboard())
        await state.clear()
        return

    if user_text in ["📝 Test / Quiz yaratish", "📚 Referat / Insho yozish", "🧮 Matematika & Masalalar"]:
        await message.answer(f"Siz '{user_text}' bo'limini tanladingiz. Mavzu yoki savolingizni batafsil yozib yuboring:")
        return
    elif user_text == "🚀 AI Startup Mentor":
        await message.answer("🚀 AI Startup Mentor bo'limiga xush kelibsiz!\n\nMen sizga yangi g'oya topish, MVP qurish, marketing, monetizatsiya va o'sish strategiyalarini tuzishda senior mentor sifatidagi amaliy tavsiyalar beraman.\n\nG'oyangiz yoki startapingiz haqida yozing, keyingi qadamlarni rejalashtiramiz:")
        return
    elif user_text == "💡 AI Ustozdan so'rash":
        await message.answer("Menga istalgan savolingizni yo'llang. Sizga eng toza va tushunarli formatda javob beraman:")
        return

    # Matnli AI so'rov qismi
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_text,
            config=ai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
        await message.answer(clean_markdown(response.text))
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await message.answer("Kechirasiz, tizimda muammo bo'ldi. Qayta urinib ko'ring.")

async def main() -> None:
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot to'xtatildi")
