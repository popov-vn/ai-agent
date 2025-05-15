from langgraph.graph import Graph, END, START
from typing import TypedDict, Annotated, List, Dict, Any, Union
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
import pandas as pd
import json
from openai import OpenAI

# Настройка OpenRouter клиента
client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key="",
)

# Определение списка подарков в виде словаря
gifts_data = [
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

# Определение prompts для каждого агента
praktik_bot_prompt = """
Ты ПрактикБот, ИИ-агент, специализирующийся на анализе полезности подарков в повседневной жизни.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
Мужчина 37 лет, проживающий в Москве.
Увлекается велосипедом, кино, музыкой.
Ходит в спортзал и любит путешествовать.
Работает программистом на Java.

ТВОЯ ЗАДАЧА:
Проанализировать список подарков и выбрать ТОЛЬКО ОДИН, который будет наиболее полезен в повседневной жизни этого человека.
Оцени, как часто подарок будет использоваться и насколько он сочетается с различными хобби и интересами.
Подарок должен приносить пользу в нескольких сферах жизни.

СПИСОК ПОДАРКОВ:
{gifts}

ФОРМАТ ОТВЕТА:
Строго в формате JSON:
{{
    "выбранный_подарок": "название подарка",
    "обоснование": "подробное объяснение выбора",
    "коэффициент_практической_ценности": число от 0 до 100
}}

Твой ответ должен содержать ТОЛЬКО JSON, без дополнительного текста.
"""

fin_expert_prompt = """
Ты ФинЭксперт, ИИ-агент, специализирующийся на анализе соотношения цена/качество подарков.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
Мужчина 37 лет, проживающий в Москве.
Увлекается велосипедом, кино, музыкой.
Ходит в спортзал и любит путешествовать.
Работает программистом на Java.

ТВОЯ ЗАДАЧА:
Проанализировать список подарков и выбрать ТОЛЬКО ОДИН с наилучшим соотношением цена/качество.
Учти стоимость подарка, его релевантность и долговечность.
Рассчитай ROI-индекс, показывающий экономическую эффективность подарка.

СПИСОК ПОДАРКОВ:
{gifts}

ФОРМАТ ОТВЕТА:
Строго в формате JSON:
{{
    "выбранный_подарок": "название подарка",
    "обоснование": "подробное объяснение выбора с экономическими выкладками",
    "roi_индекс": число (коэффициент полезности на 1000₽)
}}

Твой ответ должен содержать ТОЛЬКО JSON, без дополнительного текста.
"""

wow_factor_prompt = """
Ты ВауФактор, ИИ-агент, специализирующийся на выборе подарков с высоким эмоциональным откликом.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
Мужчина 37 лет, проживающий в Москве.
Увлекается велосипедом, кино, музыкой.
Ходит в спортзал и любит путешествовать.
Работает программистом на Java.

ТВОЯ ЗАДАЧА:
Проанализировать список подарков и выбрать ТОЛЬКО ОДИН, который вызовет наибольший восторг и эмоциональное впечатление.
Оцени, насколько подарок соответствует глубинным интересам и увлечениям человека.
Учти эффект новизны и технологичности подарка для программиста.

СПИСОК ПОДАРКОВ:
{gifts}

ФОРМАТ ОТВЕТА:
Строго в формате JSON:
{{
    "выбранный_подарок": "название подарка",
    "обоснование": "подробное объяснение эмоционального воздействия подарка",
    "степень_восторга_процент": число от 0 до 100
}}

Твой ответ должен содержать ТОЛЬКО JSON, без дополнительного текста.
"""

universal_guru_prompt = """
Ты УниверсалГуру, ИИ-агент, специализирующийся на поиске максимально универсальных подарков.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
Мужчина 37 лет, проживающий в Москве.
Увлекается велосипедом, кино, музыкой.
Ходит в спортзал и любит путешествовать.
Работает программистом на Java.

ТВОЯ ЗАДАЧА:
Проанализировать список подарков и выбрать ТОЛЬКО ОДИН, который может применяться в максимальном количестве повседневных ситуаций.
Подсчитай процент сценариев использования для каждого подарка.
Учти разнообразие контекстов применения.

СПИСОК ПОДАРКОВ:
{gifts}

ФОРМАТ ОТВЕТА:
Строго в формате JSON:
{{
    "выбранный_подарок": "название подарка",
    "обоснование": "подробное объяснение универсальности подарка",
    "процент_сценариев_использования": число от 0 до 100
}}

Твой ответ должен содержать ТОЛЬКО JSON, без дополнительного текста.
"""

surprise_master_prompt = """
Ты СюрпризМастер, ИИ-агент, специализирующийся на нестандартных и неожиданных подарках.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
Мужчина 37 лет, проживающий в Москве.
Увлекается велосипедом, кино, музыкой.
Ходит в спортзал и любит путешествовать.
Работает программистом на Java.

ТВОЯ ЗАДАЧА:
Проанализировать список подарков и выбрать ТОЛЬКО ОДИН, который будет наиболее неожиданным и запоминающимся.
Оцени, насколько подарок может открыть новые хобби или создать необычный опыт.
Учти социальные аспекты использования подарка.

СПИСОК ПОДАРКОВ:
{gifts}

ФОРМАТ ОТВЕТА:
Строго в формате JSON:
{{
    "выбранный_подарок": "название подарка",
    "обоснование": "подробное объяснение неожиданности и запоминаемости подарка",
    "шанс_запомниться_процент": число от 0 до 100
}}

Твой ответ должен содержать ТОЛЬКО JSON, без дополнительного текста.
"""

prof_rost_prompt = """
Ты ПрофРост, ИИ-агент, специализирующийся на подарках для профессионального развития.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
Мужчина 37 лет, проживающий в Москве.
Увлекается велосипедом, кино, музыкой.
Ходит в спортзал и любит путешествовать.
Работает программистом на Java.

ТВОЯ ЗАДАЧА:
Проанализировать список подарков и выбрать ТОЛЬКО ОДИН, который лучше всего поможет в профессиональном развитии.
Оцени долгосрочный потенциал подарка для карьерного роста.
Рассчитай прогнозируемое увеличение профессиональной ценности.

СПИСОК ПОДАРКОВ:
{gifts}

ФОРМАТ ОТВЕТА:
Строго в формате JSON:
{{
    "выбранный_подарок": "название подарка",
    "обоснование": "подробное объяснение пользы для профессионального развития",
    "прогноз_роста_ценности_процент": число от 0 до 100
}}

Твой ответ должен содержать ТОЛЬКО JSON, без дополнительного текста.
"""

# Структура состояния для графа
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    agents_outputs: Dict[str, Any]
    final_selection: List[Dict[str, Any]]

# Функция для форматирования данных о подарках
def format_gifts_data(gifts):
    formatted_text = ""
    for i, gift in enumerate(gifts, 1):
        formatted_text += f"{i}. {gift['подарок']} - {gift['описание']} - Стоимость: {gift['стоимость']}₽ - Релевантность: {gift['релевантность']}/10\n"
    return formatted_text

# Функция для вызова OpenRouter API вместо LangChain
def call_openrouter_api(prompt):
    completion = client.chat.completions.create(
        extra_headers={
            "HTTP-Referer": "https://github.com", 
            "X-Title": "Gift Recommendation Agent", 
        },
        model="qwen/qwen3-235b-a22b:free",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    return completion.choices[0].message.content

# Функция для запуска первого агента
def run_praktik_bot(state):
    return run_agent("praktik_bot", praktik_bot_prompt, state)

# Функция для запуска второго агента
def run_fin_expert(state):
    return run_agent("fin_expert", fin_expert_prompt, state)

# Функция для запуска третьего агента
def run_wow_factor(state):
    return run_agent("wow_factor", wow_factor_prompt, state)

# Функция для запуска четвертого агента
def run_universal_guru(state):
    return run_agent("universal_guru", universal_guru_prompt, state)

# Функция для запуска пятого агента
def run_surprise_master(state):
    return run_agent("surprise_master", surprise_master_prompt, state)

# Функция для запуска шестого агента
def run_prof_rost(state):
    return run_agent("prof_rost", prof_rost_prompt, state)

# Функции для агентов с использованием OpenRouter
def run_agent(agent_name, prompt_template, state):
    formatted_gifts = format_gifts_data(gifts_data)
    prompt = prompt_template.format(gifts=formatted_gifts)
    
    print(f"Запуск агента: {agent_name}...")
    response = call_openrouter_api(prompt)
    print(f"Получен ответ от {agent_name}")
    
    try:
        # Извлечение JSON из ответа
        json_response = json.loads(response)
        # Сохраняем результат конкретного агента
        agents_outputs = state.get("agents_outputs", {})
        agents_outputs[agent_name] = json_response
        return {"messages": state.get("messages", []) + [HumanMessage(content=prompt), AIMessage(content=response)], 
                "agents_outputs": agents_outputs}
    except json.JSONDecodeError:
        # Если ответ не в формате JSON, попробуем еще раз с более четкими инструкциями
        error_message = "Твой предыдущий ответ не был в формате JSON. Пожалуйста, предоставь ответ ТОЛЬКО в формате JSON, без дополнительного текста."
        
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
                    "agents_outputs": agents_outputs}
        except json.JSONDecodeError:
            # Второй запрос с более четкими инструкциями
            retry_prompt = prompt + "\n\n" + error_message
            retry_response = call_openrouter_api(retry_prompt)
            
            try:
                # Еще одна попытка очистки
                if "```json" in retry_response:
                    cleaned_retry = retry_response.split("```json")[1].split("```")[0].strip()
                elif "```" in retry_response:
                    cleaned_retry = retry_response.split("```")[1].split("```")[0].strip()
                else:
                    cleaned_retry = retry_response
                
                json_response = json.loads(cleaned_retry)
                agents_outputs = state.get("agents_outputs", {})
                agents_outputs[agent_name] = json_response
                return {"messages": state.get("messages", []) + [HumanMessage(content=retry_prompt), AIMessage(content=retry_response)], 
                        "agents_outputs": agents_outputs}
            except json.JSONDecodeError:
                # Если все еще не JSON, создаем примерный ответ
                print(f"Ошибка при парсинге JSON от {agent_name}, создаем стандартный ответ")
                default_response = create_default_response(agent_name)
                agents_outputs = state.get("agents_outputs", {})
                agents_outputs[agent_name] = default_response
                return {"messages": state.get("messages", []) + [HumanMessage(content=retry_prompt), AIMessage(content=retry_response)], 
                        "agents_outputs": agents_outputs}

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
    # Получаем результаты всех агентов
    agents_outputs = state.get("agents_outputs", {})
    
    # Создаем список с оценками для каждого подарка
    gift_scores = {}
    
    # Нормализуем оценки от каждого агента
    for agent, output in agents_outputs.items():
        gift_name = output.get("выбранный_подарок")
        
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
            
        if gift_name:
            if gift_name not in gift_scores:
                gift_scores[gift_name] = []
            gift_scores[gift_name].append((agent, score))
    
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
    
    return {"final_selection": final_selection}

# Определение простого линейного графа
def define_graph():
    workflow = Graph()
    
    # Добавляем узлы для каждого агента
    workflow.add_node("praktik_bot", run_praktik_bot)
    workflow.add_node("fin_expert", run_fin_expert)
    workflow.add_node("wow_factor", run_wow_factor)
    workflow.add_node("universal_guru", run_universal_guru)
    workflow.add_node("surprise_master", run_surprise_master)
    workflow.add_node("prof_rost", run_prof_rost)
    workflow.add_node("select_final_gifts", select_final_gifts)
    
    # Задаем линейную последовательность исполнения
    workflow.add_edge(START, "praktik_bot")
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
def run_gift_selection():
    graph = define_graph()
    
    # Начальное состояние
    initial_state = {"messages": [], "agents_outputs": {}}
    
    # Запускаем граф
    results = graph.invoke(initial_state)
    
    # Получаем финальный результат
    return results["final_selection"]

# Функция для красивого вывода результатов
def print_results(final_selection):
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
        
def run_neuro_gift2(user_text):
    print("Запуск системы выбора подарков с использованием OpenRouter API...")
    print("Польз")
    final_selection = run_gift_selection()
    print_results(final_selection)
    return final_selection

def run_neuro_gift(user_text):
    return "Test result: " + user_text

# Запускаем систему
if __name__ == "__main__":
    run_neuro_gift('')
    
