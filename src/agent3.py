import asyncio
import json
import logging
import os
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from openai import OpenAI

import aiohttp
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

# Настройка русскоязычного логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Вывод в консоль для Jupyter
    ]
)
logger = logging.getLogger(__name__)
logger.info("🚀 Система выбора подарков инициализирована")

# Загружаем переменные окружения
load_dotenv()

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
Ячейка 3: Модели данных с валидацией
Определяем структуры данных с автоматической проверкой корректности
"""

class GiftModel(BaseModel):
    """Модель подарка с валидацией полей"""
    подарок: str = Field(..., min_length=1, description="Название подарка")
    описание: str = Field(..., min_length=1, max_length=500, description="Описание подарка")
    стоимость: str = Field(..., min_length=1, max_length=50, description="Диапазон стоимости")
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
    выбранный_подарок: str = Field(..., min_length=1)
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
    info: str = Field(..., min_length=10, max_length=2000)
    
    @validator('info')
    def validate_person_info(cls, v):
        """Базовая защита от опасного контента"""
        dangerous_patterns = ['<script', 'javascript:', 'eval(', 'exec(', 'import(']
        v_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern in v_lower:
                raise ValueError(f'Обнаружен потенциально опасный контент: {pattern}')
        return v.strip()

print("✅ Модели данных с валидацией созданы")

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
            raise ValueError(f"Некорректный JSON в ответе: {str(e)}")
        except Exception as e:
            logger.error(f"💥 Неожиданная ошибка при парсинге: {str(e)}")
            logger.error(f"🔍 Проблемный ответ: {response[:200]}...")
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
            logger.error(f"🔍 Проблемный ответ: {response}")
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

🔥 АБСОЛЮТНО КРИТИЧНО: Твой ответ должен быть СТРОГО в формате JSON объекта.

Ответь JSON объектом с полями:
{{
  "подарок": "точное название подарка",
  "описание": "краткое описание и обоснование выбора", 
  "стоимость": "диапазон цен в формате 'минимум - максимум'",
  "релевантность": число_от_1_до_10,
  "query" : "ключевые слова для поиска в интернет магазине"
}}

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


Ответь JSON объектом с полями:
{{
 "выбранный_подарок": точное название подарка из списка
 "обоснование": детальное объяснение практической пользы  
 "коэффициент_практической_ценности": число от 0 до 100
 }}
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
{{
  "выбранный_подарок": точное название подарка из списка,
  "обоснование": экономическое обоснование с расчетами,
  "roi_индекс": число коэффициент полезности
}}
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
{{
 "выбранный_подарок": точное название подарка из списка,
 "обоснование": объяснение эмоционального воздействия,
 "степень_восторга_процент": число от 0 до 100
}}
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
{{
 "выбранный_подарок": точное название подарка из списка,
 "обоснование": объяснение универсальности применения,
 "процент_сценариев_использования": число от 0 до 100
}}
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
{{
 "выбранный_подарок": точное название подарка из списка,
 "обоснование": объяснение пользы для профессионального развития,
 "прогноз_роста_ценности_процент": число от 0 до 100
}}
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
Ячейка 7.0 Class для работы с openrouter
"""

