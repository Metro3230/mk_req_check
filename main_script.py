import pandas as pd
import requests
import json
import logging
import telebot
from telebot import types
import schedule
import time
from datetime import datetime, timedelta
from pathlib import Path
import os
from docxtpl import DocxTemplate
from dotenv import load_dotenv
import re
import shutil


script_dir = Path(__file__).parent  # Определяем путь к текущему скрипту
data_folder = script_dir / 'data'
data_zip = script_dir / 'data.zip'
log_file = script_dir / 'data/log.log'
bearer_file = script_dir / 'data/Bearer.txt'
ids_file = script_dir / 'data/tg_ids.txt'
arch_xl_table = script_dir / 'data/req_archive.xlsx'   #архив заявок. что бы найти -новые- (прошлая актуальная до нахождения новых)
actual_table = script_dir / 'data/actual_table.xlsx'           # актуальная табличка ексель--
service_pass = script_dir / 'data/service_pass.txt'
template = script_dir / 'data/template.docx'  # шаблон АВР
instruction = script_dir / 'data/instruction.JPG'  # картинка инструкции
env_file = script_dir / 'data/.env'    # файл секретиков )))

load_dotenv(env_file)

logging.basicConfig(level=logging.INFO, filename=log_file, format='%(asctime)s - %(levelname)s - %(message)s')

last_update_id = os.getenv('LAST_UPDATE_ID')
url_condition = os.getenv('DW_URL_CONDITION')
tgtoken = os.getenv('TG_TOKEN')    # читаем token tg
bot = telebot.TeleBot(tgtoken)

access_token = os.getenv('MK_BEARER')    # читаем Bearer токен из файла
headers = {
    'Authorization': f'Bearer {access_token}'  # Используем Bearer-токен в хеадерсе запроса
}

user_id = '170800459101114407'
url_export_excel = f'https://sd.servionica.ru/v1/exports?userId={user_id}'
url_delete_excel = 'https://sd.servionica.ru/v1/exports/delete'
url_download_excel = 'https://sd.servionica.ru/v1/exports/download-url'

payload_export_excel = {
	"export": {
		"condition": f"{url_condition}",
		"type": "excel",
		"tableName": "itsm_task",
		"columns": [
			"number",
			"short_description",
			"multicard_request_type",
			"state",
			"sys_created_at",
			"deadline",
			"multicard_closing_date",
			"multicard_terminal_address",
			"multicard_comment_ing",
			"multicard_pos",
			"multicard_pin_pad",
			"multicard_id_terminal",
			"multicard_return_number_pos",
			"multicard_return_number_pin",
			"multicard_terminal_vendor_pos",
			"multicard_name_client",
			"description",
			"multicard_additional_information",
			"multicard_engineer.c_fio",
			"ab_terminal_actual_address",
			"ab_spot_address",
			"resolved_at",
			"assigned_user.c_fio",
			"ab_terminal_ucstid",
			"closure_notes"
		],
	},
	"confirmExportLimitExceeded": "0",
	"userId": f"{user_id}"
}



def scheduled_messages(param=None):       # >-скрипт проверки новых заявок каждые х минут-<
    current_time = datetime.now().time()
    if (current_time >= datetime.strptime("07:00", "%H:%M").time() and current_time <= datetime.strptime("22:00", "%H:%M").time()) or param == 'exc':   #если день или передан параметр exc
        dw_actual_table()
        new_reqs_df = search_new_req()
        for req in new_reqs_df['Номер']:    # --цикл, пробегающийся по всем значениям столбца "номер" --
            try:
                json_data, req_ID = gat_req_data(req)
                msg = parse(json_data)
                if msg != None:
                    new_req(msg, req_ID)
            except:
                new_req('есть какя-то новая заявка, но не удалось загрузить инфу..', 000)
        update_archive()
        check_SLA()


