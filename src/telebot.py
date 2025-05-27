from typing import TypedDict, Annotated, List, Dict, Any, Union
from io import BytesIO
import logging
from telegram import PhotoSize, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from telegram.constants import ParseMode
import urllib.parse
import traceback
from agent_context import AgentContext

# run agent
from agent5 import run_neuro_gift
import os

from dotenv import load_dotenv

# создать файл .env

load_dotenv()
#print ("TELEGRAM_BOT_TOKEN")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


if None != TOKEN:
    print("Telegram token provided")
else:
    print("Telegram Token missed")


# Настройка логгирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Обработчик команды /start
async def start(update: Update, context):
    await update.message.reply_text("""
🎁 Привет! Я — бот сервиса “Знаю, что ты любишь”
Помогу подобрать идеальный подарок — персонально, с заботой и на основе того, что действительно важно для получателя.

Расскажи мне о человеке, которому хочешь сделать сюрприз, о его личности и увлечениях. С меня - все остальное.                                    
""")

    
# Красивый результат
# Функция для красивого вывода результатов
def string_results(final_selection):
    
    print(final_selection)
    
    result = ""
    for gift in final_selection:
        result += f"🎁 МЕСТО #{gift['место']}: {gift['подарок']}\n"
        result += f"   Описание: {gift['описание']}\n"
        result += f"   Стоимость: {gift['стоимость']}₽\n"
        result += f"   Релевантность: {gift['релевантность']}/10\n"
        try:
            result += f"   Средний балл от ИИ-агентов: {gift['средний_балл']:.2f}\n"
            result += f"   Выбран агентами: {', '.join(gift['выбран_агентами'])}\n"
        except:
            # В случае ошибки в структуре данных
            result += "   Выбран несколькими агентами\n"
            
        if 'query' in gift:
            query = urllib.parse.quote_plus(gift['query'])
            
            result += get_links(query)
        else:
            print(f"Подарок: {gift}")
        
        result += "\n"
    
    return result

def get_links(query):
    result = ""
    markets = [
        {
            "name" : "OZON",
            "link" : "https://www.ozon.ru/search/?text="
        },
        {
            "name" : "Яндекс Market",
            "link" : "https://market.yandex.ru/search?text="
        },
    ]
    
    for market in markets:
        result += f"   Ссылка на <a href=\"{market['link'] + query}\">{market['name']}</a>\n"
        
        
    print(f"Links: {result}")    
    return result

def find_max_file(files: List[PhotoSize]) -> PhotoSize:
    if not files:
        return None
    
    max_file = files[0]  # берём первый файл как начальный максимум
    for file in files[1:]:
        if file.file_size > max_file.file_size:
            max_file = file
    return max_file

def get_max_files_by_id(files: List[PhotoSize]) -> List[PhotoSize]:
    max_files = {}
    
    for file in files:
        file_id = file.file_id
        size = file.file_size
        
        if file_id not in max_files or size > max_files[file_id]['size']:
            max_files[file_id] = file
    
    return list(max_files.values())

async def try_parse_photos(update: Update, context: CallbackContext) -> List[bytes]:
    try :
        result_list = []
        
        if update.message.photo != None:
            print(f"Parse photo: {len(update.message.photo)}")
            
            max_photos = [find_max_file(update.message.photo)]
            
            for photo in max_photos:
                
                print(f"Photo: {photo.file_id} {photo.file_size}")
                
                file = await context.bot.get_file(photo.file_id)
                print(f"File: {file} {type(file)}")
                f =  BytesIO(await file.download_as_bytearray())
                fbytes = f.getvalue()
                
                result_list.append(fbytes)
            
            return result_list
                
    except Exception:
        print(traceback.format_exc())
        print("Failed parse photo")
        return []
    
def print_files_info(files : List[bytes]) :
    for file in files:
        print(f"File: {len(file)}")
        
# Обработчик текстовых сообщений (интеграция с вашим скриптом)
async def handle_message(update: Update, context: CallbackContext):
    # ответ пользователю
    await update.message.reply_text(f"Вызов принят, скоро вернусь с ответом")

    try:
        user_input = update.message.text
        print(update.message.photo.count)
        # Вызываем функцию из вашего скрипта
        
        files = await try_parse_photos(update, context)
        print_files_info(files)
        
        context = AgentContext()
        context.person_info = user_input
        context.photos = files
        
        await call_agent(context, update)
        
    except Exception:
        print(traceback.format_exc())
        await update.message.reply_text(f"Что-то пошло не так... повторите запрос")

async def call_agent(context: AgentContext, update: Update):
    #result = run_neuro_gift(context.person_info)
    #str_results = string_results(result)
    
    str_results = "Test"
    await update.message.reply_html(f"{str_results}")

# Основная функция
def main():
    application = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()