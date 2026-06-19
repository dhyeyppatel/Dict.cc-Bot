# Unofficial Dict.cc CLI & Telegram Translator Bot

An unofficial command line interface and premium Telegram translation bot for [dict.cc](https://www.dict.cc), written in Python. It supports bidirectional translations between the 12 most common languages available on the website.

---

## Table of Contents
1. [Features](#features)
2. [Supported Languages](#supported-languages)
3. [Local Command Line Interface (CLI)](#local-command-line-interface-cli)
4. [Telegram Translator Bot](#telegram-translator-bot)
5. [Deployment Guides](#deployment-guides)
    - [Option A: Deploying on Vercel (Zero-Config)](#option-a-deploying-on-vercel-zero-config)
    - [Option B: Deploying on Koyeb (Gunicorn Container)](#option-b-deploying-on-koyeb-gunicorn-container)
6. [Code Architecture](#code-architecture)

---

## Features

- **Bidirectional Translation**: Automatically detects input language and displays corresponding translations.
- **Rich Telegram Interface**: Uses HTML styling, interactive inline keyboards, settings panels, and instant translation swap buttons.
- **Telegram Inline Queries**: Translate inline in any chat by typing `@your_bot_name word`.
- **Zero-Config Webhook Registration**: Automatically detects its host URL on Vercel or Koyeb to register its own webhook with Telegram.
- **Extensible Python API**: Clean dictionary parser that can be imported into other Python scripts.

---

## Supported Languages

The following 12 languages are fully supported:

| Code | Language | Flag |
| :--- | :--- | :--- |
| `en` | English | 🇬🇧 |
| `de` | German | 🇩🇪 |
| `fr` | French | 🇫🇷 |
| `sv` | Swedish | 🇸🇪 |
| `no` | Norwegian | 🇳🇴 |
| `es` | Spanish | 🇪🇸 |
| `nl` | Dutch | 🇳🇱 |
| `bg` | Bulgarian | 🇧🇬 |
| `ro` | Romanian | 🇷🇴 |
| `it` | Italian | 🇮🇹 |
| `pt` | Portuguese | 🇵🇹 |
| `ru` | Russian | 🇷🇺 |

---

## Local Command Line Interface (CLI)

### Installation
The library works with Python 2 and Python 3. Install it using pip:
```bash
pip install dict.cc.py
```

### CLI Usage
Translate words or phrases by passing the input language, output language, and the word:
```bash
$ dict.cc.py en sv beer
Showing 2 of 2 result(s)

English                                                     Swedish
========                                                    =======
beer ...................................................... öl
beer glass ................................................ ölglas
```

Search for phrases by wrapping them in quotes:
```bash
$ dict.cc.py en de "free beer"
```

### Importing in Python Code
You can also use the scraper inside your own Python projects:
```python
from dictcc import Dict

translator = Dict()
result = translator.translate("hello", from_language="en", to_language="de")

# Print top 2 translations
print(result.translation_tuples[:2])
# Output: [('Hello !', 'Hallo!'), ('Hello !', 'Servus! [bayer.] [österr.]')]
```

---

## Telegram Translator Bot

A premium, conversational interface for translations. Once deployed, users can interact with the bot using multiple commands and modes.

### Bot Commands
- `/start` or `/help` - Greets users and displays a detailed formatting and usage guide.
- `/settings` or `/langs` - Opens an interactive inline keyboard panel allowing users to set their default Language 1 and Language 2.
- `/tr <from> <to> <word>` - Translates a word directly between two languages (e.g. `/tr en es beer`).
- `/<from><to> <word>` - Shortcut translation command (e.g. `/ensv beer` to translate English ➔ Swedish, `/defr Brot` for German ➔ French).

### Message Modes
1. **Plain Text Messages**: Sending a word directly without commands (e.g. "Bier" or "beer") will translate it using the chat's active settings (defaults to English <-> German).
2. **🔄 Swap Languages Button**: Underneath every translation query result is an inline button: `Swap (DE ➔ EN)`. Clicking it dynamically edits the message, reversing the translation direction for that word.
3. **Inline Query Mode**: In any chat window, type `@your_bot_name en de hello` or `@your_bot_name hello` (uses active settings) to view translation cards instantly and send them inline.

---

## Deployment Guides

### Option A: Deploying on Vercel (Zero-Config)
Vercel is serverless, making it perfect for hosting this bot for free with low latency.

1. **Create a Telegram Bot**: Message [@BotFather](https://t.me/BotFather) on Telegram and run `/newbot` to get your **Bot API Token**.
2. **Push to GitHub**: Fork or push this repository to your GitHub account.
3. **Deploy on Vercel**:
    - Go to Vercel and import your repository.
    - Under **Environment Variables**, add:
      - `TELEGRAM_BOT_TOKEN`: The API Token from BotFather.
    - Click **Deploy**.
4. **Register the Webhook**:
    - After deployment, open your browser and go to your Vercel URL with the `/setup_webhook` path:
      `https://your-project-name.vercel.app/setup_webhook`
    - The page will automatically detect the Vercel URL, register the webhook path on Telegram, and output a confirmation.
5. **Start Chatting**: Open your bot on Telegram and send a message.

### Option B: Deploying on Koyeb (Gunicorn Container)
Koyeb runs persistent web services, which is ideal if you want a standard server environment.

1. Log in to your [Koyeb Console](https://app.koyeb.com/) and create a new **Web Service**.
2. Link your GitHub repository.
3. Add the following **Environment Variables**:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot API token.
   - `WEBHOOK_URL`: Your Koyeb app URL (e.g. `https://your-app-name.koyeb.app`).
4. Set the **Build Command** to:
   ```bash
   pip install -r requirements.txt
   ```
5. Set the **Run Command** to:
   ```bash
   gunicorn wsgi:app --bind 0.0.0.0:${PORT}
   ```
6. Deploy. Once running, visit `https://your-app-name.koyeb.app/setup_webhook` to finalize the webhook configuration.

---

## Code Architecture

- **`api/index.py`**: The core, self-contained Flask entrypoint. It integrates the scraping parser (`DictccScraper`) and all Telegram bot routes and handlers (HTML parse mode). Doing this in a single file ensures no import errors happen in serverless environments.
- **`dictcc/`**: Contains the standalone Python module files (`dictcc.py`) for local CLI installations.
- **`scripts/dict.cc.py`**: The CLI executable script.
- **`requirements.txt`**: Specifies the package dependencies.
- **`vercel.json`**: Rewrite rules to route Vercel request URLs to the API function.
- **`wsgi.py`**: Entry point for standard WSGI servers (like Gunicorn).