def check_SLA():       # >-скрипт проверки истечения времени-<
    df = pd.read_excel(actual_table)    # Загрузка таблицы
    current_time = datetime.now()    # Получение текущего времени
    for index, row in df.iterrows():    # Перебор строк с проверкой условий
        deadline = pd.to_datetime(row['Предельный срок'], format='%Y-%m-%d %H:%M:%S')
        status = row['Статус']
        req_type = row['Тип заявки']
        req_num = row['Номер']
        if (current_time <= deadline < current_time + timedelta(hours=1)) and status != "on_hold" and req_type != "expertise":        # Проверка условий: срок истекает менее чем через час и статус подходящий            
            with open(ids_file, 'r') as f:    # Читаем содержимое файла
                lines = f.readlines()
                for line in lines:
                    try:    
                        if line != '':
                            bot.send_message(line, f"Внимание, {deadline} сгорит заявка {req_num} !")                  # Отправка сообщения о просроке всем
                    except:
                        logging.error(f"Ошибка отправки сообщения в чат - {line.strip()}, удаляем пользовтеля.")
                        rm_id(line.strip())


def new_req(msg, req_ID):    #отправка сообщения (msg), прикрипление ссылки с (req_ID) и документа по ссылке (attachment)
    try:       
        keyboard = types.InlineKeyboardMarkup()
        url_button = types.InlineKeyboardButton(text='открыть', url='https://sd.servionica.ru/record/itsm_request/' + req_ID)
        keyboard.add(url_button)
        with open(ids_file, 'r') as f:    # Читаем содержимое файла
            lines = f.readlines()
            for line in lines:
                try:    
                    if line != '':
                        bot.send_message(line, msg, reply_markup=keyboard)                  # Отправка сообщение с ссылкой
                except:
                    logging.error(f"Ошибка отправки сообщения в чат - {line.strip()}, удаляем пользовтеля.")
                    rm_id(line.strip())
    except Exception as e:
        logging.error(f"функция отправки сообщения выдала ошибку: {e}")


def plus_three_hour(in_datetime_str):    # получает дату и время в строке  , прибавляя три часа - возвращает дату и время в строке
    try:       
        time_obj = datetime.strptime(in_datetime_str, "%Y-%m-%d %H:%M:%S") # Преобразуем строку в объект datetime
    except:
        return "хз"
    new_time_obj = time_obj + timedelta(hours=3)    # Прибавляем 3 часа
    new_datetime_str = new_time_obj.strftime("%Y-%m-%d %H:%M:%S")    # Преобразуем обратно в строку
    return new_datetime_str


def dw_actual_table():   #функция скачивания актуальной таблички
    requests.post(url_export_excel, headers=headers, json=payload_export_excel)   #заказываем excel 
    time.sleep(2) 
    response_list = requests.get(url_export_excel, headers=headers)   #получаем список загрузок 
    data = response_list.content.decode('utf-8') # Декодируем данные
    json_data = json.loads(data) 
    last_sys_id = json_data['data']['exports'][0]['sysId'] #парсим id последнего файла
    
    payload_dw_del = { 						#составляем пайлоад с этим последним сис-ид
        "sysIds":[f"{last_sys_id}"],
        "userId":"170800459101114407"
        }

    start_time = time.time()		                       	# скачивание по готовности данных
    while True:
        time.sleep(3)     
        try:
            response_list = requests.get(url_export_excel, headers=headers) 	#запрос списка загрузок  
              
            if response_list.status_code == 200:
                data = response_list.content.decode('utf-8') # Декодируем данные
                json_data = json.loads(data) 
                status = json_data['data']['exports'][0]['state']  #парсим его статус
    
                if status == "completed":				#если данные готовы
                    response_dw_url = requests.post(url_download_excel, headers=headers, json=payload_dw_del)   #получаем ссылку на скачивание
                    data = response_dw_url.content.decode('utf-8') # Декодируем данные
                    json_data = json.loads(data) 
                    parse_dw_url = json_data['data']['downloadUrls'][0] #парсим ссылку
        
                    response_excel = requests.get(parse_dw_url)   # скачивание актуальной таблички 
                    if response_excel.status_code == 200:    		# Проверяем статус ответа
                        with open(actual_table, 'wb') as f:    # Открываем файл для записи в бинарном режиме
                            f.write(response_excel.content)           # перезаписываем 
                    else:
                        logging.error(f"Ошибка скачивания excel таблички: {response_excel.status_code}")
                    break
            else:
                logging.error(f"Ошибка сервера: {response_list.status_code}")

        except requests.RequestException as e:
            logging.error(f"Ошибка запроса: {e}")
            break

        # Проверяем, не истекло ли время ожидания
        if time.time() - start_time > 15:
            logging.error("Данные были не готовы > 15 секунд.")
            break

    response = requests.post(url_delete_excel, headers=headers, json=payload_dw_del)  #удаляем табличку с сервера


