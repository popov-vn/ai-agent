import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import re

def get_ozon_price_range(product_name):
    # Настройка Selenium
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get("https://www.ozon.ru/")
        time.sleep(3)  # Ожидание загрузки
        
        # Ждем появления поисковой строки (несколько возможных селекторов)
        try:
            # search_box = WebDriverWait(driver, 10).until(
            #     EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[name='text'], input.search-input"))
            # )
            search_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Искать') or contains(@placeholder, 'Search')]"))
            )
        except:
            return "Не удалось найти поисковую строку. Ozon изменил структуру страницы."
        
        search_box.clear()
        search_box.send_keys(product_name)
        search_box.send_keys(Keys.RETURN)
        time.sleep(5)  # Ожидание результатов
        
        # Прокрутка страницы для загрузки всех товаров
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Парсинг цен
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        prices = []
        
        # Ozon использует разные классы для цен, попробуем несколько вариантов
        price_selectors = [
            'span[class*="price"]',  # Стандартный класс
            'div[class*="price"]',   # Альтернативный вариант
            'span[data-widget="webPrice"]',  # Динамический виджет
        ]
        
        for selector in price_selectors:
            for el in soup.select(selector):
                price_text = el.get_text().replace('\u2009', '').replace('₽', '').strip()
                if price_text and re.match(r'^[\d\s,.]+$', price_text):
                    price = float(price_text.replace(' ', '').replace(',', '.'))
                    prices.append(price)
        
        if not prices:
            return "Цены не найдены. Возможно, товар отсутствует или изменилась структура страницы."
        
        min_price = min(prices)
        max_price = max(prices)
        
        return f"Диапазон цен на '{product_name}': от {min_price} ₽ до {max_price} ₽"
    
    except Exception as e:
        return f"Произошла ошибка: {str(e)}"
    finally:
        driver.quit()

if __name__ == "__main__":
    product = input("Введите название товара для поиска на Ozon: ")
    print(get_ozon_price_range(product))