this is debian bookworm for experiments for work tg bot )

#### Как что то исправить или просто переехать?
    1. Скачиваешь репозиторий с гита - https://github.com/Metro3230/mk_req_check.git
    2. Скачиваешь с бота файлы 'data' с актуальными данными (например /dw_data <service pass> прямо из бота)
    3. Суешь сюда в папку
    4. docker build . -t mk_req_check:vXX
    5. После сборки запускать коммандой docker run --name mk_req_check --restart unless-stopped -d mk_req_check:vXX

    Если не нужно останавливаться при тестировании:  ```docker run --name mk_req_check --restart unless-stopped -d mk_req_check:vXX tail -f /dev/null```

     

##### Поясняю:
+ actual_table.xlsx      - просто последняя скуаченная таблица. Она в докеригнор
+ log.log                - лог ошибок и сообщений
+ req_archive.xlsx       - архив заявок по которым уже не надо присылать 
+ template.docx          - шаблон заявки
+ .env                   - сервисные токены, пароли, информация. (основной файл, который требуется перенести на новую мащину со старой)
+ tg_ids.txt             - файл с id чатов к рассылке
 
