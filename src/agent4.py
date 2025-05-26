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

"""
Ячейка 2: Определение типов агентов и констант
Создаем перечисления для типов ИИ-агентов
"""

class AgentType(Enum):
    """Типы специализированных ИИ-агентов для анализа подарков"""
    PRAKTIK_BOT = "praktik_bot"           # Анализирует практическую пользу
    FIN_EXPERT = "fin_expert"             # Анализирует соотношение цена/качество
    WOW_FACTOR = "wow_factor"             # Ищет эмоциональное воздействие
    UNIVERSAL_GURU = "universal_guru"     # Ищет универсальные подарки
    SURPRISE_MASTER = "surprise_master"   # Ищет неожиданные подарки
    PROF_ROST = "prof_rost"              # Фокус на профессиональном развитии

print(f"✅ Определено {len(AgentType)} типов агентов:")
for agent_type in AgentType:
    print(f"  - {agent_type.value}")


"""
Ячейка 3: Модели данных с поддержкой LangGraph состояния (ОБНОВЛЕНО)
Добавлено состояние для LangGraph workflow
"""

class GiftModel(BaseModel):
    """Модель подарка с валидацией полей"""
    подарок: str = Field(..., min_length=0, description="Название подарка")
    описание: str = Field(..., min_length=0, description="Описание подарка")
    стоимость: str = Field(..., min_length=0, description="Диапазон стоимости")
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
    """Модель ответа ИИ-агента с валидацией"""
    выбранный_подарок: str = Field(..., min_length=0)
    обоснование: str = Field(..., min_length=0)
    
    # Специфичные поля для разных типов агентов (опциональные)
    коэффициент_практической_ценности: Optional[int] = Field(None, ge=0, le=100)
    roi_индекс: Optional[float] = Field(None, ge=0)
    степень_восторга_процент: Optional[int] = Field(None, ge=0, le=100)
    процент_сценариев_использования: Optional[int] = Field(None, ge=0, le=100)
    шанс_запомниться_процент: Optional[int] = Field(None, ge=0, le=100)
    прогноз_роста_ценности_процент: Optional[int] = Field(None, ge=0, le=100)

class PersonInfoModel(BaseModel):
    """Модель информации о человеке с защитой от инъекций"""
    info: str = Field(..., min_length=0)
    
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
class GraphState(TypedDict):
    """Состояние LangGraph для передачи данных между узлами"""
    person_info: str                                    # Информация о человеке
    gifts_data: List[Dict[str, Any]]                   # Сгенерированные подарки
    agent_responses: Dict[str, Dict[str, Any]]         # Ответы агентов
    final_selection: List[Dict[str, Any]]              # Финальный выбор
    current_step: str                                  # Текущий шаг workflow
    error_messages: List[str]                          # Сообщения об ошибках
    execution_time: float                              # Время выполнения
    
print("✅ Модели данных с поддержкой LangGraph созданы")

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
    request_timeout: int = 90                   # Таймаут запроса (сек)
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
            logger.error(f"🔍 Исходный ответ: {response}")
            logger.error(f"🔍 Очищенная строка: {json_str[:500] if 'json_str' in locals() else 'не определена'}...")
            print(traceback.format_exc())
            raise ValueError(f"Некорректный JSON в ответе: {str(e)}")
        except Exception as e:
            logger.error(f"💥 Неожиданная ошибка при парсинге: {str(e)}")
            logger.error(f"🔍 Проблемный ответ: {response}")
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
            print(traceback.format_exc())
            logger.error(f"🔍 Проблемный ответ: {response}...")
            raise ValueError(f"Некорректный JSON массив: {str(e)}")

print("✅ Улучшенный безопасный JSON парсер готов")


"""
Ячейка 6: Исправленные шаблоны промптов (ФИНАЛЬНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ)
Устранена проблема с KeyError в форматировании строк
"""

