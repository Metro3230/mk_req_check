# Указываем базовый образ
FROM debian:bookworm-20231218

# Устанавливаем часовой пояс через переменную окружения
ENV TZ=Europe/Moscow

# Обновляем систему и устанавливаем зависимости для Python
RUN apt-get update && \
    apt-get install -y tzdata python3.11 python3-pip && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && rm -rf /var/lib/apt/lists/*


# Копируем весь проект в контейнер
COPY . /mk_req_check

# Переходим в рабочую директорию
WORKDIR /mk_req_check

# Устанавливаем зависимости
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Указываем точку входа (entrypoint) для запуска
CMD ["python3", "main_script.py"]

