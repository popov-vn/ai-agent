# 7628129143:AAG1tbcssdQb6hwGDSrvvZyCwsSbUTyqsU8

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# run agent
from agent2 import run_neuro_gift
import os

from dotenv import load_dotenv

# создать файл .env

load_dotenv()
#print ("TELEGRAM_BOT_TOKEN")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Настройка логгирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Обработчик команды /start
async def start(update: Update, context):
    await update.message.reply_text("""
🎁 Привет! Я — бот сервиса “Знаю, что ты любишь”
Помогу подобрать идеальный подарок — персонально, с заботой и на основе того, что действительно важно для получателя.

Расскажи мне о человеке, которому хочешь сделать сюрприз, о его личности и увлечениях. С меня - все остальное.                                    
"""
)

# Обработчик текстовых сообщений (интеграция с вашим скриптом)
async def handle_message(update: Update, context):
    user_input = update.message.text
    # Вызываем функцию из вашего скрипта
    result = run_neuro_gift(user_input)
    await update.message.reply_text(f"{result}")

# Основная функция
def main():
    application = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()