# mk_req_check

this is debian bookworm for experiments for work tg bot )
 

 в общем при сборке образа на новую машину озаботься о том, что бы обновить тут файл tg_ids.txt - там содержатся все актуальные id чатов. Если не сохранилось - забей, но все пользователи должны будут снова подписаться на бота. 
 Остальное не так важно, но в идеале обновить тут с рабочего контейнера всю папку data. 

 Поясняю:
 actual_table.xlsx      - просто последняя скуаченная таблица. Она в докеригнор
 log.log                - лог ошибок и сообщений
 req_archive.xlsx       - архив заявок по которым уже не надо присылать 
 template.docx          - шаблон заявки
 .env                   - сервисные токены, пароли, информация. (основной файл, который требуется перенести на новую мащину со старой)
 tg_ids.txt             - файл с id чатов к рассылке
 
Собирирал docker build -t mk_req_check:test .
После сборки Dockerfile'ом, запускал коммандой docker run --name mk_req_check_test --restart unless-stopped -d mk_req_check:test
                                                docker run -d -p 5000:5000 --name mk_req_check_test --restart unless-stopped -d mk_req_check:test