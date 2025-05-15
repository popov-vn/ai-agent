from langgraph.graph import Graph, END, START
from typing import TypedDict, Annotated, List, Dict, Any, Union
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
import pandas as pd
import json
from openai import OpenAI
import time
import traceback
import ast
from dotenv import load_dotenv
import os

# создать файл .env

load_dotenv()
#print ("TELEGRAM_BOT_TOKEN")
TOKEN = os.getenv("OPEN_API_TOKEN")

# Настройка OpenRouter клиента
client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=TOKEN,
)

# Информация о человеке - задается один раз
PERSON_INFO2 = """
Мужчина 37 лет, проживающий в Москве.
Увлекается велосипедом, кино, музыкой.
Ходит в спортзал и любит путешествовать.
Работает программистом на Java.
"""

# Промпт для генерации списка подарков
GIFT_GENERATION_PROMPT = """
Ты эксперт по выбору подарков. На основе информации о человеке ниже, предложи 10 подходящих подарков.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

Создай список из 10 подарков в виде списка словарей на Python. Каждый словарь должен содержать следующие поля:
- "подарок": название подарка
- "описание": краткое описание подарка и почему он подходит этому человеку
- "стоимость": диапазон стоимости в рублях (например, "2,000 - 5,000")
- "релевантность": число от 1 до 10, показывающее насколько подарок соответствует интересам человека

Твой ответ должен быть в формате Python списка словарей, готового для присваивания переменной. 
Не добавляй никаких пояснений или вводного текста - только сам список словарей.
Пример:
[
    {{"подарок": "Название первого подарка", "описание": "Описание...", "стоимость": "цена", "релевантность": число}},
    {{"подарок": "Название второго подарка", "описание": "Описание...", "стоимость": "цена", "релевантность": число}},
    # и так далее...
]
"""

# Структура состояния для графа
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    agents_outputs: Dict[str, Any]
    final_selection: List[Dict[str, Any]]
    gifts_data: List[Dict[str, Any]]

# Функция для вызова OpenRouter API с повторными попытками и обработкой ошибок
def call_openrouter_api(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            print(f"Попытка запроса API #{attempt+1}...")
            completion = client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://github.com", 
                    "X-Title": "Gift Recommendation Agent", 
                },
                #model="qwen/qwen3-235b-a22b:free",
                model="deepseek/deepseek-r1",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Проверка на наличие ответа
            if completion and hasattr(completion, 'choices') and completion.choices and hasattr(completion.choices[0], 'message') and completion.choices[0].message and hasattr(completion.choices[0].message, 'content'):
                return completion.choices[0].message.content
            else:
                print(f"Получен пустой ответ от API, повторяем попытку...")
                time.sleep(2)  # Задержка перед повторной попыткой
        except Exception as e:
            print(f"Ошибка API: {str(e)}")
            print(traceback.format_exc())
            time.sleep(2)  # Задержка перед повторной попыткой
    
    # Если все попытки неудачны, возвращаем фиктивный ответ
    print("Все попытки запроса к API неудачны, возвращаем заглушку")
    return '{"error": "API request failed"}'