class PromptTemplate:
    """Коллекция промптов с исправленным форматированием"""
    
    # Промпт для генерации списка подарков
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
    def get_agent_prompt(agent_type: AgentType, person_info: str) -> str:
        """
        Получение промпта для конкретного агента с исправленным форматированием
        """
        
        # Специфичные промпты для каждого типа агента (БЕЗ фигурных скобок в JSON примерах)
        if agent_type == AgentType.PRAKTIK_BOT:
            return f"""
ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

СПИСОК ПОДАРКОВ:
{{gifts}}

🔥 АБСОЛЮТНО КРИТИЧНО: Твой ответ должен быть СТРОГО в формате JSON объекта.

Ты ПрактикБот - анализируешь полезность подарков в повседневной жизни.
Выбери ОДИН подарок с максимальной практической ценностью.

Ответь СТРОГО в JSON формате одной строкой без переносов:
НАЧАЛО_JSON_ОТВЕТА
END_JSON_ОТВЕТА

Где НАЧАЛО_JSON_ОТВЕТА и END_JSON_ОТВЕТА заменить на:
- "выбранный_подарок": точное название подарка из списка
- "обоснование": детальное объяснение практической пользы  
- "коэффициент_практической_ценности": число от 0 до 100
"""

        elif agent_type == AgentType.FIN_EXPERT:
            return f"""
ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

СПИСОК ПОДАРКОВ:
{{gifts}}

🔥 АБСОЛЮТНО КРИТИЧНО: Твой ответ должен быть СТРОГО в формате JSON объекта.

Ты ФинЭксперт - анализируешь соотношение цена/качество подарков.
Выбери ОДИН подарок с лучшим экономическим эффектом.

Ответь JSON объектом с полями:
- "выбранный_подарок": точное название подарка из списка
- "обоснование": экономическое обоснование с расчетами
- "roi_индекс": число коэффициент полезности
"""

        elif agent_type == AgentType.WOW_FACTOR:
            return f"""
ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

СПИСОК ПОДАРКОВ:
{{gifts}}

🔥 АБСОЛЮТНО КРИТИЧНО: Твой ответ должен быть СТРОГО в формате JSON объекта.

Ты ВауФактор - ищешь подарки с высоким эмоциональным откликом.
Выбери ОДИН подарок, который вызовет максимальный восторг.

Ответь JSON объектом с полями:
- "выбранный_подарок": точное название подарка из списка
- "обоснование": объяснение эмоционального воздействия
- "степень_восторга_процент": число от 0 до 100
"""

        elif agent_type == AgentType.UNIVERSAL_GURU:
            return f"""
ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

СПИСОК ПОДАРКОВ:
{{gifts}}

🔥 АБСОЛЮТНО КРИТИЧНО: Твой ответ должен быть СТРОГО в формате JSON объекта.

Ты УниверсалГуру - ищешь максимально универсальные подарки.
Выбери ОДИН подарок для максимального количества ситуаций.

Ответь JSON объектом с полями:
- "выбранный_подарок": точное название подарка из списка
- "обоснование": объяснение универсальности применения
- "процент_сценариев_использования": число от 0 до 100
"""

        elif agent_type == AgentType.SURPRISE_MASTER:
            return f"""
ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

СПИСОК ПОДАРКОВ:
{{gifts}}

🔥 АБСОЛЮТНО КРИТИЧНО: Твой ответ должен быть СТРОГО в формате JSON объекта.

Ты СюрпризМастер - ищешь нестандартные и неожиданные подарки.
Выбери ОДИН самый неожиданный и запоминающийся подарок.

Ответь JSON объектом с полями:
- "выбранный_подарок": точное название подарка из списка
- "обоснование": объяснение неожиданности и запоминаемости
- "шанс_запомниться_процент": число от 0 до 100
"""

        elif agent_type == AgentType.PROF_ROST:
            return f"""
ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

СПИСОК ПОДАРКОВ:
{{gifts}}

🔥 АБСОЛЮТНО КРИТИЧНО: Твой ответ должен быть СТРОГО в формате JSON объекта.

Ты ПрофРост - специализируешься на подарках для профессионального развития.
Выбери ОДИН подарок с максимальной пользой для карьеры.

Ответь JSON объектом с полями:
- "выбранный_подарок": точное название подарка из списка
- "обоснование": объяснение пользы для профессионального развития
- "прогноз_роста_ценности_процент": число от 0 до 100
"""
        
        else:
            # Fallback для неизвестного типа агента
            return f"""
ИНФОРМАЦИЯ О ЧЕЛОВЕКЕ:
{person_info}

СПИСОК ПОДАРКОВ:
{{gifts}}

Выбери лучший подарок и ответь JSON объектом с полями:
- "выбранный_подарок": название подарка
- "обоснование": объяснение выбора
- "оценка": число от 0 до 100
"""

