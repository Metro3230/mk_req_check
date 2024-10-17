import telebot
from telebot import types
import os
import time
from pathlib import Path
from keyboa import Keyboa

script_dir = Path(__file__).parent  # Определяем путь к текущему скрипту
ids_file = script_dir / 'data/tg_ids.txt'
tg_token_file = script_dir / 'data/Tg_token.txt'
log_file = script_dir / 'data/log.log'
last_update_id = None
last_update_id_file = script_dir / 'data/last_update_id.txt'
data_folder = script_dir / 'data'
tgtoken = open(tg_token_file, 'r').read()    # читаем token tg
bot = telebot.TeleBot(tgtoken)

#--------------------добавление и удаление подписки на рассылку--------------
def add_id(in_file, ids):
    with open(in_file, 'r+') as file:    # Открываем файл для чтения и записи
        lines = file.readlines()
        if ids + '\n' not in lines:       # Проверяем, есть ли уже такая строка в файле
            file.write(ids + '\n')          # Если строки нет, добавляем её в конец

def rm_id(in_file, ids):
    with open(in_file, 'r') as file:    # Читаем содержимое файла
        lines = file.readlines()
    with open(in_file, 'w') as file:    # Отфильтровываем строки, которые не совпадают с ids
        for line in lines:
            if line.strip() != ids:
                file.write(line)
#------------------------------------------------------------------------------

# Функция для чтения последнего update_id из файла
def load_last_update_id():
    global last_update_id
    if os.path.exists(last_update_id_file):
        with open(last_update_id_file, 'r') as f:
            last_update_id = int(f.read().strip())

# Функция для сохранения последнего update_id в файл
def save_last_update_id(update_id):
    with open(last_update_id_file, 'w') as f:
        f.write(str(update_id))


def check_new_messages():
    global last_update_id
    updates = bot.get_updates(offset=last_update_id, timeout=1)
    for update in updates:
        last_update_id = update.update_id + 1  # Обновляем id последнего обработанного сообщения
        save_last_update_id(last_update_id)  # Сохраняем id в файл
        if update.message:  # Проверяем, есть ли сообщение в обновлении
            usr_id = update.message.from_user.id
            message_text = update.message.text  # Получаем текст сообщения

            if message_text == "Привет":
                bot.send_message(usr_id, "Привет, чем я могу тебе помочь?")

            elif (message_text == "/start" or message_text == "/help"):
                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)    # Создаем объект клавиатуры
                button_1 = types.KeyboardButton("Подписаться")     # Добавляем кнопки
                button_2 = types.KeyboardButton("Отписаться")
                keyboard.add(button_1, button_2)
                text = ('Проверяет новые заявки каждые 10 минут.\n\n' +
                        'Подписаться или отписаться от рассылки - нажать на кнопки наже:')
                bot.send_message(usr_id, text, reply_markup=keyboard)       # Отправляем сообщение с клавиатурой

            elif message_text == "Подписаться":
                add_id(ids_file, str(usr_id))
                bot.send_message(usr_id, "Ты подписался на новые заявки по Саранску")

            elif message_text == "Отписаться":
                rm_id(ids_file, str(usr_id))
                bot.send_message(usr_id, "Ты отписался от новых заявок по саранску")

            elif message_text == "/log":
                with open(log_file, 'rb') as file:
                    bot.send_document(usr_id, file)


            else:
                bot.send_message(usr_id, "Я тебя не понимаю. Напиши /help.")


def main_logic():
    load_last_update_id()  # Загружаем последний update_id из файла при запуске
    while True:
        print("Выполняется моя логика...")
        check_new_messages()  # Проверяем новые сообщения
        time.sleep(5)

if __name__ == '__main__':
    main_logic()