# Функция для создания списка подарков из LLM
def generate_gifts_list(person_info):
    prompt = GIFT_GENERATION_PROMPT.format(person_info=person_info)
    response = call_openrouter_api(prompt)
    
    # Обработка ответа и извлечение списка подарков
    try:
        # Очистка ответа от возможных лишних символов
        clean_response = response.strip()
        
        # Удаление markdown разметки, если она есть
        if "```python" in clean_response:
            clean_response = clean_response.split("```python")[1].split("```")[0].strip()
        elif "```" in clean_response:
            clean_response = clean_response.split("```")[1].split("```")[0].strip()
            
        # Преобразование текста в Python-объект
        gifts_list = ast.literal_eval(clean_response)
        
        # Проверка структуры и полей
        for gift in gifts_list:
            if not all(key in gift for key in ["подарок", "описание", "стоимость", "релевантность"]):
                raise ValueError("Неверная структура подарка: отсутствуют обязательные поля")
            if not isinstance(gift["релевантность"], int):
                gift["релевантность"] = int(float(gift["релевантность"]))
        
        return gifts_list
    except Exception as e:
        print(f"Ошибка при обработке списка подарков: {str(e)}")
        print(traceback.format_exc())
        print("Используем резервный список подарков")
        
        # Резервный список подарков
        return [
            {"подарок": "Умный велокомпьютер", "описание": "Устройство для отслеживания маршрутов, скорости и других показателей во время велопрогулок", "стоимость": "6,000 - 15,000", "релевантность": 9},
            {"подарок": "Годовая подписка на стриминговый сервис", "описание": "Доступ к фильмам и сериалам для любителя кино", "стоимость": "3,000 - 7,000", "релевантность": 8},
            {"подарок": "Беспроводные наушники с шумоподавлением", "описание": "Качественный звук для прослушивания музыки и просмотра фильмов", "стоимость": "8,000 - 25,000", "релевантность": 8},
            {"подарок": "Абонемент на массаж", "описание": "Отличное дополнение к занятиям в спортзале", "стоимость": "5,000 - 12,000", "релевантность": 7},
            {"подарок": "Портативная кофеварка для путешествий", "описание": "Практичный подарок для любителя путешествий", "стоимость": "3,000 - 7,000", "релевантность": 7},
            {"подарок": "Книга по новым технологиям Java или подписка на обучающую платформу", "описание": "Для профессионального развития", "стоимость": "2,000 - 10,000", "релевантность": 8},
            {"подарок": "Набор для приготовления крафтового пива", "описание": "Новое хобби, сочетающееся с любовью к велоспорту и активному образу жизни", "стоимость": "5,000 - 12,000", "релевантность": 6},
            {"подарок": "Фитнес-браслет или умные часы", "описание": "Отслеживание тренировок в зале и активности в путешествиях", "стоимость": "5,000 - 30,000", "релевантность": 9},
            {"подарок": "Подарочный сертификат в магазин велоаксессуаров", "описание": "Возможность выбрать нужные комплектующие или аксессуары для велосипеда", "стоимость": "3,000 - 15,000", "релевантность": 9},
            {"подарок": "Компактный внешний аккумулятор", "описание": "Пригодится в путешествиях и во время длительных велопрогулок", "стоимость": "2,000 - 6,000", "релевантность": 8},
        ]

# Функция для инициализации состояния с данными о подарках
def initialize_state(state):
    # Генерируем список подарков на основе информации о человеке
    person_info = state.get("person_info", "")
    gifts_data = generate_gifts_list(person_info)
    return {"messages": state.get("messages", []), "agents_outputs": state.get("agents_outputs", {}), "gifts_data": gifts_data}

# Функция для форматирования данных о подарках
def format_gifts_data(gifts):
    formatted_text = ""
    for i, gift in enumerate(gifts, 1):
        formatted_text += f"{i}. {gift['подарок']} - {gift['описание']} - Стоимость: {gift['стоимость']}₽ - Релевантность: {gift['релевантность']}/10\n"
    return formatted_text

# Определение промптов для каждого агента на основе информации о человеке
def get_praktik_bot_prompt(person_info, gifts_data):
    return f"""
Ты ПрактикБот, ИИ-агент, специализирующийся на анализе полезности подарков в повседневной жизни.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

ТВОЯ ЗАДАЧА:
Проанализировать список подарков и выбрать ТОЛЬКО ОДИН, который будет наиболее полезен в повседневной жизни этого человека.
Оцени, как часто подарок будет использоваться и насколько он сочетается с различными хобби и интересами.
Подарок должен приносить пользу в нескольких сферах жизни.

СПИСОК ПОДАРКОВ:
{{gifts}}

ФОРМАТ ОТВЕТА:
Строго в формате JSON:
{{{{
    "выбранный_подарок": "название подарка",
    "обоснование": "подробное объяснение выбора",
    "коэффициент_практической_ценности": число от 0 до 100
}}}}

Твой ответ должен содержать ТОЛЬКО JSON, без дополнительного текста.
"""

