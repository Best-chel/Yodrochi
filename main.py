import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Загружаем переменные
load_dotenv(override=True)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Состояния
class AdminReply(StatesGroup):
    waiting_for_reply = State()

class UserState(StatesGroup):
    waiting_for_message = State()

# Вспомогательная функция для инструкции
async def send_instruction(message: Message, state: FSMContext):
    await state.set_state(UserState.waiting_for_message)
    await message.answer(
        "🚀 Здесь можно отправить анонимное сообщение человеку, который опубликовал эту ссылку.\n\n"
        "✍️ Напишите сюда всё, что хотите ему передать, и через несколько секунд он получит ваше сообщение.\n\n"
        "Отправить можно фото, видео, 💬 текст, 🔊 голосовые, 📷 видеосообщения (кружки), а также ✨ стикеры."
    )

# Команда /start
@dp.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("👋 Привет, Админ! Бот готов к работе.")
    else:
        await send_instruction(message, state)

# Обработка входящих от пользователей
@dp.message(F.chat.type == "private", F.chat.id != ADMIN_ID, UserState.waiting_for_message)
async def handle_user_message(message: Message, state: FSMContext):
    # 1. Отправляем админу уведомление
    await bot.send_message(chat_id=ADMIN_ID, text="🏄‍♂️ У тебя новое сообщение:")

    # Копируем сообщение пользователя (медиа или текст)
    await bot.copy_message(chat_id=ADMIN_ID, from_chat_id=message.chat.id, message_id=message.message_id)

    # 2. Создаем кнопку "Ответить"
    admin_builder = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{message.from_user.id}")
    ]])

    # 3. Отправляем данные отправителя
    admin_info = (
        f"👤 От: {message.from_user.full_name} (@{message.from_user.username or 'нет юзернейма'})\n"
        f"🆔 ID: {message.from_user.id}\n\n"
        f"↩️ Нажми кнопку ниже для ответа."
    )
    await bot.send_message(chat_id=ADMIN_ID, text=admin_info, reply_markup=admin_builder)

    # 4. Ответ пользователю
    user_builder = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✍️ Отправить ещё", callback_data="user_reply")
    ]])

    await message.answer("💬 Сообщение отправлено, ожидайте ответ!", reply_markup=user_builder)
    await state.clear()

# Обработчик кнопки "Отправить ещё"
@dp.callback_query(F.data == "user_reply")
async def user_reply_handler(callback: CallbackQuery, state: FSMContext):
    # 1. Разрешаем пользователю писать
    await state.set_state(UserState.waiting_for_message)

    # 2. Мгновенно редактируем старое сообщение (удаляем кнопку и меняем текст)
    await callback.message.edit_text(
        text="✍️ Слушаю вас, присылайте сообщение:",
        reply_markup=None # Кнопка исчезнет
    )

    await callback.answer()

# Когда админ нажал на кнопку "Ответить"
@dp.callback_query(F.data.startswith("reply_"))
async def start_reply(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split("_")[1]
    # Берем имя из текста сообщения
    user_name = callback.message.text.split("\n")[0].replace("👤 От: ", "")

    await state.update_data(user_id=user_id, user_name=user_name)
    await state.set_state(AdminReply.waiting_for_reply)
    await callback.message.answer(f"✍️ Введите ответ для пользователя {user_name}:")
    await callback.answer()

# Когда админ отправил текст ответа
@dp.message(AdminReply.waiting_for_reply)
async def send_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")
    user_name = data.get("user_name")

    # Создаем кнопку для пользователя
    user_builder = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Отправить ещё", callback_data="user_reply")
    ]])

    try:
        # Отправляем пользователю ответ и кнопку
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=user_builder # Добавили кнопку сюда!
        )
        await message.answer(f"✅ Ответ успешно отправлен пользователю {user_name}!")
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}")

    await state.clear()

async def main():
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())