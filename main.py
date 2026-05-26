import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv(override=True)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Состояния для FSM (чтобы бот "понимал", кому вы отвечаете)
class AdminReply(StatesGroup):
    waiting_for_reply = State()

@dp.message(CommandStart())
async def start_cmd(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("👋 Привет, Админ! Я пересылаю сообщения. Просто нажимай кнопку 'Ответить' под сообщением пользователя.")
    else:
        await message.answer(
            "🚀 **Здесь можно отправить сообщение человеку, который опубликовал эту ссылку.**\n\n"
            "✍️ Напишите сюда всё, что хотите ему передать.\n"
            "Отправить можно фото, видео, 💬 текст, 🔊 голосовые, 📷 видеосообщения (кружки), а также ✨ стикеры."
        )

# Обработка входящих от пользователей
@dp.message(F.chat.type == "private", F.chat.id != ADMIN_ID)
async def handle_user_message(message: Message, state: FSMContext):
    # 1. Отправляем текст сообщения от подписчика
    user_text = message.text or "Пользователь прислал медиа"
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🏄‍♂️ У тебя новое сообщение!\n\n\"{user_text}\""
    )

    # 2. Создаем кнопку "Ответить"
    builder = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{message.from_user.id}")
    ]])

    # 3. Отправляем данные отправителя с кнопкой
    admin_info = (
        f"👤 От: {message.from_user.full_name} (@{message.from_user.username or 'нет юзернейма'})\n"
        f"🆔 ID: {message.from_user.id}\n\n"
        f"↩️ Нажми кнопку ниже для ответа."
    )

    await bot.send_message(chat_id=ADMIN_ID, text=admin_info, reply_markup=builder)

    await message.reply("✅ Ваше сообщение отправлено администратору.")

# Когда админ нажал на кнопку "Ответить"
@dp.callback_query(F.data.startswith("reply_"))
async def start_reply(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split("_")[1]
    await state.update_data(user_id=user_id) # Запоминаем ID того, кому отвечаем
    await state.set_state(AdminReply.waiting_for_reply)
    await callback.message.answer(f"✍️ Введите ответ для пользователя (ID: {user_id}):")
    await callback.answer()

# Когда админ отправил текст ответа
@dp.message(AdminReply.waiting_for_reply)
async def send_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")

    try:
        await bot.copy_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)
        await message.answer("✅ Ответ отправлен!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())