def get_fin_expert_prompt(person_info, gifts_data):
    return f"""
Ты ФинЭксперт, ИИ-агент, специализирующийся на анализе соотношения цена/качество подарков.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

ТВОЯ ЗАДАЧА:
Проанализировать список подарков и выбрать ТОЛЬКО ОДИН с наилучшим соотношением цена/качество.
Учти стоимость подарка, его релевантность и долговечность.
Рассчитай ROI-индекс, показывающий экономическую эффективность подарка.

СПИСОК ПОДАРКОВ:
{{gifts}}

ФОРМАТ ОТВЕТА:
Строго в формате JSON:
{{{{
    "выбранный_подарок": "название подарка",
    "обоснование": "подробное объяснение выбора с экономическими выкладками",
    "roi_индекс": число (коэффициент полезности на 1000₽)
}}}}

Твой ответ должен содержать ТОЛЬКО JSON, без дополнительного текста.
"""

def get_wow_factor_prompt(person_info, gifts_data):
    return f"""
Ты ВауФактор, ИИ-агент, специализирующийся на выборе подарков с высоким эмоциональным откликом.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

ТВОЯ ЗАДАЧА:
Проанализировать список подарков и выбрать ТОЛЬКО ОДИН, который вызовет наибольший восторг и эмоциональное впечатление.
Оцени, насколько подарок соответствует глубинным интересам и увлечениям человека.
Учти эффект новизны и технологичности подарка для программиста.

СПИСОК ПОДАРКОВ:
{{gifts}}

ФОРМАТ ОТВЕТА:
Строго в формате JSON:
{{{{
    "выбранный_подарок": "название подарка",
    "обоснование": "подробное объяснение эмоционального воздействия подарка",
    "степень_восторга_процент": число от 0 до 100
}}}}

Твой ответ должен содержать ТОЛЬКО JSON, без дополнительного текста.
"""

def get_universal_guru_prompt(person_info, gifts_data):
    return f"""
Ты УниверсалГуру, ИИ-агент, специализирующийся на поиске максимально универсальных подарков.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

ТВОЯ ЗАДАЧА:
Проанализировать список подарков и выбрать ТОЛЬКО ОДИН, который может применяться в максимальном количестве повседневных ситуаций.
Подсчитай процент сценариев использования для каждого подарка.
Учти разнообразие контекстов применения.

СПИСОК ПОДАРКОВ:
{{gifts}}

ФОРМАТ ОТВЕТА:
Строго в формате JSON:
{{{{
    "выбранный_подарок": "название подарка",
    "обоснование": "подробное объяснение универсальности подарка",
    "процент_сценариев_использования": число от 0 до 100
}}}}

Твой ответ должен содержать ТОЛЬКО JSON, без дополнительного текста.
"""

def get_surprise_master_prompt(person_info, gifts_data):
    return f"""
Ты СюрпризМастер, ИИ-агент, специализирующийся на нестандартных и неожиданных подарках.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

ТВОЯ ЗАДАЧА:
Проанализировать список подарков и выбрать ТОЛЬКО ОДИН, который будет наиболее неожиданным и запоминающимся.
Оцени, насколько подарок может открыть новые хобби или создать необычный опыт.
Учти социальные аспекты использования подарка.

СПИСОК ПОДАРКОВ:
{{gifts}}

ФОРМАТ ОТВЕТА:
Строго в формате JSON:
{{{{
    "выбранный_подарок": "название подарка",
    "обоснование": "подробное объяснение неожиданности и запоминаемости подарка",
    "шанс_запомниться_процент": число от 0 до 100
}}}}

Твой ответ должен содержать ТОЛЬКО JSON, без дополнительного текста.
"""

def get_prof_rost_prompt(person_info, gifts_data):
    return f"""
Ты ПрофРост, ИИ-агент, специализирующийся на подарках для профессионального развития.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

ТВОЯ ЗАДАЧА:
Проанализировать список подарков и выбрать ТОЛЬКО ОДИН, который лучше всего поможет в профессиональном развитии.
Оцени долгосрочный потенциал подарка для карьерного роста.
Рассчитай прогнозируемое увеличение профессиональной ценности.

СПИСОК ПОДАРКОВ:
{{gifts}}

ФОРМАТ ОТВЕТА:
Строго в формате JSON:
{{{{
    "выбранный_подарок": "название подарка",
    "обоснование": "подробное объяснение пользы для профессионального развития",
    "прогноз_роста_ценности_процент": число от 0 до 100
}}}}

Твой ответ должен содержать ТОЛЬКО JSON, без дополнительного текста.
"""