def search_new_req():   #функция поиска новых заявок
    try:
        actual_table_df = pd.DataFrame(pd.read_excel(actual_table).iloc[0:, 0])           #выкачиваем датафрейм из файлов (первый столбец весь)
        arch_xl_table_df = pd.DataFrame(pd.read_excel(arch_xl_table).iloc[0:, 0]) 
        new_reqs_df = actual_table_df[~actual_table_df['Номер'].isin(arch_xl_table_df['Номер'])]   # Сравнение по первому столбцу и удаление строк из df2, которые есть в df1  (врозвращает новые заявки !!!)
        return new_reqs_df
    except Exception as e:
        logging.error(f"функция поиска новых заявок выдала ошибку: {e}")

def gat_req_data(req):   #функция вытаскивания данных по номеру заявки (отдаёт json со всеми нужными данными и req_ID)
    try:
        response = requests.get('https://sd.servionica.ru/v1/search?query=' + req, headers=headers)    # Делаем запрос на поисковую страничку (узнать ссылку на заявку (её ИД в системе))
        if response.status_code == 200:    # Проверяем статус ответа
            data = response.content.decode('utf-8') # Декодируем данные
            json_data = json.loads(data) # И вуаля! У нас есть JSON.
            req_ID = json_data['data']['records'][0]['sys_id']   # парсим ID для ссылки - первый результат поиска
            response = requests.get('https://sd.servionica.ru/v1/record/itsm_request/' + req_ID, headers=headers)   # Делаем запрос на страничку заявки
            if response.status_code == 200:    # Проверяем статус ответа
                data = response.content.decode('utf-8') # Декодируем данные
                json_data = json.loads(data) # И вуаля! У нас есть JSON ещё.
                return (json_data, req_ID)
            else:
                logging.error(f"Ошибка сервера: {response.status_code} - {response.text}")
        else:
            logging.error(f"Ошибка сервера: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"функция вытаскивания данных по номеру заявки выдала ошибку: {e}")

def parse(json_data):   #функция парсинга и составления сообщения
    try:
        proj = json_data['data']['sections'][1]['elements'][34]['value']['display_value'] # парсим проект 
        req = json_data['data']['sections'][1]['elements'][1]['value'] # и номер заявки
        if proj == 'АО \"АЛЬФА-БАНК\"':                  # ++++++++++-----АБ-------++++++++++++++
            info = json_data['data']['sections'][1]['elements'][41]['value']   
            adress = json_data['data']['sections'][6]['elements'][4]['value']
            deadline = json_data['data']['sections'][1]['elements'][37]['value']
            deadline = plus_three_hour(deadline)
            info = 'нет информации' if info == None else info                   # проверки на ноль
            adress = 'нет информации' if adress == None else adress
            new_req_message = ('Новая заявка: ' + req +  ' по ' + proj + '\n'
                    + adress + '\n'
                    + 'До: ' + deadline + '\n'
                    + info)
            return new_req_message
        elif proj == 'Банк ВТБ': 
            servis_type = json_data['data']['sections'][1]['elements'][22]['value']['display_value']   #  склад или сервисная
            if servis_type == 'Сервисные заявки':         # ++++++++++-----ВТБ СЕРВИС-------++++++++++++++
                req_type = json_data['data']['sections'][5]['elements'][9]['value']  
                adress = json_data['data']['sections'][5]['elements'][35]['value']
                deadline = json_data['data']['sections'][1]['elements'][37]['value']
                deadline = plus_three_hour(deadline)
                req_suts = json_data['data']['sections'][1]['elements'][2]['value']
                req_type = 'нет информации' if req_type == None else req_type               # проверки на ноль
                adress = 'нет информации' if adress == None else adress
                req_suts = 'нет информации' if req_suts == None else req_suts
                if req_type != 'expertise':                                      # кроме экспертиз
                    new_req_message = ('Новая заявка: ' + req + ' (' + req_suts + ') по ' + proj + '\n'
                            + adress + '\n'
                            + 'До: ' + deadline + '\n'
                            + 'Тип: ' + req_type)
                    return new_req_message
            elif servis_type == 'Складские заявки':         # ++++++++++-----ВТБ СКЛАД-------++++++++++++++
                deadline = json_data['data']['sections'][1]['elements'][37]['value']
                deadline = plus_three_hour(deadline)
                req_suts = json_data['data']['sections'][1]['elements'][2]['value']
                req_suts = 'нет информации' if req_suts == None else req_suts
                new_req_message = ('Новая складская заявка: ' + req + ' по ' + proj + '\n'
                        'Предельный срок: ' + deadline + '\n')
                return new_req_message
            else:                                           # ++++++++++-----ВТБ ХЗ-------++++++++++++++
                info = json_data['data']['sections'][1]['elements'][41]['value']   
                info = 'нет информации' if info == None else info                   # проверки на ноль
                new_req_message = ('Новая заявка: ' + req + '\n'
                        'по ' + proj + '\n'
                        'Информация: ' + info)
                return new_req_message
        else:                                                # ++++++++++-----ВООБЩЕ ХЗ-------++++++++++++++
            info = json_data['data']['sections'][1]['elements'][41]['value']   
            info = 'нет информации' if info == None else info                   # проверки на ноль
            new_req_message = ('Новая заявка: ' + req + '\n'
                    'по проекту ' + proj + '\n'
                    'Информация: ' + info)
            return new_req_message
    except Exception as e:
        logging.error(f"функция парсинга и составления сообщения выдала ошибку: {e}")
    
def get_AVR(req, chat_id):         # заполнение шаблона (принимает json данные - отдаёт ссылку на созданый заполненый .docx)
    try:
        logging.info('запрос АВР для ' + req)
        waiting_msg = bot.send_message(chat_id, 'Готовлю АВР...')
        try:
            json_data, req_ID = gat_req_data(req)   #пытаемся получить json данные по заявке
        except:
            bot.delete_message(chat_id, waiting_msg.message_id)
            bot.send_message(chat_id, "Не удалось, что то не так, может лишний символ?")
            logging.error('запрос АВР для "' + req + '" не удался')
            return
        proj = json_data['data']['sections'][1]['elements'][34]['value']['display_value'] # парсим проект 
        if proj == 'АО \"АЛЬФА-БАНК\"':                  # поверка на АБ
            adress = json_data['data']['sections'][6]['elements'][4]['value']
            name = json_data['data']['sections'][6]['elements'][18]['value']
            full_name = json_data['data']['sections'][6]['elements'][32]['value']
            tid = json_data['data']['sections'][6]['elements'][2]['value']
            template_doc = DocxTemplate(template)    # Загружаем шаблон документа
            context = {    # Данные для замены в шаблоне
                'req': req,
                'name': name,
                'full_name': full_name,
                'adress': adress,
                'tid': tid,
            }
            template_doc.render(context)    # Заполняем шаблон данными 
            output_filename = script_dir / f'data/{req}.docx'   # Сохраняем новый документ
            template_doc.save(output_filename)    # сохранение документа
            with open(output_filename, 'rb') as doc:
                name_fmd2 = escape_markdown_v2(name)
                bot.send_document(chat_id, doc, caption=f'АВР для {name_fmd2}\nСсылка для инженера \(копируется нажатием\):\n`{req}, {name_fmd2}, https://sd\.servionica\.ru/record/itsm_request/{req_ID}`', parse_mode='MarkdownV2')   #грузим1
            bot.delete_message(chat_id, waiting_msg.message_id)
            os.remove(output_filename)
        else:
            bot.delete_message(chat_id, waiting_msg.message_id)
            bot.send_message(chat_id, "Ошибка: проект заявки не АБ")
    except Exception as e:
        logging.error(f"функция парсинга и составления сообщения выдала ошибку: {e}")

def escape_markdown_v2(text):   #подготовка текста для защиты от испорченного Markdown (добавляем \)
    special_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(r"([{}])".format(re.escape(special_chars)), r"\\\1", text)

def update_archive(): #функция обновления архива заявок
    actual_table_df = pd.DataFrame(pd.read_excel(actual_table).iloc[0:, 0])  # дастаём DF актуальной табличики
    actual_table_df.to_excel(arch_xl_table, index=False)  # пересохраняем архив заявок 

#--------------------добавление и удаление подписки на рассылку--------------
def add_id(id):
    id = str(id)
    with open(ids_file, 'r+') as file:    # Открываем файл для чтения и записи
        lines = file.readlines()
        if id + '\n' not in lines:       # Проверяем, есть ли уже такая строка в файле
            file.write(id + '\n')          # Если строки нет, добавляем её в конец
            bot.send_message(id, "Ты подписался на новые заявки по Саранску")
            logging.info(id + ' подписался')
        else:
            bot.send_message(id, "Ты уже подписан")

def rm_id(id):
    id = str(id)
    with open(ids_file, 'r') as file:    # Читаем содержимое файла
        lines = file.readlines()
    with open(ids_file, 'w') as file:    # Отфильтровываем строки, которые не совпадают с ids
        for line in lines:
            if line.strip() != id:
                file.write(line)
#------------------------------------------------------------------------------

# Функция для чтения последнего update_id из файла
def load_last_update_id():
    global last_update_id
    last_update_id = os.getenv('LAST_UPDATE_ID')

# Функция для сохранения последнего update_id в файл
def save_last_update_id(update_id):
    update_env_variable('LAST_UPDATE_ID', update_id)


#-----------------\/-сервисные команды обновления сервисных файлов и клава-\/----------------------------

def handle_new_mk_bearer(message, chat_id, msg_id): #---обновление токена мультикарты---
    try:
        old_bearer = os.getenv('MK_BEARER')       # пишем в лог старый файл на всякий
        logging.info('попытка смены bearer: "' + old_bearer + '" на новый...')

        command_parts = message.split(maxsplit=2)         # Разделяем текст команды на части

        if len(command_parts) < 3:         # Проверяем, что есть и пароль, и новый токен
            bot.send_message(chat_id, "Ошибка: формат команды /new_bearer <pass> <new_bearer>")
            return
        
        input_password = command_parts[1]
        new_token = command_parts[2]

        if input_password == os.getenv('SERVICE_PASS'):        # Проверяем правильность сервисного пароля
            bot.delete_message(chat_id, msg_id)
            update_env_variable('MK_BEARER', new_token)
            global headers
            headers = {                      #обновляем Bearer токен в headers для запросов
              'Authorization': f'Bearer {new_token}'  
            }
            bot.send_message(chat_id, "Токен успешно обновлён!")
            logging.info('новый bearer установлен: ' + new_token)
        elif input_password == os.getenv('FOLLOW_PASS'):  #если это пароль на подписку
            bot.send_message(chat_id, "Это пароль на подписку. Так не прокатит.")
            logging.info('Токен не обновлён пользователем ' + str(chat_id) + '(ввёл пароль на подписку)')
        else:
            bot.send_message(chat_id, "Неверный пароль.")

    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")


def handle_new_service_pass(message, chat_id, msg_id): #---обновление сервисного пароля---
    try:
        old_service_pass = os.getenv('SERVICE_PASS')       # пишем в лог старый файл на всякий
        logging.info('попытка смены сервисного пароля: "' + old_service_pass + '" на новый...')

        command_parts = message.split(maxsplit=2)         # Разделяем текст команды на части

        if len(command_parts) < 3:         # Проверяем, что есть и пароль, и новый токен
            bot.send_message(chat_id, "Ошибка: формат команды /new_service_pass <service_pass> <new_service_pass>")
            return
        
        input_password = command_parts[1]
        new_service_pass = command_parts[2]

        if input_password == os.getenv('SERVICE_PASS'):        # Проверяем правильность старого сервисного пароля
            bot.delete_message(chat_id, msg_id)
            update_env_variable('SERVICE_PASS', new_service_pass)
            bot.send_message(chat_id, "Сервисный пароль успешно обновлён!")
            logging.info('новый сервсиный пароль установлен: ' + new_service_pass)
        elif input_password == os.getenv('FOLLOW_PASS'):  #если это пароль на подписку
            bot.send_message(chat_id, "Это пароль на подписку. Так не прокатит.")
            logging.info('Сервисный пароль не обновлён пользователем ' + str(chat_id) + '(ввёл пароль на подписку)')
        else:
            bot.send_message(chat_id, "Неверный пароль.")

    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")


def handle_new_follow_pass(message, chat_id, msg_id): #---обновление пароля на подписку-------------+
    try:
        old_follow_pass = os.getenv('FOLLOW_PASS')       # пишем в лог старый файл на всякий
        logging.info('попытка смены пароля на подписку: "' + old_follow_pass + '" на новый...')

        command_parts = message.split(maxsplit=2)         # Разделяем текст команды на части

        if len(command_parts) < 3:         # Проверяем, что есть и пароль, и новый токен
            bot.send_message(chat_id, "Ошибка: формат команды /new_follow_pass <service_pass> <new_follow_pass>")
            return
        
        input_password = command_parts[1]
        new_follow_pass = command_parts[2]

        if input_password == os.getenv('SERVICE_PASS'):        # Проверяем правильность сервисного пароля
            bot.delete_message(chat_id, msg_id)
            update_env_variable('FOLLOW_PASS', new_follow_pass)
            bot.send_message(chat_id, "Пароль на подписку успешно обновлён!")
            logging.info('новый пароль на подписку установлен: ' + new_follow_pass)
        elif input_password == os.getenv('FOLLOW_PASS'):  #если это пароль на подписку
            bot.send_message(chat_id, "Это пароль на подписку. Так не прокатит.")
            logging.info('Пароль на подписку не обновлён пользователем ' + str(chat_id) + '(ввёл пароль на подписку)')
        else:
            bot.send_message(chat_id, "Неверный сервисный пароль.")

    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")


def handle_dw_logs(message, chat_id, msg_id): #---скачивание логов-----------------------------------+
    try:
        command_parts = message.split(maxsplit=2)         # Разделяем текст команды на части

        if len(command_parts) < 2:         # Проверяем, что есть и пароль
            bot.send_message(chat_id, "Ошибка: формат команды /log <pass>")
            return
        
        input_password = command_parts[1]

        if input_password == os.getenv('SERVICE_PASS'):        # Проверяем правильность пароля
            bot.delete_message(chat_id, msg_id) #удаляем пароль из чата
            with open(log_file, 'rb') as file:
                bot.send_document(chat_id, file)
            logging.info('log скачен пользователем ' + str(chat_id))
        elif input_password == os.getenv('FOLLOW_PASS'):  #если это пароль на подписку
            bot.send_message(chat_id, "Это пароль на подписку. Так не прокатит.")
            logging.info('log не скачен пользователем ' + str(chat_id) + ' (ввёл пароль на подписку)')
        else:
            bot.send_message(chat_id, "Неверный пароль.")

    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")

def handle_dw_data(message, chat_id, msg_id): #---скачивание данных------------------------------------+
    try:
        command_parts = message.split(maxsplit=2)         # Разделяем текст команды на части

        if len(command_parts) < 2:         # Проверяем, что есть и пароль
            bot.send_message(chat_id, "Ошибка: формат команды /dw_data <pass>")
            return
        
        input_password = command_parts[1]

        if input_password == os.getenv('SERVICE_PASS'):        # Проверяем правильность пароля
            bot.delete_message(chat_id, msg_id) #удаляем пароль из чата
            shutil.make_archive(str(data_zip).replace('.zip', ''), 'zip', data_folder)
            with open(data_zip, 'rb') as file:
                bot.send_document(chat_id, file)
            os.remove(data_zip)
            logging.info('data скачен пользователем ' + str(chat_id))
        elif input_password == os.getenv('FOLLOW_PASS'):  #если это пароль на подписку
            bot.send_message(chat_id, "Это пароль на подписку. Так не прокатит.")
            logging.info('data не скачен пользователем ' + str(chat_id) + '(ввёл пароль на подписку)')
        else:
            bot.send_message(chat_id, "Неверный пароль.")

    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")


def handle_new_url(message, chat_id, msg_id): #---обновление ЮРЛ--------------------------------------+
    global url_condition
    try:
        logging.info('попытка смены url condition: "' + url_condition + '" на новый...')

        command_parts = message.split(maxsplit=2)         # Разделяем текст команды на части

        if len(command_parts) < 3:         # Проверяем, что есть и пароль, и новый url
            bot.send_message(chat_id, "Ошибка: формат команды /new_url <pass> <url_condition>")
            return
        
        input_password = command_parts[1]
        new_url_condition = command_parts[2]

        if input_password == os.getenv('SERVICE_PASS'):        # Проверяем правильность пароля
            bot.delete_message(chat_id, msg_id) #удаляем пароль из чата
            update_env_variable('DW_URL_CONDITION', new_url_condition)
            url_condition = new_url_condition
            bot.send_message(chat_id, "URL успешно обновлён!")
            logging.info('новый URL установлен: ' + url_condition)
        elif input_password == os.getenv('FOLLOW_PASS'):  #если это пароль на подписку
            bot.send_message(chat_id, "Это пароль на подписку. Так не прокатит.")
            logging.info('URL не обновлён пользователем ' + str(chat_id) + '(ввёл пароль на подписку)')
        else:
            bot.send_message(chat_id, "Неверный пароль.")

    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")


def update_env_variable(key, value): #---функция обновления параметра в файле secrets.env------------+

    if os.path.exists(env_file):    # Считаем текущие данные из .env файла
        with open(env_file, 'r') as file:
            lines = file.readlines()
    else:
        lines = []

    key_found = False    # Флаг, чтобы понять, был ли ключ найден
    new_lines = []

    for line in lines:    # Проходим по каждой строке и ищем ключ
        if line.startswith(f'{key}='):        # Если строка начинается с нужного ключа, заменяем его
            new_lines.append(f'{key}={value}\n')
            key_found = True
        else:
            new_lines.append(line)

    if not key_found:    # Если ключ не найден, добавляем его в конец
        new_lines.append(f'{key}={value}\n')

    with open(env_file, 'w') as file:    # Записываем обновленные данные обратно в .env файл
        file.writelines(new_lines)
    
    load_dotenv(env_file, override=True)    # повторно загружаем значения из env с перезаписью


def send_keyboard(usr_id, send_text):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)    # Создаем объект клавиатуры
        button_1 = types.KeyboardButton("Подписаться")     # Добавляем кнопки
        button_2 = types.KeyboardButton("Отписаться")
        button_3 = types.KeyboardButton("Обновить принудительно")
        keyboard.row(button_1, button_2)
        keyboard.row(button_3)
        bot.send_message(usr_id, send_text, reply_markup=keyboard)       # Отправляем сообщение с клавиатурой

