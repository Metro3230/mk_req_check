import os
from pathlib import Path
import time
from datetime import datetime
from docxtpl import DocxTemplate
import json


script_dir = Path(__file__).parent  # Определяем путь к текущему скрипту
file_path = script_dir / '../template.docx'  # Указываем путь к файлу относительно скрипта
json_file_1 = script_dir / 'dataVTB(newactual).json' 
json_file_2 = script_dir / 'dataAB(newactual).json'  
json_file_3 = script_dir / 'dataVTB(actual).json' 


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




def parce_json_by_column(column_id_to_find, json_data):
    try:
        proj = None  # Инициализируем переменную proj значением None      
        for section in json_data['data']['sections']:
            elements = section.get('elements', [])  # Получаем элементы, если их нет - пустой список
            for item in elements:
                if 'column_id' in item and item['column_id'] == column_id_to_find:
                    value = item['value']
                    # Проверяем, является ли value словарем и содержит ли он ключ 'display_value'
                    if isinstance(value, dict) and 'display_value' in value:
                        proj = value['display_value']
                    else:
                        proj = value  # Присваиваем значение value, если это не словарь
                    break  # Если нашли, то выходим из цикла
                
            if proj is not None:
                break  # Если proj установлен, выходим из внешнего цикла
        
        return proj
    except Exception as e:
        # logging.error(f"функция парсинга и составления сообщения выдала ошибку: {e}")
        pass




def parse(json_data):   #функция парсинга и составления сообщения
    # ID ячеек в S1
    #    156943341307400069 - проект
    #    155931135900001081 - номер заявки 
    #    
    #    155931135900001085 - инфо
    #    163765849995310104 - дедлайн 
    #    
    #    163765531797059074 - Тип склад или сервисная (для ВТБ)
    #    168296787793543524 - тип заявки ВТБ
    #    168296773998887574 - адресс терминала ВТБ
    #    163770345094995261 - номер SUTSPROD ВТБ
    #    
    #    171267113290922982 - адресс АБ
    try:        
        
        proj = parce_json_by_column("156943341307400069", json_data) #  проект 
        req = parce_json_by_column("155931135900001081", json_data) # номер заявки
        info = parce_json_by_column("155931135900001085", json_data)  
        deadline = parce_json_by_column("163765849995310104", json_data) 
        info = 'хз' if info == None else info                   # проверки на ноль
        # deadline = 'хз' if deadline == None else plus_three_hour(deadline)  #если не 0 то +3 часа
        deadline = 'хз' if deadline == None else deadline  # только для отладки (!)

        if proj == 'АО \"АЛЬФА-БАНК\"':                  # ++++++++++-----АБ-------++++++++++++++
            adress = parce_json_by_column("171267113290922982", json_data)            
            adress = 'хз' if adress == None else adress
            new_req_message = ('Новая заявка: ' + req +  ' по ' + proj + '\n'
                    + adress + '\n'
                    + 'До: ' + deadline + '\n'
                    + info)
            return new_req_message

        elif proj == 'Банк ВТБ':
            servis_type = parce_json_by_column("163765531797059074", json_data)   #  склад или сервисная
            if servis_type == 'Сервисные заявки':         # ++++++++++-----ВТБ СЕРВИС-------++++++++++++++
                req_type = parce_json_by_column("168296787793543524", json_data)   #тип заявки ВТБ
                adress = parce_json_by_column("168296773998887574", json_data) 
                req_suts = parce_json_by_column("163770345094995261", json_data) 
                adress = 'хз' if adress == None else adress              # проверки на ноль
                req_suts = 'хз' if req_suts == None else req_suts
                if req_type != 'expertise':                                      # кроме экспертиз
                    new_req_message = ('Новая заявка: ' + req + ' (' + req_suts + ') по ' + proj + '\n'
                            + adress + '\n'
                            + 'До: ' + deadline + '\n'
                            + 'Тип: ' + req_type)
                    return new_req_message

            elif servis_type == 'Складские заявки':         # ++++++++++-----ВТБ СКЛАД-------++++++++++++++
                req_suts = parce_json_by_column("163770345094995261", json_data) 
                req_suts = 'хз' if req_suts == None else req_suts
                new_req_message = ('Новая складская заявка: ' + req + ' по ' + proj + '\n'
                        'Предельный срок: ' + deadline + '\n')
                return new_req_message

            else:                                           # ++++++++++-----ВТБ ХЗ-------++++++++++++++            
                new_req_message = ('Новая заявка: ' + req + '\n'
                        'по ' + proj + '\n'
                        'Информация: ' + info)
                return new_req_message

        else:                                                # ++++++++++-----ОСТАЛЬНОЕ-------++++++++++++++
            new_req_message = ('Новая заявка: ' + req + '\n'
                    'по проекту ' + proj + '\n'
                    'Информация: ' + info)
            return new_req_message
        
    except Exception as e:
        new_req_message = ('Новая заявка: ' + req + '\n'
                'по проекту ' + proj)
        # logging.error(f"функция парсинга и составления сообщения выдала ошибку: {e}")
        print(e)
        return new_req_message

# # Пример использования
# name = "ДОКТОР КРАФТ"
# req = "REQ987654321"
# fill_template(name, req)

# # ОТЛАДКА ФУНКЦИИ ПОИСКА ПАРАМЕТРОВ ПО ID ЯЧЕЙКИ
# column_id = "163770345094995261"
# with open(json_file_1, 'r', encoding='utf-8') as file:
#     json_data_1 = json.load(file)  
# with open(json_file_2, 'r', encoding='utf-8') as file:
#     json_data_2 = json.load(file)  
# print(parce_json_by_column(column_id, json_data_1))
# print(parce_json_by_column(column_id, json_data_2))


# ОТЛАДКА ФУНКЦИИ ПАРСИНГА ЖСОН И СОСТАВЛЕНИЯ СООБЩЕНИЯ
with open(json_file_1, 'r', encoding='utf-8') as file:
    json_data_1 = json.load(file)  
with open(json_file_2, 'r', encoding='utf-8') as file:
    json_data_2 = json.load(file)  
print('________________')
print(parse(json_data_1))
print('________________')
print(parse(json_data_2))
print('________________')




