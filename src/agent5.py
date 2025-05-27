"""
Ячейка 1: Импорты и базовая настройка (ОБНОВЛЕНО С LANGGRAPH)
Импортируем все необходимые библиотеки включая LangGraph
"""

import asyncio
import json
import logging
import os
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union, Annotated
from enum import Enum
import operator

import aiohttp
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

# LangGraph импорты
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agent_context import AgentContext
import gigafile

# Настройка русскоязычного логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Вывод в консоль для Jupyter
    ]
)
logger = logging.getLogger(__name__)
logger.info("🚀 Система выбора подарков с LangGraph инициализирована")

# Загружаем переменные окружения
load_dotenv()

print("✅ Импорты с LangGraph загружены")
print("📦 Требуется установка: pip install langgraph")

"""
Ячейка 2: Расширенные типы агентов с селектором (ОБНОВЛЕНО)
Добавлены новые специализированные агенты и селектор агентов
"""

class AgentType(Enum):
    """Расширенные типы специализированных ИИ-агентов для анализа подарков"""
    
    # Оригинальные агенты
    PRAKTIK_BOT = "praktik_bot"           # Анализирует практическую пользу
    FIN_EXPERT = "fin_expert"             # Анализирует соотношение цена/качество
    WOW_FACTOR = "wow_factor"             # Ищет эмоциональное воздействие
    UNIVERSAL_GURU = "universal_guru"     # Ищет универсальные подарки
    SURPRISE_MASTER = "surprise_master"   # Ищет неожиданные подарки
    PROF_ROST = "prof_rost"              # Фокус на профессиональном развитии
    
    # Новые специализированные агенты
    ROMANTIC_ADVISOR = "romantic_advisor"  # Романтические подарки
    KIDS_EXPERT = "kids_expert"           # Подарки для детей
    ELDERLY_CARE = "elderly_care"         # Подарки для пожилых людей
    HOBBY_HUNTER = "hobby_hunter"         # Подарки по хобби и увлечениям
    LUXURY_CURATOR = "luxury_curator"     # Премиум и люксовые подарки
    BUDGET_SAVER = "budget_saver"         # Бюджетные, но качественные подарки
    TECH_GURU = "tech_guru"              # Технологичные подарки
    CREATIVE_SOUL = "creative_soul"       # Подарки для творческих людей
    WELLNESS_COACH = "wellness_coach"     # Подарки для здоровья и красоты
    TRAVEL_EXPERT = "travel_expert"       # Подарки для путешественников
    FOODIE_GUIDE = "foodie_guide"        # Подарки для гурманов
    FAMILY_BONDS = "family_bonds"        # Семейные подарки
    COLLEAGUE_CONNECTOR = "colleague_connector"  # Подарки для коллег
    
    # Специальный селектор агентов
    AGENT_SELECTOR = "agent_selector"     # Выбирает подходящих агентов

class GiftRecipientType(Enum):
    """Типы получателей подарков для определения подходящих агентов"""
    COLLEAGUE = "коллега"
    RELATIVE = "родственник"
    CHILD = "ребенок" 
    GIRLFRIEND = "девушка"
    BOYFRIEND = "парень"
    ELDERLY = "пожилой человек"
    FRIEND = "друг"
    BOSS = "начальник"
    PARENT = "родитель"
    SIBLING = "брат/сестра"
    SPOUSE = "супруг/супруга"
    TEACHER = "учитель"
    NEIGHBOR = "сосед"
    ACQUAINTANCE = "знакомый"

print(f"✅ Определено {len(AgentType)} типов агентов (включая селектор)")
print(f"✅ Определено {len(GiftRecipientType)} типов получателей подарков")

# Показываем новых агентов
new_agents = [
    "ROMANTIC_ADVISOR", "KIDS_EXPERT", "ELDERLY_CARE", "HOBBY_HUNTER",
    "LUXURY_CURATOR", "BUDGET_SAVER", "TECH_GURU", "CREATIVE_SOUL", 
    "WELLNESS_COACH", "TRAVEL_EXPERT", "FOODIE_GUIDE", "FAMILY_BONDS",
    "COLLEAGUE_CONNECTOR", "AGENT_SELECTOR"
]

print(f"\n🆕 Новые агенты ({len(new_agents)}):")
for agent in new_agents:
    print(f"  - {agent}")
    
"""
Ячейка 3: Обновленные модели данных с поддержкой всех новых агентов (ИСПРАВЛЕНО)
Добавлены все поля для новых агентов
"""

class GiftModel(BaseModel):
    """Модель подарка с валидацией полей"""
    подарок: str = Field(..., min_length=1, description="Название подарка")
    описание: str = Field(..., min_length=1, description="Описание подарка")
    стоимость: str = Field(..., min_length=1, description="Диапазон стоимости")
    релевантность: int = Field(..., ge=1, le=10, description="Оценка релевантности от 1 до 10")
    query: str = Field(..., min_length=0, description="query")

    @validator('релевантность')
    def validate_relevance(cls, v):
        """Проверяем, что релевантность - это число от 1 до 10"""
        if not isinstance(v, int):
            try:
                return int(float(v))
            except (ValueError, TypeError):
                raise ValueError('Релевантность должна быть числом от 1 до 10')
        return v

class AgentResponseModel(BaseModel):
    """Расширенная модель ответа ИИ-агента с поддержкой всех новых агентов"""
    выбранный_подарок: str = Field(..., min_length=1)
    обоснование: str = Field(..., min_length=1)
    
    # Поля для оригинальных агентов
    коэффициент_практической_ценности: Optional[int] = Field(None, ge=0, le=100)
    roi_индекс: Optional[float] = Field(None, ge=0)
    степень_восторга_процент: Optional[int] = Field(None, ge=0, le=100)
    процент_сценариев_использования: Optional[int] = Field(None, ge=0, le=100)
    шанс_запомниться_процент: Optional[int] = Field(None, ge=0, le=100)
    прогноз_роста_ценности_процент: Optional[int] = Field(None, ge=0, le=100)
    
    # Поля для новых агентов
    уровень_романтики_процент: Optional[int] = Field(None, ge=0, le=100)
    детская_радость_процент: Optional[int] = Field(None, ge=0, le=100)
    возрастная_уместность_процент: Optional[int] = Field(None, ge=0, le=100)
    соответствие_хобби_процент: Optional[int] = Field(None, ge=0, le=100)
    уровень_роскоши_процент: Optional[int] = Field(None, ge=0, le=100)
    экономичность_процент: Optional[int] = Field(None, ge=0, le=100)
    уровень_технологий_процент: Optional[int] = Field(None, ge=0, le=100)
    творческий_потенциал_процент: Optional[int] = Field(None, ge=0, le=100)
    польза_здоровью_процент: Optional[int] = Field(None, ge=0, le=100)
    туристическая_ценность_процент: Optional[int] = Field(None, ge=0, le=100)
    кулинарная_привлекательность_процент: Optional[int] = Field(None, ge=0, le=100)
    семейная_ценность_процент: Optional[int] = Field(None, ge=0, le=100)
    корпоративная_уместность_процент: Optional[int] = Field(None, ge=0, le=100)

class PersonInfoModel(BaseModel):
    """Модель информации о человеке с защитой от инъекций"""
    info: str = Field(..., min_length=10)
    
    @validator('info')
    def validate_person_info(cls, v):
        """Базовая защита от опасного контента"""
        dangerous_patterns = ['<script', 'javascript:', 'eval(', 'exec(', 'import(']
        v_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern in v_lower:
                raise ValueError(f'Обнаружен потенциально опасный контент: {pattern}')
        return v.strip()