class OpenRouterClient:
    def __init__(self, config: Configuration):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        # Семафор ограничивает количество одновременных запросов
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)
        self.logger = logging.getLogger("OpenRouterClient")
        
        self.client = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_token,
        )
    
    async def __aenter__(self):
        print("dumb enter")
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print("dumb exit")
        
    async def make_request(self, prompt: str) -> str:
        async with self._semaphore:
            start_time = time.time()
            for attempt in range(self.config.max_retries):
                try:
                    print(f"Попытка запроса API #{attempt+1}...")
                    completion = self.client.chat.completions.create(
                        extra_headers={
                            "HTTP-Referer": "https://github.com", 
                            "X-Title": "Gift Recommendation Agent", 
                        },
                        #model="qwen/qwen3-235b-a22b:free",
                        model=self.config.model,
                        #"google/gemini-2.5-flash-preview:thinking",
                        #model="deepseek/deepseek-r1",
                        messages=[
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    )
                    
                    # Проверка на наличие ответа
                    if completion and hasattr(completion, 'choices') and completion.choices and hasattr(completion.choices[0], 'message') and completion.choices[0].message and hasattr(completion.choices[0].message, 'content'):
                        answer = completion.choices[0].message.content
                        
                        analysis_time = time.time() - start_time
                        self.logger.info(f"⏱️ OpenRouter запрос завершен за {analysis_time:.2f} секунд")
                        
                        print(f"OpenRouter response: {answer}")
                        return  answer
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
        
        self.logger.info(f"🔄 API запрос, prompt {prompt}")
        
        # Ограничиваем количество одновременных запросов
        async with self._semaphore:
            for attempt in range(self.config.max_retries):
                try:
                    self.logger.info(f"🔄 API запрос {self.config.base_url}")
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
                                self.logger.info(f"✅ Получен ответ {content}")
                                return content
                        
                        self.logger.warning(f"⚠️ API вернул статус {response.status}")
                        
                except asyncio.TimeoutError:
                    self.logger.warning(f"⏰ Таймаут на попытке {attempt + 1}")
                except Exception as e:
                    self.logger.error(f"❌ Ошибка API на попытке {attempt + 1}: {str(e)}")
                
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
Ячейка 8: Окончательно исправленные агенты
Устранены все проблемы с форматированием и парсингом
"""

class Agent(ABC):
    """Абстрактный базовый класс для всех ИИ-агентов"""
    
    def __init__(self, agent_type: AgentType, api_client: OpenRouterClient):
        self.agent_type = agent_type
        self.api_client = api_client
        self.logger = logging.getLogger(f"Agent.{agent_type.value}")
    
    @abstractmethod
    async def analyze_gifts(self, person_info: str, gifts_data: List[GiftModel]) -> AgentResponseModel:
        """Абстрактный метод анализа подарков"""
        pass
    
    def format_gifts_for_prompt(self, gifts: List[GiftModel]) -> str:
        """Форматирование списка подарков для промпта"""
        formatted_text = ""
        for i, gift in enumerate(gifts, 1):
            formatted_text += (
                f"{i}. {gift.подарок} - {gift.описание} - "
                f"Стоимость: {gift.стоимость}₽ - Релевантность: {gift.релевантность}/10\n"
            )
        return formatted_text

class SpecializedAgent(Agent):
    """Специализированный агент с полностью исправленной логикой"""
    
    async def analyze_gifts(self, person_info: str, gifts_data: List[GiftModel]) -> AgentResponseModel:
        """Анализ подарков с исправленной обработкой промптов"""
        try:
            self.logger.info(f"🔍 Запуск анализа агентом {self.agent_type.value}")
            
            # Подготовка данных для промпта
            formatted_gifts = self.format_gifts_for_prompt(gifts_data)
            
            # ИСПРАВЛЕНИЕ: Получаем промпт без вызова .format()
            base_prompt = PromptTemplate.get_agent_prompt(self.agent_type, person_info)
            
            # Заменяем {gifts} на реальные данные о подарках
            prompt = base_prompt.replace("{gifts}", formatted_gifts)
            
            self.logger.info(f"🔍 Отправляем промпт агенту {self.agent_type.value}")
            
            # Выполнение запроса к API
            response = await self.api_client.make_request(prompt)
            
            # ОТЛАДКА: логируем полученный ответ
            self.logger.info(f"🔍 Получен ответ от {self.agent_type.value}: {response[:300]}...")
            
            # Попробуем сначала простую очистку
            cleaned_response = response.strip()
            
            # Если ответ не начинается с {, попробуем найти JSON
            if not cleaned_response.startswith('{'):
                self.logger.warning(f"⚠️ Ответ не начинается с {{, ищем JSON в тексте...")
                
                # Попробуем найти JSON объект в ответе
                start_idx = cleaned_response.find('{')
                end_idx = cleaned_response.rfind('}')
                
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    cleaned_response = cleaned_response[start_idx:end_idx + 1]
                    self.logger.info(f"🔍 Извлечен JSON: {cleaned_response}")
                else:
                    self.logger.error(f"❌ JSON объект не найден в ответе")
                    raise ValueError("JSON объект не найден в ответе")
            
            # Безопасный парсинг JSON ответа
            try:
                parsed_response = JSONParser.parse_json_response(cleaned_response)
            except Exception as parse_error:
                self.logger.error(f"❌ Ошибка парсинга для {self.agent_type.value}: {parse_error}")
                self.logger.error(f"🔍 Пробуем парсить: {cleaned_response[:200]}...")
                raise parse_error
            
            # Валидация ответа через Pydantic модель
            validated_response = AgentResponseModel(**parsed_response)
            
            self.logger.info(f"✅ Агент {self.agent_type.value} выбрал: {validated_response.выбранный_подарок}")
            return validated_response
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка в агенте {self.agent_type.value}: {str(e)}")
            traceback.print_exc()
            # При ошибке возвращаем резервный ответ
            return self._get_fallback_response(gifts_data)
    
    def _get_fallback_response(self, gifts_data: List[GiftModel]) -> AgentResponseModel:
        """Создание резервного ответа при ошибке"""
        if not gifts_data:
            raise ValueError("Нет доступных подарков для создания fallback ответа")
        
        # Выбираем первый подарок как резервный вариант
        fallback_gift = gifts_data[0]
        
        # Резервные ответы для каждого типа агента
        fallback_responses = {
            AgentType.PRAKTIK_BOT: {
                "выбранный_подарок": fallback_gift.подарок,
                "обоснование": "Высокая практическая ценность в повседневной жизни (резервный выбор)",
                "коэффициент_практической_ценности": 75
            },
            AgentType.FIN_EXPERT: {
                "выбранный_подарок": fallback_gift.подарок,
                "обоснование": "Оптимальное соотношение цены и качества (резервный выбор)",
                "roi_индекс": 2.5
            },
            AgentType.WOW_FACTOR: {
                "выбранный_подарок": fallback_gift.подарок,
                "обоснование": "Высокий эмоциональный отклик (резервный выбор)",
                "степень_восторга_процент": 80
            },
            AgentType.UNIVERSAL_GURU: {
                "выбранный_подарок": fallback_gift.подарок,
                "обоснование": "Универсальное применение в различных ситуациях (резервный выбор)",
                "процент_сценариев_использования": 70
            },
            AgentType.SURPRISE_MASTER: {
                "выбранный_подарок": fallback_gift.подарок,
                "обоснование": "Неожиданный и запоминающийся выбор (резервный выбор)",
                "шанс_запомниться_процент": 75
            },
            AgentType.PROF_ROST: {
                "выбранный_подарок": fallback_gift.подарок,
                "обоснование": "Способствует профессиональному развитию (резервный выбор)",
                "прогноз_роста_ценности_процент": 65
            }
        }
        
        self.logger.warning(f"⚠️ Использован резервный ответ для {self.agent_type.value}")
        return AgentResponseModel(**fallback_responses[self.agent_type])

print("✅ Окончательно исправленные классы агентов готовы")

"""
Ячейка 9: Генератор подарков
Создает начальный список подарков на основе информации о человеке
"""

class GiftGenerator:
   """
   Генератор списка подарков на основе информации о человеке
   Использует ИИ для создания персонализированных рекомендаций
   """
   
   def __init__(self, api_client: OpenRouterClient):
       self.api_client = api_client
       self.logger = logging.getLogger("GiftGenerator")
   
   async def generate_gifts(self, person_info: str) -> List[GiftModel]:
       """
       Генерация списка подарков на основе информации о человеке
       
       Args:
           person_info: Информация о человеке (интересы, хобби, работа и т.д.)
           
       Returns:
           Список валидированных моделей подарков
       """
       try:
           self.logger.info("🎁 Начинаем генерацию персонализированного списка подарков")
           
           # Валидация входных данных на предмет безопасности
           validated_person_info = PersonInfoModel(info=person_info)
           
           # Подготовка промпта для генерации подарков
           prompt = PromptTemplate.GIFT_GENERATION_PROMPT.format(
               person_info=validated_person_info.info
           )
           
           # Запрос к ИИ модели
           response = await self.api_client.make_request(prompt)
           
           # Парсинг JSON массива подарков
           gifts_data = JSONParser.parse_json_array(response)
           
           # Валидация каждого подарка через Pydantic
           validated_gifts = []
           for i, gift_data in enumerate(gifts_data):
               try:
                   validated_gift = GiftModel(**gift_data)
                   validated_gifts.append(validated_gift)
               except Exception as e:
                   self.logger.warning(f"⚠️ Подарок #{i+1} не прошел валидацию: {e}")
           
           if not validated_gifts:
               raise ValueError("Ни один подарок не прошел валидацию")
           
           self.logger.info(f"✅ Сгенерировано {len(validated_gifts)} валидных подарков")
           
           # Выводим краткий список для проверки
           print("🎯 Сгенерированные подарки:")
           for i, gift in enumerate(validated_gifts[:5], 1):  # Показываем первые 5
               print(f"  {i}. {gift.подарок} (релевантность: {gift.релевантность}/10)")
           if len(validated_gifts) > 5:
               print(f"  ... и еще {len(validated_gifts) - 5} подарков")
           
           return validated_gifts
           
       except Exception as e:
           self.logger.error(f"❌ Ошибка генерации подарков: {str(e)}")
           self.logger.info("🔄 Переключаемся на резервный список подарков")
           return self._get_fallback_gifts()
   
   def _get_fallback_gifts(self) -> List[GiftModel]:
       """
       Резервный список подарков на случай ошибки ИИ генерации
       
       Returns:
           Список предустановленных подарков
       """
       self.logger.info("📦 Используем предустановленный список подарков")
       
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
           },
           {
               "подарок": "Портативная кофеварка для путешествий",
               "описание": "Практичный подарок для любителя путешествий",
               "стоимость": "3000 - 7000",
               "релевантность": 7
           },
           {
               "подарок": "Книга по новым технологиям Java",
               "описание": "Для профессионального развития программиста",
               "стоимость": "2000 - 10000",
               "релевантность": 8
           },
           {
               "подарок": "Абонемент на массаж",
               "описание": "Отличное дополнение к занятиям в спортзале",
               "стоимость": "5000 - 12000",
               "релевантность": 7
           },
           {
               "подарок": "Компактный внешний аккумулятор",
               "описание": "Пригодится в путешествиях и во время длительных велопрогулок",
               "стоимость": "2000 - 6000",
               "релевантность": 8
           },
           {
               "подарок": "Годовая подписка на стриминговый сервис",
               "описание": "Доступ к фильмам и сериалам для любителя кино",
               "стоимость": "3000 - 7000",
               "релевантность": 8
           },
           {
               "подарок": "Набор для приготовления крафтового пива",
               "описание": "Новое хобби, сочетающееся с любовью к активному образу жизни",
               "стоимость": "5000 - 12000",
               "релевантность": 6
           },
           {
               "подарок": "Подарочный сертификат в магазин велоаксессуаров",
               "описание": "Возможность выбрать нужные комплектующие или аксессуары для велосипеда",
               "стоимость": "3000 - 15000",
               "релевантность": 9
           }
       ]
       
       return [GiftModel(**gift) for gift in fallback_data]

print("✅ Генератор подарков готов к работе")


"""
Ячейка 10: Главный сервис системы
Координирует работу всех агентов и принимает финальное решение
"""

class GiftSelectionService:
   """
   Основной сервис для координации работы ИИ-агентов
   и принятия финального решения о выборе подарков
   """
   
   def __init__(self, config: Configuration):
       self.config = config
       self.logger = logging.getLogger("GiftSelectionService")
   
   async def select_gifts(self, person_info: str) -> List[Dict[str, Any]]:
       """
       Основной метод выбора подарков с использованием множественных ИИ-агентов
       
       Args:
           person_info: Информация о человеке
           
       Returns:
           Список из 2 лучших подарков с рейтингами
       """
       # Используем async context manager для правильного управления HTTP сессией
       async with OpenRouterClient(self.config) as api_client:
           try:
               self.logger.info("🚀 Запуск системы выбора подарков")
               
               # Этап 1: Генерация списка подарков
               self.logger.info("📝 Этап 1: Генерация персонализированного списка подарков")
               gift_generator = GiftGenerator(api_client)
               gifts_data = await gift_generator.generate_gifts(person_info)
               
               # Этап 2: Создание команды ИИ-агентов
               self.logger.info("🤖 Этап 2: Создание команды из 6 специализированных ИИ-агентов")
               agents = [
                   SpecializedAgent(agent_type, api_client)
                   for agent_type in AgentType
               ]
               
               print(f"👥 Агенты готовы к анализу:")
               for agent in agents:
                   print(f"  - {agent.agent_type.value}")
               
               # Этап 3: Параллельный запуск всех агентов (КЛЮЧЕВОЕ УЛУЧШЕНИЕ!)
               self.logger.info("⚡ Этап 3: Параллельный анализ всеми агентами")
               start_time = time.time()
               
               # Создаем задачи для параллельного выполнения
               tasks = [
                   agent.analyze_gifts(person_info, gifts_data)
                   for agent in agents
               ]
               
               # Выполняем все задачи параллельно с обработкой исключений
               agent_responses = await asyncio.gather(*tasks, return_exceptions=True)
               
               analysis_time = time.time() - start_time
               self.logger.info(f"⏱️ Анализ завершен за {analysis_time:.2f} секунд")
               
               # Этап 4: Обработка результатов агентов
               valid_responses = []
               for i, response in enumerate(agent_responses):
                   if isinstance(response, Exception):
                       self.logger.error(f"❌ Агент {agents[i].agent_type.value} вернул ошибку: {response}")
                       continue
                   valid_responses.append((agents[i].agent_type, response))
               
               self.logger.info(f"✅ Получены валидные ответы от {len(valid_responses)}/{len(agents)} агентов")
               
               # Этап 5: Принятие финального решения
               self.logger.info("🎯 Этап 5: Принятие финального решения")
               final_selection = self._select_final_gifts(valid_responses, gifts_data)
               
               self.logger.info("🏆 Система успешно завершила работу!")
               return final_selection
               
           except Exception as e:
               self.logger.error(f"💥 Критическая ошибка в сервисе: {str(e)}")
               self.logger.error(traceback.format_exc())
               return self._get_fallback_final_selection()
   
   def _select_final_gifts(
       self, 
       agent_responses: List[tuple], 
       gifts_data: List[GiftModel]
   ) -> List[Dict[str, Any]]:
       """
       Алгоритм выбора финальных подарков на основе голосов агентов
       
       Args:
           agent_responses: Список кортежей (тип_агента, ответ_агента)
           gifts_data: Исходный список подарков
           
       Returns:
           Топ-2 подарка с детальной информацией
       """
       self.logger.info("🔍 Анализ голосов агентов для принятия решения")
       
       # Словарь для накопления оценок по каждому подарку
       gift_scores = {}
       
       # Обработка голосов каждого агента
       for agent_type, response in agent_responses:
           gift_name = response.выбранный_подарок
           
           # Извлечение численной оценки в зависимости от типа агента
           score = self._extract_score_from_response(agent_type, response)
           
           # Накопление голосов
           if gift_name not in gift_scores:
               gift_scores[gift_name] = []
           gift_scores[gift_name].append((agent_type.value, score))
           
           self.logger.info(f"🗳️ {agent_type.value} выбрал '{gift_name}' с оценкой {score}")
       
       # Расчет средних оценок и статистики
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
       
       # Сортировка по количеству голосов (приоритет) и среднему баллу
       sorted_gifts = sorted(
           average_scores.items(),
           key=lambda x: (x[1]["количество_голосов"], x[1]["средний_балл"]),
           reverse=True
       )
       
       self.logger.info("📊 Результаты голосования:")
       for gift, metrics in sorted_gifts:
           self.logger.info(
               f"  {gift}: {metrics['количество_голосов']} голосов, "
               f"средний балл {metrics['средний_балл']:.1f}"
           )
       
       # Формирование финального списка топ-2
       final_selection = []
       for i, (gift_name, metrics) in enumerate(sorted_gifts[:2]):
           # Поиск детальной информации о подарке
           gift_details = next(
               (gift for gift in gifts_data if gift.подарок == gift_name), 
               None
           )
           
           if gift_details:
               final_selection.append({
                   "место": i + 1,
                   "подарок": gift_name,
                   "описание": gift_details.описание,
                   "стоимость": gift_details.стоимость,
                   "query": gift_details.query,
                   "релевантность": gift_details.релевантность,
                   "средний_балл": round(metrics["средний_балл"], 2),
                   "количество_голосов": metrics["количество_голосов"],
                   "выбран_агентами": metrics["голоса_агентов"],
                   "детали_оценок": metrics["детали_голосов"]
               })
       
       # Дополнение до 2 подарков если необходимо
       if len(final_selection) < 2:
           self._add_backup_gifts(final_selection, gifts_data)
       
       return final_selection
   
   def _extract_score_from_response(self, agent_type: AgentType, response: AgentResponseModel) -> float:
       """
       Извлечение и нормализация численной оценки из ответа агента
       
       Args:
           agent_type: Тип агента
           response: Ответ агента
           
       Returns:
           Нормализованная оценка (0-100)
       """
       score_mapping = {
           AgentType.PRAKTIK_BOT: response.коэффициент_практической_ценности or 0,
           AgentType.FIN_EXPERT: min((response.roi_индекс or 0) * 20, 100),  # Нормализация с ограничением
           AgentType.WOW_FACTOR: response.степень_восторга_процент or 0,
           AgentType.UNIVERSAL_GURU: response.процент_сценариев_использования or 0,
           AgentType.SURPRISE_MASTER: response.шанс_запомниться_процент or 0,
           AgentType.PROF_ROST: response.прогноз_роста_ценности_процент or 0
       }
       return float(score_mapping.get(agent_type, 0))
   
   def _add_backup_gifts(self, final_selection: List[Dict], gifts_data: List[GiftModel]) -> None:
       """Добавление резервных подарков если агенты выбрали менее 2 вариантов"""
       selected_gifts = {item["подарок"] for item in final_selection}
       
       for gift in gifts_data:
           if gift.подарок not in selected_gifts and len(final_selection) < 2:
               final_selection.append({
                   "место": len(final_selection) + 1,
                   "подарок": gift.подарок,
                   "описание": gift.описание,
                   "стоимость": gift.стоимость,
                   "релевантность": gift.релевантность,
                   "средний_балл": 75.0,
                   "количество_голосов": 0,
                   "выбран_агентами": ["автодополнение"],
                   "детали_оценок": []
               })
   
   def _get_fallback_final_selection(self) -> List[Dict[str, Any]]:
       """Экстренный резервный выбор при критических ошибках"""
       self.logger.warning("⚠️ Используем экстренный резервный выбор подарков")
       return [
           {
               "место": 1,
               "подарок": "Фитнес-браслет или умные часы",
               "описание": "Отслеживание тренировок в зале и активности в путешествиях",
               "стоимость": "5000 - 30000",
               "релевантность": 9,
               "средний_балл": 85.0,
               "количество_голосов": 1,
               "выбран_агентами": ["emergency_system"],
               "детали_оценок": [("emergency_system", 85.0)]
           },
           {
               "место": 2,
               "подарок": "Умный велокомпьютер",
               "описание": "Устройство для отслеживания маршрутов, скорости и других показателей во время велопрогулок",
               "стоимость": "6000 - 15000",
               "релевантность": 9,
               "средний_балл": 90.0,
               "количество_голосов": 1,
               "выбран_агентами": ["emergency_system"],
               "детали_оценок": [("emergency_system", 90.0)]
           }
       ]

print("✅ Основной сервис выбора подарков готов")

"""
Ячейка 11: Красивое отображение результатов
Форматирует выходные данные для удобного просмотра в Jupyter
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
       result += "🎁 СИСТЕМА ВЫБОРА ПОДАРКОВ - РЕЗУЛЬТАТЫ АНАЛИЗА\n"
       result += "="*60 + "\n\n"
       
       # Секция 1: Сгенерированный список подарков
       result += "📝 СГЕНЕРИРОВАННЫЙ СПИСОК ПОДАРКОВ:\n"
       result += "-" * 40 + "\n"
       for i, gift in enumerate(gifts_data, 1):
           result += f"{i:2}. {gift.подарок}\n"
           result += f"    💰 {gift.стоимость}₽ | ⭐ {gift.релевантность}/10\n"
       
       result += "\n" + "="*60 + "\n"
       result += "🏆 ФИНАЛЬНЫЕ РЕКОМЕНДАЦИИ ОТ ИИ-АГЕНТОВ\n"
       result += "="*60 + "\n\n"
       
       # Секция 2: Топ рекомендации
       for gift in final_selection:
           result += f"🥇 МЕСТО #{gift['место']}: {gift['подарок']}\n"
           result += "-" * (len(gift['подарок']) + 15) + "\n"
           result += f"📝 Описание: {gift['описание']}\n"
           result += f"💰 Стоимость: {gift['стоимость']}₽\n"
           result += f"⭐ Релевантность: {gift['релевантность']}/10\n"
           result += f"🎯 Средний балл ИИ: {gift['средний_балл']}/100\n"
           result += f"🗳️  Голосов агентов: {gift['количество_голосов']}\n"
           result += f"🤖 Выбрали агенты: {', '.join(gift['выбран_агентами'])}\n"
           
           # Детали оценок если есть
           if gift.get('детали_оценок'):
               result += f"📊 Детальные оценки:\n"
               for agent, score in gift['детали_оценок']:
                   result += f"     • {agent}: {score}\n"
           
           result += "\n"
       
       result += "="*60 + "\n"
       result += "✨ Анализ завершен! Приятного выбора подарка! ✨\n"
       result += "="*60 + "\n"
       
       return result
   
   @staticmethod
   def display_progress(step: str, details: str = ""):
       """Отображение прогресса выполнения"""
       print(f"🔄 {step}")
       if details:
           print(f"   {details}")
   
   @staticmethod
   def display_agent_analysis(agent_type: str, chosen_gift: str, score: float):
       """Отображение результата анализа отдельного агента"""
       print(f"🤖 {agent_type}: выбрал '{chosen_gift}' (оценка: {score:.1f})")

print("✅ Форматтер результатов готов")


"""
Ячейка 12: Основные функции для запуска системы (ИСПРАВЛЕННАЯ ВЕРСИЯ)
Исправлена проблема с event loop в Jupyter Notebook
"""

async def run_neuro_gift_async(person_info: str) -> List[Dict[str, Any]]:
    """
    Асинхронная версия основной функции системы выбора подарков
    
    Args:
        person_info: Информация о человеке для персонализации подарков
        
    Returns:
        Список из 2 лучших подарков с детальной информацией
    """
    try:
        # Создание конфигурации из переменных окружения
        config = Configuration.from_env()
        logger.info(f"🔧 Система инициализирована с моделью: {config.model}")
        
        # Создание и запуск основного сервиса
        service = GiftSelectionService(config)
        
        logger.info("🚀 Запуск системы выбора подарков...")
        logger.info(f"👤 Анализируем профиль: {person_info[:100]}...")
        
        # Выполнение основной логики
        final_selection = await service.select_gifts(person_info)
        
        logger.info("🎉 Система успешно завершила работу!")
        return final_selection
        
    except Exception as e:
        logger.error(f"💥 Критическая ошибка в главной функции: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Возврат экстренного fallback результата
        logger.warning("⚠️ Переключаемся на резервную систему")
        try:
            service = GiftSelectionService(Configuration.from_env())
            return service._get_fallback_final_selection()
        except:
            # Если даже резервная система не работает
            return [{
                "место": 1,
                "подарок": "Универсальный подарок",
                "описание": "Подарок выбран экстренной системой",
                "стоимость": "5000 - 15000",
                "релевантность": 7,
                "средний_балл": 75.0,
                "количество_голосов": 0,
                "выбран_агентами": ["emergency_fallback"],
                "детали_оценок": []
            }]

def run_neuro_gift(person_info: str) -> List[Dict[str, Any]]:
    """
    Синхронная обертка для Jupyter Notebook (ИСПРАВЛЕННАЯ ВЕРСИЯ)
    Правильно работает с уже запущенным event loop
    
    Args:
        person_info: Информация о человеке
        
    Returns:
        Список рекомендованных подарков
    """
    try:
        # Валидация входных данных
        PersonInfoModel(info=person_info)
        
        # Проверяем, есть ли уже запущенный event loop (как в Jupyter)
        try:
            # Если event loop уже запущен, используем create_task
            loop = asyncio.get_running_loop()
            logger.info("🔄 Обнаружен запущенный event loop, используем await")
            
            # Создаем задачу в текущем event loop
            import nest_asyncio
            nest_asyncio.apply()  # Разрешаем вложенные event loops
            
            # Теперь можем использовать asyncio.run
            return asyncio.run(run_neuro_gift_async(person_info))
            
        except RuntimeError:
            # Если event loop не запущен, создаем новый
            logger.info("🆕 Создаем новый event loop")
            return asyncio.run(run_neuro_gift_async(person_info))
        
    except Exception as e:
        logger.error(f"❌ Ошибка в синхронной обертке: {str(e)}")
        # Минимальный fallback для критических ошибок
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

# Альтернативная функция специально для Jupyter
async def run_neuro_gift_jupyter(person_info: str) -> List[Dict[str, Any]]:
    """
    Специальная функция для Jupyter Notebook
    Используйте эту функцию с await в Jupyter
    """
    return await run_neuro_gift_async(person_info)

print("✅ Исправленные главные функции системы готовы к запуску")
#print("💡 Для Jupyter используйте: await run_neuro_gift_jupyter('профиль')")

"""
СТАРАЯ ЯЧЕЙКА !!!! Ячейка 13: Демонстрация работы системы (ИСПРАВЛЕННАЯ ВЕРСИЯ)
Исправлены проблемы с event loop для Jupyter Notebook
"""

async def demo_run(person_info: str = None):
    """
    Демонстрационный запуск системы выбора подарков
    
    Args:
        person_info: Информация о человеке (если не указана, используется пример)
    """
    # Пример информации о человеке для демонстрации
    if person_info is None:
        person_info = """
        Мужчина 37 лет, проживающий в Москве.
        Увлекается велосипедом, кино, музыкой.
        Ходит в спортзал и любит путешествовать.
        Работает программистом на Java.
        """
    
    try:
        print("🎯 ДЕМОНСТРАЦИЯ СИСТЕМЫ ВЫБОРА ПОДАРКОВ")
        print("=" * 50)
        print(f"👤 Профиль для анализа:")
        print(person_info.strip())
        print("\n" + "=" * 50)
        
        # Засекаем время выполнения
        start_time = time.time()
        
        # Запуск основной системы
        final_selection = await run_neuro_gift_async(person_info)
        
        # Подсчет времени выполнения
        execution_time = time.time() - start_time
        
        # Красивое отображение результатов
        if final_selection:
            # Создаем демонстрационные данные для форматтера
            demo_gifts = [
                GiftModel(
                    подарок=gift["подарок"],
                    описание=gift["описание"],
                    стоимость=gift["стоимость"],
                    релевантность=gift["релевантность"]
                )
                for gift in final_selection
            ]
            
            # Форматированный вывод
            formatted_result = ResultFormatter.format_results(final_selection, demo_gifts)
            print(formatted_result)
            
            # Статистика выполнения
            print(f"⏱️ Время выполнения: {execution_time:.2f} секунд")
            print(f"🤖 Агентов участвовало: {len(AgentType)}")
            print(f"🎁 Финальных рекомендаций: {len(final_selection)}")
            
        else:
            print("❌ Не удалось получить рекомендации")
        
        return final_selection
        
    except Exception as e:
        print(f"💥 Ошибка в демонстрации: {str(e)}")
        print("🔧 Проверьте настройки API и попробуйте снова")
        return []

def quick_demo():
    """Быстрая демонстрация для Jupyter Notebook (ИСПРАВЛЕННАЯ ВЕРСИЯ)"""
    person_info = """
    Женщина 28 лет, живет в Санкт-Петербурге.
    Увлекается йогой, чтением, фотографией.
    Работает дизайнером, любит искусство и путешествия.
    """
    
    print("🚀 БЫСТРАЯ ДЕМОНСТРАЦИЯ")
    print("=" * 30)
    
    try:
        # Проверяем, запущен ли event loop
        try:
            loop = asyncio.get_running_loop()
            print("🔄 Jupyter event loop обнаружен, используем асинхронный вызов")
            print("💡 Используйте: await quick_demo_async() вместо quick_demo()")
            
            # Возвращаем инструкцию вместо попытки запуска
            return "Используйте await quick_demo_async() в Jupyter"
            
        except RuntimeError:
            # Event loop не запущен, можем использовать asyncio.run
            result = asyncio.run(run_neuro_gift_async(person_info))
            
            print("🏆 РЕЗУЛЬТАТЫ:")
            for gift in result:
                print(f"  🎁 {gift['место']}. {gift['подарок']}")
                print(f"     💰 {gift['стоимость']}₽")
                print(f"     ⭐ Оценка: {gift['средний_балл']}/100")
                print()
            
            return result
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

async def quick_demo_async():
    """Асинхронная версия быстрой демонстрации для Jupyter"""
    person_info = """
    Женщина 28 лет, живет в Санкт-Петербурге.
    Улекается йогой, чтением, фотографией.
    Работает дизайнером, любит искусство и путешествия.
    """
    
    print("🚀 БЫСТРАЯ АСИНХРОННАЯ ДЕМОНСТРАЦИЯ")
    print("=" * 40)
    
    try:
        result = await run_neuro_gift_async(person_info)
        
        print("🏆 РЕЗУЛЬТАТЫ:")
        for gift in result:
            print(f"  🎁 {gift['место']}. {gift['подарок']}")
            print(f"     💰 {gift['стоимость']}₽")
            print(f"     ⭐ Оценка: {gift['средний_балл']}/100")
            print()
        
        return result
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

# print("✅ Исправленные демонстрационные функции готовы")
# print("\n📖 ИНСТРУКЦИЯ ПО ЗАПУСКУ В JUPYTER:")
# print("1. Для асинхронного запуска: await demo_run()")
# print("2. Для быстрой демонстрации: await quick_demo_async()")
# print("3. Для своих данных: await demo_run('ваша информация о человеке')")


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
        fallback_result = quick_demo()
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