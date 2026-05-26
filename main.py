import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from dotenv import load_dotenv

# Загружаем переменные из файла .env (если он существует локально)
load_dotenv()

# Получаем данные из переменных окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# Проверяем, задан ли токен
if not BOT_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не найдена! Проверьте файл .env или настройки Railway.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработка команды /start
@dp.message(CommandStart())
async def start_cmd(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "👋 Привет, Админ! Я готов пересылать тебе вопросы от подписчиков.\n\n"
            "Чтобы ответить пользователю, делайте **Reply (Ответить)** на мое сообщение, которое начинается с 'ID: ...'"
        )
    else:
        await message.answer("👋 Привет! Напишите свой вопрос или отправьте медиа (фото/файл), и я передам его администратору.")

# Обработка ответов от АДМИНА пользователям
@dp.message(F.chat.id == ADMIN_ID, F.reply_to_message)
async def reply_to_user(message: Message):
    try:
        # Проверяем, что админ отвечает на сообщение с ID
        reply_text = message.reply_to_message.text
        if reply_text and reply_text.startswith("ID: "):
            # Извлекаем ID пользователя из первой строчки сообщения бота
            user_id = int(reply_text.split("\n")[0].split(": ")[1])

            # Копируем сообщение админа (текст, фото, голос и т.д.) и отправляем пользователю
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            await message.reply("✅ Ответ успешно отправлен пользователю!")
        else:
            await message.reply("⚠️ Пожалуйста, делайте Reply (Ответить) именно на то сообщение бота, где написано 'ID: ...'")
    except Exception as e:
        await message.reply(f"❌ Ошибка при отправке: {e}")

# Обработка входящих сообщений от ПОЛЬЗОВАТЕЛЕЙ
@dp.message(F.chat.type == "private", F.chat.id != ADMIN_ID)
async def handle_user_message(message: Message):
    try:
        # Пересылаем сообщение пользователя админу
        forwarded = await message.forward(chat_id=ADMIN_ID)

        # Отправляем техническое сообщение с ID для админа (на него нужно отвечать)
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"ID: {message.from_user.id}\nОт: @{message.from_user.username or 'Скрыто'}\nИмя: {message.from_user.full_name}",
            reply_to_message_id=forwarded.message_id
        )

        await message.reply("✅ Ваше сообщение отправлено администратору. Ожидайте ответа.")
    except Exception as e:
        await message.reply("⚠️ К сожалению, не удалось отправить сообщение. Попробуйте позже.")
        print(f"Ошибка при пересылке: {e}")

async def main():
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())