#-----------------/\-сервисные команды обновления сервисных файлов и клава-/\---------------------------



def check_new_messages():
    global last_update_id
    try:
        updates = bot.get_updates(offset=last_update_id, timeout=4)
        for update in updates:
            last_update_id = update.update_id + 1  # Обновляем id последнего обработанного сообщения
            save_last_update_id(last_update_id)  # Сохраняем id в файл
            if update.message:  # Проверяем, есть ли сообщение в обновлении
                usr_id = update.message.from_user.id
                message_text = update.message.text  # Получаем текст сообщения
                message_id = update.message.message_id   

                if update.message.document:                             # обновление  шаблона
                    message_file_id = update.message.document.file_id
                    message_file_name = update.message.document.file_name
                    if os.path.exists(service_pass):       # Получаем сохраненный пароль из файла
                        with open(service_pass, 'r') as f:
                            s_pass = f.read().strip()
                    if message_file_name == 'template.docx' and update.message.caption == s_pass: # если прикреплен новый шаблон и введён пароль
                        bot.delete_message(usr_id, message_id)   #удаляем сообщение с
                        downloaded_file = bot.download_file(bot.get_file(message_file_id).file_path)
                        with open(template, 'wb') as new_file:            # Сохраняем файл на сервере, заменяя старый
                            new_file.write(downloaded_file)
                        bot.send_message(usr_id, "Шаблон успешно обновлён")
                    else:
                        bot.send_message(usr_id, "Что бы заменить шаблон на сервере нужно прикрепить файл с названием template.docx и в сообщении ввести сервисный пароль")


                else:

                    if message_text == "Привет" or message_text == "привет":
                        bot.send_message(usr_id, 'from oldest SHTEBLETS')

                    elif message_text.startswith('REQ'):        # полуение АВР для заявки
                        get_AVR(message_text, usr_id)

                    elif (message_text == "/start" or message_text == "/help"):
                        send_text = ('Проверяет новые заявки каждые 10 минут.\n\n' +
                                    'Подписаться или отписаться от рассылки - нажать на кнопки ниже:')
                        send_keyboard(usr_id, send_text)

                    elif message_text == "Подписаться":
                        bot.send_message(usr_id, "Введи пароль:")

                    elif message_text == "Отписаться":
                        try:
                            rm_id(usr_id)
                            bot.send_message(id, "Ты отписался от новых заявок по саранску")
                            logging.info(id + ' отписался самостоятельно')
                        except:
                            bot.send_message(id, "Странно, отписаться не получилось, скажи Сане")
                            logging.error(id + ' не смог отписаться. Что то пошло не так.')
                            
                    elif message_text == "Обновить принудительно":
                        scheduled_messages('exc')
                        bot.send_message(usr_id, "Принудительно обновлено...")

                    elif "/log" in message_text:
                        handle_dw_logs(message_text, usr_id, message_id)

                    elif "/dw_data" in message_text:
                        handle_dw_data(message_text, usr_id, message_id)

                    elif message_text == "/service":
                        bot.send_message(usr_id, '/new_bearer - заменить Bearer токен S1\n' +
                                                '/new_url - заменить ссылку скачивания .xlsx новых заявок (но сначала смотри инструкцию: /new_url_instruction)\n'
                                                '/new_service_pass - замена сервисного пароля\n'
                                                '/new_follow_pass - замена пароля на подписку\n'
                                                '/dw_template - скачать текущий шаблон АВР\n'
                                                '/log - скачать логи\n'
                                                '/dw_data - скачать все данные текущего состояния бота\n'
                                                'Для обновления шаблона на сервере - прикрепи к сообщению с сервисным паролем документ "template.docx" (скачай, измени, загрузи)')

                    elif "/new_bearer" in message_text:           # ==сервисная команда: замены Bearer токена
                        handle_new_mk_bearer(message_text, usr_id, message_id)

                    elif message_text ==  "/new_url_instruction":   # ==сервисная команда: показать инструкцию
                        with open(instruction, 'rb') as file:
                            bot.send_document(usr_id, file)
                            
                    elif "/new_url" in message_text:           # ==сервисная команда: замены URL
                        handle_new_url(message_text, usr_id, message_id)

                    elif message_text ==  "/dw_template":           # ==сервисная команда: скачать текущий шаблон
                        with open(template, 'rb') as file:
                            bot.send_document(usr_id, file)

                    elif "/new_service_pass" in message_text:           # ==сервисная команда: замены сервисного пароля
                        handle_new_service_pass(message_text, usr_id, message_id)

                    elif "/new_follow_pass" in message_text:           # ==сервисная команда: замены сервисного пароля
                        handle_new_follow_pass(message_text, usr_id, message_id)
                        
                    elif message_text == os.getenv('FOLLOW_PASS'):       # команда 'подписаться'
                        bot.delete_message(usr_id, message_id) #удаляем пароль из чата
                        bot.delete_message(usr_id, message_id - 1) 
                        add_id(usr_id)
                    else:
                        send_text = ('🤔...')
                        send_keyboard(usr_id, send_text)                    
    except:
        logging.error(f"Ошибка запроса новых сообщений.")


def main_logic():
    schedule.every(15).minutes.do(scheduled_messages) # Планируем задачу на каждые x минут
    logging.info('скрипт запущен')
    load_last_update_id()  # Загружаем последний update_id из файла при запуске
    # scheduled_messages() # выполнение при запуске
    while True:
        schedule.run_pending()
        check_new_messages()  # Проверяем новые сообщения
        time.sleep(5)

if __name__ == '__main__':
    main_logic()