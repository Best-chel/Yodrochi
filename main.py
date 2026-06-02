import asyncio
import os
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv

# Загружаем переменные
load_dotenv(override=True)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# Список админов (если один, тоже работает отличноо)
ADMIN_IDS = [int(id.strip()) for id in os.environ.get("ADMIN_IDS", "").split(",") if id.strip()]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Глобальные переменные
BOT_LINK = ""
user_button_messages = {} # Словарь для запоминания сообщений с кнопками у пользователей

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
    if message.from_user.id in ADMIN_IDS:
        await message.answer("👋 Привет, Админ! Бот готов к работе.")
    else:
        await send_instruction(message, state)

# Обработка входящих от пользователей
@dp.message(F.chat.type == "private", ~F.chat.id.in_(ADMIN_IDS), UserState.waiting_for_message)
async def handle_user_message(message: Message, state: FSMContext):
    # Невидимая ссылка для привязки ID
    invisible_link = f'<a href="tg://user?id={message.from_user.id}">&#8203;</a>'

    # 1. Отправляем сообщение подписчика админам
    caption_supported = message.content_type not in [
        'sticker', 'video_note', 'location', 'contact', 'poll', 'dice'
    ]

    for admin_id in ADMIN_IDS:
        if message.text:
            msg_text = (
                f"🏄‍♂️ У тебя новое анонимное сообщение!{invisible_link}\n\n"
                f"{message.html_text}\n\n"
                f"👉 <a href=\"{BOT_LINK}\">Ссылка на бота</a>\n"
                "↩️ Свайпни для ответа."
            )
            await bot.send_message(chat_id=admin_id, text=msg_text, parse_mode="HTML", disable_web_page_preview=True)
        elif caption_supported:
            caption = message.html_text if message.caption else ""
            new_caption = f"🏄‍♂️ У тебя новое анонимное сообщение!{invisible_link}\n\n"
            if caption:
                new_caption += f"{caption}\n\n"
            new_caption += f"👉 <a href=\"{BOT_LINK}\">Ссылка на бота</a>\n"
            new_caption += "↩️ Свайпни для ответа."

            await bot.copy_message(
                chat_id=admin_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                caption=new_caption,
                parse_mode="HTML"
            )
        else:
            await bot.copy_message(chat_id=admin_id, from_chat_id=message.chat.id, message_id=message.message_id)

        # Отправляем инфо об отправителе
        admin_builder = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{message.from_user.id}")
        ]])
        admin_info = (
            f"👤 От: {message.from_user.full_name} (@{message.from_user.username or 'нет юзернейма'}){invisible_link}\n"
            f"↩️ Нажми кнопку ниже для ответа."
        )
        await bot.send_message(chat_id=admin_id, text=admin_info, reply_markup=admin_builder, parse_mode="HTML")

    # 2. Удаляем старую кнопку у пользователя, если она есть
    old_msg_id = user_button_messages.get(message.from_user.id)
    if old_msg_id:
        try:
            await bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=old_msg_id, reply_markup=None)
        except Exception:
            pass

    # 3. Ответ пользователю
    user_builder = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✍️ Отправить ещё", callback_data="user_reply")
    ]])
    sent_msg = await message.answer("💬 Сообщение отправлено, ожидайте ответ!", reply_markup=user_builder)

    # Запоминаем ID сообщения с новой кнопкой
    user_button_messages[message.from_user.id] = sent_msg.message_id
    await state.clear()

# Обработчик кнопки "Отправить ещё"
@dp.callback_query(F.data == "user_reply")
async def user_reply_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserState.waiting_for_message)
    try:
        await callback.message.edit_text(
            text=callback.message.text + "\n\n✍️ Теперь напишите ваше новое сообщение:",
            reply_markup=None
        )
    except TelegramBadRequest:
        pass

    # Очищаем память о кнопке
    user_button_messages.pop(callback.from_user.id, None)
    await callback.answer()

# Обработка ответа "свайпом" от админа
@dp.message(F.chat.type == "private", F.chat.id.in_(ADMIN_IDS), F.reply_to_message)
async def admin_swipe_reply_handler(message: Message, state: FSMContext):
    user_id = None
    reply_msg = message.reply_to_message

    # Ищем невидимую ссылку
    entities = reply_msg.entities or reply_msg.caption_entities or []
    for ent in entities:
        if ent.type == 'text_link' and ent.url and ent.url.startswith("tg://user?id="):
            user_id = ent.url.split("=")[1]
            break

    # Ищем ID в тексте, если не нашли ссылку
    if not user_id and reply_msg.text:
        match = re.search(r"🆔 ID: (\d+)", reply_msg.text)
        if match:
            user_id = match.group(1)

    if user_id:
        user_id_int = int(user_id)

        # Скрываем старую кнопку у пользователя
        old_msg_id = user_button_messages.get(user_id_int)
        if old_msg_id:
            try:
                await bot.edit_message_reply_markup(chat_id=user_id_int, message_id=old_msg_id, reply_markup=None)
            except Exception:
                pass

        user_builder = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Ответить", callback_data="user_reply")
        ]])
        try:
            sent_reply = await bot.copy_message(
                chat_id=user_id_int,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=user_builder
            )
            user_button_messages[user_id_int] = sent_reply.message_id
            await message.answer("✅ Ответ успешно отправлен пользователю!")
        except Exception as e:
            await message.answer(f"❌ Ошибка при отправке: {e}")

        await state.clear()
    else:
        await message.answer("❌ Не удалось определить получателя. Пожалуйста, используйте кнопку «💬 Ответить».")

# Когда админ нажал на кнопку "Ответить"
@dp.callback_query(F.data.startswith("reply_"))
async def start_reply(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split("_")[1]

    raw_name = callback.message.text.split("\n")[0].replace("👤 От: ", "")
    user_name = raw_name.replace("\u200b", "").strip()

    await state.update_data(user_id=user_id, user_name=user_name)
    await state.set_state(AdminReply.waiting_for_reply)
    await callback.message.answer(f"✍️ Введите ответ для пользователя {user_name}:")
    await callback.answer()

# Когда админ отправил текст ответа (после нажатия кнопки)
@dp.message(AdminReply.waiting_for_reply)
async def send_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = int(data.get("user_id"))
    user_name = data.get("user_name")

    # Скрываем старую кнопку у пользователя
    old_msg_id = user_button_messages.get(user_id)
    if old_msg_id:
        try:
            await bot.edit_message_reply_markup(chat_id=user_id, message_id=old_msg_id, reply_markup=None)
        except Exception:
            pass

    user_builder = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Ответить", callback_data="user_reply")
    ]])

    try:
        sent_reply = await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=user_builder
        )
        user_button_messages[user_id] = sent_reply.message_id
        await message.answer(f"✅ Ответ успешно отправлен пользователю {user_name}!")
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}")

    await state.clear()

async def main():
    global BOT_LINK
    bot_info = await bot.get_me()
    BOT_LINK = f"https://t.me/{bot_info.username}?start=start"
    print(f"Бот @{bot_info.username} успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())