# LangGraph State - состояние workflow
class GraphState(dict):
    """Состояние LangGraph для передачи данных между узлами"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setdefault("person_info", "")
        self.setdefault("gifts_data", [])
        self.setdefault("agent_responses", {})
        self.setdefault("final_selection", [])
        self.setdefault("current_step", "initialized")
        self.setdefault("error_messages", [])
        self.setdefault("execution_time", 0.0)
        self.setdefault("selected_agents", [])  # Новое поле для списка выбранных агентов
        
print("✅ Обновленные модели данных с поддержкой всех агентов созданы")

"""
Ячейка 4: Централизованная конфигурация
Настройки API, лимиты, таймауты и другие параметры системы
"""

@dataclass
class Configuration:
    """Централизованная конфигурация всех параметров системы"""
    api_token: str                              # API токен для OpenRouter
    base_url: str = "https://openrouter.ai/api/v1"  # Базовый URL API
    model: str = "google/gemini-2.5-flash-preview:thinking"  # Модель ИИ
    max_retries: int = 3                        # Максимум попыток при ошибке
    retry_delay: float = 2.0                    # Задержка между попытками (сек)
    request_timeout: int = 30                   # Таймаут запроса (сек)
    max_concurrent_requests: int = 6            # Максимум одновременных запросов

    @classmethod
    def from_env(cls) -> 'Configuration':
        """Создание конфигурации из переменных окружения"""
        token = os.getenv("OPEN_API_TOKEN")
        if not token:
            raise ValueError("❌ OPEN_API_TOKEN не найден в переменных окружения!")
        
        config = cls(
            api_token=token,
            base_url=os.getenv("OPENROUTER_BASE_URL", cls.base_url),
            model=os.getenv("OPENROUTER_MODEL", cls.model),
            max_retries=int(os.getenv("MAX_RETRIES", cls.max_retries)),
            retry_delay=float(os.getenv("RETRY_DELAY", cls.retry_delay)),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", cls.request_timeout)),
            max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", cls.max_concurrent_requests))
        )
        
        print(f"✅ Конфигурация загружена:")
        print(f"  - Модель: {config.model}")
        print(f"  - Максимум одновременных запросов: {config.max_concurrent_requests}")
        print(f"  - Таймаут: {config.request_timeout}с")
        
        return config

print("✅ Класс конфигурации готов")

"""
Ячейка 5: Безопасный парсер JSON ответов (ИСПРАВЛЕННАЯ ВЕРСИЯ)
Заменяет небезопасный ast.literal_eval на json.loads с улучшенной обработкой
"""

class JSONParser:
    """
    Безопасный парсер JSON ответов от ИИ моделей
    Устраняет уязвимость выполнения произвольного кода
    """
    
    @staticmethod
    def parse_json_response(response: str) -> Dict[str, Any]:
        """
        Безопасное извлечение и парсинг JSON из ответа ИИ
        
        Args:
            response: Необработанный ответ от ИИ модели
            
        Returns:
            Словарь с распарсенными данными
            
        Raises:
            ValueError: Если JSON некорректен или не найден
        """
        try:
            # Шаг 1: Очистка ответа от лишних символов
            clean_response = response.strip()
            
            # Шаг 2: Удаление markdown разметки
            if "```json" in clean_response:
                parts = clean_response.split("```json")
                if len(parts) > 1:
                    clean_response = parts[1].split("```")[0].strip()
            elif "```" in clean_response:
                parts = clean_response.split("```")
                if len(parts) > 1:
                    clean_response = parts[1].split("```")[0].strip()
            
            # Шаг 3: Поиск JSON объекта в тексте (улучшенный алгоритм)
            json_str = clean_response
            
            # Ищем фигурные скобки для объекта
            start_idx = clean_response.find('{')
            if start_idx != -1:
                # Находим соответствующую закрывающую скобку
                brace_count = 0
                end_idx = -1
                
                for i in range(start_idx, len(clean_response)):
                    if clean_response[i] == '{':
                        brace_count += 1
                    elif clean_response[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i
                            break
                
                if end_idx != -1:
                    json_str = clean_response[start_idx:end_idx + 1]
            
            # Шаг 4: Дополнительная очистка JSON строки
            # Удаляем лишние пробелы и переносы строк внутри строк
            json_str = json_str.replace('\n', ' ').replace('\r', ' ')
            
            # Нормализуем множественные пробелы
            import re
            json_str = re.sub(r'\s+', ' ', json_str)
            
            # Шаг 5: БЕЗОПАСНЫЙ парсинг только через json.loads
            parsed_data = json.loads(json_str)
            
            # Шаг 6: Проверка типа результата
            if not isinstance(parsed_data, dict):
                raise ValueError("Ответ должен быть JSON объектом (словарем)")
            
            logger.info(f"✅ JSON успешно распарсен, полей: {len(parsed_data)}")
            return parsed_data
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {str(e)}")
            logger.error(f"🔍 Исходный ответ: {response[:500]}...")
            logger.error(f"🔍 Очищенная строка: {json_str[:500] if 'json_str' in locals() else 'не определена'}...")
            print(traceback.format_exc())
            raise ValueError(f"Некорректный JSON в ответе: {str(e)}")
        except Exception as e:
            logger.error(f"💥 Неожиданная ошибка при парсинге: {str(e)}")
            logger.error(f"🔍 Проблемный ответ: {response[:200]}...")
            print(traceback.format_exc())
            raise ValueError(f"Ошибка обработки ответа: {str(e)}")
    
    @staticmethod
    def parse_json_array(response: str) -> List[Dict[str, Any]]:
        """
        Парсинг JSON массива (для списка подарков) - улучшенная версия
        
        Args:
            response: Ответ содержащий JSON массив
            
        Returns:
            Список словарей
        """
        try:
            clean_response = response.strip()
            
            # Удаление markdown разметки
            if "```json" in clean_response:
                clean_response = clean_response.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_response:
                clean_response = clean_response.split("```")[1].split("```")[0].strip()
            
            # Поиск JSON массива с улучшенным алгоритмом
            start_idx = clean_response.find('[')
            if start_idx != -1:
                # Находим соответствующую закрывающую скобку
                bracket_count = 0
                end_idx = -1
                
                for i in range(start_idx, len(clean_response)):
                    if clean_response[i] == '[':
                        bracket_count += 1
                    elif clean_response[i] == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end_idx = i
                            break
                
                if end_idx != -1:
                    json_str = clean_response[start_idx:end_idx + 1]
                else:
                    json_str = clean_response
            else:
                json_str = clean_response
            
            # Очистка строки
            json_str = json_str.replace('\n', ' ').replace('\r', ' ')
            import re
            json_str = re.sub(r'\s+', ' ', json_str)
            
            # Безопасный парсинг массива
            parsed_data = json.loads(json_str)
            
            if not isinstance(parsed_data, list):
                raise ValueError("Ответ должен быть JSON массивом")
            
            logger.info(f"✅ JSON массив распарсен, элементов: {len(parsed_data)}")
            return parsed_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга JSON массива: {str(e)}")
            logger.error(f"🔍 Проблемный ответ: {response[:300]}...")
            print(traceback.format_exc())
            raise ValueError(f"Некорректный JSON массив: {str(e)}")

print("✅ Улучшенный безопасный JSON парсер готов")


"""
Ячейка 6: Расширенные промпты для всех агентов (ОБНОВЛЕНО)
Добавлены промпты для новых агентов и селектора
"""

class PromptTemplate:
    """Расширенная коллекция промптов для всех агентов"""
    
    # Оригинальный промпт для генерации подарков (без изменений)
    GIFT_GENERATION_PROMPT = """
Ты эксперт по выбору подарков. На основе информации о человеке предложи 10 подходящих подарков.

ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

🔥 КРИТИЧЕСКИ ВАЖНО: Твой ответ должен быть СТРОГО в формате JSON массива, без дополнительного текста, объяснений или markdown разметки.

Структура каждого элемента массива:
{{
  "подарок": "точное название подарка",
  "описание": "краткое описание и обоснование выбора", 
  "стоимость": "диапазон цен в формате 'минимум - максимум'",
  "релевантность": число_от_1_до_10,
  "query" : "ключевые слова для поиска в интернет магазине"
}}

❗ НЕ добавляй никакого текста до или после JSON массива
❗ НЕ используй markdown разметку
❗ Отвечай ТОЛЬКО JSON массивом из 10 подарков
"""

    @staticmethod
    def get_agent_selector_prompt(person_info: str, recipient_type: str) -> str:
        """Промпт для селектора агентов"""
        return f"""
ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

ТИП ПОЛУЧАТЕЛЯ ПОДАРКА: {recipient_type}

Ты АгентСелектор - определяешь какие специализированные агенты лучше всего подойдут для выбора подарка.

ДОСТУПНЫЕ АГЕНТЫ:
- praktik_bot: практичные подарки для повседневной жизни
- fin_expert: бюджетные решения с лучшим соотношением цена/качество  
- wow_factor: подарки с эмоциональным эффектом "вау"
- universal_guru: универсальные подарки для любых ситуаций
- surprise_master: неожиданные и запоминающиеся подарки
- prof_rost: подарки для профессионального развития
- romantic_advisor: романтические подарки для близких отношений
- kids_expert: подарки специально для детей
- elderly_care: подарки для пожилых людей
- hobby_hunter: подарки по увлечениям и хобби
- luxury_curator: премиум и дорогие подарки
- budget_saver: качественные бюджетные варианты
- tech_guru: современные технологичные подарки
- creative_soul: подарки для творческих натур
- wellness_coach: подарки для здоровья и красоты
- travel_expert: подарки для путешественников
- foodie_guide: подарки для любителей еды
- family_bonds: семейные подарки
- colleague_connector: корпоративные подарки для коллег

Выбери 4-6 наиболее подходящих агентов для данного получателя и ситуации.

Ответь СТРОГО в JSON формате:
{{
  "selected_agents": ["agent1", "agent2", "agent3", "agent4"],
  "reasoning": "объяснение выбора агентов"
}}
"""

    @staticmethod  
    def get_agent_prompt(agent_type: AgentType, person_info: str) -> str:
        """Получение промпта для конкретного агента"""
        
        base_structure = f"""
ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

СПИСОК ПОДАРКОВ:
{{gifts}}

🔥 КРИТИЧЕСКИ ВАЖНО: Твой ответ должен быть СТРОГО в формате JSON объекта.
❗ НЕ добавляй никакого текста до или после JSON
❗ Отвечай ТОЛЬКО чистым JSON объектом
"""

        # Промпты для всех агентов
        agent_prompts = {
            # Оригинальные агенты
            AgentType.PRAKTIK_BOT: base_structure + """
Ты ПрактикБот - анализируешь практическую пользу подарков в повседневной жизни.
Выбери ОДИН подарок с максимальной практической ценностью.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "детальное объяснение практической пользы",
  "коэффициент_практической_ценности": число_от_0_до_100
}""",

            AgentType.FIN_EXPERT: base_structure + """
Ты ФинЭксперт - анализируешь соотношение цена/качество подарков.
Выбери ОДИН подарок с лучшим экономическим эффектом.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "экономическое обоснование с расчетами", 
  "roi_индекс": число_коэффициент_полезности
}""",

            AgentType.WOW_FACTOR: base_structure + """
Ты ВауФактор - ищешь подарки с высоким эмоциональным откликом.
Выбери ОДИН подарок, который вызовет максимальный восторг.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение эмоционального воздействия",
  "степень_восторга_процент": число_от_0_до_100
}""",

            AgentType.UNIVERSAL_GURU: base_structure + """
Ты УниверсалГуру - ищешь максимально универсальные подарки.
Выбери ОДИН подарок для максимального количества ситуаций.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение универсальности применения",
  "процент_сценариев_использования": число_от_0_до_100
}""",

            AgentType.SURPRISE_MASTER: base_structure + """
