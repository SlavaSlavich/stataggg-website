#!/bin/bash

# Configuration
APP_DIR="/home/ubuntu/botberserkcd"
WEB_DIR="$APP_DIR/web_v1"
VENV_DIR="$APP_DIR/venv"
SERVICE_NAME="stataggg"

echo "🚀 Starting Stataggg Web Deployment..."

# 1. Update System & Install Nginx
echo "📦 Installing Nginx..."
sudo apt update
sudo apt install -y nginx

# 2. Install Python Dependencies
echo "🐍 Installing Python libs..."
source "$VENV_DIR/bin/activate"
pip install -r "$WEB_DIR/requirements.txt"

# 3. Setup Systemd Service
echo "⚙️ Configuring Systemd Service..."
# Update paths in service file just in case (dynamic)
sed -i "s|/home/ubuntu/botberserkcd|$APP_DIR|g" "$WEB_DIR/stataggg.service"
sudo cp "$WEB_DIR/stataggg.service" "/etc/systemd/system/$SERVICE_NAME.service"

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

# 4. Setup Nginx
echo "🌐 Configuring Nginx..."
sudo cp "$WEB_DIR/stataggg_nginx.conf" "/etc/nginx/sites-available/$SERVICE_NAME"
sudo ln -sf "/etc/nginx/sites-available/$SERVICE_NAME" "/etc/nginx/sites-enabled/"
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl restart nginx
sudo ufw allow 'Nginx Full'

echo "✅ Deployment Complete!"
echo "🌍 Check your site at: http://stataggg.ru (or server IP)"