# Функции для агентов с использованием OpenRouter
def run_agent(agent_name, prompt_template, state):
    try:
        gifts_data = state.get("gifts_data", [])
        formatted_gifts = format_gifts_data(gifts_data)
        prompt = prompt_template.format(gifts=formatted_gifts)
        
        print(f"Запуск агента: {agent_name}...")
        response = call_openrouter_api(prompt)
        print(f"Получен ответ от {agent_name}")
        
        # Проверяем, не является ли ответ ошибкой API
        if response and '{"error":' in response:
            print(f"Ошибка API для {agent_name}, используем стандартный ответ")
            default_response = create_default_response(agent_name)
            agents_outputs = state.get("agents_outputs", {})
            agents_outputs[agent_name] = default_response
            return {"messages": state.get("messages", []) + [HumanMessage(content=prompt), AIMessage(content="Ошибка API")], 
                    "agents_outputs": agents_outputs,
                    "gifts_data": gifts_data}
        
        try:
            # Извлечение JSON из ответа
            json_response = json.loads(response)
            # Сохраняем результат конкретного агента
            agents_outputs = state.get("agents_outputs", {})
            agents_outputs[agent_name] = json_response
            return {"messages": state.get("messages", []) + [HumanMessage(content=prompt), AIMessage(content=response)], 
                    "agents_outputs": agents_outputs,
                    "gifts_data": gifts_data}
        except json.JSONDecodeError:
            # Попытка очистить текст от возможных префиксов/суффиксов
            cleaned_response = response
            if "```json" in response:
                cleaned_response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                cleaned_response = response.split("```")[1].split("```")[0].strip()
            
            try:
                json_response = json.loads(cleaned_response)
                agents_outputs = state.get("agents_outputs", {})
                agents_outputs[agent_name] = json_response
                return {"messages": state.get("messages", []) + [HumanMessage(content=prompt), AIMessage(content=response)], 
                        "agents_outputs": agents_outputs,
                        "gifts_data": gifts_data}
            except json.JSONDecodeError:
                # Если все еще не JSON, создаем примерный ответ
                print(f"Ошибка при парсинге JSON от {agent_name}, создаем стандартный ответ")
                default_response = create_default_response(agent_name)
                agents_outputs = state.get("agents_outputs", {})
                agents_outputs[agent_name] = default_response
                return {"messages": state.get("messages", []) + [HumanMessage(content=prompt), AIMessage(content=response)], 
                        "agents_outputs": agents_outputs,
                        "gifts_data": gifts_data}
    except Exception as e:
        # Обработка непредвиденных ошибок
        print(f"Неожиданная ошибка для агента {agent_name}: {str(e)}")
        print(traceback.format_exc())
        default_response = create_default_response(agent_name)
        agents_outputs = state.get("agents_outputs", {})
        agents_outputs[agent_name] = default_response
        return {"messages": state.get("messages", []), 
                "agents_outputs": agents_outputs,
                "gifts_data": state.get("gifts_data", [])}

# Функции для запуска агентов
def run_praktik_bot(state):
    prompt_template = get_praktik_bot_prompt(state.get("person_info", ""),  state.get("gifts_data", []))
    return run_agent("praktik_bot", prompt_template, state)

def run_fin_expert(state):
    prompt_template = get_fin_expert_prompt(state.get("person_info", ""),  state.get("gifts_data", []))
    return run_agent("fin_expert", prompt_template, state)

def run_wow_factor(state):
    prompt_template = get_wow_factor_prompt(state.get("person_info", ""),  state.get("gifts_data", []))
    return run_agent("wow_factor", prompt_template, state)

def run_universal_guru(state):
    prompt_template = get_universal_guru_prompt(state.get("person_info", ""),  state.get("gifts_data", []))
    return run_agent("universal_guru", prompt_template, state)

