import os
from pathlib import Path
import time
from datetime import datetime
from docxtpl import DocxTemplate


script_dir = Path(__file__).parent  # Определяем путь к текущему скрипту
file_path = script_dir / 'data/template.docx'  # Указываем путь к файлу относительно скрипта


def fill_template(req, name, adress):
    # Загружаем шаблон документа
    template = DocxTemplate(file_path)
    
    # Данные для замены в шаблоне
    context = {
        'req': req,
        'name': name,
        'full_name': 'РОГИ И КОПЫТА НА УЛИЦЕ СЕЗАМ',
        'adress': 'улимца сезам',
        'tid': '456789123',
    }
    
    # Заполняем шаблон данными
    template.render(context)
    
    # Сохраняем новый документ
    output_filename = f"{req}.docx"
    template.save(output_filename)
    
    print(f"Документ сохранен как {output_filename}")

# Пример использования
name = "ДОКТОР КРАФТ"
req = "REQ987654321"
fill_template(name, req)