Ты СюрпризМастер - ищешь нестандартные и неожиданные подарки.
Выбери ОДИН самый неожиданный и запоминающийся подарок.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение неожиданности и запоминаемости",
  "шанс_запомниться_процент": число_от_0_до_100
}""",

            AgentType.PROF_ROST: base_structure + """
Ты ПрофРост - специализируешься на подарках для профессионального развития.
Выбери ОДИН подарок с максимальной пользой для карьеры.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение пользы для профессионального развития",
  "прогноз_роста_ценности_процент": число_от_0_до_100
}""",

            # НОВЫЕ АГЕНТЫ
            AgentType.ROMANTIC_ADVISOR: base_structure + """
Ты РомантикСоветник - специалист по романтическим подаркам для близких отношений.
Выбери ОДИН подарок с максимальным романтическим потенциалом.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение романтической ценности подарка",
  "уровень_романтики_процент": число_от_0_до_100
}""",

            AgentType.KIDS_EXPERT: base_structure + """
Ты ДетскийЭксперт - специалист по подаркам для детей разного возраста.
Выбери ОДИН подарок, наиболее подходящий для ребенка.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение пользы для развития и радости ребенка",
  "детская_радость_процент": число_от_0_до_100
}""",

            AgentType.ELDERLY_CARE: base_structure + """
Ты ЗаботаОПожилых - специалист по подаркам для людей старшего возраста.
Выбери ОДИН подарок, учитывающий потребности пожилого человека.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка", 
  "обоснование": "объяснение пользы и удобства для пожилого человека",
  "возрастная_уместность_процент": число_от_0_до_100
}""",

            AgentType.HOBBY_HUNTER: base_structure + """
Ты ОхотникХобби - специалист по подаркам, связанным с увлечениями и хобби.
Выбери ОДИН подарок, максимально соответствующий увлечениям человека.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение связи подарка с хобби и интересами",
  "соответствие_хобби_процент": число_от_0_до_100
}""",

            AgentType.LUXURY_CURATOR: base_structure + """
Ты КураторЛюкса - специалист по премиальным и роскошным подаркам.
Выбери ОДИН подарок с максимальным уровнем престижа и качества.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение премиальности и престижности подарка",
  "уровень_роскоши_процент": число_от_0_до_100
}""",

            AgentType.BUDGET_SAVER: base_structure + """
Ты БюджетСпаситель - специалист по качественным, но доступным подаркам.
Выбери ОДИН подарок с минимальной стоимостью и максимальной ценностью.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение экономности при сохранении качества",
  "экономичность_процент": число_от_0_до_100
}""",

            AgentType.TECH_GURU: base_structure + """
Ты ТехГуру - специалист по современным технологичным подаркам.
Выбери ОДИН самый технологичный и современный подарок.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение технологичности и инновационности",
  "уровень_технологий_процент": число_от_0_до_100
}""",

            AgentType.CREATIVE_SOUL: base_structure + """
Ты ТворческаяДуша - специалист по подаркам для креативных и артистичных людей.
Выбери ОДИН подарок, способствующий творческому самовыражению.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение влияния на творчество и самовыражение",
  "творческий_потенциал_процент": число_от_0_до_100
}""",

            AgentType.WELLNESS_COACH: base_structure + """
Ты ВелнесТренер - специалист по подаркам для здоровья, красоты и благополучия.
Выбери ОДИН подарок, максимально полезный для физического и ментального здоровья.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение пользы для здоровья и самочувствия",
  "польза_здоровью_процент": число_от_0_до_100
}""",

            AgentType.TRAVEL_EXPERT: base_structure + """
Ты ЭкспертПутешествий - специалист по подаркам для любителей путешествий.
Выбери ОДИН подарок, наиболее полезный в поездках и путешествиях.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение пользы в путешествиях и поездках",
  "туристическая_ценность_процент": число_от_0_до_100
}""",

            AgentType.FOODIE_GUIDE: base_structure + """
Ты ГидГурмана - специалист по подаркам для любителей еды и кулинарии.
Выбери ОДИН подарок, связанный с едой, кулинарией или гастрономией.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение гастрономической ценности подарка",
  "кулинарная_привлекательность_процент": число_от_0_до_100
}""",

            AgentType.FAMILY_BONDS: base_structure + """
Ты СемейныеУзы - специалист по подаркам, укрепляющим семейные отношения.
Выбери ОДИН подарок, способствующий семейному единству и общению.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение влияния на семейные отношения",
  "семейная_ценность_процент": число_от_0_до_100
}""",

            AgentType.COLLEAGUE_CONNECTOR: base_structure + """
Ты КоллегиальныйСвязующий - специалист по корпоративным подаркам для коллег.
Выбери ОДИН подарок, подходящий для рабочих отношений.

Ответь JSON объектом:
{
  "выбранный_подарок": "точное название подарка из списка",
  "обоснование": "объяснение уместности в рабочей среде",
  "корпоративная_уместность_процент": число_от_0_до_100
}"""
        }
        
        return agent_prompts.get(agent_type, base_structure + """
Выбери лучший подарок и ответь JSON объектом:
{
  "выбранный_подарок": "название подарка",
  "обоснование": "объяснение выбора", 
  "оценка": число_от_0_до_100
}""")

print("✅ Расширенные промпты для всех агентов готовы")
print(f"📝 Всего промптов: {len(AgentType)} агентов")

"""
Ячейка 7: HTTP клиент для работы с OpenRouter API
Асинхронный клиент с connection pooling и retry логикой
"""

class APIClient:
    """Асинхронный HTTP клиент с защитой от перегрузок и автоповторами"""
    
    def __init__(self, config: Configuration):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        # Семафор ограничивает количество одновременных запросов
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)
        self.logger = logging.getLogger("APIClient")
    
    async def __aenter__(self):
        """Создание HTTP сессии при входе в async context manager"""
        # Настройка connection pool для эффективного использования соединений
        connector = aiohttp.TCPConnector(
            ssl=True,           # Принудительное использование SSL
            limit=100,          # Общий лимит соединений
            limit_per_host=10   # Лимит соединений на хост
        )
        
        # Настройка таймаутов
        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        
        # Создание сессии с заголовками
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self.config.api_token}",
                "HTTP-Referer": "https://github.com",
                "X-Title": "Gift Recommendation Agent",
                "Content-Type": "application/json"
            }
        )
        self.logger.info("🔗 HTTP сессия создана")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие HTTP сессии при выходе из context manager"""
        if self.session:
            await self.session.close()
            self.logger.info("🔌 HTTP сессия закрыта")
    
    async def make_request(self, prompt: str) -> str:
        """
        Выполнение HTTP запроса с retry логикой и exponential backoff
        
        Args:
            prompt: Текст промпта для ИИ
            
        Returns:
            Ответ от ИИ модели
            
        Raises:
            Exception: Если все попытки запроса неудачны
        """
        # Ограничиваем количество одновременных запросов
        async with self._semaphore:
            for attempt in range(self.config.max_retries):
                try:
                    self.logger.info(f"🔄 API запрос, попытка {attempt + 1}/{self.config.max_retries}")
                    
                    # Подготовка payload для OpenRouter API
                    payload = {
                        "model": self.config.model,
                        "messages": [{"role": "user", "content": prompt}]
                    }
                    
                    # Выполнение HTTP POST запроса
                    async with self.session.post(
                        f"{self.config.base_url}/chat/completions",
                        json=payload
                    ) as response:
                        
                        if response.status == 200:
                            data = await response.json()
                            # Проверяем корректность структуры ответа
                            if (data.get("choices") and 
                                len(data["choices"]) > 0 and 
                                data["choices"][0].get("message", {}).get("content")):
                                
                                content = data["choices"][0]["message"]["content"]
                                self.logger.info(f"✅ Получен ответ длиной {len(content)} символов")
                                return content
                        
                        self.logger.warning(f"⚠️ API вернул статус {response.status}")
                        
                except asyncio.TimeoutError:
                    self.logger.warning(f"⏰ Таймаут на попытке {attempt + 1}")
                    print(traceback.format_exc())
                except Exception as e:
                    self.logger.error(f"❌ Ошибка API на попытке {attempt + 1}: {str(e)}")
                    print(traceback.format_exc())
                
                # Exponential backoff: задержка увеличивается с каждой попыткой
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    self.logger.info(f"⏳ Ожидание {delay}с перед следующей попыткой")
                    await asyncio.sleep(delay)
            
            # Если все попытки исчерпаны
            error_msg = f"API запрос не удался после {self.config.max_retries} попыток"
            self.logger.error(f"💥 {error_msg}")
            raise Exception(error_msg)

print("✅ API клиент готов к работе")

"""
Ячейка 8: Селектор агентов и обновленная архитектура (ИСПРАВЛЕННАЯ ВЕРСИЯ)
Добавлен селектор агентов и поддержка всех новых агентов
"""