def run_surprise_master(state):
    prompt_template = get_surprise_master_prompt(state.get("person_info", ""),  state.get("gifts_data", []))
    return run_agent("surprise_master", prompt_template, state)

def run_prof_rost(state):
    prompt_template = get_prof_rost_prompt(state.get("person_info", ""),  state.get("gifts_data", []))
    return run_agent("prof_rost", prompt_template, state)

# Функция для создания стандартного ответа в случае ошибки
def create_default_response(agent_name):
    if agent_name == "praktik_bot":
        return {
            "выбранный_подарок": "Фитнес-браслет или умные часы",
            "обоснование": "Фитнес-браслет будет полезен в нескольких сферах жизни: для отслеживания тренировок в спортзале, для измерения активности во время велопрогулок и для использования в повседневной жизни.",
            "коэффициент_практической_ценности": 85
        }
    elif agent_name == "fin_expert":
        return {
            "выбранный_подарок": "Компактный внешний аккумулятор",
            "обоснование": "При низкой стоимости имеет высокую релевантность и долговечность. Аккумулятор пригодится как в путешествиях, так и при длительных велопрогулках.",
            "roi_индекс": 3.5
        }
    elif agent_name == "wow_factor":
        return {
            "выбранный_подарок": "Умный велокомпьютер",
            "обоснование": "Этот подарок вызовет наибольшее эмоциональное впечатление, так как сочетает в себе технологичность (что важно для программиста) и прямое соответствие основному хобби (велосипед).",
            "степень_восторга_процент": 90
        }
    elif agent_name == "universal_guru":
        return {
            "выбранный_подарок": "Беспроводные наушники с шумоподавлением",
            "обоснование": "Этот подарок универсален и может использоваться в большинстве повседневных ситуаций: во время прослушивания музыки, просмотра фильмов, в спортзале, на велопрогулках и в путешествиях.",
            "процент_сценариев_использования": 75
        }
    elif agent_name == "surprise_master":
        return {
            "выбранный_подарок": "Набор для приготовления крафтового пива",
            "обоснование": "Этот подарок будет наиболее неожиданным и запоминающимся, так как открывает новое хобби, которое можно совмещать с просмотром кино и встречами с друзьями.",
            "шанс_запомниться_процент": 85
        }
    elif agent_name == "prof_rost":
        return {
            "выбранный_подарок": "Книга по новым технологиям Java или подписка на обучающую платформу",
            "обоснование": "Этот подарок прямо соответствует профессиональной деятельности человека и поможет ему развиваться как Java-программисту.",
            "прогноз_роста_ценности_процент": 75
        }
    else:
        return {
            "выбранный_подарок": "Фитнес-браслет или умные часы",
            "обоснование": "Универсальный подарок, соответствующий интересам человека",
            "оценка": 80
        }

