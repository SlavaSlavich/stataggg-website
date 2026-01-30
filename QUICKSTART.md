# Быстрый старт для GitHub и VPS

## 📦 Загрузка на GitHub

### 1. Проверьте конфигурацию

Убедитесь, что ваш `config.py` НЕ будет загружен на GitHub:

```bash
# В папке проекта
git status
```

Если видите `config.py` в списке - **СТОП!** Проверьте `.gitignore`.

### 2. Инициализация Git

```bash
cd C:\Users\Slava\Desktop\сайт
git init
git add .
git commit -m "Initial commit: Stataggg website and payment bot"
```

### 3. Создайте репозиторий на GitHub

1. Зайдите на https://github.com
2. Нажмите "New repository"
3. Назовите: `stataggg-website`
4. **НЕ** добавляйте README (он уже есть)
5. Создайте репозиторий

### 4. Загрузите код

```bash
git branch -M main
git remote add origin https://github.com/ВАШ_USERNAME/stataggg-website.git
git push -u origin main
```

---

## 🚀 Развертывание на VPS

### Быстрая установка (Ubuntu/Debian)

```bash
# 1. Подключитесь к VPS
ssh root@ВАШ_IP

# 2. Установите зависимости
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv nginx git

# 3. Клонируйте проект
cd /var/www
git clone https://github.com/ВАШ_USERNAME/stataggg-website.git stataggg
cd stataggg

# 4. Настройте конфигурацию
cp web_v1/config_example.py web_v1/config.py
cp bot_payment/config_example.py bot_payment/config.py

# Отредактируйте config.py (вставьте токены)
nano web_v1/config.py
nano bot_payment/config.py

# 5. Установите зависимости Python
cd web_v1
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

cd ../bot_payment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 6. Установите systemd сервисы
cd /var/www/stataggg
cp deploy/stataggg-web.service /etc/systemd/system/
cp deploy/stataggg-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable stataggg-web stataggg-bot
systemctl start stataggg-web stataggg-bot

# 7. Настройте Nginx
cp deploy/nginx.conf /etc/nginx/sites-available/stataggg
# Отредактируйте домен
nano /etc/nginx/sites-available/stataggg
# Активируйте
ln -s /etc/nginx/sites-available/stataggg /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# 8. Настройте firewall
ufw allow 22
ufw allow 80
ufw allow 443
ufw enable

# 9. Получите SSL (опционально)
apt install -y certbot python3-certbot-nginx
certbot --nginx -d ВАШ_ДОМЕН.ru
```

### Проверка

```bash
# Статус сервисов
systemctl status stataggg-web
systemctl status stataggg-bot

# Логи
journalctl -u stataggg-web -f
journalctl -u stataggg-bot -f
```

---

## 🔧 Обновление кода

После изменений на GitHub:

```bash
cd /var/www/stataggg
git pull origin main
systemctl restart stataggg-web
systemctl restart stataggg-bot
```

---

## ⚠️ Важно перед загрузкой на GitHub

- [ ] Проверьте, что `config.py` в `.gitignore`
- [ ] Убедитесь, что нет токенов в коде
- [ ] Проверьте, что `*.db` и `*.log` исключены
- [ ] Замените токены на плейсхолдеры в `config_example.py`

---

## 📚 Полная документация

Подробные инструкции: [deployment_guide.md](deployment_guide.md)