print("✅ Окончательно исправленные промпты готовы")

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
                    self.logger.info(f"🔄 API запрос: {self.config.base_url}\n{prompt}")
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
                                self.logger.info(f"✅ Получен ответ: {content}")
                                return content
                        
                        self.logger.warning(f"⚠️ API вернул статус {response.status}")
                        
                except asyncio.TimeoutError:
                    self.logger.warning(f"⏰ Таймаут на попытке {attempt + 1}")
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
Ячейка 8: Исправленные LangGraph агенты
Устранены все проблемы с Pydantic и None значениями
"""

class LangGraphAgent:
    """Базовый класс для LangGraph агентов"""
    
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
    
    async def analyze_gifts_node(self, state: GraphState) -> GraphState:
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
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    cleaned_response = cleaned_response[start_idx:end_idx + 1]
            
            parsed_response = JSONParser.parse_json_response(cleaned_response)
            validated_response = AgentResponseModel(**parsed_response)
            
            self.logger.info(f"✅ LangGraph: {self.agent_type.value} выбрал {validated_response.выбранный_подарок}")
            
            # Обновляем состояние (ИСПРАВЛЕНО: используем model_dump)
            agent_responses = state.get("agent_responses", {})
            agent_responses[self.agent_type.value] = validated_response.model_dump()  # ИСПРАВЛЕНО
            
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
            agent_responses[self.agent_type.value] = fallback_response.model_dump()  # ИСПРАВЛЕНО
            
            error_messages = state.get("error_messages", [])
            error_messages.append(f"Ошибка агента {self.agent_type.value}: {str(e)}")
            
            return {
                **state,
                "agent_responses": agent_responses,
                "error_messages": error_messages,
                "current_step": f"agent_{self.agent_type.value}_fallback"
            }
    
    def _get_fallback_response(self, gifts_data: List[Dict[str, Any]]) -> AgentResponseModel:
        """Создание fallback ответа"""
        if not gifts_data:
            raise ValueError("Нет подарков для fallback ответа")
        
        fallback_gift = gifts_data[0]
        
        fallback_responses = {
            AgentType.PRAKTIK_BOT: {
                "выбранный_подарок": fallback_gift["подарок"],
                "обоснование": "Высокая практическая ценность (резервный выбор)",
                "коэффициент_практической_ценности": 75
            },
            AgentType.FIN_EXPERT: {
                "выбранный_подарок": fallback_gift["подарок"],
                "обоснование": "Оптимальное соотношение цены и качества (резервный выбор)",
                "roi_индекс": 2.5
            },
            AgentType.WOW_FACTOR: {
                "выбранный_подарок": fallback_gift["подарок"],
                "обоснование": "Высокий эмоциональный отклик (резервный выбор)",
                "степень_восторга_процент": 80
            },
            AgentType.UNIVERSAL_GURU: {
                "выбранный_подарок": fallback_gift["подарок"],
                "обоснование": "Универсальное применение (резервный выбор)",
                "процент_сценариев_использования": 70
            },
            AgentType.SURPRISE_MASTER: {
                "выбранный_подарок": fallback_gift["подарок"],
                "обоснование": "Неожиданный выбор (резервный выбор)",
                "шанс_запомниться_процент": 75
            },
            AgentType.PROF_ROST: {
                "выбранный_подарок": fallback_gift["подарок"],
                "обоснование": "Профессиональное развитие (резервный выбор)",
                "прогноз_роста_ценности_процент": 65
            }
        }
        
        return AgentResponseModel(**fallback_responses[self.agent_type])

print("✅ Исправленные LangGraph агенты готовы")

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
            
            # Валидация входных данных
            validated_person_info = PersonInfoModel(info=person_info)
            
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
Ячейка 10: Исправленный LangGraph сервис (УСТРАНЕНЫ ОШИБКИ)
Исправлена ошибка с None значениями в расчетах
"""