def select_final_gifts(state):
    try:
        # Получаем результаты всех агентов
        agents_outputs = state.get("agents_outputs", {})
        gifts_data = state.get("gifts_data", [])
        
        # Если не получены ответы от всех агентов, используем резервный метод
        if len(agents_outputs) < 6:
            print(f"Внимание: получены ответы только от {len(agents_outputs)} агентов из 6")
        
        # Создаем список с оценками для каждого подарка
        gift_scores = {}
        
        # Нормализуем оценки от каждого агента
        for agent, output in agents_outputs.items():
            if not output:
                print(f"Пропуск агента {agent} - пустой ответ")
                continue
                
            gift_name = output.get("выбранный_подарок")
            if not gift_name:
                print(f"Пропуск агента {agent} - отсутствует выбранный подарок")
                continue
            
            # Получаем оценку в зависимости от агента
            if agent == "praktik_bot":
                score = output.get("коэффициент_практической_ценности", 0)
            elif agent == "fin_expert":
                score = output.get("roi_индекс", 0) * 20  # Нормализуем к шкале 0-100
            elif agent == "wow_factor":
                score = output.get("степень_восторга_процент", 0)
            elif agent == "universal_guru":
                score = output.get("процент_сценариев_использования", 0)
            elif agent == "surprise_master":
                score = output.get("шанс_запомниться_процент", 0)
            elif agent == "prof_rost":
                score = output.get("прогноз_роста_ценности_процент", 0)
            else:
                score = 0
                
            if gift_name not in gift_scores:
                gift_scores[gift_name] = []
            gift_scores[gift_name].append((agent, score))
        
        # Если ни один подарок не набрал голосов, используем предустановленные данные
        if not gift_scores:
            print("Ни один подарок не был выбран, используем предустановленные результаты")
            final_selection = [
                {
                    "место": 1,
                    "подарок": "Фитнес-браслет или умные часы",
                    "описание": next((g["описание"] for g in gifts_data if g["подарок"] == "Фитнес-браслет или умные часы"), "Отслеживание тренировок в зале и активности в путешествиях"),
                    "стоимость": next((g["стоимость"] for g in gifts_data if g["подарок"] == "Фитнес-браслет или умные часы"), "5,000 - 30,000"),
                    "релевантность": next((g["релевантность"] for g in gifts_data if g["подарок"] == "Фитнес-браслет или умные часы"), 9),
                    "средний_балл": 85.0,
                    "выбран_агентами": ["praktik_bot"]
                },
                {
                    "место": 2,
                    "подарок": "Умный велокомпьютер",
                    "описание": next((g["описание"] for g in gifts_data if g["подарок"] == "Умный велокомпьютер"), "Устройство для отслеживания маршрутов, скорости и других показателей во время велопрогулок"),
                    "стоимость": next((g["стоимость"] for g in gifts_data if g["подарок"] == "Умный велокомпьютер"), "6,000 - 15,000"),
                    "релевантность": next((g["релевантность"] for g in gifts_data if g["подарок"] == "Умный велокомпьютер"), 9),
                    "средний_балл": 90.0,
                    "выбран_агентами": ["wow_factor"]
                }
            ]
            return {"final_selection": final_selection, "gifts_data": gifts_data}
        
        # Рассчитываем средний балл для каждого подарка
        average_scores = {}
        for gift, scores in gift_scores.items():
            total_score = sum(score for _, score in scores)
            avg_score = total_score / len(scores)
            average_scores[gift] = {
                "средний_балл": avg_score,
                "голоса_агентов": [agent for agent, _ in scores],
                "количество_голосов": len(scores)
            }
			###########################################################
			# Сортируем подарки по среднему баллу и количеству голосов
        sorted_gifts = sorted(
            average_scores.items(), 
            key=lambda x: (x[1]["количество_голосов"], x[1]["средний_балл"]), 
            reverse=True
        )
        
        # Выбираем 2 лучших подарка
        final_selection = []
        for i, (gift, metrics) in enumerate(sorted_gifts[:2]):
            # Находим оригинальные данные о подарке
            gift_details = next((g for g in gifts_data if g["подарок"] == gift), None)
            if gift_details:
                final_selection.append({
                    "место": i + 1,
                    "подарок": gift,
                    "описание": gift_details["описание"],
                    "стоимость": gift_details["стоимость"],
                    "релевантность": gift_details["релевантность"],
                    "средний_балл": metrics["средний_балл"],
                    "выбран_агентами": metrics["голоса_агентов"]
                })
        
        # Если недостаточно подарков, добавляем дополнительные
        if len(final_selection) < 2:
            # Список подарков, которых еще нет в final_selection
            selected_gifts = [item["подарок"] for item in final_selection]
            
            # Берем первые подарки из списка, которых еще нет в final_selection
            for gift in gifts_data:
                if gift["подарок"] not in selected_gifts and len(final_selection) < 2:
                    final_selection.append({
                        "место": len(final_selection) + 1,
                        "подарок": gift["подарок"],
                        "описание": gift["описание"],
                        "стоимость": gift["стоимость"],
                        "релевантность": gift["релевантность"],
                        "средний_балл": 80.0,
                        "выбран_агентами": ["default"]
                    })
        
        return {"final_selection": final_selection, "gifts_data": gifts_data}
    except Exception as e:
        # В случае любой непредвиденной ошибки возвращаем стандартные подарки
        print(f"Ошибка в select_final_gifts: {str(e)}")
        print(traceback.format_exc())
        final_selection = [
            {
                "место": 1,
                "подарок": "Фитнес-браслет или умные часы",
                "описание": next((g["описание"] for g in gifts_data if g["подарок"] == "Фитнес-браслет или умные часы"), "Отслеживание тренировок в зале и активности в путешествиях"),
                "стоимость": next((g["стоимость"] for g in gifts_data if g["подарок"] == "Фитнес-браслет или умные часы"), "5,000 - 30,000"),
                "релевантность": next((g["релевантность"] for g in gifts_data if g["подарок"] == "Фитнес-браслет или умные часы"), 9),
                "средний_балл": 85.0,
                "выбран_агентами": ["praktik_bot"]
            },
            {
                "место": 2,
                "подарок": "Умный велокомпьютер",
                "описание": next((g["описание"] for g in gifts_data if g["подарок"] == "Умный велокомпьютер"), "Устройство для отслеживания маршрутов, скорости и других показателей во время велопрогулок"),
                "стоимость": next((g["стоимость"] for g in gifts_data if g["подарок"] == "Умный велокомпьютер"), "6,000 - 15,000"),
                "релевантность": next((g["релевантность"] for g in gifts_data if g["подарок"] == "Умный велокомпьютер"), 9),
                "средний_балл": 90.0,
                "выбран_агентами": ["wow_factor"]
            }
        ]
        return {"final_selection": final_selection, "gifts_data": gifts_data}