class AgentSelector:
    """Селектор агентов для определения подходящих агентов под конкретную задачу"""
    
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
        self.logger = logging.getLogger("AgentSelector")
    
    async def select_agents(self, person_info: str, recipient_type: str) -> List[str]:
        """
        Выбор подходящих агентов на основе информации о человеке и типе получателя
        
        Args:
            person_info: Информация о человеке
            recipient_type: Тип получателя подарка
            
        Returns:
            Список имен выбранных агентов
        """
        try:
            self.logger.info(f"🎯 Выбор агентов для получателя типа: {recipient_type}")
            
            # Получаем промпт для селектора
            prompt = PromptTemplate.get_agent_selector_prompt(person_info, recipient_type)
            
            # Запрос к API
            response = await self.api_client.make_request(prompt)
            
            # Парсинг ответа
            cleaned_response = response.strip()
            if not cleaned_response.startswith('{'):
                start_idx = cleaned_response.find('{')
                end_idx = cleaned_response.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    cleaned_response = cleaned_response[start_idx:end_idx + 1]
            
            parsed_response = JSONParser.parse_json_response(cleaned_response)
            
            selected_agents = parsed_response.get("selected_agents", [])
            reasoning = parsed_response.get("reasoning", "")
            
            self.logger.info(f"✅ Выбрано {len(selected_agents)} агентов: {', '.join(selected_agents)}")
            self.logger.info(f"📝 Обоснование: {reasoning}")
            
            return selected_agents
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка селектора агентов: {str(e)}")
            # Fallback: возвращаем базовый набор агентов
            return self._get_fallback_agents(recipient_type)
    
    def _get_fallback_agents(self, recipient_type: str) -> List[str]:
        """Резервный выбор агентов на основе типа получателя"""
        
        # Предустановленные наборы агентов для разных типов получателей
        fallback_mappings = {
            "коллега": ["colleague_connector", "prof_rost", "praktik_bot", "budget_saver"],
            "ребенок": ["kids_expert", "creative_soul", "surprise_master", "tech_guru"],
            "девушка": ["romantic_advisor", "wellness_coach", "luxury_curator", "creative_soul"],
            "парень": ["tech_guru", "hobby_hunter", "praktik_bot", "surprise_master"],
            "пожилой человек": ["elderly_care", "wellness_coach", "family_bonds", "praktik_bot"], 
            "родственник": ["family_bonds", "universal_guru", "wellness_coach", "hobby_hunter"],
            "друг": ["surprise_master", "hobby_hunter", "universal_guru", "wow_factor"],
            "начальник": ["luxury_curator", "prof_rost", "colleague_connector", "universal_guru"],
            "супруг/супруга": ["romantic_advisor", "luxury_curator", "family_bonds", "wellness_coach"]
        }
        
        selected = fallback_mappings.get(recipient_type, 
                                       ["universal_guru", "praktik_bot", "surprise_master", "fin_expert"])
        
        self.logger.warning(f"⚠️ Используем резервный набор агентов для '{recipient_type}': {selected}")
        return selected

