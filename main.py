import os
import logging
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.utils.markdown import hbold
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from google import genai
from google.genai import types as ai_types
from dotenv import load_dotenv

# PDF yaratish uchun ReportLab
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = 8407085035  # ⚠️ DIQQAT: Bu yerga o'zingizning Telegram ID raqamingizni yozing!

if not TOKEN or not AI_API_KEY:
    raise ValueError("XATOLIK: .env faylida tokenlar to'liq emas!")

client = genai.Client(api_key=AI_API_KEY)
dp = Dispatcher()

# Ma'lumotlar bazasini sozlash
conn = sqlite3.connect("users_v2.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT
    )
""")
conn.commit()

# Bot xotirasi holatlari
class BotStates(StatesGroup):
    waiting_for_input = State()
    waiting_for_ad = State() # Admin reklama yuborishi uchun holat

SYSTEM_PROMPT = "SEN “O‘QITUVCHI AI” NOMLI PROFESSIONAL SUN’IY INTELLEKT YORDAMCHISISAN..."

# Asosiy menyu
def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton(text="📝 Test / Quiz yaratish"), KeyboardButton(text="📚 Referat / Insho yozish")],
        [KeyboardButton(text="🧮 Matematika & Buxgalteriya"), KeyboardButton(text="🇬🇧 Ingliz / 🇷🇺 Rus tili")],
        [KeyboardButton(text="📊 Excel & Dars rejalari"), KeyboardButton(text="💡 AI Ustozdan so'rash")],
        [KeyboardButton(text="📄 PDF formatida yuklab olish")]
    ]
    # Agar foydalanuvchi admin bo'lsa, unga qo'shimcha Admin Panel tugmasini chiqaramiz
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="⚙️ Admin Panel")])
        
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# Admin panel tugmalari
def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Foydalanuvchilar statistikasi")],
            [KeyboardButton(text="📢 Hammasiga xabar yuborish")],
            [KeyboardButton(text="⬅️ Bosh menyuga qaytish")]
        ],
        resize_keyboard=True
    )

def create_pdf(text, filename="Oqituvchi_AI_Referat.pdf"):
    # (Oldingi PDF yaratish kodi o'zgarishsiz qoladi)
    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('PDFTitle', parent=styles['Heading1'], fontSize=22, leading=26, alignment=TA_CENTER, spaceAfter=20, textColor="#1A237E")
    body_style = ParagraphStyle('PDFBody', parent=styles['Normal'], fontSize=12, leading=18, alignment=TA_JUSTIFY, spaceAfter=10)
    story = [Paragraph("<b>“O‘QITUVCHI AI” TAQDIM ETADI</b>", title_style), Spacer(1, 15)]
    for line in text.split("\n"):
        if line.strip():
            clean_line = line.replace("**", "<b>").replace("__", "<i>")
            story.append(Paragraph(clean_line, body_style))
        else:
            story.append(Spacer(1, 8))
    doc.build(story)
    return filename

@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    # Foydalanuvchini bazaga qo'shish (agar u avval kirmagan bo'lsa)
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)", (user_id, username, full_name))
    conn.commit()
    
    await message.answer(
        f"Assalomu alaykum, {hbold(full_name)}!\n\nMen **“O‘QITUVCHI AI”** botiman. Menyudan yo'nalishni tanlang:",
        reply_markup=get_main_keyboard(user_id)
    )

@dp.message()
async def main_handler(message: types.Message, state: FSMContext) -> None:
    user_text = message.text
    user_id = message.from_user.id
    
    # ADMIN PANEL FUNKSIYALARI
    if user_text == "⚙️ Admin Panel" and user_id == ADMIN_ID:
        await message.answer("Admin panelga xush kelibsiz. Kerakli bo'limni tanlang:", reply_markup=get_admin_keyboard())
        return
        
    elif user_text == "📊 Foydalanuvchilar statistikasi" and user_id == ADMIN_ID:
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        await message.answer(f"📊 **Bot statistikasi:**\n\nJami foydalanuvchilar soni: **{total_users} ta**")
        return
        
    elif user_text == "📢 Hammasiga xabar yuborish" and user_id == ADMIN_ID:
        await message.answer("Foydalanuvchilarga yubormoqchi bo'lgan xabaringizni (matn, rasm yoki e'lon) yuboring:")
        await state.set_state(BotStates.waiting_for_ad)
        return
        
    elif user_text == "⬅️ Bosh menyuga qaytish":
        await message.answer("Bosh menyuga qaytdingiz:", reply_markup=get_main_keyboard(user_id))
        return

    # AI KATEGORIYALARI MATNLARI
    if user_text in ["📝 Test / Quiz yaratish", "📚 Referat / Insho yozish", "🧮 Matematika & Buxgalteriya", "🇬🇧 Ingliz / 🇷🇺 Rus tili", "📊 Excel & Dars rejalari", "💡 AI Ustozdan so'rash"]:
        await message.answer(f"Siz **'{user_text}'** bo'limini tanladingiz. Mavzuni yoki savolingizni batafsil yozib yuboring:")
        return
        
    elif user_text == "📄 PDF formatida yuklab olish":
        user_data = await state.get_data()
        last_response = user_data.get("last_response")
        if not last_response:
            await message.answer("Kechirasiz, avval biron bir mavzuda referat yoki ma'lumot so'rang.")
            return
        await message.answer("PDF fayl tayyorlanmoqda...")
        pdf_file_path = create_pdf(last_response)
        await message.answer_document(document=FSInputFile(pdf_file_path), caption="Tayyor PDF hujjat.")
        os.remove(pdf_file_path)
        return

    # REKLAMA TARQATISH JARAYONI
    current_state = await state.get_state()
    if current_state == BotStates.waiting_for_ad.state and user_id == ADMIN_ID:
        cursor.execute("SELECT user_id FROM users")
        all_users = cursor.fetchall()
        
        await message.answer(f"{len(all_users)} ta foydalanuvchiga xabar yuborish boshlandi...")
        
        success_count = 0
        for u in all_users:
            try:
                # Xabarni barchaga nusxalab yuborish (rasm, matn, audio farqi yo'q)
                await message.copy_to(chat_id=u[0])
                success_count += 1
                await asyncio.sleep(0.05) # Telegram bloklab qo'ymasligi uchun ozgina kutish
            except Exception:
                pass # Botni bloklagan foydalanuvchilarni o'tkazib yuboradi
                
        await message.answer(f"📢 Xabar tarqatish yakunlandi.\nUshbu xabarni **{success_count} ta** odam qabul qildi.", reply_markup=get_admin_keyboard())
        await state.clear()
        return

    # ODDIY MATN KELGANDA AI JAVOB BERISHI
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_text,
            config=ai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
        ai_reply = response.text
        await state.update_data(last_response=ai_reply)
        await message.answer(ai_reply, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await message.answer("Xatolik yuz berdi. Qayta urinib ko'ring.")

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