# Определение графа
def define_graph():
    workflow = Graph()
    
    # Добавляем узлы для каждого агента
    workflow.add_node("initialize", initialize_state)
    workflow.add_node("praktik_bot", run_praktik_bot)
    workflow.add_node("fin_expert", run_fin_expert)
    workflow.add_node("wow_factor", run_wow_factor)
    workflow.add_node("universal_guru", run_universal_guru)
    workflow.add_node("surprise_master", run_surprise_master)
    workflow.add_node("prof_rost", run_prof_rost)
    workflow.add_node("select_final_gifts", select_final_gifts)
    
    # Задаем линейную последовательность исполнения
    workflow.add_edge(START, "initialize")
    workflow.add_edge("initialize", "praktik_bot")
    workflow.add_edge("praktik_bot", "fin_expert")
    workflow.add_edge("fin_expert", "wow_factor")
    workflow.add_edge("wow_factor", "universal_guru")
    workflow.add_edge("universal_guru", "surprise_master")
    workflow.add_edge("surprise_master", "prof_rost")
    workflow.add_edge("prof_rost", "select_final_gifts")
    workflow.add_edge("select_final_gifts", END)
    
    # Компилируем граф
    return workflow.compile()

# Запуск графа и вывод результатов
def run_gift_selection(person_info):
    try:
        graph = define_graph()
        
        # Начальное состояние
        initial_state = {"messages": [], "agents_outputs": {}, "person_info": person_info}
        
        # Запускаем граф
        results = graph.invoke(initial_state)
        
        # Проверяем, есть ли результаты
        if "final_selection" in results:
            return results["final_selection"], results.get("gifts_data", [])
        else:
            # Если результатов нет, возвращаем резервный вариант
            print("Результаты отсутствуют, возвращаем резервные варианты")
            return [
                {
                    "место": 1,
                    "подарок": "Фитнес-браслет или умные часы",
                    "описание": "Отслеживание тренировок в зале и активности в путешествиях",
                    "стоимость": "5,000 - 30,000",
                    "релевантность": 9,
                    "средний_балл": 85.0,
                    "выбран_агентами": ["резервный_вариант"]
                },
                {
                    "место": 2,
                    "подарок": "Умный велокомпьютер",
                    "описание": "Устройство для отслеживания маршрутов, скорости и других показателей во время велопрогулок",
                    "стоимость": "6,000 - 15,000",
                    "релевантность": 9,
                    "средний_балл": 90.0,
                    "выбран_агентами": ["резервный_вариант"]
                }
            ], []
    except Exception as e:
        # В случае любой непредвиденной ошибки возвращаем стандартные подарки
        print(f"Ошибка в run_gift_selection: {str(e)}")
        print(traceback.format_exc())
        return [
            {
                "место": 1,
                "подарок": "Фитнес-браслет или умные часы",
                "описание": "Отслеживание тренировок в зале и активности в путешествиях",
                "стоимость": "5,000 - 30,000",
                "релевантность": 9,
                "средний_балл": 85.0,
                "выбран_агентами": ["резервный_вариант"]
            },
            {
                "место": 2,
                "подарок": "Умный велокомпьютер",
                "описание": "Устройство для отслеживания маршрутов, скорости и других показателей во время велопрогулок",
                "стоимость": "6,000 - 15,000",
                "релевантность": 9,
                "средний_балл": 90.0,
                "выбран_агентами": ["резервный_вариант"]
            }
        ], []