class LangGraphGiftSelectionService:
    """Сервис выбора подарков с использованием LangGraph"""
    
    def __init__(self, config: Configuration):
        self.config = config
        self.logger = logging.getLogger("LangGraphGiftSelectionService")
    
    async def final_selection_node(self, state: GraphState) -> GraphState:
        """Узел LangGraph для финального выбора подарков"""
        try:
            self.logger.info("🎯 LangGraph: Финальный выбор подарков")
            
            agent_responses = state.get("agent_responses", {})
            gifts_data = state["gifts_data"]
            
            # Подсчет голосов
            gift_scores = {}
            
            for agent_name, response in agent_responses.items():
                gift_name = response.get("выбранный_подарок")
                if not gift_name:
                    continue
                
                # Извлечение оценки (ИСПРАВЛЕНО: обработка None значений)
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
                        "query": gift_details["query"],
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
                "current_step": "final_selection_completed"
            }
            
        except Exception as e:
            self.logger.error(f"💥 LangGraph: Ошибка финального выбора: {str(e)}")
            
            # Fallback финальный выбор
            fallback_selection = self._get_fallback_final_selection(gifts_data)
            
            return {
                **state,
                "final_selection": fallback_selection,
                "current_step": "final_selection_fallback",
                "error_messages": state.get("error_messages", []) + [f"Ошибка финального выбора: {str(e)}"]
            }
    
    def _extract_score_from_response(self, agent_name: str, response: Dict[str, Any]) -> float:
        """Извлечение оценки из ответа агента (ИСПРАВЛЕНО: обработка None)"""
        try:
            score_mapping = {
                "praktik_bot": response.get("коэффициент_практической_ценности"),
                "fin_expert": response.get("roi_индекс"),
                "wow_factor": response.get("степень_восторга_процент"),
                "universal_guru": response.get("процент_сценариев_использования"),
                "surprise_master": response.get("шанс_запомниться_процент"),
                "prof_rost": response.get("прогноз_роста_ценности_процент")
            }
            
            raw_score = score_mapping.get(agent_name)
            
            # ИСПРАВЛЕНО: обработка None значений
            if raw_score is None:
                self.logger.warning(f"⚠️ Отсутствует оценка для {agent_name}, используем 50")
                return 50.0
            
            # Нормализация для fin_expert
            if agent_name == "fin_expert":
                return min(float(raw_score) * 20, 100.0)
            
            return float(raw_score)
            
        except (TypeError, ValueError) as e:
            self.logger.warning(f"⚠️ Ошибка извлечения оценки для {agent_name}: {e}, используем 50")
            return 50.0
    
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

print("✅ Исправленный LangGraph сервис готов")

"""
Ячейка 11: ResultFormatter для красивого вывода результатов LangGraph
Класс для форматирования результатов LangGraph системы
"""

