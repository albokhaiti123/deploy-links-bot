# Telegram Promotional Groups Bot

A Telegram bot designed to send a customizable promotional message when new members join groups it has been added to. 
The bot features anti-spam (cooldowns) and an in-Telegram admin panel.

## Features

- **Welcome Promos**: Sends a promotional message when new users join.
- **Admin Dashboard**: Change promo text, URL, button text, and rate limits entirely inside Telegram.
- **Anti-Spam / Rate Limiting**: Cooldown mechanism per group to avoid spamming multiple joining members.
- **SQLite Database**: Simple and robust storage using `aiosqlite`.
- **Bot Promotion**: Built-in deep linking button allowing others to easily add the bot to their own groups.

## Requirements

- Python 3.11+
- Requirements listed in `requirements.txt` (`aiogram 3.x`, `aiosqlite`, `python-dotenv`)

## Setup Instructions

1. **Create the Bot via BotFather**:
   - Go to [@BotFather](https://t.me/BotFather) on Telegram.
   - Send `/newbot` and follow the instructions to create your bot.
   - Copy the HTTP API Token.

2. **Get your Admin ID**:
   - Go to [@userinfobot](https://t.me/userinfobot) or similar to get your Telegram User ID (an integer like `123456789`).

3. **Configure Environment Variables**:
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` and fill in:
     - `BOT_TOKEN`: Your API token.
     - `ADMIN_ID`: Your Telegram User ID.
     - `BOT_USERNAME`: The username of your bot (without `@`).

4. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the Bot**:
   ```bash
   python bot.py
   ```

## Deploying on Ubuntu VPS (Systemd)

To run the bot continuously on a Linux server:

1. Create a service file:
   ```bash
   sudo nano /etc/systemd/system/promobot.service
   ```
2. Add the following (adjust paths!):
   ```ini
   [Unit]
   Description=Telegram Promo Bot
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/path/to/telegram_promo_bot
   ExecStart=/path/to/telegram_promo_bot/venv/bin/python bot.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
3. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable promobot.service
   sudo systemctl start promobot.service
   ```

## Usage & Management

- Send `/start` to the bot in a private message to get the "Add to group" button.
- Send `/admin` in a private message to open the Admin Panel (only works if your ID matches `ADMIN_ID`).
- From the panel, you can adjust the cooldown, modify the promo message, view active groups, and more.