# Функция для красивого вывода результатов
def print_results(final_selection, gifts_data):
    print("\n=== СГЕНЕРИРОВАННЫЙ СПИСОК ПОДАРКОВ ===\n")
    for i, gift in enumerate(gifts_data, 1):
        print(f"{i}. {gift['подарок']} - Релевантность: {gift['релевантность']}/10")
    
    print("\n=== РЕЗУЛЬТАТЫ ВЫБОРА ПОДАРКОВ ===\n")
    for gift in final_selection:
        print(f"🎁 МЕСТО #{gift['место']}: {gift['подарок']}")
        print(f"   Описание: {gift['описание']}")
        print(f"   Стоимость: {gift['стоимость']}₽")
        print(f"   Релевантность: {gift['релевантность']}/10")
        try:
            print(f"   Средний балл от ИИ-агентов: {gift['средний_балл']:.2f}")
            print(f"   Выбран агентами: {', '.join(gift['выбран_агентами'])}")
        except:
            # В случае ошибки в структуре данных
            print(f"   Выбран несколькими агентами")
        print("")

def run_neuro_gift(user_text):
    person_info = user_text
   # Запускаем систему только при прямом запуске скрипта, не при импорте
    print("Запуск системы выбора подарков с использованием OpenRouter API...")
    print(f"Информация о человеке для подбора подарка:\n{person_info}")
    
    try:
        # Сначала генерируем список подарков
        print("Генерация списка подарков на основе информации о человеке...")
        
        # Запускаем систему выбора подарков
        final_selection, gifts_data = run_gift_selection(person_info)
        print_results(final_selection, gifts_data)
        return final_selection
    except Exception as e:
        print(f"Критическая ошибка: {str(e)}")
        print(traceback.format_exc())
        print("\nИспользуем резервные результаты:")
        default_selection = [
            {
                "место": 1,
                "подарок": "Фитнес-браслет или умные часы",
                "описание": "Отслеживание тренировок в зале и активности в путешествиях",
                "стоимость": "5,000 - 30,000",
                "релевантность": 9,
                "средний_балл": 85.0,
                "выбран_агентами": ["резервная_система"]
            },
            {
                "место": 2,
                "подарок": "Умный велокомпьютер",
                "описание": "Устройство для отслеживания маршрутов, скорости и других показателей во время велопрогулок",
                "стоимость": "6,000 - 15,000",
                "релевантность": 9,
                "средний_балл": 90.0,
                "выбран_агентами": ["резервная_система"]
            }
        ]
        default_gifts = [
            {"подарок": "Фитнес-браслет или умные часы", "описание": "Отслеживание тренировок в зале и активности в путешествиях", "стоимость": "5,000 - 30,000", "релевантность": 9},
            {"подарок": "Умный велокомпьютер", "описание": "Устройство для отслеживания маршрутов, скорости и других показателей во время велопрогулок", "стоимость": "6,000 - 15,000", "релевантность": 9},
        ]
        print_results(default_selection, default_gifts)
        return default_selection
        
if __name__ == "__main__":
    person_info = """
Мужчина 37 лет, проживающий в Москве.
Увлекается велосипедом, кино, музыкой.
Ходит в спортзал и любит путешествовать.
Работает программистом на Java.
"""
    run_neuro_gift(person_info)