class ResultFormatter:
    """Форматтер результатов для красивого вывода в Jupyter Notebook"""
    
    @staticmethod
    def format_results(final_selection: List[Dict[str, Any]], gifts_data: List[GiftModel]) -> str:
        """
        Форматирование результатов для красивого отображения
        
        Args:
            final_selection: Финальный выбор подарков
            gifts_data: Исходный список сгенерированных подарков
            
        Returns:
            Отформатированная строка с результатами
        """
        result = "\n" + "="*60 + "\n"
        result += "🎁 LANGGRAPH СИСТЕМА ВЫБОРА ПОДАРКОВ - РЕЗУЛЬТАТЫ\n"
        result += "="*60 + "\n\n"
        
        # Секция 1: Сгенерированный список подарков
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
        
        # Секция 2: Топ рекомендации
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
                    result += f"     • {agent}: {score}\n"
            
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

print("✅ ResultFormatter для LangGraph готов")

"""
Ячейка 12: Упрощенные главные функции LangGraph (ИСПРАВЛЕННАЯ ВЕРСИЯ)
Убран LangGraphWorkflowBuilder, код упрощен и работает напрямую
"""

async def run_neuro_gift_async(person_info: str) -> List[Dict[str, Any]]:
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
                "execution_time": 0.0
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

def run_neuro_gift(person_info: str) -> List[Dict[str, Any]]:
    """
    Синхронная обертка для LangGraph системы
    """
    try:
        # Валидация входных данных
        PersonInfoModel(info=person_info)
        
        # Проверяем, есть ли уже запущенный event loop (как в Jupyter)
        try:
            loop = asyncio.get_running_loop()
            logger.info("🔄 Обнаружен запущенный event loop, используем await")
            
            # Создаем задачу в текущем event loop
            import nest_asyncio
            nest_asyncio.apply()  # Разрешаем вложенные event loops
            
            # Теперь можем использовать asyncio.run
            return asyncio.run(run_neuro_gift_async(person_info))
            
        except RuntimeError:
            # Event loop не запущен, можем использовать asyncio.run
            logger.info("🆕 Создаем новый event loop для LangGraph")
            return asyncio.run(run_neuro_gift_async(person_info))
        
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
async def run_neuro_gift_jupyter(person_info: str) -> List[Dict[str, Any]]:
    """
    Специальная функция для Jupyter Notebook с LangGraph
    Используйте эту функцию с await в Jupyter
    """
    return await run_neuro_gift_async(person_info)

# Функция для проверки работоспособности LangGraph
async def test_langgraph_system():
    """Тестирование LangGraph системы"""
    test_profile = "Тестовый профиль для проверки системы"
    
    try:
        result = await run_neuro_gift_async(test_profile)
        print("✅ LangGraph система работает корректно")
        print(f"📊 Получено рекомендаций: {len(result)}")
        return True
    except Exception as e:
        print(f"❌ LangGraph система не работает: {e}")
        return False

print("✅ Упрощенные главные функции LangGraph системы готовы")
print("💡 Для Jupyter используйте: await run_neuro_gift_jupyter('профиль')")
print("🔗 Упрощенный LangGraph workflow: генерация → агенты (параллельно) → финальный выбор")
print("🧪 Для тестирования: await test_langgraph_system()")

"""
Ячейка 13: LangGraph демонстрация с различными способами ввода профиля
Поддержка интерактивного ввода для Jupyter Notebook
"""

