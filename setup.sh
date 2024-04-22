#!/bin/bash

# Установка зависимостей
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv postgresql

# Создание базы данных PostgreSQL
sudo -u postgres psql -c "CREATE DATABASE myapp;"

# Клонирование репозитория с кодом
git clone https://github.com/metnerium/back1.git
cd back1

# Создание виртуального окружения Python
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей Python
pip install -r requirements.txt

# Создание таблиц в базе данных
python create_tables.py

# Запуск бэкенд-сервера
uvicorn main:app --host 0.0.0.0 --port 8000

