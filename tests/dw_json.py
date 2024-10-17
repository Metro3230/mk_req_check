import pandas as pd
import requests
import json


access_token = open('data/Bearer.txt', 'r').read()    # читаем Bearer токен из файла
headers = {
    'Authorization': f'Bearer {access_token}'  # Используем Bearer-токен в хеадерсе запроса
}




# --------------------------СКАЧАТЬ В JSON ФАЙЛ ПО ССЫВЛКЕ:-----------------------
req = 'REQ0647044'

# Делаем запрос к URL
response = requests.get('https://sd.servionica.ru/v1/search?query=' + req, headers=headers)
data = response.content.decode('utf-8') # Декодируем данные
json_data = json.loads(data) # И вуаля! У нас есть JSON.
req_ID = json_data['data']['records'][0]['sys_id']   # и мы его парсим доставая оттуда ID для ссылки
print(req_ID)
print('-----------------\n')

response = requests.get('https://sd.servionica.ru/v1/record/itsm_request/' + req_ID, headers=headers)
data = response.content.decode('utf-8') # Декодируем данные
json_data = json.loads(data) # И вуаля! У нас есть JSON ещё.
itogo = json_data['data']['sections'][4]['elements'][2]['value']   # и мы его парсим доставая оттуда ID для ссылки

with open('data_sklad.json', 'w', encoding='utf-8') as f:
    json.dump(json_data, f, ensure_ascii=False, indent=4)
#---------------------------------------------------------------------------------