class LangGraphAgent:
    """Универсальный класс для всех LangGraph агентов"""
    
    def __init__(self, agent_type: AgentType, api_client: APIClient):
        self.agent_type = agent_type
        self.api_client = api_client
        self.logger = logging.getLogger(f"LangGraphAgent.{agent_type.value}")
    
    def format_gifts_for_prompt(self, gifts_data: List[Dict[str, Any]]) -> str:
        """Форматирование подарков для промпта"""
        formatted_text = ""
        for i, gift in enumerate(gifts_data, 1):
            formatted_text += (
                f"{i}. {gift['подарок']} - {gift['описание']} - "
                f"Стоимость: {gift['стоимость']}₽ - Релевантность: {gift['релевантность']}/10\n"
            )
        return formatted_text
    
    async def analyze_gifts_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Узел LangGraph для анализа подарков агентом"""
        try:
            self.logger.info(f"🔍 LangGraph: Анализ агентом {self.agent_type.value}")
            
            person_info = state["person_info"]
            gifts_data = state["gifts_data"]
            
            # Подготовка промпта
            formatted_gifts = self.format_gifts_for_prompt(gifts_data)
            base_prompt = PromptTemplate.get_agent_prompt(self.agent_type, person_info)
            prompt = base_prompt.replace("{gifts}", formatted_gifts)
            
            # Запрос к API
            response = await self.api_client.make_request(prompt)
            
            # Парсинг ответа
            cleaned_response = response.strip()
            if not cleaned_response.startswith('{'):
                start_idx = cleaned_response.find('{')
                end_idx = cleaned_response.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    cleaned_response = cleaned_response[start_idx:end_idx + 1]
            
            parsed_response = JSONParser.parse_json_response(cleaned_response)
            validated_response = AgentResponseModel(**parsed_response)
            
            self.logger.info(f"✅ LangGraph: {self.agent_type.value} выбрал {validated_response.выбранный_подарок}")
            
            # Обновляем состояние
            agent_responses = state.get("agent_responses", {})
            agent_responses[self.agent_type.value] = validated_response.model_dump()
            
            return {
                **state,
                "agent_responses": agent_responses,
                "current_step": f"agent_{self.agent_type.value}_completed"
            }
            
        except Exception as e:
            self.logger.error(f"❌ LangGraph: Ошибка агента {self.agent_type.value}: {str(e)}")
            
            # Fallback ответ
            fallback_response = self._get_fallback_response(state["gifts_data"])
            
            agent_responses = state.get("agent_responses", {})
            agent_responses[self.agent_type.value] = fallback_response.model_dump()
            
            error_messages = state.get("error_messages", [])
            error_messages.append(f"Ошибка агента {self.agent_type.value}: {str(e)}")
            
            return {
                **state,
                "agent_responses": agent_responses,
                "error_messages": error_messages,
                "current_step": f"agent_{self.agent_type.value}_fallback"
            }
    
    def _get_fallback_response(self, gifts_data: List[Dict[str, Any]]) -> AgentResponseModel:
        """Создание fallback ответа для любого агента"""
        if not gifts_data:
            raise ValueError("Нет подарков для fallback ответа")
        
        fallback_gift = gifts_data[0]
        
        # Универсальный fallback ответ
        fallback_data = {
            "выбранный_подарок": fallback_gift["подарок"],
            "обоснование": f"Подарок выбран агентом {self.agent_type.value} (резервный режим)"
        }
        
        # Добавляем специфичное поле в зависимости от типа агента
        agent_specific_fields = {
            AgentType.PRAKTIK_BOT: {"коэффициент_практической_ценности": 75},
            AgentType.FIN_EXPERT: {"roi_индекс": 2.5},
            AgentType.WOW_FACTOR: {"степень_восторга_процент": 75},
            AgentType.UNIVERSAL_GURU: {"процент_сценариев_использования": 70},
            AgentType.SURPRISE_MASTER: {"шанс_запомниться_процент": 75},
            AgentType.PROF_ROST: {"прогноз_роста_ценности_процент": 70},
            AgentType.ROMANTIC_ADVISOR: {"уровень_романтики_процент": 80},
            AgentType.KIDS_EXPERT: {"детская_радость_процент": 85},
            AgentType.ELDERLY_CARE: {"возрастная_уместность_процент": 80},
            AgentType.HOBBY_HUNTER: {"соответствие_хобби_процент": 75},
            AgentType.LUXURY_CURATOR: {"уровень_роскоши_процент": 90},
            AgentType.BUDGET_SAVER: {"экономичность_процент": 85},
            AgentType.TECH_GURU: {"уровень_технологий_процент": 80},
            AgentType.CREATIVE_SOUL: {"творческий_потенциал_процент": 75},
            AgentType.WELLNESS_COACH: {"польза_здоровью_процент": 80},
            AgentType.TRAVEL_EXPERT: {"туристическая_ценность_процент": 75},
            AgentType.FOODIE_GUIDE: {"кулинарная_привлекательность_процент": 80},
            AgentType.FAMILY_BONDS: {"семейная_ценность_процент": 85},
            AgentType.COLLEAGUE_CONNECTOR: {"корпоративная_уместность_процент": 70}
        }
        
        # Добавляем специфичное поле для агента
        specific_field = agent_specific_fields.get(self.agent_type, {"оценка": 75})
        fallback_data.update(specific_field)
        
        return AgentResponseModel(**fallback_data)

print("✅ Исправленный селектор агентов и LangGraph агенты готовы")
print(f"🎯 Поддерживается {len(AgentType) - 1} специализированных агентов + селектор")

"""
Ячейка 9: Исправленный LangGraph генератор подарков
Устранено предупреждение Pydantic
"""

class LangGraphGiftGenerator:
    """Генератор подарков для LangGraph workflow"""
    
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
        self.logger = logging.getLogger("LangGraphGiftGenerator")
    
    async def generate_gifts_node(self, state: GraphState) -> GraphState:
        """Узел LangGraph для генерации подарков"""
        try:
            self.logger.info("🎁 LangGraph: Генерация списка подарков")
            
            person_info = state["person_info"]
            files = state["files"]
            
            # Валидация входных данных
            validated_person_info = PersonInfoModel(info=person_info)
            
            for file in files:
                person_info += "\n" + gigafile.analyze_picture(file)
            
            # Подготовка промпта
            prompt = PromptTemplate.GIFT_GENERATION_PROMPT.format(
                person_info=validated_person_info.info
            )
            
            # Запрос к API
            response = await self.api_client.make_request(prompt)
            
            # Парсинг JSON массива
            gifts_data = JSONParser.parse_json_array(response)
            
            # Валидация подарков (ИСПРАВЛЕНО: используем model_dump вместо dict)
            validated_gifts = []
            for gift_data in gifts_data:
                try:
                    validated_gift = GiftModel(**gift_data)
                    validated_gifts.append(validated_gift.model_dump())  # ИСПРАВЛЕНО
                except Exception as e:
                    self.logger.warning(f"⚠️ Подарок не прошел валидацию: {e}")
            
            if not validated_gifts:
                self.logger.warning("🔄 Используем резервный список подарков")
                validated_gifts = self._get_fallback_gifts()
            
            self.logger.info(f"✅ LangGraph: Сгенерировано {len(validated_gifts)} подарков")
            
            # Обновляем состояние LangGraph
            return {
                **state,
                "gifts_data": validated_gifts,
                "current_step": "gifts_generated"
            }
            
        except Exception as e:
            self.logger.error(f"❌ LangGraph: Ошибка генерации подарков: {str(e)}")
            
            # В случае ошибки используем fallback
            fallback_gifts = self._get_fallback_gifts()
            
            return {
                **state,
                "gifts_data": fallback_gifts,
                "current_step": "gifts_generated_fallback",
                "error_messages": state.get("error_messages", []) + [f"Ошибка генерации: {str(e)}"]
            }
    
    def _get_fallback_gifts(self) -> List[Dict[str, Any]]:
        """Резервный список подарков"""
        fallback_data = [
            {
                "подарок": "Умный велокомпьютер",
                "описание": "Устройство для отслеживания маршрутов, скорости и других показателей во время велопрогулок",
                "стоимость": "6000 - 15000",
                "релевантность": 9
            },
            {
                "подарок": "Беспроводные наушники с шумоподавлением",
                "описание": "Качественный звук для прослушивания музыки и просмотра фильмов",
                "стоимость": "8000 - 25000",
                "релевантность": 8
            },
            {
                "подарок": "Фитнес-браслет или умные часы",
                "описание": "Отслеживание тренировок в зале и активности в путешествиях",
                "стоимость": "5000 - 30000",
                "релевантность": 9
            }
        ]
        
        return fallback_data

print("✅ Исправленный LangGraph генератор подарков готов")

"""
Ячейка 10: Исправленный LangGraph сервис с корректным извлечением оценок (ОБНОВЛЕНО)
Поддержка всех новых агентов и улучшенный отчет
"""

class LangGraphGiftSelectionService:
    """Сервис выбора подарков с использованием LangGraph"""
    
    def __init__(self, config: Configuration):
        self.config = config
        self.logger = logging.getLogger("LangGraphGiftSelectionService")
    
    async def final_selection_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Узел LangGraph для финального выбора подарков
        """
        try:
            self.logger.info("🎯 LangGraph: Финальный выбор подарков")
            
            agent_responses = state.get("agent_responses", {})
            gifts_data = state["gifts_data"]
            
            # Подсчет голосов
            gift_scores = {}
            participating_agents = list(agent_responses.keys())  # Список участвовавших агентов
            
            for agent_name, response in agent_responses.items():
                gift_name = response.get("выбранный_подарок")
                if not gift_name:
                    continue
                
                # Извлечение оценки (ИСПРАВЛЕНО: поддержка всех агентов)
                score = self._extract_score_from_response(agent_name, response)
                
                if gift_name not in gift_scores:
                    gift_scores[gift_name] = []
                gift_scores[gift_name].append((agent_name, score))
                
                self.logger.info(f"🗳️ LangGraph: {agent_name} выбрал '{gift_name}' с оценкой {score}")
            
            # Расчет средних оценок
            average_scores = {}
            for gift, scores in gift_scores.items():
                total_score = sum(score for _, score in scores)
                avg_score = total_score / len(scores) if scores else 0
                
                average_scores[gift] = {
                    "средний_балл": avg_score,
                    "голоса_агентов": [agent for agent, _ in scores],
                    "количество_голосов": len(scores),
                    "детали_голосов": scores
                }
            
            # Сортировка
            sorted_gifts = sorted(
                average_scores.items(),
                key=lambda x: (x[1]["количество_голосов"], x[1]["средний_балл"]),
                reverse=True
            )
            
            # Формирование финального списка
            final_selection = []
            for i, (gift_name, metrics) in enumerate(sorted_gifts[:2]):
                gift_details = next(
                    (gift for gift in gifts_data if gift["подарок"] == gift_name),
                    None
                )
                
                if gift_details:
                    final_selection.append({
                        "место": i + 1,
                        "подарок": gift_name,
                        "описание": gift_details["описание"],
                        "стоимость": gift_details["стоимость"],
                        "релевантность": gift_details["релевантность"],
                        "query" : gift_details["query"],
                        "средний_балл": round(metrics["средний_балл"], 2),
                        "количество_голосов": metrics["количество_голосов"],
                        "выбран_агентами": metrics["голоса_агентов"],
                        "детали_оценок": metrics["детали_голосов"]
                    })
            
            # Дополнение до 2 подарков
            if len(final_selection) < 2:
                self._add_backup_gifts(final_selection, gifts_data)
            
            self.logger.info(f"🏆 LangGraph: Финальный выбор завершен, подарков: {len(final_selection)}")
            
            return {
                **state,
                "final_selection": final_selection,
                "participating_agents": participating_agents,  # Добавляем список агентов
                "current_step": "final_selection_completed"
            }
            
        except Exception as e:
            self.logger.error(f"💥 LangGraph: Ошибка финального выбора: {str(e)}")
            
            # Fallback финальный выбор
            fallback_selection = self._get_fallback_final_selection(gifts_data)
            
            return {
                **state,
                "final_selection": fallback_selection,
                "participating_agents": list(state.get("agent_responses", {}).keys()),
                "current_step": "final_selection_fallback",
                "error_messages": state.get("error_messages", []) + [f"Ошибка финального выбора: {str(e)}"]
            }
    
    def _extract_score_from_response(self, agent_name: str, response: Dict[str, Any]) -> float:
        """Извлечение оценки из ответа агента (ИСПРАВЛЕНО: поддержка всех агентов)"""
        try:
            # Расширенная карта оценок для всех агентов
            score_mappings = {
                "praktik_bot": response.get("коэффициент_практической_ценности"),
                "fin_expert": response.get("roi_индекс"),
                "wow_factor": response.get("степень_восторга_процент"),
                "universal_guru": response.get("процент_сценариев_использования"),
                "surprise_master": response.get("шанс_запомниться_процент"),
                "prof_rost": response.get("прогноз_роста_ценности_процент"),
                # Новые агенты
                "romantic_advisor": response.get("уровень_романтики_процент"),
                "kids_expert": response.get("детская_радость_процент"),
                "elderly_care": response.get("возрастная_уместность_процент"),
                "hobby_hunter": response.get("соответствие_хобби_процент"),
                "luxury_curator": response.get("уровень_роскоши_процент"),
                "budget_saver": response.get("экономичность_процент"),
                "tech_guru": response.get("уровень_технологий_процент"),
                "creative_soul": response.get("творческий_потенциал_процент"),
                "wellness_coach": response.get("польза_здоровью_процент"),
                "travel_expert": response.get("туристическая_ценность_процент"),
                "foodie_guide": response.get("кулинарная_привлекательность_процент"),
                "family_bonds": response.get("семейная_ценность_процент"),
                "colleague_connector": response.get("корпоративная_уместность_процент"),
                "agent_selector": response.get("оценка", 50)  # Селектор агентов использует общую оценку
            }
            
            raw_score = score_mappings.get(agent_name)
            
            # Обработка None значений
            if raw_score is None:
                self.logger.warning(f"⚠️ Отсутствует оценка для {agent_name}, используем 75")
                return 75.0
            
            # Нормализация для fin_expert
            if agent_name == "fin_expert":
                return min(float(raw_score) * 20, 100.0)
            
            return float(raw_score)
            
        except (TypeError, ValueError) as e:
            self.logger.warning(f"⚠️ Ошибка извлечения оценки для {agent_name}: {e}, используем 75")
            return 75.0
    
    def _add_backup_gifts(self, final_selection: List[Dict], gifts_data: List[Dict]):
        """Добавление резервных подарков"""
        selected_gifts = {item["подарок"] for item in final_selection}
        
        for gift in gifts_data:
            if gift["подарок"] not in selected_gifts and len(final_selection) < 2:
                final_selection.append({
                    "место": len(final_selection) + 1,
                    "подарок": gift["подарок"],
                    "описание": gift["описание"],
                    "стоимость": gift["стоимость"],
                    "релевантность": gift["релевантность"],
                    "средний_балл": 75.0,
                    "количество_голосов": 0,
                    "выбран_агентами": ["автодополнение"],
                    "детали_оценок": []
                })
    
    def _get_fallback_final_selection(self, gifts_data: List[Dict]) -> List[Dict[str, Any]]:
        """Резервный финальный выбор"""
        if gifts_data:
            return [{
                "место": 1,
                "подарок": gifts_data[0]["подарок"],
                "описание": gifts_data[0]["описание"],
                "стоимость": gifts_data[0]["стоимость"],
                "релевантность": gifts_data[0]["релевантность"],
                "средний_балл": 75.0,
                "количество_голосов": 0,
                "выбран_агентами": ["fallback_system"],
                "детали_оценок": []
            }]
        else:
            return [{
                "место": 1,
                "подарок": "Универсальный подарок",
                "описание": "Резервный выбор системы",
                "стоимость": "5000 - 15000",
                "релевантность": 7,
                "средний_балл": 75.0,
                "количество_голосов": 0,
                "выбран_агентами": ["emergency_fallback"],
                "детали_оценок": []
            }]

print("✅ Исправленный LangGraph сервис с поддержкой всех агентов готов")

"""
Ячейка 11: Обновленный ResultFormatter с информацией об агентах (УЛУЧШЕНО)
Добавлена информация об участвовавших агентах
"""

