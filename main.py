import asyncio
import os
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
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

# Вспомогательная функция для удаления предыдущего уведомления у пользователя
async def delete_user_last_msg(bot: Bot, user_id: int):
    user_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    user_context = FSMContext(storage=dp.storage, key=user_key)

    user_data = await user_context.get_data()
    last_msg_id = user_data.get("last_sent_msg_id")

    if last_msg_id:
        try:
            await bot.delete_message(chat_id=user_id, message_id=last_msg_id)
        except Exception:
            pass

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
    # 0. Удаляем сообщение-подсказку "Теперь напишите ваше новое сообщение:", если оно было сохранено
    user_data = await state.get_data()
    prompt_msg_id = user_data.get("prompt_msg_id")
    if prompt_msg_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        except Exception:
            pass
        # Стираем ID подсказки из памяти, так как она уже удалена
        await state.update_data(prompt_msg_id=None)

    invisible_link = f'<a href="tg://user?id={message.from_user.id}">&#8203;</a>'

    # 1. Отправляем сообщение подписчика
    caption_supported = message.content_type not in [
        'sticker', 'video_note', 'location', 'contact', 'poll', 'dice'
    ]

    if message.text:
        msg_text = (
            f"🏄‍♂️ У тебя новое анонимное сообщение!{invisible_link}\n\n"
            f"{message.html_text}\n\n"
            "👉 https://t.me/anonim_the_best_bot?start=start\n"
            "↩️ Свайпни для ответа."
        )
        await bot.send_message(chat_id=ADMIN_ID, text=msg_text, parse_mode="HTML", disable_web_page_preview=True)
    elif caption_supported:
        caption = message.html_text if message.caption else ""
        new_caption = f"🏄‍♂️ У тебя новое анонимное сообщение!{invisible_link}\n\n"
        if caption:
            new_caption += f"{caption}\n\n"
        new_caption += "👉 https://t.me/anonim_the_best_bot?start=start\n"
        new_caption += "↩️ Свайпни для ответа."

        await bot.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=new_caption,
            parse_mode="HTML"
        )
    else:
        # Для стикеров и кружков отправляем само медиа как есть
        await bot.copy_message(chat_id=ADMIN_ID, from_chat_id=message.chat.id, message_id=message.message_id)

    # 2. Создаем кнопку "Ответить" и отправляем данные отправителя
    admin_builder = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{message.from_user.id}")
    ]])

    # Сформируем текст с ID пользователя по вашему шаблону
    admin_info = (
        f"👤 От: {message.from_user.full_name} (@{message.from_user.username or 'нет юзернейма'}){invisible_link}\n"
        f"🆔 ID: tg://openmessage?user_id={message.from_user.id}\n\n"
    )
    await bot.send_message(chat_id=ADMIN_ID, text=admin_info, reply_markup=admin_builder, parse_mode="HTML")

    # 3. Ответ пользователю
    user_builder = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✍️ Отправить ещё", callback_data="user_reply")
    ]])

    sent_msg = await message.answer("💬 Сообщение отправлено, ожидайте ответ!", reply_markup=user_builder)

    # Сохраняем ID отправленного уведомления, чтобы удалить его позже
    await state.update_data(last_sent_msg_id=sent_msg.message_id)

    # Сбрасываем только состояние (чтобы пользователь мог свободно нажимать кнопки),
    # но сохраняем его данные (для этого вместо clear() переключаем состояние в None)
    await state.set_state(None)

# Обработчик кнопки "Отправить ещё" / "Ответить"
@dp.callback_query(F.data == "user_reply")
async def user_reply_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserState.waiting_for_message)

    if callback.message.text and "Сообщение отправлено" in callback.message.text:
        try:
            await callback.message.delete()
        except Exception:
            pass
    else:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    prompt_msg = await callback.message.answer("✍️ Теперь напишите ваше новое сообщение:")

    # --- ЭТУ СТРОКУ НУЖНО ДОБАВИТЬ ---
    await state.update_data(prompt_msg_id=prompt_msg.message_id)
    # ---------------------------------
    await callback.answer()

# Обработка ответа "свайпом" от админа
@dp.message(F.chat.type == "private", F.chat.id == ADMIN_ID, F.reply_to_message)
async def admin_swipe_reply_handler(message: Message, state: FSMContext):
    user_id = None
    reply_msg = message.reply_to_message

    # 1. Пытаемся найти ID в скрытой ссылке (если админ свайпнул на само сообщение от пользователя)
    entities = reply_msg.entities or reply_msg.caption_entities or []
    for ent in entities:
        if ent.type == 'text_link' and ent.url and ent.url.startswith("tg://user?id="):
            user_id = ent.url.split("=")[1]
            break

    # 2. Если не нашли скрытую ссылку, ищем ID в тексте (распознает формат tg://openmessage?user_id=)
    if not user_id and reply_msg.text:
        match = re.search(r"🆔 ID: (?:tg://openmessage\?user_id=)?(\d+)", reply_msg.text)
        if match:
            user_id = match.group(1)

    # Если удалось найти получателя
    if user_id:
        user_id = int(user_id)
        await delete_user_last_msg(bot, user_id)

        user_builder = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Ответить", callback_data="user_reply")
        ]])
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=user_builder
            )
            await message.answer("✅ Ответ успешно отправлен пользователю!")
        except Exception as e:
            await message.answer(f"❌ Ошибка при отправке: {e}")

        await state.clear()
    else:
        # Если админ свайпнул на сообщение, к которому нельзя привязать ID (например на голый стикер)
        await message.answer("❌ Не удалось определить получателя. Пожалуйста, используйте кнопку «💬 Ответить» под вторым сообщением.")

# Когда админ нажал на кнопку "Ответить"
@dp.callback_query(F.data.startswith("reply_"))
async def start_reply(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split("_")[1]
    user_name = callback.message.text.split("\n")[0].replace("👤 От: ", "")

    await state.update_data(user_id=user_id, user_name=user_name)
    await state.set_state(AdminReply.waiting_for_reply)
    await callback.message.answer(f"✍️ Введите ответ для пользователя {user_name}:")
    await callback.answer()

# Когда админ отправил текст ответа (после нажатия кнопки)
@dp.message(AdminReply.waiting_for_reply)
async def send_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")
    user_name = data.get("user_name")

    if user_id:
        user_id = int(user_id)
        await delete_user_last_msg(bot, user_id)

    user_builder = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Ответить", callback_data="user_reply")
    ]])

    try:
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=user_builder
        )
        await message.answer(f"✅ Ответ успешно отправлен пользователю {user_name}!")
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}")

    await state.clear()

# --- ДОБАВЛЕННЫЕ ФОЛЛБЕК-ОБРАБОТЧИКИ (ЗАГЛУШКИ ПРИ ОТСУТСТВИИ НАЖАТИЯ КНОПКИ) ---

# Заглушка для Админа (если он написал сообщение без свайпа и без нажатия кнопки "Ответить")
@dp.message(F.chat.type == "private", F.chat.id == ADMIN_ID)
async def admin_no_state_handler(message: Message):
    await message.answer(
        "⚠️ Нажмите кнопку «💬 Ответить» под данными пользователя."
    )

# Заглушка для Пользователя (если он написал сообщение без нажатия кнопки "Ответить" / "Отправить ещё")
@dp.message(F.chat.type == "private", F.chat.id != ADMIN_ID)
async def user_no_state_handler(message: Message):
    await message.answer(
        "⚠️ Нажмите кнопку под последним сообщением, чтобы отправить анонимку."
    )

# -------------------------------------------------------------------------------

async def main():
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())