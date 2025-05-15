from PIL import Image

def resize_image(input_path, output_path, width=640, height=360):
    try:
        # Открываем изображение
        img = Image.open(input_path)
        
        # Изменяем размер
        resized_img = img.resize((width, height), Image.LANCZOS)
        
        # Сохраняем результат
        resized_img.save(output_path)
        print(f"Изображение сохранено как {output_path} ({width}x{height}px)")
    
    except Exception as e:
        print(f"Ошибка: {e}")

# Пример использования
resize_image(
    input_path="logo_original.jpg",  # Путь к исходному файлу
    output_path="logo.jpg"               # Путь для сохранения
)
