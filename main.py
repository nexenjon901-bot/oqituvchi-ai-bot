import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.utils.markdown import hbold
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from google import genai
from google.genai import types as ai_types
from dotenv import load_dotenv

# PDF yaratish uchun ReportLab kutubxonalari
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN or not AI_API_KEY:
    raise ValueError("XATOLIK: .env faylida tokenlar to'liq emas!")

client = genai.Client(api_key=AI_API_KEY)
dp = Dispatcher()

# Bot xotirasida oxirgi matnni saqlab turish uchun holat (State)
class BotStates(StatesGroup):
    waiting_for_input = State()

SYSTEM_PROMPT = """
SEN “O‘QITUVCHI AI” NOMLI PROFESSIONAL SUN’IY INTELLEKT YORDAMCHISISAN.
Foydalanuvchi so'ragan mavzuda mukammal va darslik darajasidagi ma'lumotlarni berasan.
Agar referat yoki insho so'ralsa, uni REJA, KIRISH, ASOSIY QISM va XULOSA shaklida yoz.
O'zbek tilidagi o'ziga xos harflarni (o', g', sh, ch) imlo qoidalariga mos yoz.
"""

# Asosiy menyu tugmalari
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Test / Quiz yaratish"), KeyboardButton(text="📚 Referat / Insho yozish")],
            [KeyboardButton(text="🧮 Matematika & Buxgalteriya"), KeyboardButton(text="🇬🇧 Ingliz / 🇷🇺 Rus tili")],
            [KeyboardButton(text="📊 Excel & Dars rejalari"), KeyboardButton(text="💡 AI Ustozdan so'rash")],
            [KeyboardButton(text="📄 PDF formatida yuklab olish")] # Yangi funksiya tugmasi
        ],
        resize_keyboard=True
    )
    return keyboard

# Matnni PDF faylga aylantirish funksiyasi
def create_pdf(text, filename="Oqituvchi_AI_Referat.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )
    styles = getSampleStyleSheet()
    
    # Maxsus chiroyli stillar
    title_style = ParagraphStyle(
        'PDFTitle',
        parent=styles['Heading1'],
        fontSize=22,
        leading=26,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor="#1A237E"
    )
    
    body_style = ParagraphStyle(
        'PDFBody',
        parent=styles['Normal'],
        fontSize=12,
        leading=18,
        alignment=TA_JUSTIFY,
        spaceAfter=10
    )

    story = []
    
    # Sarlavha qo'shish
    story.append(Paragraph("<b>“O‘QITUVCHI AI” TAQDIM ETADI</b>", title_style))
    story.append(Spacer(1, 15))
    
    # Matnni qatorlarga bo'lib, PDF ga joylash
    lines = text.split("\n")
    for line in lines:
        if line.strip():
            # Markdown belgilarini tozalash yoki almashtirish
            clean_line = line.replace("**", "<b>").replace("__", "<i>")
            clean_line = clean_line.replace("<b>", "", 1) if clean_line.count("<b>") % 2 != 0 else clean_line
            
            story.append(Paragraph(clean_line, body_style))
        else:
            story.append(Spacer(1, 8))
            
    doc.build(story)
    return filename

@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    await message.answer(
        f"Assalomu alaykum, {hbold(message.from_user.full_name)}!\n\n"
        f"Men **“O‘QITUVCHI AI”** professional ustoz botiman.\n"
        f"Quyidagi menyudan o'zingizga kerakli yo'nalishni tanlang:",
        reply_markup=get_main_keyboard()
    )

@dp.message()
async def ai_teacher_handler(message: types.Message, state: FSMContext) -> None:
    user_text = message.text
    
    # Tugmalar bosilganda yo'riqnomalar ko'rsatish
    if user_text == "📝 Test / Quiz yaratish":
        await message.answer("Sizga qaysi mavzuda va qanday darajadagi test kerak? Mavzuni yozing:")
        return
    elif user_text == "📚 Referat / Insho yozish":
        await message.answer("Menga referat yoki insho mavzusini yuboring. Uni tayyorlab berganimdan so'ng '📄 PDF formatida yuklab olish' tugmasini bosib fayl ko'rinishida olishingiz mumkin:")
        return
    elif user_text == "🧮 Matematika & Buxgalteriya":
        await message.answer("Misol, masala yoki buxgalteriya bo'yicha savolingizni yuboring:")
        return
    elif user_text == "🇬🇧 Ingliz / 🇷🇺 Rus tili":
        await message.answer("Grammatika, tarjima yoki mashqlar uchun mavzuni yoki matnni yuboring:")
        return
    elif user_text == "📊 Excel & Dars rejalari":
        await message.answer("Excel formulasi yoki kerakli dars rejasining mavzusini kiriting:")
        return
    elif user_text == "💡 AI Ustozdan so'rash":
        await message.answer("Istalgan murakkab mavzuni yuboring, sodda tilda tushuntiraman:")
        return
        
    # PDF yuklab olish tugmasi bosilganda
    elif user_text == "📄 PDF formatida yuklab olish":
        user_data = await state.get_data()
        last_response = user_data.get("last_response")
        
        if not last_response:
            await message.answer("Kechirasiz, hali hech qanday ma'lumot tayyorlanmadi. Avval mavzuni yozing, keyin PDF yuklab oling.")
            return
            
        await message.answer("Fayl tayyorlanmoqda, iltimos kuting...")
        
        # PDF yaratish va yuborish
        pdf_file_path = create_pdf(last_response)
        document = FSInputFile(pdf_file_path)
        
        await message.answer_document(document=document, caption="Siz so'ragan ma'lumotlar asosida tayyorlangan PDF hujjat.")
        
        # Vaqtinchalik yaratilgan faylni o'chirish
        if os.path.exists(pdf_file_path):
            os.remove(pdf_file_path)
        return

    # Foydalanuvchi oddiy matn (savol yoki mavzu) yuborganida AI javob beradi
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_text,
            config=ai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
        )
        
        ai_reply = response.text
        
        # Keyinchalik PDF qilish uchun javobni bot xotirasida (State) saqlab qo'yamiz
        await state.update_data(last_response=ai_reply)
        
        await message.answer(ai_reply, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await message.answer("Kechirasiz, so‘rovni bajarishda xatolik bo'ldi. Qaytadan urinib ko'ring.")

async def main() -> None:
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())