class ResultFormatter:
    """Форматтер результатов для красивого вывода в Jupyter Notebook"""
    
    @staticmethod
    def format_results(final_selection: List[Dict[str, Any]], gifts_data: List[GiftModel], participating_agents: List[str] = None) -> str:
        """
        Форматирование результатов для красивого отображения
        
        Args:
            final_selection: Финальный выбор подарков
            gifts_data: Исходный список сгенерированных подарков
            participating_agents: Список участвовавших агентов
            
        Returns:
            Отформатированная строка с результатами
        """
        result = "\n" + "="*60 + "\n"
        result += "🎁 LANGGRAPH СИСТЕМА ВЫБОРА ПОДАРКОВ - РЕЗУЛЬТАТЫ\n"
        result += "="*60 + "\n\n"
        
        # Секция 1: Информация об участвовавших агентах
        if participating_agents:
            result += "🤖 УЧАСТВОВАВШИЕ ИИ-АГЕНТЫ:\n"
            result += "-" * 30 + "\n"
            
            # Разделяем агентов на группы для красивого отображения
            agent_names = {
                "praktik_bot": "ПрактикБот",
                "fin_expert": "ФинЭксперт", 
                "wow_factor": "ВауФактор",
                "universal_guru": "УниверсалГуру",
                "surprise_master": "СюрпризМастер",
                "prof_rost": "ПрофРост",
                "romantic_advisor": "РомантикСоветник",
                "kids_expert": "ДетскийЭксперт",
                "elderly_care": "ЗаботаОПожилых",
                "hobby_hunter": "ОхотникХобби",
                "luxury_curator": "КураторЛюкса",
                "budget_saver": "БюджетСпаситель",
                "tech_guru": "ТехГуру",
                "creative_soul": "ТворческаяДуша",
                "wellness_coach": "ВелнесТренер",
                "travel_expert": "ЭкспертПутешествий",
                "foodie_guide": "ГидГурмана",
                "family_bonds": "СемейныеУзы",
                "colleague_connector": "КоллегиальныйСвязующий",
                "agent_selector": "СелекторАгентов"
            }
            
            agent_display_names = []
            for agent in participating_agents:
                display_name = agent_names.get(agent, agent)
                agent_display_names.append(display_name)
            
            result += f"Всего агентов: {len(participating_agents)}\n"
            result += f"Агенты: {', '.join(agent_display_names)}\n\n"
        
        # Секция 2: Сгенерированный список подарков
        result += "📝 СГЕНЕРИРОВАННЫЙ СПИСОК ПОДАРКОВ:\n"
        result += "-" * 40 + "\n"
        for i, gift in enumerate(gifts_data, 1):
            # Обработка как объектов GiftModel, так и словарей
            if hasattr(gift, 'подарок'):
                result += f"{i:2}. {gift.подарок}\n"
                result += f"    💰 {gift.стоимость}₽ | ⭐ {gift.релевантность}/10\n"
            else:
                result += f"{i:2}. {gift['подарок']}\n"
                result += f"    💰 {gift['стоимость']}₽ | ⭐ {gift['релевантность']}/10\n"
        
        result += "\n" + "="*60 + "\n"
        result += "🏆 ФИНАЛЬНЫЕ РЕКОМЕНДАЦИИ ОТ LANGGRAPH ИИ-АГЕНТОВ\n"
        result += "="*60 + "\n\n"
        
        # Секция 3: Топ рекомендации
        for gift in final_selection:
            medal = "🥇" if gift['место'] == 1 else "🥈" if gift['место'] == 2 else "🥉"
            result += f"{medal} МЕСТО #{gift['место']}: {gift['подарок']}\n"
            result += "-" * (len(gift['подарок']) + 15) + "\n"
            result += f"📝 Описание: {gift['описание']}\n"
            result += f"💰 Стоимость: {gift['стоимость']}₽\n"
            result += f"⭐ Релевантность: {gift['релевантность']}/10\n"
            result += f"🎯 Средний балл ИИ: {gift['средний_балл']}/100\n"
            result += f"🗳️  Голосов агентов: {gift['количество_голосов']}\n"
            result += f"🤖 Выбрали агенты: {', '.join(gift['выбран_агентами'])}\n"
            
            # Детали оценок если есть
            if gift.get('детали_оценок'):
                result += f"📊 Детальные оценки LangGraph агентов:\n"
                for agent, score in gift['детали_оценок']:
                    display_name = agent_names.get(agent, agent) if 'agent_names' in locals() else agent
                    result += f"     • {display_name}: {score}\n"
            
            result += "\n"
        
        result += "="*60 + "\n"
        result += "✨ LangGraph анализ завершен! Приятного выбора подарка! ✨\n"
        result += "="*60 + "\n"
        
        return result
    
    @staticmethod
    def display_progress(step: str, details: str = ""):
        """Отображение прогресса выполнения LangGraph"""
        print(f"🔄 LangGraph: {step}")
        if details:
            print(f"   {details}")
    
    @staticmethod
    def display_agent_analysis(agent_type: str, chosen_gift: str, score: float):
        """Отображение результата анализа отдельного LangGraph агента"""
        print(f"🤖 LangGraph {agent_type}: выбрал '{chosen_gift}' (оценка: {score:.1f})")

print("✅ Обновленный ResultFormatter с информацией об агентах готов")

"""
Ячейка 12: Упрощенные главные функции LangGraph (ИСПРАВЛЕННАЯ ВЕРСИЯ)
Убран LangGraphWorkflowBuilder, код упрощен и работает напрямую
"""