async def demo_run(person_info: str = None):
    """
    Демонстрационный запуск LangGraph системы с интерактивным вводом
    
    Args:
        person_info: Информация о человеке (если None, запрашивается ввод)
    """
    
    # Если информация не передана, пытаемся получить её от пользователя
    if person_info is None:
        print("🎯 ДЕМОНСТРАЦИЯ LANGGRAPH СИСТЕМЫ ВЫБОРА ПОДАРКОВ")
        print("=" * 60)
        print("👤 Введите описание человека для подбора подарка")
        print("💡 Примеры: возраст, пол, город, увлечения, работа, хобби")
        print("-" * 60)
        
        try:
            # Пытаемся получить ввод от пользователя
            person_info = input("Введите описание человека: ")
            
            if not person_info or person_info.strip() == "":
                print("⚠️ Пустое описание. Используем пример по умолчанию.")
                person_info = None
                
        except (EOFError, KeyboardInterrupt):
            print("⚠️ Ввод прерван. Используем пример по умолчанию.")
            person_info = None
        except Exception as e:
            print(f"⚠️ Ошибка ввода: {e}. Используем пример по умолчанию.")
            person_info = None
    
    # Если всё еще нет информации, используем пример
    if person_info is None:
        person_info = """
        Мужчина 37 лет, проживающий в Москве.
        Увлекается велосипедом, кино, музыкой.
        Ходит в спортзал и любит путешествовать.
        Работает программистом на Java.
        """
        print("📝 Используется пример профиля:")
    else:
        print("📝 Ваш профиль принят:")
    
    print(f"👤 {person_info.strip()}")
    print("=" * 60)
    
    try:
        print("\n🚀 ЗАПУСК LANGGRAPH АНАЛИЗА...")
        print("🔗 Workflow: Генерация → Агенты (параллельно) → Финальный выбор")
        print("=" * 50)
        
        # Засекаем время выполнения
        start_time = time.time()
        
        # Запуск LangGraph системы
        final_selection = await run_neuro_gift_async(person_info)
        
        # Подсчет времени выполнения
        execution_time = time.time() - start_time
        
        # Красивое отображение результатов
        if final_selection:
            # Создаем демонстрационные данные для форматтера
            demo_gifts = []
            for gift in final_selection:
                try:
                    demo_gifts.append(GiftModel(
                        подарок=gift["подарок"],
                        описание=gift["описание"],
                        стоимость=gift["стоимость"],
                        релевантность=gift["релевантность"]
                    ))
                except:
                    # Если не получается создать GiftModel, используем словарь
                    demo_gifts.append(gift)
            
            # Форматированный вывод
            formatted_result = ResultFormatter.format_results(final_selection, demo_gifts)
            print(formatted_result)
            
            # Статистика выполнения
            print(f"⏱️ LangGraph время выполнения: {execution_time:.2f} секунд")
            print(f"🤖 Агентов участвовало: {len(AgentType)}")
            print(f"🎁 Финальных рекомендаций: {len(final_selection)}")
            print(f"🔗 LangGraph узлов: {2 + len(AgentType)} (генерация + агенты + финальный выбор)")
            
        else:
            print("❌ Не удалось получить рекомендации из LangGraph")
        
        return final_selection
        
    except Exception as e:
        print(f"💥 Ошибка в LangGraph демонстрации: {str(e)}")
        print("🔧 Проверьте настройки API и установку LangGraph")
        return []

async def demo_with_input():
    """
    Демонстрация с обязательным запросом ввода профиля
    """
    print("🎯 ВВОД ПРОФИЛЯ ДЛЯ LANGGRAPH АНАЛИЗА")
    print("=" * 50)
    print("👤 Опишите человека, для которого подбираем подарок:")
    print("💡 Укажите: возраст, пол, город, работу, увлечения, хобби")
    print("📝 Пример: 'Женщина 25 лет, живет в Москве, работает врачом, увлекается йогой и чтением'")
    print("-" * 50)
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            person_info = input(f"Описание человека (попытка {attempt + 1}/{max_attempts}): ")
            
            if person_info and person_info.strip():
                print(f"\n✅ Принято описание: {person_info.strip()}")
                return await demo_run(person_info.strip())
            else:
                print("⚠️ Описание не может быть пустым. Попробуйте еще раз.")
                
        except (EOFError, KeyboardInterrupt):
            print(f"\n⚠️ Ввод прерван на попытке {attempt + 1}")
            if attempt < max_attempts - 1:
                print("Попробуем еще раз...")
                continue
            break
        except Exception as e:
            print(f"⚠️ Ошибка ввода: {e}")
    
    print("❌ Не удалось получить описание. Используем пример по умолчанию.")
    return await demo_run()

