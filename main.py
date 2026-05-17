import os
import logging
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from google import genai
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AI_API_KEY = os.getenv("AIzaSyA5zam1PyP53aRo_o4ucy4azbF2vJ-F2c8")
ADMIN_ID = 8407085035  # O'zingizning Telegram ID raqamingizni yozing

if not TOKEN or not AI_API_KEY:
    raise ValueError("XATOLIK: .env faylida tokenlar to'liq emas!")

# Barqaror AI mijozini ulash
client = genai.Client(api_key=AI_API_KEY)
dp = Dispatcher()

# Ma'lumotlar bazasini sozlash
conn = sqlite3.connect("oqituvchi_final.db", check_same_thread=False)
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
Siz dunyo darajasidagi "O‘QITUVCHI AI" (Senior Mentor, Productivity Coach, Professional Guide) yordamchisiz.
Asosiy maqsad: Foydalanuvchilarni bilimli, intizomli va muvaffaqiyatli inson darajasiga olib chiqish.

JAVOB BERISH USLUBI:
- Matnda mutlaqo yulduzcha (*), qalinlashtirish (**) yoki xunuk teglarni ishlatmang. Oddiy va toza matn yuboring.
- Har doim sarlavhalar va qator tashlashlardan foydalaning.
- Foydalanuvchi qaysi tilda yozsa, faqat o'sha tilda insondek tabiiy javob bering.
- Javob oxirida doim keyingi qadamni ko'rsating va motivatsiya bering.
"""

# Asosiy menyu tugmalari
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

# /start buyrug'i
@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)", 
                   (user_id, message.from_user.username, message.from_user.full_name))
    conn.commit()
    
    welcome_text = (
        f"Assalomu alaykum, hurmatli {message.from_user.full_name}!\n\n"
        f"Men — O‘QITUVCHI AI professional sun'iy intellekt yordamchisiman.\n\n"
        f"Sizga quyidagi yo'nalishlarda professional yordam bera olaman:\n"
        f"• Ta'lim: Testlar, insholar va referatlar tayyorlash\n"
        f"• Biznes: Startup g'oyalar va marketing strategiyalari\n"
        f"• Fayllar va Ovoz: Rasm va ovozli xabarlarni tahlil qilish\n\n"
        f"Boshlash uchun pastdagi menyudan kerakli bo'limni tanlang:"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(user_id))

# Rasm va Skrinshot tahlili
@dp.message(F.photo)
async def photo_handler(message: types.Message):
    user_id = message.from_user.id
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    photo = message.photo[-1]
    file_info = await message.bot.get_file(photo.file_id)
    destination = f"photo_{user_id}.jpg"
    await message.bot.download_file(file_info.file_path, destination)
    
    caption = message.caption if message.caption else "Ushbu rasm yoki skrinshotni tahlil qil va tushuntir."
    await message.answer("📥 Tasvir qabul qilindi. AI tahlil qilmoqda...")
    
    try:
        with open(destination, "rb") as f:
            image_bytes = f.read()
            
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                {"mime_type": "image/jpeg", "data": image_bytes},
                caption
            ],
            config={"system_instruction": SYSTEM_PROMPT}
        )
        # Matnni tozalab yuborish
        clean_text = response.text.replace("**", "").replace("*", "").replace("`", "")
        await message.answer(clean_text)
    except Exception as e:
        await message.answer("Tasvirni tahlil qilishda xatolik bo'ldi.")
    finally:
        if os.path.exists(destination):
            os.remove(destination)

# Ovozli xabarlar tahlili
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
                {"mime_type": "audio/ogg", "data": voice_bytes},
                "Ovozli xabarni eshitib, unga juda tabiiy va professional javob qaytar."
            ],
            config={"system_instruction": SYSTEM_PROMPT}
        )
        clean_text = response.text.replace("**", "").replace("*", "").replace("`", "")
        await message.answer(clean_text)
    except Exception as e:
        await message.answer("Ovozli xabarni tahlil qilishda xatolik bo'ldi.")
    finally:
        if os.path.exists(destination):
            os.remove(destination)

# Matnli xabarlar va menyu boshqaruvi
@dp.message()
async def main_handler(message: types.Message, state: FSMContext) -> None:
    user_text = message.text
    user_id = message.from_user.id
    
    # Admin boshqaruvi
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

    # Reklama yuborish qismi
    current_state = await state.get_state()
    if current_state == BotStates.waiting_for_ad.state and user_id == ADMIN_ID:
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        for u in users:
            try: await message.copy_to(chat_id=u[0]); await asyncio.sleep(0.05)
            except: pass
        await message.answer("Xabar tarqatildi.", reply_markup=get_admin_keyboard())
        await state.clear()
        return

    # Bo'lim eslatmalari
    if user_text in ["📝 Test / Quiz yaratish", "📚 Referat / Insho yozish", "🧮 Matematika & Masalalar"]:
        await message.answer(f"Siz '{user_text}' bo'limini tanladingiz. Mavzu yoki savolingizni batafsil yozib yuboring:")
        return
    elif user_text == "🚀 AI Startup Mentor":
        await message.answer("🚀 AI Startup Mentor bo'limiga xush kelibsiz!\nG'oyangiz yoki startapingiz haqida yozing, men sizga bosqichma-bosqich amaliy strategiya tuzib beraman:")
        return
    elif user_text == "💡 AI Ustozdan so'rash":
        await message.answer("Menga istalgan savolingizni yo'llang, eng toza va tushunarli formatda javob beraman:")
        return

    # Toza va xatosiz matnli AI so'rovi
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_text,
            config={"system_instruction": SYSTEM_PROMPT}
        )
        # Barcha xato beruvchi markdown belgilarini tozalash
        clean_reply = response.text.replace("**", "").replace("*", "").replace("`", "")
        await message.answer(clean_reply)
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await message.answer("Kechirasiz, hozir javob berishda muammo bo'ldi. Qayta urinib ko'ring.")

async def main() -> None:
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot to'xtatildi")
