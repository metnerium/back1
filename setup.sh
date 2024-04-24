#!/bin/bash

# Обновление пакетов
sudo apt-get update
sudo apt-get upgrade -y

# Установка зависимостей
sudo apt-get install -y python3-pip python3-venv postgresql nginx

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей Python
pip install -r requirements.txt

# Настройка PostgreSQL
sudo -u postgres psql -c "CREATE USER user WITH PASSWORD 'Fogot173546';"
sudo -u postgres psql -c "CREATE DATABASE online_school;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE online_school TO user;"

# Клонирование репозитория и запуск сервера
git clone https://github.com/your_repo/online_school.git
cd online_school
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &

# Настройка Nginx
sudo tee /etc/nginx/sites-available/online_school >/dev/null <<EOT
server {
    listen 80;
    server_name your_server_ip;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOT

sudo ln -s /etc/nginx/sites-available/online_school /etc/nginx/sites-enabled/
sudo systemctl restart nginx

# Открытие порта в firewall
sudo ufw allow 'Nginx Full'

echo "Сервер развернут и доступен на http://your_server_ip"