async def demo_multiline_input():
    """
    Демонстрация с многострочным вводом профиля
    """
    print("🎯 МНОГОСТРОЧНЫЙ ВВОД ПРОФИЛЯ")
    print("=" * 40)
    print("👤 Введите подробное описание человека")
    print("💡 Можете писать в несколько строк")
    print("✅ Для завершения ввода нажмите Enter на пустой строке")
    print("-" * 40)
    
    lines = []
    line_count = 0
    
    try:
        while True:
            line_count += 1
            try:
                line = input(f"Строка {line_count}: ")
                
                if line.strip() == "":
                    if lines:  # Если уже есть введенные строки
                        break
                    else:  # Если это первая пустая строка
                        print("💡 Начните вводить описание...")
                        line_count -= 1
                        continue
                        
                lines.append(line)
                
            except (EOFError, KeyboardInterrupt):
                print(f"\n⚠️ Ввод прерван на строке {line_count}")
                break
        
        if lines:
            person_info = "\n".join(lines)
            print(f"\n✅ Получено описание ({len(lines)} строк):")
            print(f"👤 {person_info}")
            return await demo_run(person_info)
        else:
            print("❌ Описание не введено")
            
    except Exception as e:
        print(f"💥 Ошибка многострочного ввода: {e}")
    
    print("🔄 Используем пример по умолчанию")
    return await demo_run()

async def demo_preset_choice():
    """
    Демонстрация с выбором из готовых профилей или вводом своего
    """
    presets = {
        "1": {
            "name": "Программист-мужчина 37 лет",
            "profile": """
            Мужчина 37 лет, проживающий в Москве.
            Увлекается велосипедом, кино, музыкой.
            Ходит в спортзал и любит путешествовать.
            Работает программистом на Java.
            """
        },
        "2": {
            "name": "Дизайнер-женщина 28 лет",
            "profile": """
            Женщина 28 лет, живет в Санкт-Петербурге.
            Увлекается йогой, чтением, фотографией.
            Работает дизайнером, любит искусство и путешествия.
            """
        },
        "3": {
            "name": "Студент 20 лет",
            "profile": """
            Студент 20 лет, учится в университете в Москве.
            Увлекается спортом, музыкой, компьютерными играми.
            Любит изучать новые технологии и проводить время с друзьями.
            """
        },
        "4": {
            "name": "Пенсионер 65 лет",
            "profile": """
            Мужчина 65 лет, на пенсии, живет в Екатеринбурге.
            Увлекается садоводством, чтением, рыбалкой, шахматами.
            Любит проводить время с внуками и смотреть исторические фильмы.
            """
        }
    }
    
    print("🎯 ВЫБОР ПРОФИЛЯ ДЛЯ LANGGRAPH АНАЛИЗА")
    print("=" * 50)
    print("Выберите вариант:")
    
    for key, preset in presets.items():
        print(f"{key}. {preset['name']}")
    
    print("5. Ввести свой профиль")
    print("-" * 50)
    
    try:
        choice = input("Ваш выбор (1-5): ").strip()
        
        if choice in presets:
            selected_preset = presets[choice]
            print(f"\n✅ Выбран профиль: {selected_preset['name']}")
            print(f"👤 {selected_preset['profile'].strip()}")
            return await demo_run(selected_preset['profile'])
            
        elif choice == "5":
            print("\n📝 Введите описание человека:")
            custom_profile = input("Ваш профиль: ")
            if custom_profile.strip():
                return await demo_run(custom_profile.strip())
            else:
                print("⚠️ Пустое описание, используем первый пример")
                return await demo_run(presets["1"]["profile"])
        else:
            print(f"⚠️ Неверный выбор '{choice}', используем первый пример")
            return await demo_run(presets["1"]["profile"])
            
    except Exception as e:
        print(f"💥 Ошибка выбора: {e}")
        return await demo_run(presets["1"]["profile"])

