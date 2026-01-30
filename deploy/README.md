# Deployment Files

This directory contains configuration templates for deploying Stataggg to a VPS.

## Files

- **stataggg-web.service** - Systemd service for the web application
- **stataggg-bot.service** - Systemd service for the payment bot
- **nginx.conf** - Nginx reverse proxy configuration

## Usage

1. Copy service files to `/etc/systemd/system/`:
   ```bash
   sudo cp stataggg-web.service /etc/systemd/system/
   sudo cp stataggg-bot.service /etc/systemd/system/
   ```

2. Copy nginx config to `/etc/nginx/sites-available/`:
   ```bash
   sudo cp nginx.conf /etc/nginx/sites-available/stataggg
   sudo ln -s /etc/nginx/sites-available/stataggg /etc/nginx/sites-enabled/
   ```

3. Reload services:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable stataggg-web stataggg-bot
   sudo systemctl start stataggg-web stataggg-bot
   sudo nginx -t && sudo systemctl reload nginx
   ```

For detailed instructions, see [deployment_guide.md](../deployment_guide.md)
