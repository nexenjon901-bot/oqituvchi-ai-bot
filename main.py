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
from google.genai import types as ai_types
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = 8407085035  # Sizning Telegram ID raqamingiz

if not TOKEN or not AI_API_KEY:
    raise ValueError("XATOLIK: .env faylida tokenlar to'liq emas!")

client = genai.Client(api_key=AI_API_KEY)
dp = Dispatcher()

# Ma'lumotlar bazasini sozlash (Faqat foydalanuvchilar uchun, tarix kerak emas)
conn = sqlite3.connect("oqituvchi_users.db", check_same_thread=False)
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

SYSTEM_PROMPT = "Sen O‘qituvchi AI nomli professional sun'iy intellekt yordamchisisan. Berilgan savollarga aniq, tushunarli va chiroyli javob ber. Hech qanday ortiqcha yulduzcha (*) yoki xunuk teglarni ishlatma."

# Asosiy menyu (Tarixni tozalash tugmasi olib tashlandi)
def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton(text="📝 Test / Quiz yaratish"), KeyboardButton(text="📚 Referat / Insho yozish")],
        [KeyboardButton(text="🧮 Matematika & Masalalar"), KeyboardButton(text="💡 AI Ustozdan so'rash")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# Admin menyusi
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
        f"Sizga quyidagi ishlarda yordam bera olaman:\n"
        f"• Istalgan mavzuda Test va Quizlar yaratish\n"
        f"• Sifatli Referat, Insho va Esse yozish\n"
        f"• Matematika, Mantiq va qiyin masalalarni yechish\n"
        f"• Ingliz va Rus tillari bo'yicha savollarga javob berish\n\n"
        f"Hatto menga misollarni rasmga olib tashlasangiz ham yechib bera olaman!\n\n"
        f"Boshlash uchun pastdagi menyudan kerakli bo'limni tanlang:"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(user_id))

# Rasm qabul qilish
@dp.message(F.photo)
async def photo_handler(message: types.Message):
    user_id = message.from_user.id
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    photo = message.photo[-1]
    file_info = await message.bot.get_file(photo.file_id)
    destination = f"photo_{user_id}.jpg"
    await message.bot.download_file(file_info.file_path, destination)
    
    caption = message.caption if message.caption else "Ushbu rasmdagi topshiriq yoki misolni yechib, tushuntirib ber."
    await message.answer("Rasm qabul qilindi. AI tahlil qilmoqda, iltimos kuting...")
    
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
        await message.answer(response.text)
    except Exception as e:
        await message.answer(f"Xatolik yuz berdi: {e}")
    finally:
        if os.path.exists(destination):
            os.remove(destination)

# Xabarlar va Admin panel
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
            try: 
                await message.copy_to(chat_id=u[0])
                await asyncio.sleep(0.05)
            except: 
                pass
        await message.answer("Xabar barcha foydalanuvchilarga tarqatildi.", reply_markup=get_admin_keyboard())
        await state.clear()
        return

    if user_text in ["📝 Test / Quiz yaratish", "📚 Referat / Insho yozish", "🧮 Matematika & Masalalar", "💡 AI Ustozdan so'rash"]:
        await message.answer(f"Siz '{user_text}' bo'limini tanladingiz. Mavzu yoki savolingizni batafsil yozib yuboring:")
        return

    # Toza va mustaqil AI javob berish tizimi
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_text,
            config=ai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
        await message.answer(response.text)
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await message.answer("Kechirasiz, xatolik yuz berdi. Qayta urinib ko'ring.")

async def main() -> None:
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try: 
        asyncio.run(main())
    except KeyboardInterrupt: 
        print("Bot to'xtatildi")