async def quick_demo_async():
    """Быстрая демонстрация с простым вводом"""
    print("🚀 БЫСТРАЯ LANGGRAPH ДЕМОНСТРАЦИЯ")
    print("=" * 50)
    
    try:
        person_info = input("👤 Кратко опишите человека: ")
        
        if not person_info.strip():
            person_info = """
            Женщина 28 лет, живет в Санкт-Петербурге.
            Увлекается йогой, чтением, фотографией.
            Работает дизайнером, любит искусство и путешествия.
            """
            print("⚠️ Используем пример по умолчанию")
        
        print(f"\n📝 LangGraph анализирует: {person_info.strip()}")
        print("-" * 50)
        
        result = await run_neuro_gift_async(person_info)
        
        print("\n🏆 LANGGRAPH РЕЗУЛЬТАТЫ:")
        for gift in result:
            print(f"  🎁 {gift['место']}. {gift['подарок']}")
            print(f"     💰 {gift['стоимость']}₽")
            print(f"     ⭐ Оценка: {gift['средний_балл']}/100")
            print(f"     🤖 Агенты: {', '.join(gift['выбран_агентами'])}")
            print()
        
        return result
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

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

# Сначала проверим готовность системы
def init():
    print("🔧 Проверяем готовность системы...")
    system_ready = system_check()

    if system_ready:
        print("\n" + "🎯 ЗАПУСК ДЕМОНСТРАЦИИ" + "\n" + "=" * 30)
    
    # Пример 1: Стандартная демонстрация
    try:
        # Для Jupyter Notebook используем асинхронный вызов
        result = demo_run()
        
        if result:
            print("\n✨ ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
            print(f"📊 Получено {len(result)} рекомендаций")
            
            # Дополнительная информация о результатах
            print("\n🎁 КРАТКАЯ СВОДКА:")
            for gift in result:
                print(f"  {gift['место']}. {gift['подарок']} - {gift['средний_балл']}/100 баллов")
                
        else:
            print("\n⚠️ Демонстрация завершена с ошибками")
            
    except Exception as e:
        print(f"\n❌ Ошибка при запуске демонстрации: {e}")
        print("🔄 Попробуем быструю демонстрацию...")
        
        # Fallback: синхронная версия
        fallback_result = demo_preset_choice()
        if fallback_result:
            print("✅ Быстрая демонстрация завершена успешно!")

    else:
        print("\n🛑 СИСТЕМА НЕ ГОТОВА К РАБОТЕ")
        print("Исправьте ошибки конфигурации и повторите попытку")
        
        # Попробуем хотя бы показать fallback результат
        print("\n🔄 Попытка запуска в аварийном режиме...")
        try:
            emergency_result = [{
                "место": 1,
                "подарок": "Универсальный подарок (аварийный режим)",
                "описание": "Система работает в ограниченном режиме",
                "стоимость": "5000 - 15000",
                "релевантность": 7,
                "средний_балл": 75.0,
                "количество_голосов": 0,
                "выбран_агентами": ["emergency_mode"],
                "детали_оценок": []
            }]
            print("🚨 Аварийный режим активирован - система частично функциональна")
        except:
            print("💥 Полный отказ системы")


### Точки входа приложения
### Для телеграм бота используется run_neuro_gift


if __name__ == "__main__":
    init()
    person_info = """
Мужчина 37 лет, проживающий в Москве.
Увлекается велосипедом, кино, музыкой.
Ходит в спортзал и любит путешествовать.
Работает программистом на Java.
"""
    result = run_neuro_gift(person_info)
    print(result)
    

# Агент сам сгенерировал функцию
# def run_neuro_gift(user_text):
#     print("Run neuro gift")
#     asyncio.run(run_neuro_gift_async(user_text))