async def run_neuro_gift_async(context: AgentContext) -> List[Dict[str, Any]]:
    """
    Асинхронная версия с упрощенным LangGraph workflow
    
    Args:
        person_info: Информация о человеке для персонализации подарков
        
    Returns:
        Список из 2 лучших подарков с детальной информацией
    """
    try:
        # Создание конфигурации
        config = Configuration.from_env()
        person_info = context.person_info
        logger.info(f"🔧 LangGraph система инициализирована с моделью: {config.model}")
        
        logger.info("🚀 Запуск LangGraph системы выбора подарков...")
        logger.info(f"👤 Анализируем профиль: {person_info[:100]}...")
        
        start_time = time.time()
        
        # Используем API клиент для создания workflow напрямую
        async with APIClient(config) as api_client:
            
            # Создаем начальное состояние LangGraph
            state = {
                "person_info": person_info,
                "gifts_data": [],
                "agent_responses": {},
                "final_selection": [],
                "current_step": "initialized",
                "error_messages": [],
                "execution_time": 0.0,
                "photos" : context.photos
            }
            
            # ЭТАП 1: Генерация подарков (LangGraph узел)
            logger.info("📝 LangGraph Этап 1: Генерация подарков")
            gift_generator = LangGraphGiftGenerator(api_client)
            state = await gift_generator.generate_gifts_node(state)
            
            if not state.get("gifts_data"):
                logger.error("❌ LangGraph: Не удалось сгенерировать подарки")
                raise Exception("Генерация подарков не удалась")
            
            # ЭТАП 2: Параллельный анализ агентами (LangGraph узлы)
            logger.info("🤖 LangGraph Этап 2: Параллельный анализ агентами")
            
            # Создаем всех агентов
            agents = []
            for agent_type in AgentType:
                agent = LangGraphAgent(agent_type, api_client)
                agents.append(agent)
            
            # Запускаем всех агентов параллельно
            agent_tasks = []
            for agent in agents:
                task = agent.analyze_gifts_node(state)
                agent_tasks.append(task)
            
            # Ждем завершения всех агентов
            agent_results = await asyncio.gather(*agent_tasks, return_exceptions=True)
            
            # Объединяем результаты агентов в единое состояние
            combined_agent_responses = {}
            for i, (agent, result) in enumerate(zip(agents, agent_results)):
                if isinstance(result, Exception):
                    logger.error(f"❌ LangGraph: Ошибка агента {agent.agent_type.value}: {result}")
                    continue
                
                agent_responses = result.get("agent_responses", {})
                combined_agent_responses.update(agent_responses)
            
            # Обновляем состояние с результатами всех агентов
            state = {
                **state,
                "agent_responses": combined_agent_responses
            }
            
            logger.info(f"✅ LangGraph: Получены ответы от {len(combined_agent_responses)} агентов")
            
            # ЭТАП 3: Финальный выбор (LangGraph узел)
            logger.info("🎯 LangGraph Этап 3: Финальный выбор")
            selection_service = LangGraphGiftSelectionService(config)
            final_state = await selection_service.final_selection_node(state)
            
            execution_time = time.time() - start_time
            logger.info(f"⏱️ LangGraph workflow завершен за {execution_time:.2f} секунд")
            
            final_selection = final_state.get("final_selection", [])
            
            if final_selection:
                logger.info("🎉 LangGraph система успешно завершила работу!")
                return final_selection
            else:
                logger.warning("⚠️ LangGraph: Финальный выбор пуст, используем fallback")
                return selection_service._get_fallback_final_selection(state.get("gifts_data", []))
        
    except Exception as e:
        logger.error(f"💥 Критическая ошибка в LangGraph функции: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Возврат экстренного fallback результата
        logger.warning("⚠️ Переключаемся на экстренную резервную систему")
        return [{
            "место": 1,
            "подарок": "Универсальный подарок (экстренный режим)",
            "описание": "Подарок выбран экстренной системой из-за ошибки LangGraph",
            "стоимость": "5000 - 15000",
            "релевантность": 7,
            "средний_балл": 75.0,
            "количество_голосов": 0,
            "выбран_агентами": ["emergency_langgraph_fallback"],
            "детали_оценок": []
        }]

def run_neuro_gift(context: AgentContext) -> List[Dict[str, Any]]:
    """
    Синхронная обертка для LangGraph системы
    """
    try:
        # Валидация входных данных
        PersonInfoModel(info=context.person_info)
        
        # Проверяем, есть ли уже запущенный event loop (как в Jupyter)
        try:
            try:
                loop = asyncio.get_running_loop()
            except:
                pass
            logger.info("🔄 Обнаружен запущенный event loop, используем await")
            
            # Создаем задачу в текущем event loop
            import nest_asyncio
            nest_asyncio.apply()  # Разрешаем вложенные event loops
            
            # Теперь можем использовать asyncio.run
            return asyncio.run(run_neuro_gift_async(context))
            
        except RuntimeError:
            # Event loop не запущен, можем использовать asyncio.run
            logger.info("🆕 Создаем новый event loop для LangGraph")
            return asyncio.run(run_neuro_gift_async(context))
        
    except Exception as e:
        logger.error(f"❌ Ошибка в синхронной LangGraph обертке: {str(e)}")
        return [{
            "место": 1,
            "подарок": "Универсальный подарок",
            "описание": "Подарок выбран в аварийном режиме",
            "стоимость": "5000 - 15000",
            "релевантность": 7,
            "средний_балл": 75.0,
            "количество_голосов": 0,
            "выбран_агентами": ["emergency_wrapper"],
            "детали_оценок": []
        }]

# Альтернативная функция специально для Jupyter с LangGraph
async def run_neuro_gift_jupyter(context: AgentContext) -> List[Dict[str, Any]]:
    """
    Специальная функция для Jupyter Notebook с LangGraph
    Используйте эту функцию с await в Jupyter
    """
    return await run_neuro_gift_async(context)

# Функция для проверки работоспособности LangGraph
# async def test_langgraph_system():
#     """Тестирование LangGraph системы"""
#     test_profile = "Тестовый профиль для проверки системы"
    
#     try:
        
        
        
#         result = await run_neuro_gift_async(test_profile)
#         print("✅ LangGraph система работает корректно")
#         print(f"📊 Получено рекомендаций: {len(result)}")
#         return True
#     except Exception as e:
#         print(f"❌ LangGraph система не работает: {e}")
#         return False

print("✅ Упрощенные главные функции LangGraph системы готовы")
print("💡 Для Jupyter используйте: await run_neuro_gift_jupyter('профиль')")
print("🔗 Упрощенный LangGraph workflow: генерация → агенты (параллельно) → финальный выбор")
print("🧪 Для тестирования: await test_langgraph_system()")

"""
Ячейка 13: LangGraph демонстрация с различными способами ввода профиля
Поддержка интерактивного ввода для Jupyter Notebook
"""

# async def demo_run(person_info: str = None):
#     """
#     Демонстрационный запуск LangGraph системы с интерактивным вводом
    
#     Args:
#         person_info: Информация о человеке (если None, запрашивается ввод)
#     """
    
#     # Если информация не передана, пытаемся получить её от пользователя
#     if person_info is None:
#         print("🎯 ДЕМОНСТРАЦИЯ LANGGRAPH СИСТЕМЫ ВЫБОРА ПОДАРКОВ")
#         print("=" * 60)
#         print("👤 Введите описание человека для подбора подарка")
#         print("💡 Примеры: возраст, пол, город, увлечения, работа, хобби")
#         print("-" * 60)
        
#         try:
#             # Пытаемся получить ввод от пользователя
#             person_info = input("Введите описание человека: ")
            
#             if not person_info or person_info.strip() == "":
#                 print("⚠️ Пустое описание. Используем пример по умолчанию.")
#                 person_info = None
                
#         except (EOFError, KeyboardInterrupt):
#             print("⚠️ Ввод прерван. Используем пример по умолчанию.")
#             person_info = None
#         except Exception as e:
#             print(f"⚠️ Ошибка ввода: {e}. Используем пример по умолчанию.")
#             person_info = None
    
#     # Если всё еще нет информации, используем пример
#     if person_info is None:
#         person_info = """
#         Мужчина 37 лет, проживающий в Москве.
#         Увлекается велосипедом, кино, музыкой.
#         Ходит в спортзал и любит путешествовать.
#         Работает программистом на Java.
#         """
#         print("📝 Используется пример профиля:")
#     else:
#         print("📝 Ваш профиль принят:")
    
#     print(f"👤 {person_info.strip()}")
#     print("=" * 60)
    
#     try:
#         print("\n🚀 ЗАПУСК LANGGRAPH АНАЛИЗА...")
#         print("🔗 Workflow: Генерация → Агенты (параллельно) → Финальный выбор")
#         print("=" * 50)
        
#         # Засекаем время выполнения
#         start_time = time.time()
        
#         # Запуск LangGraph системы
#         final_selection = await run_neuro_gift_async(person_info)
        
#         # Подсчет времени выполнения
#         execution_time = time.time() - start_time
        
#         # Красивое отображение результатов
#         if final_selection:
#             # Создаем демонстрационные данные для форматтера
#             demo_gifts = []
#             for gift in final_selection:
#                 try:
#                     demo_gifts.append(GiftModel(
#                         подарок=gift["подарок"],
#                         описание=gift["описание"],
#                         стоимость=gift["стоимость"],
#                         релевантность=gift["релевантность"],
#                         query=gift["query"]
#                     ))
#                 except:
#                     # Если не получается создать GiftModel, используем словарь
#                     demo_gifts.append(gift)
            
#             # Форматированный вывод
#             formatted_result = ResultFormatter.format_results(final_selection, demo_gifts)
#             print(formatted_result)
            
#             # Статистика выполнения
#             print(f"⏱️ LangGraph время выполнения: {execution_time:.2f} секунд")
#             print(f"🤖 Агентов участвовало: {len(AgentType)}")
#             print(f"🎁 Финальных рекомендаций: {len(final_selection)}")
#             print(f"🔗 LangGraph узлов: {2 + len(AgentType)} (генерация + агенты + финальный выбор)")
            
#         else:
#             print("❌ Не удалось получить рекомендации из LangGraph")
        
#         return final_selection
        
#     except Exception as e:
#         print(f"💥 Ошибка в LangGraph демонстрации: {str(e)}")
#         print("🔧 Проверьте настройки API и установку LangGraph")
#         return []

# async def demo_with_input():
#     """
#     Демонстрация с обязательным запросом ввода профиля
#     """
#     print("🎯 ВВОД ПРОФИЛЯ ДЛЯ LANGGRAPH АНАЛИЗА")
#     print("=" * 50)
#     print("👤 Опишите человека, для которого подбираем подарок:")
#     print("💡 Укажите: возраст, пол, город, работу, увлечения, хобби")
#     print("📝 Пример: 'Женщина 25 лет, живет в Москве, работает врачом, увлекается йогой и чтением'")
#     print("-" * 50)
    
#     max_attempts = 3
#     for attempt in range(max_attempts):
#         try:
#             person_info = input(f"Описание человека (попытка {attempt + 1}/{max_attempts}): ")
            
#             if person_info and person_info.strip():
#                 print(f"\n✅ Принято описание: {person_info.strip()}")
#                 return await demo_run(person_info.strip())
#             else:
#                 print("⚠️ Описание не может быть пустым. Попробуйте еще раз.")
                
#         except (EOFError, KeyboardInterrupt):
#             print(f"\n⚠️ Ввод прерван на попытке {attempt + 1}")
#             if attempt < max_attempts - 1:
#                 print("Попробуем еще раз...")
#                 continue
#             break
#         except Exception as e:
#             print(f"⚠️ Ошибка ввода: {e}")
    
#     print("❌ Не удалось получить описание. Используем пример по умолчанию.")
#     return await demo_run()

# async def demo_multiline_input():
#     """
#     Демонстрация с многострочным вводом профиля
#     """
#     print("🎯 МНОГОСТРОЧНЫЙ ВВОД ПРОФИЛЯ")
#     print("=" * 40)
#     print("👤 Введите подробное описание человека")
#     print("💡 Можете писать в несколько строк")
#     print("✅ Для завершения ввода нажмите Enter на пустой строке")
#     print("-" * 40)
    
#     lines = []
#     line_count = 0
    
#     try:
#         while True:
#             line_count += 1
#             try:
#                 line = input(f"Строка {line_count}: ")
                
#                 if line.strip() == "":
#                     if lines:  # Если уже есть введенные строки
#                         break
#                     else:  # Если это первая пустая строка
#                         print("💡 Начните вводить описание...")
#                         line_count -= 1
#                         continue
                        
#                 lines.append(line)
                
#             except (EOFError, KeyboardInterrupt):
#                 print(f"\n⚠️ Ввод прерван на строке {line_count}")
#                 break
        
#         if lines:
#             person_info = "\n".join(lines)
#             print(f"\n✅ Получено описание ({len(lines)} строк):")
#             print(f"👤 {person_info}")
#             return await demo_run(person_info)
#         else:
#             print("❌ Описание не введено")
            
#     except Exception as e:
#         print(f"💥 Ошибка многострочного ввода: {e}")
    
#     print("🔄 Используем пример по умолчанию")
#     return await demo_run()

# async def demo_preset_choice():
#     """
#     Демонстрация с выбором из готовых профилей или вводом своего
#     """
#     presets = {
#         "1": {
#             "name": "Программист-мужчина 37 лет",
#             "profile": """
#             Мужчина 37 лет, проживающий в Москве.
#             Увлекается велосипедом, кино, музыкой.
#             Ходит в спортзал и любит путешествовать.
#             Работает программистом на Java.
#             """
#         },
#         "2": {
#             "name": "Дизайнер-женщина 28 лет",
#             "profile": """
#             Женщина 28 лет, живет в Санкт-Петербурге.
#             Увлекается йогой, чтением, фотографией.
#             Работает дизайнером, любит искусство и путешествия.
#             """
#         },
#         "3": {
#             "name": "Студент 20 лет",
#             "profile": """
#             Студент 20 лет, учится в университете в Москве.
#             Увлекается спортом, музыкой, компьютерными играми.
#             Любит изучать новые технологии и проводить время с друзьями.
#             """
#         },
#         "4": {
#             "name": "Пенсионер 65 лет",
#             "profile": """
#             Мужчина 65 лет, на пенсии, живет в Екатеринбурге.
#             Увлекается садоводством, чтением, рыбалкой, шахматами.
#             Любит проводить время с внуками и смотреть исторические фильмы.
#             """
#         }
#     }
    
#     print("🎯 ВЫБОР ПРОФИЛЯ ДЛЯ LANGGRAPH АНАЛИЗА")
#     print("=" * 50)
#     print("Выберите вариант:")
    
#     for key, preset in presets.items():
#         print(f"{key}. {preset['name']}")
    
#     print("5. Ввести свой профиль")
#     print("-" * 50)
    
#     try:
#         choice = input("Ваш выбор (1-5): ").strip()
        
#         if choice in presets:
#             selected_preset = presets[choice]
#             print(f"\n✅ Выбран профиль: {selected_preset['name']}")
#             print(f"👤 {selected_preset['profile'].strip()}")
#             return await demo_run(selected_preset['profile'])
            
#         elif choice == "5":
#             print("\n📝 Введите описание человека:")
#             custom_profile = input("Ваш профиль: ")
#             if custom_profile.strip():
#                 return await demo_run(custom_profile.strip())
#             else:
#                 print("⚠️ Пустое описание, используем первый пример")
#                 return await demo_run(presets["1"]["profile"])
#         else:
#             print(f"⚠️ Неверный выбор '{choice}', используем первый пример")
#             return await demo_run(presets["1"]["profile"])
            
#     except Exception as e:
#         print(f"💥 Ошибка выбора: {e}")
#         return await demo_run(presets["1"]["profile"])

# async def quick_demo_async():
#     """Быстрая демонстрация с простым вводом"""
#     print("🚀 БЫСТРАЯ LANGGRAPH ДЕМОНСТРАЦИЯ")
#     print("=" * 50)
    
#     try:
#         person_info = input("👤 Кратко опишите человека: ")
        
#         if not person_info.strip():
#             person_info = """
#             Женщина 28 лет, живет в Санкт-Петербурге.
#             Увлекается йогой, чтением, фотографией.
#             Работает дизайнером, любит искусство и путешествия.
#             """
#             print("⚠️ Используем пример по умолчанию")
        
#         print(f"\n📝 LangGraph анализирует: {person_info.strip()}")
#         print("-" * 50)
        
#         result = await run_neuro_gift_async(person_info)
        
#         print("\n🏆 LANGGRAPH РЕЗУЛЬТАТЫ:")
#         for gift in result:
#             print(f"  🎁 {gift['место']}. {gift['подарок']}")
#             print(f"     💰 {gift['стоимость']}₽")
#             print(f"     ⭐ Оценка: {gift['средний_балл']}/100")
#             print(f"     🤖 Агенты: {', '.join(gift['выбран_агентами'])}")
#             print()
        
#         return result
#     except Exception as e:
#         print(f"❌ Ошибка: {e}")
#         return []

print("✅ LangGraph демонстрационные функции с интерактивным вводом готовы")
print("\n📖 ДОСТУПНЫЕ КОМАНДЫ ДЛЯ ВВОДА ПРОФИЛЯ:")
print("• await demo_run() - с попыткой запроса ввода")
print("• await demo_with_input() - обязательный запрос ввода")
print("• await demo_multiline_input() - многострочный ввод")
print("• await demo_preset_choice() - выбор из готовых профилей или свой ввод")
print("• await quick_demo_async() - быстрый ввод одной строкой")
print("• await demo_run('ваш профиль') - прямая передача профиля")

"""
Ячейка 14: Финальная проверка и инициализация
Проверяем все компоненты системы перед запуском
"""

def system_check():
   """
   Проверка готовности всех компонентов системы
   """
   print("🔍 ПРОВЕРКА ГОТОВНОСТИ СИСТЕМЫ")
   print("=" * 40)
   
   checks_passed = 0
   total_checks = 6
   
   # Проверка 1: API токен
   try:
       config = Configuration.from_env()
       print("✅ 1. API токен найден и загружен")
       print(f"   Модель: {config.model}")
       checks_passed += 1
   except Exception as e:
       print(f"❌ 1. Ошибка API токена: {e}")
       print("   💡 Создайте файл .env с OPEN_API_TOKEN=your_token_here")
   
   # Проверка 2: Импорты библиотек
   try:
       import aiohttp
       import pydantic
       print("✅ 2. Все необходимые библиотеки импортированы")
       checks_passed += 1
   except ImportError as e:
       print(f"❌ 2. Отсутствует библиотека: {e}")
       print("   💡 Установите: pip install aiohttp pydantic python-dotenv")
   
   # Проверка 3: Модели данных
   try:
       test_gift = GiftModel(
           подарок="Тест",
           описание="Тестовое описание",
           стоимость="1000 - 2000",
           релевантность=5
       )
       print("✅ 3. Модели данных работают корректно")
       checks_passed += 1
   except Exception as e:
       print(f"❌ 3. Ошибка моделей данных: {e}")
   
   # Проверка 4: JSON парсер
   try:
       test_json = '{"тест": "значение", "число": 42}'
       parsed = JSONParser.parse_json_response(test_json)
       print("✅ 4. JSON парсер функционирует")
       checks_passed += 1
   except Exception as e:
       print(f"❌ 4. Ошибка JSON парсера: {e}")
   
   # Проверка 5: Типы агентов
   try:
       agents_count = len(AgentType)
       print(f"✅ 5. Определено {agents_count} типов ИИ-агентов")
       checks_passed += 1
   except Exception as e:
       print(f"❌ 5. Ошибка типов агентов: {e}")
   
   # Проверка 6: Промпты
   try:
       test_prompt = PromptTemplate.get_agent_prompt(AgentType.PRAKTIK_BOT, "тест")
       if "JSON" in test_prompt:
           print("✅ 6. Промпты с JSON инструкциями готовы")
           checks_passed += 1
       else:
           print("❌ 6. Промпты не содержат JSON инструкции")
   except Exception as e:
       print(f"❌ 6. Ошибка промптов: {e}")
   
   # Итоговый результат
   print("\n" + "=" * 40)
   if checks_passed == total_checks:
       print("🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! СИСТЕМА ГОТОВА К РАБОТЕ!")
       print("\n🚀 Можете запускать:")
       print("   • await demo_run() - для полной демонстрации")
       print("   • quick_demo() - для быстрого теста")
       return True
   else:
       print(f"⚠️ Пройдено {checks_passed}/{total_checks} проверок")
       print("🔧 Исправьте ошибки перед запуском системы")
       return False

# Создаем глобальную конфигурацию при импорте ячейки
try:
   CONFIG = Configuration.from_env()
   print("✅ Система выбора подарков загружена и готова к работе!")
   print("📖 Запустите system_check() для полной диагностики")
except Exception as e:
   print("⚠️ Система загружена, но требует настройки API токена")
   print(f"   Ошибка: {e}")
   print("📖 Запустите system_check() для диагностики")
   
"""
Ячейка 15: Практический пример использования
Готовый к запуску код для демонстрации системы
"""

# # Сначала проверим готовность системы
# print("🔧 Проверяем готовность системы...")
# system_ready = system_check()

# if system_ready:
#    print("\n" + "🎯 ЗАПУСК ДЕМОНСТРАЦИИ" + "\n" + "=" * 30)
   
#    # Пример 1: Стандартная демонстрация
#    try:
#        # Для Jupyter Notebook используем асинхронный вызов
#        result = await demo_run()
       
#        if result:
#            print("\n✨ ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
#            print(f"📊 Получено {len(result)} рекомендаций")
           
#            # Дополнительная информация о результатах
#            print("\n🎁 КРАТКАЯ СВОДКА:")
#            for gift in result:
#                print(f"  {gift['место']}. {gift['подарок']} - {gift['средний_балл']}/100 баллов")
               
#        else:
#            print("\n⚠️ Демонстрация завершена с ошибками")
           
#    except Exception as e:
#        print(f"\n❌ Ошибка при запуске демонстрации: {e}")
#        print("🔄 Попробуем быструю демонстрацию...")
       
#        # Fallback: синхронная версия
#        fallback_result = quick_demo()
#        if fallback_result:
#            print("✅ Быстрая демонстрация завершена успешно!")

# else:
#    print("\n🛑 СИСТЕМА НЕ ГОТОВА К РАБОТЕ")
#    print("Исправьте ошибки конфигурации и повторите попытку")
   
#    # Попробуем хотя бы показать fallback результат
#    print("\n🔄 Попытка запуска в аварийном режиме...")
#    try:
#        emergency_result = [{
#            "место": 1,
#            "подарок": "Универсальный подарок (аварийный режим)",
#            "описание": "Система работает в ограниченном режиме",
#            "стоимость": "5000 - 15000",
#            "релевантность": 7,
#            "средний_балл": 75.0,
#            "количество_голосов": 0,
#            "выбран_агентами": ["emergency_mode"],
#            "детали_оценок": []
#        }]
#        print("🚨 Аварийный режим активирован - система частично функциональна")
#    except:
#        print("💥 Полный отказ системы")

# print("\n" + "=" * 50)
# print("📝 ИНСТРУКЦИИ ДЛЯ ДАЛЬНЕЙШЕГО ИСПОЛЬЗОВАНИЯ:")
# print("=" * 50)
# print("1. Для анализа своего профиля:")
# print("   await demo_run('ваш профиль здесь')")
# print()
# print("2. Для программного использования:")
# print("   result = await run_neuro_gift_async('профиль')")
# print()
# print("3. Для интеграции в другой код:")
# print("   result = run_neuro_gift('профиль')")
# print()
# print("4. Для настройки параметров:")
# print("   Отредактируйте файл .env или переменные окружения")
# print()
# print("5. Если система не работает:")
# print("   - Проверьте наличие файла .env с OPEN_API_TOKEN")
# print("   - Установите библиотеки: pip install aiohttp pydantic python-dotenv")
# print("   - Запустите system_check() для диагностики")

if __name__ == "__main__":
    
    person_info = """
Мужчина 37 лет, проживающий в Москве.
Увлекается велосипедом, кино, музыкой.
Ходит в спортзал и любит путешествовать.
Работает программистом на Java.
"""
    context = AgentContext()
    context.person_info = person_info
    result = run_neuro_gift(context)
    print(result)